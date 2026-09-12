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
from graph.nodes.pfz_agent import pfz_agent
from graph.nodes.risk_agent import risk_agent
from graph.nodes.synthesis import synthesis
from graph.nodes.weather_agent import weather_agent
from graph.state import AgentResult, ORCAState

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
    return {
        state_key: cached,
        "trace": current_trace + [cached],
        "evidence": current_evidence + cached_evidence,
    }


# ---------------------------------------------------------------------------
# Wrapped node functions that respect needs_* flags + M5 cache reuse
# ---------------------------------------------------------------------------

def _weather_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    if not intent or not intent.get("needs_weather"):
        return _skip("weather_agent", state)
    if _can_reuse_cached("weather_agent", state):
        return _reuse_cached("weather_agent", state)
    return weather_agent(state)


def _pfz_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    if not intent or not intent.get("needs_pfz"):
        return _skip("pfz_agent", state)
    if _can_reuse_cached("pfz_agent", state):
        return _reuse_cached("pfz_agent", state)
    return pfz_agent(state)


def _hazard_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    if not intent or not intent.get("needs_hazard"):
        return _skip("hazard_agent", state)
    if _can_reuse_cached("hazard_agent", state):
        return _reuse_cached("hazard_agent", state)
    return hazard_agent(state)


def _geofence_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    if not intent or not intent.get("needs_geofence"):
        return _skip("geofence_agent", state)
    if _can_reuse_cached("geofence_agent", state):
        return _reuse_cached("geofence_agent", state)
    return geofence_agent(state)


def _risk_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    if intent and intent.get("needs_risk"):
        return risk_agent(state)
    return _skip("risk_agent", state)


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
    builder.add_node("hazard_agent", _hazard_node)
    builder.add_node("geofence_agent", _geofence_node)
    builder.add_node("risk_agent", _risk_node)
    builder.add_node("explain_risk", _explain_risk_node)
    builder.add_node("synthesis", synthesis)

    # --- Entry point ---
    builder.set_entry_point("detect_and_parse")

    # --- Sequential edges (deterministic routing) ---
    # After parsing, always run all specialist wrappers in order.
    # The wrappers check needs_* and cache internally.
    builder.add_edge("detect_and_parse", "weather_agent")
    builder.add_edge("weather_agent", "pfz_agent")
    builder.add_edge("pfz_agent", "hazard_agent")
    builder.add_edge("hazard_agent", "geofence_agent")
    builder.add_edge("geofence_agent", "risk_agent")
    builder.add_edge("risk_agent", "explain_risk")
    builder.add_edge("explain_risk", "synthesis")
    builder.add_edge("synthesis", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Module-level singleton (imported by main.py)
# ---------------------------------------------------------------------------

graph = build_graph()
