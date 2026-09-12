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
    → synthesis         (always)
    → END

The supervisor is a deterministic conditional edge function — it reads
the needs_* booleans from parsed_intent and routes accordingly.
No LLM hop in the supervisor — this is more demo-reliable and transparent.

LangGraph note on parallel fan-out:
  LangGraph executes conditional edges sequentially in a single graph pass.
  For a true parallel fan-out you would use Send() / map-reduce.  For
  Milestone 1 we keep it simple and sequential; the ordering is:
    weather → pfz → hazard → geofence → risk → synthesis
  Each agent is only called if its needs_* flag is True.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from graph.nodes.detect_and_parse import detect_and_parse
from graph.nodes.geofence_agent import geofence_agent
from graph.nodes.hazard_agent import hazard_agent
from graph.nodes.pfz_agent import pfz_agent
from graph.nodes.risk_agent import risk_agent
from graph.nodes.synthesis import synthesis
from graph.nodes.weather_agent import weather_agent
from graph.state import AgentResult, ORCAState


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
# Wrapped node functions that respect needs_* flags
# ---------------------------------------------------------------------------

def _weather_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    if intent and intent.get("needs_weather"):
        return weather_agent(state)
    return _skip("weather_agent", state)


def _pfz_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    if intent and intent.get("needs_pfz"):
        return pfz_agent(state)
    return _skip("pfz_agent", state)


def _hazard_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    if intent and intent.get("needs_hazard"):
        return hazard_agent(state)
    return _skip("hazard_agent", state)


def _geofence_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    if intent and intent.get("needs_geofence"):
        return geofence_agent(state)
    return _skip("geofence_agent", state)


def _risk_node(state: ORCAState) -> dict:
    intent = state.get("parsed_intent")
    if intent and intent.get("needs_risk"):
        return risk_agent(state)
    return _skip("risk_agent", state)


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
    builder.add_node("synthesis", synthesis)

    # --- Entry point ---
    builder.set_entry_point("detect_and_parse")

    # --- Sequential edges (deterministic routing) ---
    # After parsing, always run all specialist wrappers in order.
    # The wrappers check needs_* internally and short-circuit to "skipped".
    # This keeps the graph topology static (easier to visualise) while
    # still achieving conditional execution.
    builder.add_edge("detect_and_parse", "weather_agent")
    builder.add_edge("weather_agent", "pfz_agent")
    builder.add_edge("pfz_agent", "hazard_agent")
    builder.add_edge("hazard_agent", "geofence_agent")
    builder.add_edge("geofence_agent", "risk_agent")
    builder.add_edge("risk_agent", "synthesis")
    builder.add_edge("synthesis", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Module-level singleton (imported by main.py)
# ---------------------------------------------------------------------------

graph = build_graph()
