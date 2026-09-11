"""
hazard_agent node
-----------------
Returns actionable marine/weather hazard advisories for the queried location.

Milestone 1: Returns deterministic mock hazard data.
             Milestone 2: Replace `_fetch_live_hazards()` with
             tools/hazard_client.py (IMD/INCOIS advisory retrieval + cached
             fallback).

Key design requirement from the PRD:
  Absence of a retrieved warning MUST be phrased as
  "no relevant warning found in the available data" — NEVER as a guarantee
  that no hazard exists. Enforce this in the summary field below.
"""

from __future__ import annotations

from graph.state import AgentResult, ORCAState

# ---------------------------------------------------------------------------
# Mock hazard data per location
# ---------------------------------------------------------------------------
_FALLBACK_HAZARDS: dict[str, dict] = {
    "thoothukudi": {
        "advisory_timestamp": "2026-09-11T12:00:00Z",
        "cyclone_warning": False,
        "cyclone_name": None,
        "cyclone_severity": None,
        "lightning_advisory": True,
        "lightning_details": "Isolated lightning possible over Gulf of Mannar; fishermen advised caution",
        "rough_sea_advisory": False,
        "rough_sea_details": None,
        "overall_hazard_level": "low",
        "active_warnings": ["lightning_advisory"],
        "source_agency": "IMD Chennai",
    },
    "rameswaram": {
        "advisory_timestamp": "2026-09-11T12:00:00Z",
        "cyclone_warning": False,
        "cyclone_name": None,
        "cyclone_severity": None,
        "lightning_advisory": False,
        "lightning_details": None,
        "rough_sea_advisory": False,
        "rough_sea_details": None,
        "overall_hazard_level": "none",
        "active_warnings": [],
        "source_agency": "IMD Chennai",
    },
    "chennai": {
        "advisory_timestamp": "2026-09-11T12:00:00Z",
        "cyclone_warning": False,
        "cyclone_name": None,
        "cyclone_severity": None,
        "lightning_advisory": True,
        "lightning_details": "Squally weather with lightning expected along N Tamil Nadu coast",
        "rough_sea_advisory": True,
        "rough_sea_details": "Wave height 2.0-2.5 m; fishermen advised not to venture into sea",
        "overall_hazard_level": "moderate",
        "active_warnings": ["lightning_advisory", "rough_sea_advisory"],
        "source_agency": "IMD Chennai / INCOIS",
    },
}

_DEFAULT_HAZARDS = {
    "advisory_timestamp": "2026-09-11T12:00:00Z",
    "cyclone_warning": False,
    "cyclone_name": None,
    "cyclone_severity": None,
    "lightning_advisory": False,
    "lightning_details": None,
    "rough_sea_advisory": False,
    "rough_sea_details": None,
    "overall_hazard_level": "none",
    "active_warnings": [],
    "source_agency": "IMD / INCOIS (fallback snapshot)",
}


def _fetch_live_hazards(lat: float, lon: float, time_window: str) -> dict | None:
    """
    Milestone 2: call tools/hazard_client.py here (IMD/INCOIS advisory
    retrieval with ≤5s timeout).
    Return None on any error/timeout so the fallback path kicks in.
    """
    return None  # live integration deferred to Milestone 2


def hazard_agent(state: ORCAState) -> dict:
    """
    LangGraph node: fetch/mock marine and weather hazard advisories.
    """
    intent = state["parsed_intent"]
    assert intent is not None

    lat = intent["lat"] or 8.7642
    lon = intent["lon"] or 78.1348
    location_name = intent["location_name"].lower()
    time_window = intent["time_window"]

    live_data = _fetch_live_hazards(lat, lon, time_window)
    if live_data:
        data = live_data
        used_fallback = False
        source = (
            f"IMD / INCOIS Marine Advisory (live) — "
            f"{data.get('advisory_timestamp', 'N/A')}"
        )
    else:
        data = _FALLBACK_HAZARDS.get(location_name, _DEFAULT_HAZARDS).copy()
        used_fallback = True
        source = (
            f"IMD / INCOIS Advisory snapshot — "
            f"{data.get('advisory_timestamp', 'N/A')} (cached, used_fallback=True)"
        )

    # Build a careful summary that respects the PRD's language requirement.
    active = data.get("active_warnings", [])
    level = data.get("overall_hazard_level", "none")

    if not active:
        # PRD requirement: do NOT say "sea is safe" — say no warning found.
        summary = (
            f"No relevant hazard warning found in available data "
            f"(as of {data['advisory_timestamp']}). "
            "This does not guarantee absence of hazard."
        )
    else:
        warning_labels = {
            "cyclone_warning": "cyclone warning",
            "lightning_advisory": "lightning advisory",
            "rough_sea_advisory": "rough sea advisory",
        }
        active_str = ", ".join(warning_labels.get(w, w) for w in active)
        summary = (
            f"Active hazard alerts ({level} level): {active_str}. "
            f"Source: {data['source_agency']}, {data['advisory_timestamp']}."
        )

    result: AgentResult = {
        "agent_name": "hazard_agent",
        "status": "success",
        "data": data,
        "source": source,
        "summary": summary,
        "used_fallback": used_fallback,
    }

    current_trace = state.get("trace") or []
    return {
        "hazard_result": result,
        "trace": current_trace + [result],
    }
