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
            timestamp=source_time,
            data_type="forecast",
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
            timestamp=source_time,
            data_type="forecast",
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
            timestamp=source_time,
            data_type="forecast",
        ))

    if data.get("pressure_msl_hpa") is not None:
        evidence.append(EvidenceItem(
            claim=f"Atmospheric surface pressure (MSL) is {data['pressure_msl_hpa']} hPa",
            value=data["pressure_msl_hpa"],
            unit="hPa",
            source=source,
            source_time=source_time,
            retrieved_at=retrieved_at,
            location=loc,
            provenance_tier="global_model",
            timestamp=source_time,
            data_type="forecast",
        ))

    return evidence


# ---------------------------------------------------------------------------
# Public node function
# ---------------------------------------------------------------------------

def weather_agent(state: ORCAState) -> dict:
    """
    LangGraph node: fetch marine conditions and normalise to AgentResult.
    Strictly consumes state.resolved_location and enforces V2.1 contract.
    """
    resolved = state.get("resolved_location")
    if not resolved or not resolved.get("coastal"):
        logger.info("[Weather] Skipped: resolved_location is missing or non-coastal")
        result: AgentResult = {
            "agent_name": "weather_agent",
            "status": "skipped",
            "execution_status": "skipped",
            "data_status": "unavailable",
            "location_used": None,
            "observed_at": None,
            "data": {},
            "source": "Open-Meteo Marine + Forecast",
            "summary": "Weather assessment skipped: location is not a verified coastal zone.",
            "used_fallback": False,
            "data_quality": "unavailable",
            "timestamp": "",
            "error": None,
            "evidence": [],
        }
        return {"weather_result": result}

    lat = resolved["lat"]
    lon = resolved["lon"]
    location_name = resolved.get("name", "Coastal Location")
    location_used = {"lat": round(lat, 4), "lon": round(lon, 4)}

    intent = state.get("parsed_intent")
    time_window = intent.get("time_window", "next_24h") if intent else "next_24h"
    time_start_utc = intent.get("time_start_utc", "") if intent else ""

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    logger.info("[Weather] Fetching conditions for %s (%s)", location_name, time_window)

    # ---- Attempt live fetch ----
    live: Optional[MarineConditions] = None
    try:
        live = fetch_marine_conditions(lat, lon, time_window, time_start_utc)
    except Exception as exc:
        logger.warning("[Weather] Live fetch failed with exception: %s", exc)

    if live is None:
        # PRD §5 & §20: Eliminate silent fallback fabrication on live failure
        logger.warning("[Weather] Live marine weather unavailable for %s — failing without fabrication", location_name)
        result: AgentResult = {
            "agent_name": "weather_agent",
            "status": "error",
            "execution_status": "failed",
            "data_status": "unavailable",
            "location_used": location_used,
            "observed_at": None,
            "data": {},
            "source": "Open-Meteo Marine + Forecast",
            "summary": f"Live marine weather data unavailable for {location_name}.",
            "used_fallback": False,
            "data_quality": "unavailable",
            "timestamp": retrieved_at,
            "error": "LIVE_WEATHER_UNAVAILABLE",
            "evidence": [],
        }
        dq_report: DataQualityReport = {
            "agent_name":      "weather_agent",
            "source_key":      "open_meteo",
            "source":          "Open-Meteo Marine + Forecast",
            "provenance_tier": "global_model",
            "is_official":     False,
            "is_proxy":        False,
            "is_fallback":     False,
            "is_stale":        True,
            "freshness_hours": 9999.0,
            "quality_score":   0.0,
            "warnings":        ["Live marine weather fetch failed; source unavailable."],
        }
        current_trace = state.get("trace") or []
        current_evidence = state.get("evidence") or []
        current_dq_reports = state.get("data_quality_reports") or []
        return {
            "weather_result": result,
            "trace": current_trace + [result],
            "evidence": current_evidence,
            "data_quality_reports": current_dq_reports + [dq_report],
        }

    data = {
        "wave_height_m": live.wave_height_m,
        "wave_direction_deg": live.wave_direction_deg,
        "wind_speed_kmh": live.wind_speed_kmh,
        "wind_speed_ms": live.wind_speed_ms,
        "wind_direction_deg": live.wind_direction_deg,
        "sea_state": live.sea_state,
        "visibility_km": live.visibility_km,
        "pressure_msl_hpa": live.pressure_msl_hpa,
        "forecast_time": live.forecast_time,
        "source_time": live.source_time,
        "retrieved_at": live.retrieved_at,
    }
    source = live.source
    source_time = live.source_time
    logger.info(
        "[Weather] Live data: wave=%.2fm wind=%.1fkm/h msl=%s sea=%s (source=%s)",
        live.wave_height_m, live.wind_speed_kmh, live.pressure_msl_hpa, live.sea_state, source,
    )

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

    evidence = _build_evidence(data, source, source_time, retrieved_at, lat, lon)

    # M8: DataQuality report
    dq = make_data_quality(
        source_key="open_meteo",
        source=source,
        retrieved_at=retrieved_at,
        data_timestamp=source_time,
        is_fallback=False,
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
        "execution_status": "success",
        "data_status": "live",
        "location_used": location_used,
        "observed_at": source_time,
        "data": data,
        "source": source,
        "summary": summary,
        "used_fallback": False,
        "data_quality": "live",
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
