"""
weather_agent node
------------------
Returns sea-state / atmospheric conditions for the queried location.

Milestone 1: Returns deterministic mock data seeded from the query location.
             In Milestone 2 replace `_fetch_live_weather()` with the CMEMS
             client and keep the fallback path as-is.
"""

from __future__ import annotations

from graph.state import AgentResult, ORCAState

# ---------------------------------------------------------------------------
# Mock fallback data per location (keyed by location_name lowercase)
# Extend this before the demo with every location you plan to rehearse.
# ---------------------------------------------------------------------------
_FALLBACK_WEATHER: dict[str, dict] = {
    "thoothukudi": {
        "wave_height_m": 1.8,
        "wind_speed_kmh": 28,
        "wind_direction": "SW",
        "visibility_km": 8,
        "sea_state": "moderate",
        "sst_celsius": 29.4,
        "advisory_timestamp": "2026-09-11T18:00:00Z",
    },
    "rameswaram": {
        "wave_height_m": 1.2,
        "wind_speed_kmh": 20,
        "wind_direction": "SE",
        "visibility_km": 10,
        "sea_state": "slight",
        "sst_celsius": 30.1,
        "advisory_timestamp": "2026-09-11T18:00:00Z",
    },
    "chennai": {
        "wave_height_m": 2.1,
        "wind_speed_kmh": 35,
        "wind_direction": "NE",
        "visibility_km": 6,
        "sea_state": "rough",
        "sst_celsius": 28.8,
        "advisory_timestamp": "2026-09-11T18:00:00Z",
    },
}

_DEFAULT_WEATHER = {
    "wave_height_m": 2.0,
    "wind_speed_kmh": 30,
    "wind_direction": "SW",
    "visibility_km": 8,
    "sea_state": "moderate",
    "sst_celsius": 29.0,
    "advisory_timestamp": "2026-09-11T18:00:00Z",
}


def _fetch_live_weather(lat: float, lon: float, time_window: str) -> dict | None:
    """
    Milestone 2: call copernicusmarine client here.
    Return None on any error/timeout so the fallback path kicks in.
    """
    return None  # live integration deferred to Milestone 2


def weather_agent(state: ORCAState) -> dict:
    """
    LangGraph node: fetch/mock weather & sea-state conditions.
    """
    intent = state["parsed_intent"]
    assert intent is not None

    lat = intent["lat"] or 8.7642
    lon = intent["lon"] or 78.1348
    location_name = intent["location_name"].lower()
    time_window = intent["time_window"]

    live_data = _fetch_live_weather(lat, lon, time_window)
    if live_data:
        data = live_data
        used_fallback = False
        source = f"CMEMS Ocean Physics (live) — {lat:.4f}N, {lon:.4f}E"
    else:
        data = _FALLBACK_WEATHER.get(location_name, _DEFAULT_WEATHER).copy()
        used_fallback = True
        source = "CMEMS fallback snapshot — 2026-09-11 (cached)"

    wave = data["wave_height_m"]
    wind = data["wind_speed_kmh"]
    sea = data["sea_state"]
    summary = (
        f"Wave height {wave} m, wind {wind} km/h ({data['wind_direction']}), "
        f"sea state: {sea}."
    )

    result: AgentResult = {
        "agent_name": "weather_agent",
        "status": "success",
        "data": data,
        "source": source,
        "summary": summary,
        "used_fallback": used_fallback,
    }

    current_trace = state.get("trace") or []
    return {
        "weather_result": result,
        "trace": current_trace + [result],
    }
