"""
ORCA Graph State Schema
-----------------------
Defines all TypedDicts that flow through the LangGraph pipeline.

Milestone 2 additions:
  - AgentResult gains: timestamp, error, evidence
  - EvidenceItem: structured factual claim with source + timestamp
  - ParsedIntent gains: time_start_utc, time_end_utc for explicit temporal resolution
  - ORCAState gains: evidence (accumulated list from all agents)

Milestone 3 additions:
  - AgentResult gains: data_quality ("live" | "fallback" | "historical_proxy")
  - RiskComponent: per-factor breakdown struct
  - RiskResult: structured risk result with component-level transparency

Milestone 5 additions:
  - ParsedIntent gains: query_type extended to include "risk_explanation"
  - ORCAState gains: conversation_history, last_parsed_intent, last_results, changed_fields
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from typing_extensions import TypedDict


class EvidenceItem(TypedDict):
    """
    A single structured, source-attributed factual claim produced by an agent.

    Every numerical fact in the synthesis should trace back to an EvidenceItem.
    The synthesis LLM must not invent values not present in evidence[].
    """
    claim: str              # human-readable description: "Wave height is 1.8 m"
    value: Any              # the numerical or categorical value
    unit: str               # unit string, e.g. "m", "km/h", "km", "" for categories
    source: str             # citation: "INCOIS ERDDAP (Oceansat-2)"
    source_time: str        # ISO-8601 UTC: when the data was valid/observed
    retrieved_at: str       # ISO-8601 UTC: when we fetched it
    location: Optional[Dict[str, float]]  # {"lat": ..., "lon": ...} if applicable


class RiskComponent(TypedDict):
    """
    Per-factor contribution to the composite risk score.

    Milestone 4: emitted by risk_agent so synthesis and explain_risk can
    name the top contributors in plain language without re-computing.
    """
    label: str          # "Wave Height", "Wind Speed", "Hazard Level", "Boundary Proximity"
    raw_value: float    # actual measured value (e.g. 1.2 for 1.2 m waves)
    raw_unit: str       # unit of raw_value ("m", "km/h", "category", "km")
    component_score: float  # 0–100 score for this factor
    weight: float       # weight applied (from config.RISK_WEIGHTS)
    contribution: float # component_score * weight  (0–100 scale)
    max_possible: float # weight * 100  (maximum possible contribution of this factor)


class AgentResult(TypedDict):
    """Structured output from every specialist agent.

    Milestone 2 changes (backward-compatible):
      - timestamp:    when the agent completed its data retrieval (ISO-8601 UTC)
      - error:        non-None only when status == "error"
      - evidence:     list of EvidenceItem; empty list when status == "skipped"

    Milestone 3 additions:
      - data_quality: "live"             — freshly fetched from the live API this request
                      "fallback"         — live API unavailable; using cached/static backup data
                      "historical_proxy" — data is real but from historical/satellite dataset;
                                          not a real-time advisory (e.g. INCOIS Oceansat-2 CHL)
    """

    agent_name: str
    status: Literal["success", "skipped", "error"]
    data: Dict[str, Any]    # structured, agent-specific payload
    source: str             # human-readable citation string
    summary: str            # one-line plain-language summary
    used_fallback: bool     # True when live data was unavailable
    data_quality: Literal["live", "fallback", "historical_proxy"]  # M3: data provenance label
    timestamp: str          # ISO-8601 UTC retrieval time (or "" if skipped)
    error: Optional[str]    # error message when status == "error"
    evidence: List[EvidenceItem]  # structured claims for synthesis


class ParsedIntent(TypedDict):
    """Structured representation of what the user is asking.

    Milestone 2 additions:
      - time_start_utc: explicit UTC ISO-8601 start of the requested time window
      - time_end_utc:   explicit UTC ISO-8601 end of the requested time window

    Milestone 5 additions:
      - query_type extended with "risk_explanation"
    """

    location_name: str
    lat: Optional[float]
    lon: Optional[float]
    time_window: str        # e.g. "tomorrow_morning", "now", "next_24h"
    time_start_utc: str     # e.g. "2026-09-13T00:30:00Z"
    time_end_utc: str       # e.g. "2026-09-13T06:30:00Z"
    query_type: Literal["safety_check", "pfz_lookup", "general", "risk_explanation"]
    needs_weather: bool
    needs_pfz: bool
    needs_hazard: bool
    needs_geofence: bool
    needs_risk: bool


class ConversationTurn(TypedDict):
    """A single turn in the conversation history (user or assistant)."""
    role: Literal["user", "assistant"]
    content: str


class ORCAState(TypedDict):
    """Full mutable state shared across all nodes in the graph."""

    raw_query: str
    detected_language: str              # BCP-47 tag: "hi", "ta", "en"
    parsed_intent: Optional[ParsedIntent]
    weather_result: Optional[AgentResult]
    pfz_result: Optional[AgentResult]
    hazard_result: Optional[AgentResult]
    geofence_result: Optional[AgentResult]
    risk_result: Optional[AgentResult]
    final_answer_text: str
    map_geojson: Dict[str, Any]
    evidence: List[EvidenceItem]        # accumulated across all agents
    trace: List[AgentResult]            # ordered list of every agent that ran

    # Milestone 5: Multi-turn conversational memory
    # These are passed in from the client and threaded through state.
    conversation_history: List[ConversationTurn]    # last ≤6 turns of dialogue
    last_parsed_intent: Optional[ParsedIntent]      # intent from the previous turn
    last_results: Dict[str, AgentResult]            # cached agent results from previous turn
    changed_fields: List[str]                       # fields that changed vs last turn

    # Milestone 6: Execution transparency
    parse_method: Literal["llm", "rule_based_fallback"]
    synthesis_method: Literal["llm", "template_fallback"]

