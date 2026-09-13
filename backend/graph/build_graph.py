"""
build_graph.py
--------------
Wires the Tarang LangGraph StateGraph.

Graph topology:
  detect_and_parse
    → supervisor  (conditional fan-out)
      → weather_agent   (if needs_weather)
      → pfz_agent       (if needs_pfz)
      → hazard_agent    (if needs_hazard)
      → geofence_agent  (if needs_geofence)
    → risk_agent        (if needs_risk AND at least one specialist ran)
    → explain_risk      (if query_type == "risk_explanation"; skips data fetch)
    → synthesis         (always)
    → END

The supervisor is a deterministic conditional edge function — it reads
the needs_* booleans from parsed_intent and routes accordingly.
No LLM hop in the supervisor — this is more demo-reliable and transparent.

Milestone 5: Selective agent re-invocation.
  Each specialist wrapper checks config.AGENT_DEPENDS_ON against changed_fields
  from detect_and_parse. If none of the agent's dependent fields changed AND
  a valid cached result from the previous turn is available within
  FOLLOWUP_CACHE_TTL_SECONDS, the cached result is reused instead of
  calling the live API again.

  Risk agent always recomputes deterministically regardless of cache.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from langgraph.graph import END, StateGraph

import config
from graph.nodes.detect_and_parse import detect_and_parse
from graph.nodes.explain_risk import explain_risk
from graph.nodes.geofence_agent import geofence_agent
from graph.nodes.hazard_agent import hazard_agent
from graph.nodes.ocean_agent import ocean_agent
from graph.nodes.pfz_agent import pfz_agent
from graph.nodes.risk_agent import risk_agent
from graph.nodes.synthesis import synthesis
from graph.nodes.weather_agent import weather_agent
from graph.state import AgentResult, ORCAState, ExecutionStatus, DataStatus


logger = logging.getLogger("tarang.graph")


# ---------------------------------------------------------------------------
# Skip helper — injects a "skipped" AgentResult so the trace is complete
# ---------------------------------------------------------------------------

def _skip(agent_name: str, state: ORCAState) -> dict:
    result: AgentResult = {
        "agent_name": agent_name,
        "status": "skipped",
        "data": {},
        "source": "not invoked for this query",
        "summary": f"{agent_name} was not needed for this query type.",
        "used_fallback": False,
        "data_quality": "live",   # skipped nodes don't affect data quality
        "timestamp": "",
        "error": None,
        "evidence": [],
    }
    state_key = f"{agent_name.replace('_agent', '')}_result"
    current_trace = state.get("trace") or []
    return {
        state_key: result,
        "trace": current_trace + [result],
    }


# ---------------------------------------------------------------------------
# Cache-reuse helper (Milestone 5)
# ---------------------------------------------------------------------------

def _can_reuse_cached(agent_name: str, state: ORCAState) -> bool:
    """
    Return True if we can safely reuse the previous turn's result for this agent.

    Conditions for reuse:
      1. Agent has dependent fields listed in config.AGENT_DEPENDS_ON
      2. None of those fields appear in changed_fields
      3. A cached result exists in last_results
      4. The cached result was fetched within FOLLOWUP_CACHE_TTL_SECONDS
      5. The cached result has data_quality != "fallback" (don't lock in bad data)
    """
    depends_on = config.AGENT_DEPENDS_ON.get(agent_name, [])
    # risk_agent always recomputes — empty depends_on means always re-run
    if not depends_on:
        return False

    changed_fields = state.get("changed_fields") or []
    last_results = state.get("last_results") or {}
    cached = last_results.get(agent_name)

    if not cached or cached.get("status") != "success":
        return False

    # Check TTL
    cached_ts = cached.get("timestamp", "")
    if cached_ts:
        try:
            cached_dt = datetime.fromisoformat(cached_ts.replace("Z", "+00:00"))
            age_s = (datetime.now(timezone.utc) - cached_dt).total_seconds()
            if age_s > config.FOLLOWUP_CACHE_TTL_SECONDS:
                logger.debug("[Cache] %s result expired (age=%.0fs)", agent_name, age_s)
                return False
        except ValueError:
            return False

    # Don't reuse fallback data — force a live fetch attempt
    if cached.get("data_quality") == "fallback":
        return False

    # Check if any of this agent's dependent fields changed
    for field in depends_on:
        if field in changed_fields:
            logger.debug("[Cache] %s: field '%s' changed, must re-fetch", agent_name, field)
            return False

    logger.info("[Cache] Reusing cached %s result (no dependent fields changed)", agent_name)
    return True


def _reuse_cached(agent_name: str, state: ORCAState) -> dict:
    """Inject the cached AgentResult from last_results into state."""
    cached = (state.get("last_results") or {}).get(agent_name)
    state_key = f"{agent_name.replace('_agent', '')}_result"
    current_trace = state.get("trace") or []
    current_evidence = state.get("evidence") or []
    cached_evidence = cached.get("evidence", []) if cached else []
    logger.info("[Cache] Reinjecting cached %s result into state", agent_name)

    current_dq = state.get("data_quality_reports") or []
    cached_dq = []
    if cached and cached.get("data_quality"):
        cached_dq = [{
            "agent_name": agent_name,
            "data_quality": cached.get("data_quality", "live"),
            "used_fallback": cached.get("used_fallback", False),
            "timestamp": cached.get("timestamp", ""),
            "staleness_hours": 0.0,
            "error": cached.get("error"),
        }]

    return {
        state_key: cached,
        "trace": current_trace + [cached],
        "evidence": current_evidence + cached_evidence,
        "data_quality_reports": current_dq + cached_dq,
    }


# ---------------------------------------------------------------------------
# Wrapped node functions that respect needs_* flags + M5 cache reuse
# ---------------------------------------------------------------------------

def _log_agent_trace(agent_name: str, action: str, lat: float | None, lon: float | None, res_dict: dict):
    agent_key = f"{agent_name.replace('_agent', '')}_result"
    ar = res_dict.get(agent_key) or {}
    logger.info(
        f"[TRACE][4/5] Agent '{agent_name}' action={action} lat={lat} lon={lon} "
        f"status={ar.get('status')} used_fallback={ar.get('used_fallback')} data_quality={ar.get('data_quality')}"
    )


def _weather_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    lat, lon = (intent.get("lat"), intent.get("lon")) if intent else (None, None)
    if not intent or not intent.get("needs_weather"):
        res = _skip("weather_agent", state)
        _log_agent_trace("weather_agent", "SKIPPED", lat, lon, res)
        return res
    if _can_reuse_cached("weather_agent", state):
        res = _reuse_cached("weather_agent", state)
        _log_agent_trace("weather_agent", "REUSED_CACHE", lat, lon, res)
        return res
    res = weather_agent(state)
    _log_agent_trace("weather_agent", "RUN_LIVE", lat, lon, res)
    return res


def _pfz_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    lat, lon = (intent.get("lat"), intent.get("lon")) if intent else (None, None)
    if not intent or not intent.get("needs_pfz"):
        res = _skip("pfz_agent", state)
        _log_agent_trace("pfz_agent", "SKIPPED", lat, lon, res)
        return res
    if _can_reuse_cached("pfz_agent", state):
        res = _reuse_cached("pfz_agent", state)
        _log_agent_trace("pfz_agent", "REUSED_CACHE", lat, lon, res)
        return res
    res = pfz_agent(state)
    _log_agent_trace("pfz_agent", "RUN_LIVE", lat, lon, res)
    return res


def _ocean_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    lat, lon = (intent.get("lat"), intent.get("lon")) if intent else (None, None)
    if not intent or (not intent.get("needs_ocean") and intent.get("query_type") not in ("weather_only", "weather", "safety_check", "general", "ocean_tide")):
        res = _skip("ocean_agent", state)
        _log_agent_trace("ocean_agent", "SKIPPED", lat, lon, res)
        return res
    res = ocean_agent(state)
    _log_agent_trace("ocean_agent", "RUN_LIVE", lat, lon, res)
    return res


def _hazard_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    lat, lon = (intent.get("lat"), intent.get("lon")) if intent else (None, None)
    if not intent or not intent.get("needs_hazard"):
        res = _skip("hazard_agent", state)
        _log_agent_trace("hazard_agent", "SKIPPED", lat, lon, res)
        return res
    if _can_reuse_cached("hazard_agent", state):
        res = _reuse_cached("hazard_agent", state)
        _log_agent_trace("hazard_agent", "REUSED_CACHE", lat, lon, res)
        return res
    res = hazard_agent(state)
    _log_agent_trace("hazard_agent", "RUN_LIVE", lat, lon, res)
    return res


def _geofence_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    lat, lon = (intent.get("lat"), intent.get("lon")) if intent else (None, None)
    if not intent or not intent.get("needs_geofence"):
        res = _skip("geofence_agent", state)
        _log_agent_trace("geofence_agent", "SKIPPED", lat, lon, res)
        return res
    if _can_reuse_cached("geofence_agent", state):
        res = _reuse_cached("geofence_agent", state)
        _log_agent_trace("geofence_agent", "REUSED_CACHE", lat, lon, res)
        return res
    res = geofence_agent(state)
    _log_agent_trace("geofence_agent", "RUN_LIVE", lat, lon, res)
    return res


def _risk_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    lat, lon = (intent.get("lat"), intent.get("lon")) if intent else (None, None)
    if intent and intent.get("needs_risk"):
        res = risk_agent(state)
        _log_agent_trace("risk_agent", "RUN_LIVE", lat, lon, res)
        return res
    res = _skip("risk_agent", state)
    _log_agent_trace("risk_agent", "SKIPPED", lat, lon, res)
    return res


def _explain_risk_node(state: ORCAState) -> dict:
    """Only invoked for risk_explanation queries. Uses last turn's risk_result."""
    intent = state.get("parsed_intent")
    if intent and intent.get("query_type") == "risk_explanation":
        # Carry forward risk_result from last_results if not in current state or if skipped
        risk_res = state.get("risk_result")
        if not risk_res or risk_res.get("status") == "skipped":
            last_results = state.get("last_results") or {}
            cached_risk = last_results.get("risk_agent")
            if cached_risk and cached_risk.get("status") == "success":
                logger.info("[ExplainRisk] Loading risk_result from last_results cache")
                # Temporarily inject into a modified-view state (we can't mutate TypedDict)
                state = dict(state)  # type: ignore[assignment]
                state["risk_result"] = cached_risk  # type: ignore[index]
        return explain_risk(state)  # type: ignore[arg-type]
    # Not an explanation query — return a no-op
    return {}


def _status_validator_node(state: ORCAState) -> dict:
    """
    Computes decoupled execution_status and overall_data_status across all specialist agents.
    execution_status: 'success' | 'partial' | 'failed' | 'skipped'
    overall_data_status: 'live' | 'cached' | 'mixed' | 'unavailable'
    """
    resolved = state.get("resolved_location")

    # If location is inland or unresolved, clarification was successfully given
    if not resolved or not resolved.get("coastal"):
        return {
            "execution_status": "skipped" if not resolved else "success",
            "overall_data_status": "unavailable",
        }

    # Inspect all agents that ran
    trace = state.get("trace") or []
    executed = [r for r in trace if r.get("status") != "skipped"]

    if not executed:
        exec_status: ExecutionStatus = "skipped"
        data_status: DataStatus = "unavailable"
    else:
        successes = [r for r in executed if r.get("status") == "success"]
        errors = [r for r in executed if r.get("status") in ("error", "insufficient_data")]

        if len(errors) == 0:
            exec_status = "success"
        elif len(successes) > 0:
            exec_status = "partial"
        else:
            exec_status = "failed"

        # Check data quality among successful agents
        qualities = [r.get("data_quality", "live") for r in successes]
        has_fallback = any(q == "fallback" for q in qualities)
        has_live = any(q == "live" for q in qualities)
        has_proxy = any(q == "historical_proxy" for q in qualities)

        if not successes:
            data_status = "unavailable"
        elif has_fallback and not has_live:
            data_status = "cached"
        elif has_live and not has_fallback and not has_proxy:
            data_status = "live"
        else:
            data_status = "mixed"

    logger.info("[StatusValidator] execution_status=%s overall_data_status=%s", exec_status, data_status)
    return {
        "execution_status": exec_status,
        "overall_data_status": data_status,
    }


# ---------------------------------------------------------------------------
# Build & compile the graph
# ---------------------------------------------------------------------------

def build_graph() -> "CompiledGraph":  # type: ignore[type-arg]
    """
    Build and compile the ORCA LangGraph StateGraph.

    Returns a compiled graph ready for .invoke() or .astream().
    """
    builder = StateGraph(ORCAState)

    # --- Register nodes ---
    builder.add_node("detect_and_parse", detect_and_parse)
    builder.add_node("weather_agent", _weather_node)
    builder.add_node("pfz_agent", _pfz_node)
    builder.add_node("ocean_agent", _ocean_node)
    builder.add_node("hazard_agent", _hazard_node)
    builder.add_node("geofence_agent", _geofence_node)
    builder.add_node("risk_agent", _risk_node)
    builder.add_node("explain_risk", _explain_risk_node)
    builder.add_node("status_validator", _status_validator_node)
    builder.add_node("synthesis", synthesis)

    # --- Entry point ---
    builder.set_entry_point("detect_and_parse")

    # --- Sequential edges (deterministic routing) ---
    # After parsing, always run all specialist wrappers in order.
    builder.add_edge("detect_and_parse", "weather_agent")
    builder.add_edge("weather_agent", "pfz_agent")
    builder.add_edge("pfz_agent", "ocean_agent")
    builder.add_edge("ocean_agent", "hazard_agent")
    builder.add_edge("hazard_agent", "geofence_agent")
    builder.add_edge("geofence_agent", "risk_agent")
    builder.add_edge("risk_agent", "explain_risk")
    builder.add_edge("explain_risk", "status_validator")
    builder.add_edge("status_validator", "synthesis")
    builder.add_edge("synthesis", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Module-level singleton (imported by main.py)
# ---------------------------------------------------------------------------

graph = build_graph()

