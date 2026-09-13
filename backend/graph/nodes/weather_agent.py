"""
weather_agent node
------------------
Returns sea-state / atmospheric conditions for the queried location.

Milestone 2: Calls tools/marine_weather_client.py (Open-Meteo Marine + Forecast API)
             with fallback to data/fallback_weather.json.

Milestone 3: Emits data_quality = "live" or "fallback".

Data flow:
  Open-Meteo Marine + Forecast API
       ↓
  cmems_client.fetch_marine_conditions()
       ↓
  MarineConditions (normalised)
       ↓
  weather_agent  →  AgentResult + EvidenceItems
       ↓
  weather_result in ORCAState
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from graph.state import AgentResult, DataQualityReport, EvidenceItem, ORCAState
from tools.data_validator import make_data_quality
from tools.marine_weather_client import MarineConditions, fetch_marine_conditions

logger = logging.getLogger("tarang.weather")

# ---------------------------------------------------------------------------
# Fallback data (loaded from file; never silently presented as live)
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_FALLBACK_FILE = _DATA_DIR / "fallback_weather.json"

_DEFAULT_WEATHER = {
    "wave_height_m": 2.0,
    "wind_speed_kmh": 30.0,
    "wind_direction_deg": 225,
    "wave_direction_deg": 210,
    "sea_state": "moderate",
    "sst_celsius": None,
    "visibility_km": 8.0,
    "forecast_time": "fallback",
    "source_time": "fallback",
    "retrieved_at": "fallback",
}


def _load_fallback(location_name: str) -> dict:
    """Load weather fallback for a location, or default values."""
    try:
        if _FALLBACK_FILE.exists():
            raw = json.loads(_FALLBACK_FILE.read_text(encoding="utf-8"))
            locations = raw.get("locations", {})
            entry = locations.get(location_name.lower())
            if entry:
                # Enrich with fields the new schema expects
                entry.setdefault("wave_direction_deg", 210)
                entry.setdefault("wind_direction_deg", 225)
                entry.setdefault("sst_celsius", None)
                entry.setdefault("visibility_km", 8.0)
                entry.setdefault("forecast_time", raw.get("generated", "fallback"))
                entry.setdefault("source_time", raw.get("generated", "fallback"))
                entry.setdefault("retrieved_at", "fallback")
                return entry
    except Exception as exc:
        logger.warning("[Weather] Failed to load fallback file: %s", exc)
    return _DEFAULT_WEATHER.copy()


# ---------------------------------------------------------------------------
# Evidence builder
# ---------------------------------------------------------------------------

def _build_evidence(data: dict, source: str, source_time: str, retrieved_at: str,
                    lat: float, lon: float) -> list[EvidenceItem]:
    """Build structured EvidenceItem list from marine conditions data."""
    evidence: list[EvidenceItem] = []
    loc = {"lat": round(lat, 4), "lon": round(lon, 4)}

    if data.get("wave_height_m") is not None:
        evidence.append(EvidenceItem(
            claim=f"Significant wave height is {data['wave_height_m']} m",
            value=data["wave_height_m"],
            unit="m",
            source=source,
            source_time=source_time,
            retrieved_at=retrieved_at,
            location=loc,
            provenance_tier="global_model",
        ))

    if data.get("wind_speed_kmh") is not None:
        evidence.append(EvidenceItem(
            claim=f"Wind speed is {data['wind_speed_kmh']} km/h",
            value=data["wind_speed_kmh"],
            unit="km/h",
            source=source,
            source_time=source_time,
            retrieved_at=retrieved_at,
            location=loc,
            provenance_tier="global_model",
        ))

    if data.get("sea_state"):
        evidence.append(EvidenceItem(
            claim=f"Sea state is {data['sea_state']}",
            value=data["sea_state"],
            unit="",
            source=source,
            source_time=source_time,
            retrieved_at=retrieved_at,
            location=loc,
            provenance_tier="global_model",
        ))

    return evidence


# ---------------------------------------------------------------------------
# Public node function
# ---------------------------------------------------------------------------

def weather_agent(state: ORCAState) -> dict:
    """
    LangGraph node: fetch marine conditions and normalise to AgentResult.

    Priority:
      1. Open-Meteo Marine + Forecast API (via marine_weather_client)
      2. fallback_weather.json (clearly disclosed)
    """
    intent = state["parsed_intent"]
    assert intent is not None

    lat = intent["lat"] or 8.7642
    lon = intent["lon"] or 78.1348
    location_name = intent["location_name"]
    time_window = intent["time_window"]
    time_start_utc = intent.get("time_start_utc", "")

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    logger.info("[Weather] Fetching conditions for %s (%s)", location_name, time_window)

    # ---- Attempt live fetch ----
    live: Optional[MarineConditions] = None
    try:
        live = fetch_marine_conditions(lat, lon, time_window, time_start_utc)
    except Exception as exc:
        logger.warning("[Weather] Live fetch failed with exception: %s", exc)

    if live is not None:
        data = {
            "wave_height_m": live.wave_height_m,
            "wave_direction_deg": live.wave_direction_deg,
            "wind_speed_kmh": live.wind_speed_kmh,
            "wind_speed_ms": live.wind_speed_ms,
            "wind_direction_deg": live.wind_direction_deg,
            "sea_state": live.sea_state,
            "sst_celsius": live.sst_celsius,
            "visibility_km": live.visibility_km,
            "forecast_time": live.forecast_time,
            "source_time": live.source_time,
            "retrieved_at": live.retrieved_at,
        }
        used_fallback = False
        source = live.source
        source_time = live.source_time
        logger.info(
            "[Weather] Live data: wave=%.2fm wind=%.1fkm/h sea=%s (source=%s)",
            live.wave_height_m, live.wind_speed_kmh, live.sea_state, source,
        )
    else:
        data = _load_fallback(location_name)
        used_fallback = True
        source = "fallback_weather.json (live source unavailable)"
        source_time = data.get("source_time", "fallback")
        logger.warning("[Weather] Using fallback data for %s", location_name)

    wave = data["wave_height_m"]
    wind = data["wind_speed_kmh"]
    sea = data["sea_state"]

    # Direction labels
    def _deg_to_compass(deg: Optional[float]) -> str:
        if deg is None:
            return "—"
        dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
                "S","SSW","SW","WSW","W","WNW","NW","NNW"]
        return dirs[round(deg / 22.5) % 16]

    wind_dir_label = _deg_to_compass(data.get("wind_direction_deg"))
    wave_dir_label = _deg_to_compass(data.get("wave_direction_deg"))

    summary = (
        f"Wave height {wave} m ({wave_dir_label}), "
        f"wind {wind} km/h ({wind_dir_label}), "
        f"sea state: {sea}."
    )
    if used_fallback:
        summary += " [⚠️ Using cached fallback — live source unavailable]"

    evidence = _build_evidence(data, source, source_time, retrieved_at, lat, lon)

    # M8: DataQuality report
    source_key = "open_meteo" if not used_fallback else "fallback_static"
    dq = make_data_quality(
        source_key=source_key,
        source=source,
        retrieved_at=retrieved_at,
        data_timestamp=data.get("source_time", source_time),
        is_fallback=used_fallback,
        is_proxy=False,
    )
    dq_report: DataQualityReport = {
        "agent_name":      "weather_agent",
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
        "agent_name": "weather_agent",
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

    current_trace      = state.get("trace") or []
    current_evidence   = state.get("evidence") or []
    current_dq_reports = state.get("data_quality_reports") or []
    return {
        "weather_result": result,
        "trace": current_trace + [result],
        "evidence": current_evidence + evidence,
        "data_quality_reports": current_dq_reports + [dq_report],
    }
