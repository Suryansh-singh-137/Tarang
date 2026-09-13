"""
hazard_agent node
-----------------
Returns actionable marine/weather hazard advisories for the queried location.

Milestone 2: Calls tools/hazard_client.py (Open-Meteo WMO weather-code
             interpretation) with fallback to data/fallback_hazards.json.
Milestone 3: Emits data_quality = "live" or "fallback".

Milestone 8 (M8) — Source priority (hierarchical, not averaged):
  1. IMD official warnings (imd_client) — TIER 1 [Official Operational]
     Currently a stub; always returns None until API credentials set.
  2. GDACS tropical cyclone events (gdacs_client) — TIER 2 [Scientific Model]
     Queries live GDACS API; filters spatially (radius = config.GDACS_SEARCH_RADIUS_KM).
     GDACS cyclones NEVER override existing IMD hazard level.
  3. Open-Meteo WMO codes (hazard_client) — TIER 3 [Proxy]
     Unchanged from previous milestones.
  4. fallback_hazards.json — TIER 5 [Historical Fallback]

Key design requirements:
  - Absence of data → "no warning found in available data" NOT "no hazard"
  - Severity normalisation: none / low / moderate / high / extreme
  - GDACS cyclone result integrated into HazardAdvisory before it is passed
    to risk_agent (no risk_agent changes needed)

GeoJSON cyclone features added when relevant cyclone found.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from graph.state import AgentResult, DataQualityReport, EvidenceItem, ORCAState
from tools.data_validator import make_data_quality
from tools.gdacs_client import GDACSTCEvent, GDACSTCResult, fetch_active_cyclones
from tools.hazard_client import HazardAdvisory, fetch_hazard_advisory
from tools.imd_client import IMDAdvisoryResult, fetch_imd_warnings

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
# GDACS cyclone integration helpers
# ---------------------------------------------------------------------------

_GDACS_SEVERITY_MAP = {
    "Green":  "low",
    "Orange": "moderate",
    "Red":    "high",
}

def _gdacs_to_hazard_level(alert_level: str) -> str:
    """Map GDACS alert level to Tarang severity string."""
    return _GDACS_SEVERITY_MAP.get(alert_level, "moderate")


def _build_cyclone_geojson_feature(ev: GDACSTCEvent) -> dict:
    """Build a GeoJSON Point feature for a GDACS cyclone event."""
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [ev.lon, ev.lat]},
        "properties": {
            "feature_type":    "cyclone_warning",
            "name":            ev.name,
            "alert_level":     ev.alert_level,
            "wind_speed_kmh":  ev.wind_speed_kmh,
            "distance_km":     ev.distance_km,
            "from_date":       ev.from_date,
            "to_date":         ev.to_date,
            "source":          ev.source,
        },
    }


def _merge_gdacs_into_hazard(
    base_data: dict,
    gdacs: GDACSTCResult,
    retrieved_at: str,
) -> tuple[dict, list[EvidenceItem]]:
    """
    Merge GDACS cyclone events into the base hazard data dict.

    Returns updated data dict and additional EvidenceItems.
    GDACS cyclone NEVER downgrades an existing high/extreme level.
    """
    extra_evidence: list[EvidenceItem] = []
    if not gdacs.events:
        return base_data, extra_evidence

    nearest = min(gdacs.events, key=lambda e: e.distance_km)
    cyclone_level = _gdacs_to_hazard_level(nearest.alert_level)

    # Severity ordering
    _order = ["none", "low", "moderate", "high", "extreme"]
    current_level = base_data.get("overall_hazard_level", "none")
    new_level = (
        cyclone_level
        if _order.index(cyclone_level) > _order.index(current_level)
        else current_level
    )

    base_data = dict(base_data)  # shallow copy
    base_data["cyclone_warning"] = True
    base_data["cyclone_name"] = nearest.name
    base_data["cyclone_distance_km"] = nearest.distance_km
    base_data["cyclone_wind_kmh"] = nearest.wind_speed_kmh
    base_data["cyclone_alert_level"] = nearest.alert_level
    base_data["overall_hazard_level"] = new_level
    base_data["gdacs_events"] = [
        {
            "name": ev.name, "lat": ev.lat, "lon": ev.lon,
            "distance_km": ev.distance_km, "wind_speed_kmh": ev.wind_speed_kmh,
            "alert_level": ev.alert_level, "from_date": ev.from_date,
        }
        for ev in gdacs.events
    ]

    active = list(base_data.get("active_warnings", []))
    if "cyclone_warning" not in active:
        active.append("cyclone_warning")
    base_data["active_warnings"] = active

    # Evidence items
    extra_evidence.append(EvidenceItem(
        claim=(
            f"GDACS cyclone '{nearest.name}' ({nearest.alert_level} alert) is "
            f"{nearest.distance_km:.0f} km from query location, "
            f"maximum wind speed {nearest.wind_speed_kmh:.0f} km/h."
        ),
        value=nearest.distance_km,
        unit="km",
        source=nearest.source,
        source_time=nearest.to_date,
        retrieved_at=retrieved_at,
        location={"lat": nearest.lat, "lon": nearest.lon},
        provenance_tier="scientific_model",
    ))

    logger.info(
        "[Hazard] GDACS cyclone '%s' merged: distance=%.0fkm level=%s→%s",
        nearest.name, nearest.distance_km, current_level, new_level,
    )
    return base_data, extra_evidence


# ---------------------------------------------------------------------------
# Evidence builder (for Open-Meteo path)
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
        provenance_tier="proxy",  # Open-Meteo WMO = Tier 3/proxy
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
            provenance_tier="proxy",
        ))

    return evidence


# ---------------------------------------------------------------------------
# Public node function
# ---------------------------------------------------------------------------

def hazard_agent(state: ORCAState) -> dict:
    """
    LangGraph node: fetch/interpret hazard advisories.

    M8 Priority:
      1. IMD official warnings (stub — always None until credentials set)
      2. GDACS active cyclones (live, spatially filtered)
      3. Open-Meteo WMO weather-code advisory
      4. fallback_hazards.json
    """
    intent = state["parsed_intent"]
    assert intent is not None

    lat = intent["lat"] or 8.7642
    lon = intent["lon"] or 78.1348
    location_name = intent["location_name"]
    time_window = intent["time_window"]

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    logger.info("[Hazard] Fetching advisories for %s (%s)", location_name, time_window)

    # ── Tier 1: IMD official warnings (stub) ─────────────────────────────────
    imd_result: Optional[IMDAdvisoryResult] = None
    try:
        imd_result = fetch_imd_warnings(lat, lon, time_window)
    except Exception as exc:
        logger.warning("[Hazard] IMD fetch raised exception: %s", exc)

    # ── Tier 2: GDACS cyclone events ─────────────────────────────────────────
    gdacs_result: Optional[GDACSTCResult] = None
    try:
        gdacs_result = fetch_active_cyclones(lat, lon)
    except Exception as exc:
        logger.warning("[Hazard] GDACS fetch raised exception: %s", exc)

    # ── Tier 3: Open-Meteo WMO codes ─────────────────────────────────────────
    live: Optional[HazardAdvisory] = None
    try:
        live = fetch_hazard_advisory(lat, lon, time_window)
    except Exception as exc:
        logger.warning("[Hazard] Open-Meteo fetch raised exception: %s", exc)

    # ── Build base data dict ──────────────────────────────────────────────────
    gdacs_evidence: list[EvidenceItem] = []
    source_key = "open_meteo_wmo"

    if live is not None:
        data = {
            "hazards": [
                {
                    "type":             h.hazard_type,
                    "severity":         h.severity,
                    "title":            h.title,
                    "detail":           h.detail,
                    "valid_from":       h.valid_from,
                    "valid_until":      h.valid_until,
                    "source":           h.source,
                    "location_relevant": h.location_relevant,
                }
                for h in live.hazards
            ],
            "overall_hazard_level":  live.overall_level,
            "active_warnings":       live.active_warnings,
            "cyclone_warning":       live.cyclone_warning,
            "lightning_advisory":    any(h.hazard_type == "thunderstorm" for h in live.hazards),
            "rough_sea_advisory":    any(h.hazard_type in ("rough_sea_advisory", "heavy_rain") for h in live.hazards),
            "source_time":           live.source_time,
            "retrieved_at":          live.retrieved_at,
            "source_agency":         live.source,
        }
        used_fallback = False
        source = live.source
        source_time = live.source_time
        evidence = _build_evidence(live, source, lat, lon)
        logger.info(
            "[Hazard] Open-Meteo: %d hazard(s), level=%s",
            len(live.hazards), live.overall_level,
        )
    else:
        fb = _load_fallback(location_name)
        data = _fallback_to_normalized(fb, retrieved_at)
        data["source_agency"] = "fallback_hazards.json"
        used_fallback = True
        source = "fallback_hazards.json (live source unavailable)"
        source_time = fb.get("advisory_timestamp", retrieved_at)
        source_key = "fallback_static"
        evidence = [EvidenceItem(
            claim=f"Overall hazard level: {data.get('overall_hazard_level', 'none')} (fallback data)",
            value=data.get("overall_hazard_level", "none"),
            unit="",
            source=source,
            source_time=source_time,
            retrieved_at=retrieved_at,
            location={"lat": round(lat, 4), "lon": round(lon, 4)},
            provenance_tier="historical_fallback",
        )]
        logger.warning("[Hazard] Falling back to cached dataset for %s", location_name)

    # ── Merge GDACS into data (Tier 2 cyclone augmentation) ──────────────────
    if gdacs_result is not None and gdacs_result.events:
        data, gdacs_evidence = _merge_gdacs_into_hazard(data, gdacs_result, retrieved_at)
        evidence = evidence + gdacs_evidence

    # ── Build summary ─────────────────────────────────────────────────────────
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

    if gdacs_result and gdacs_result.events:
        nearest_tc = min(gdacs_result.events, key=lambda e: e.distance_km)
        summary += (
            f" | GDACS: Cyclone '{nearest_tc.name}' {nearest_tc.distance_km:.0f} km "
            f"away ({nearest_tc.alert_level} alert, {nearest_tc.wind_speed_kmh:.0f} km/h)."
        )

    # ── DataQuality report ────────────────────────────────────────────────────
    dq = make_data_quality(
        source_key=source_key,
        source=source,
        retrieved_at=retrieved_at,
        data_timestamp=source_time,
        is_fallback=used_fallback,
        is_proxy=(source_key in ("open_meteo_wmo", "fallback_static")),
    )
    dq_report: DataQualityReport = {
        "agent_name":      "hazard_agent",
        "source_key":      dq.source_key,
        "source":          dq.source,
        "provenance_tier": dq.provenance_tier.value,
        "is_official":     dq.is_official,
        "is_proxy":        dq.is_proxy,
        "is_fallback":     dq.is_fallback,
        "is_stale":        dq.is_stale,
        "freshness_hours": dq.freshness_hours,
        "quality_score":   dq.quality_score,
        "warnings":        dq.warnings,
    }

    result: AgentResult = {
        "agent_name":    "hazard_agent",
        "status":        "success",
        "data":          data,
        "source":        source,
        "summary":       summary,
        "used_fallback": used_fallback,
        "data_quality":  "fallback" if used_fallback else "live",
        "timestamp":     retrieved_at,
        "error":         None,
        "evidence":      evidence,
    }

    current_trace      = state.get("trace") or []
    current_evidence   = state.get("evidence") or []
    current_dq_reports = state.get("data_quality_reports") or []
    return {
        "hazard_result":        result,
        "trace":                current_trace + [result],
        "evidence":             current_evidence + evidence,
        "data_quality_reports": current_dq_reports + [dq_report],
    }
