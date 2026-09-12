"""
hazard_agent node
-----------------
Returns actionable marine/weather hazard advisories for the queried location.

Milestone 2: Calls tools/hazard_client.py (Open-Meteo WMO weather-code
             interpretation) with fallback to data/fallback_hazards.json.
Milestone 3: Emits data_quality = "live" or "fallback".

Key design requirement from the PRD:
  Absence of a retrieved warning MUST be phrased as
  "no relevant warning found in the available data" — NEVER as a guarantee
  that no hazard exists.

Severity normalisation (PRD §16):
  All hazard levels → none / low / moderate / high / extreme.
  Normalisation happens in hazard_client.py, not here.

Data flow:
  Open-Meteo Forecast API (WMO codes + wind gusts)
       ↓
  hazard_client.fetch_hazard_advisory()
       ↓
  HazardAdvisory (normalised)
       ↓
  hazard_agent  →  AgentResult + EvidenceItems
       ↓
  hazard_result in ORCAState
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from graph.state import AgentResult, EvidenceItem, ORCAState
from tools.hazard_client import HazardAdvisory, fetch_hazard_advisory

logger = logging.getLogger("tarang.hazard")

# ---------------------------------------------------------------------------
# Fallback data (loaded from file)
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_FALLBACK_FILE = _DATA_DIR / "fallback_hazards.json"

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
    "source_agency": "fallback_hazards.json",
}


def _load_fallback(location_name: str) -> dict:
    """Load hazard fallback for a location."""
    try:
        if _FALLBACK_FILE.exists():
            raw = json.loads(_FALLBACK_FILE.read_text(encoding="utf-8"))
            locations = raw.get("locations", {})
            entry = locations.get(location_name.lower())
            if entry:
                return entry
    except Exception as exc:
        logger.warning("[Hazard] Failed to load fallback file: %s", exc)
    return _DEFAULT_HAZARDS.copy()


def _fallback_to_normalized(fallback_data: dict, retrieved_at: str) -> dict:
    """Convert fallback dict to the normalized structure used by the risk agent."""
    active = fallback_data.get("active_warnings", [])
    return {
        "hazards": [],
        "overall_hazard_level": fallback_data.get("overall_hazard_level", "none"),
        "active_warnings": active,
        "cyclone_warning": fallback_data.get("cyclone_warning", False),
        "lightning_advisory": fallback_data.get("lightning_advisory", False),
        "rough_sea_advisory": fallback_data.get("rough_sea_advisory", False),
        "source_time": fallback_data.get("advisory_timestamp", retrieved_at),
        "retrieved_at": retrieved_at,
    }


# ---------------------------------------------------------------------------
# Evidence builder
# ---------------------------------------------------------------------------

def _build_evidence(
    hazard: HazardAdvisory, source: str, lat: float, lon: float
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    loc = {"lat": round(lat, 4), "lon": round(lon, 4)}

    evidence.append(EvidenceItem(
        claim=f"Overall hazard level: {hazard.overall_level}",
        value=hazard.overall_level,
        unit="",
        source=source,
        source_time=hazard.source_time,
        retrieved_at=hazard.retrieved_at,
        location=loc,
    ))

    for h in hazard.hazards:
        evidence.append(EvidenceItem(
            claim=h.title + ": " + h.detail[:120],
            value=h.severity,
            unit="severity",
            source=source,
            source_time=h.valid_from,
            retrieved_at=hazard.retrieved_at,
            location=loc,
        ))

    return evidence


# ---------------------------------------------------------------------------
# Public node function
# ---------------------------------------------------------------------------

def hazard_agent(state: ORCAState) -> dict:
    """
    LangGraph node: fetch/interpret hazard advisories.

    Priority:
      1. Open-Meteo WMO weather-code advisory (via hazard_client)
      2. fallback_hazards.json (clearly disclosed)
    """
    intent = state["parsed_intent"]
    assert intent is not None

    lat = intent["lat"] or 8.7642
    lon = intent["lon"] or 78.1348
    location_name = intent["location_name"]
    time_window = intent["time_window"]

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    logger.info("[Hazard] Fetching advisories for %s (%s)", location_name, time_window)

    # ---- Attempt live fetch ----
    live: Optional[HazardAdvisory] = None
    try:
        live = fetch_hazard_advisory(lat, lon, time_window)
    except Exception as exc:
        logger.warning("[Hazard] Live fetch raised exception: %s", exc)

    if live is not None:
        # Build agent data dict compatible with risk_agent expectations
        data = {
            "hazards": [
                {
                    "type": h.hazard_type,
                    "severity": h.severity,
                    "title": h.title,
                    "detail": h.detail,
                    "valid_from": h.valid_from,
                    "valid_until": h.valid_until,
                    "source": h.source,
                    "location_relevant": h.location_relevant,
                }
                for h in live.hazards
            ],
            "overall_hazard_level": live.overall_level,
            "active_warnings": live.active_warnings,
            "cyclone_warning": live.cyclone_warning,
            "lightning_advisory": any(
                h.hazard_type == "thunderstorm" for h in live.hazards
            ),
            "rough_sea_advisory": any(
                h.hazard_type in ("rough_sea_advisory", "heavy_rain") for h in live.hazards
            ),
            "source_time": live.source_time,
            "retrieved_at": live.retrieved_at,
            "source_agency": live.source,
        }
        used_fallback = False
        source = live.source
        source_time = live.source_time
        logger.info(
            "[Hazard] Live: %d hazard(s), level=%s (source=%s)",
            len(live.hazards), live.overall_level, source,
        )
    else:
        fb = _load_fallback(location_name)
        data = _fallback_to_normalized(fb, retrieved_at)
        data["source_agency"] = "fallback_hazards.json"
        used_fallback = True
        source = "fallback_hazards.json (live source unavailable)"
        source_time = fb.get("advisory_timestamp", retrieved_at)
        logger.warning("[Hazard] Falling back to cached dataset for %s", location_name)

    # ---- Build summary ----
    active = data.get("active_warnings", [])
    level = data.get("overall_hazard_level", "none")

    if not active:
        summary = (
            f"No relevant hazard warning found in available data "
            f"(as of {source_time}). "
            "This does not guarantee absence of hazard. "
            "Cyclone advisories: consult IMD/INCOIS directly for authoritative warnings."
        )
    else:
        warning_labels = {
            "thunderstorm":       "lightning/thunderstorm advisory",
            "rough_sea_advisory": "rough sea advisory",
            "heavy_rain":         "heavy rain advisory",
            "high_wind":          "high wind advisory",
            "cyclone_warning":    "cyclone warning",
        }
        active_str = ", ".join(warning_labels.get(w, w) for w in active)
        summary = (
            f"Active hazard alerts ({level} level): {active_str}. "
            f"Source: {data.get('source_agency', source)}, {source_time}."
        )

    if used_fallback:
        summary += " [⚠️ Using cached fallback — live source unavailable]"

    evidence: list[EvidenceItem] = []
    if live is not None:
        evidence = _build_evidence(live, source, lat, lon)
    else:
        # Minimal evidence from fallback
        evidence.append(EvidenceItem(
            claim=f"Overall hazard level: {level} (fallback data)",
            value=level,
            unit="",
            source=source,
            source_time=source_time,
            retrieved_at=retrieved_at,
            location={"lat": round(lat, 4), "lon": round(lon, 4)},
        ))

    result: AgentResult = {
        "agent_name": "hazard_agent",
        "status": "success",
        "data": data,
        "source": source,
        "summary": summary,
        "used_fallback": used_fallback,
        "data_quality": "fallback" if used_fallback else "live",
        "timestamp": retrieved_at,
        "error": None,
        "evidence": evidence,
    }

    current_trace = state.get("trace") or []
    current_evidence = state.get("evidence") or []
    return {
        "hazard_result": result,
        "trace": current_trace + [result],
        "evidence": current_evidence + evidence,
    }
