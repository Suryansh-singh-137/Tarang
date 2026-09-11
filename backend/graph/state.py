"""
ORCA Graph State Schema
-----------------------
Defines all TypedDicts that flow through the LangGraph pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from typing_extensions import TypedDict


class AgentResult(TypedDict):
    """Structured output from every specialist agent."""

    agent_name: str
    status: Literal["success", "skipped", "error"]
    data: Dict[str, Any]  # structured, agent-specific payload
    source: str           # human-readable citation string
    summary: str          # one-line plain-language summary
    used_fallback: bool   # True when live data was unavailable


class ParsedIntent(TypedDict):
    """Structured representation of what the user is asking."""

    location_name: str
    lat: Optional[float]
    lon: Optional[float]
    time_window: str       # e.g. "tomorrow_morning", "now", "next_24h"
    query_type: Literal["safety_check", "pfz_lookup", "general"]
    needs_weather: bool
    needs_pfz: bool
    needs_hazard: bool
    needs_geofence: bool
    needs_risk: bool


class ORCAState(TypedDict):
    """Full mutable state shared across all nodes in the graph."""

    raw_query: str
    detected_language: str          # BCP-47 tag: "hi", "ta", "en"
    parsed_intent: Optional[ParsedIntent]
    weather_result: Optional[AgentResult]
    pfz_result: Optional[AgentResult]
    hazard_result: Optional[AgentResult]
    geofence_result: Optional[AgentResult]
    risk_result: Optional[AgentResult]
    final_answer_text: str
    map_geojson: Dict[str, Any]
    trace: List[AgentResult]        # ordered list of every agent that ran
