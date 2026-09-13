"""
marine_weather_client.py
------------------------
Marine conditions client for Tarang (Milestone 2+).

Strategy: Open-Meteo Marine API + Open-Meteo Forecast API
  - Free, no credentials required
  - Provides: wave_height, wave_direction, wind_speed, wind_direction
  - Model: ERA5 reanalysis + ICON NWP for forecast

Normalised output: MarineConditions dataclass.

Data freshness:
  - source_time:   the forecast valid time (first hour of the requested window)
  - retrieved_at:  the moment this function was called

Caching: in-memory TTL cache keyed by (lat_1dp, lon_1dp, time_window).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from cachetools import TTLCache, cached

import config

logger = logging.getLogger("tarang.marine_weather")

# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------
_marine_cache: TTLCache = TTLCache(maxsize=64, ttl=config.CACHE_TTL_MARINE_S)


# ---------------------------------------------------------------------------
# Normalised result type
# ---------------------------------------------------------------------------

@dataclass
class MarineConditions:
    """Normalised marine / atmospheric conditions for a location + time."""
    wave_height_m: float
    wave_direction_deg: float
    wind_speed_kmh: float
    wind_direction_deg: float
    wind_speed_ms: float
    sea_state: str              # WMO sea-state label
    sst_celsius: Optional[float]
    visibility_km: Optional[float]
    forecast_time: str          # ISO-8601 UTC: valid time of first forecast hour
    source_time: str            # same as forecast_time (for evidence layer)
    retrieved_at: str           # ISO-8601 UTC: when we fetched
    pressure_msl_hpa: Optional[float] = None
    source: str = "Open-Meteo Marine + Forecast (ERA5-ICON)"
    used_fallback: bool = False




# ---------------------------------------------------------------------------
# Sea-state classification (WMO Douglas scale)
# ---------------------------------------------------------------------------

def _sea_state(wave_m: float) -> str:
    """Return WMO sea-state label from significant wave height."""
    if wave_m < 0.1:
        return "calm"
    elif wave_m < 0.5:
        return "smooth"
    elif wave_m < 1.25:
        return "slight"
    elif wave_m < 2.5:
        return "moderate"
    elif wave_m < 4.0:
        return "rough"
    elif wave_m < 6.0:
        return "very rough"
    else:
        return "high"


# ---------------------------------------------------------------------------
# Time-window → forecast day + hour range
# ---------------------------------------------------------------------------

def _resolve_forecast_window(time_window: str, time_start_utc: str) -> tuple[int, int, int]:
    """
    Return (forecast_day_offset, start_hour_utc, end_hour_utc) for slicing
    Open-Meteo hourly arrays.

    forecast_day_offset: 0 = today, 1 = tomorrow, etc.
    start/end are UTC hours (0–23) to average over.
    """
    tw = time_window.lower()
    if "tomorrow" in tw and "morning" in tw:
        return 1, 0, 11       # tomorrow 00:00–11:00 UTC ≈ 05:30–16:30 IST
    elif "tomorrow" in tw and "evening" in tw:
        return 1, 10, 15      # tomorrow 10:00–15:00 UTC ≈ 15:30–20:30 IST
    elif "tomorrow" in tw:
        return 1, 0, 23
    elif "morning" in tw:
        return 0, 0, 11
    elif "evening" in tw:
        return 0, 10, 15
    elif "now" in tw:
        return 0, 0, 3
    elif "today" in tw:
        return 0, 0, 23
    else:
        return 0, 0, 23       # next_24h


def _average_circular(angles: list[float]) -> float:
    """Circular mean for wind/wave direction values."""
    if not angles:
        return 0.0
    sin_sum = sum(math.sin(math.radians(a)) for a in angles)
    cos_sum = sum(math.cos(math.radians(a)) for a in angles)
    return round((math.degrees(math.atan2(sin_sum, cos_sum)) + 360) % 360, 1)


# ---------------------------------------------------------------------------
# Core fetch function (with timeout + error handling)
# ---------------------------------------------------------------------------

def _fetch_open_meteo_marine(
    lat: float, lon: float, time_window: str, time_start_utc: str
) -> Optional[MarineConditions]:
    """
    Fetch marine conditions from Open-Meteo Marine + Forecast APIs.
    Returns None on any error (timeout, HTTP error, parse failure).
    """
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    day_offset, hour_start, hour_end = _resolve_forecast_window(time_window, time_start_utc)
    forecast_days = day_offset + 2  # always request enough days

    logger.info(
        "[Weather] Fetching Open-Meteo marine: lat=%.4f lon=%.4f window=%s",
        lat, lon, time_window,
    )

    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT) as client:
            # ---- Marine API: wave_height, wave_direction ----
            marine_resp = client.get(
                config.OPEN_METEO_MARINE_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": "wave_height,wave_direction",
                    "length_unit": "metric",
                    "timezone": "UTC",
                    "forecast_days": forecast_days,
                },
            )
            marine_resp.raise_for_status()
            marine_data = marine_resp.json()

            # ---- Forecast API: wind_speed, wind_direction, visibility ----
            forecast_resp = client.get(
                config.OPEN_METEO_FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": "wind_speed_10m,wind_direction_10m,visibility,pressure_msl",
                    "wind_speed_unit": "ms",
                    "timezone": "UTC",
                    "forecast_days": forecast_days,
                },
            )
            forecast_resp.raise_for_status()
            forecast_data = forecast_resp.json()

    except httpx.TimeoutException:
        logger.warning("[Weather] Open-Meteo request timed out after %ds", config.HTTP_TIMEOUT)
        return None
    except httpx.HTTPError as exc:
        logger.warning("[Weather] Open-Meteo HTTP error: %s", exc)
        return None
    except Exception as exc:
        logger.warning("[Weather] Unexpected error fetching Open-Meteo: %s", exc)
        return None

    # ---- Parse marine hourly arrays ----
    try:
        marine_times: list[str] = marine_data["hourly"]["time"]
        wave_heights: list[Optional[float]] = marine_data["hourly"]["wave_height"]
        wave_dirs: list[Optional[float]] = marine_data["hourly"]["wave_direction"]

        forecast_times: list[str] = forecast_data["hourly"]["time"]
        wind_speeds_ms: list[Optional[float]] = forecast_data["hourly"]["wind_speed_10m"]
        wind_dirs: list[Optional[float]] = forecast_data["hourly"]["wind_direction_10m"]
        visibilities: list[Optional[float]] = forecast_data["hourly"].get("visibility", [])
        pressures: list[Optional[float]] = forecast_data["hourly"].get("pressure_msl", [])

        # Determine slice: day_offset * 24 + hour range
        slice_start = day_offset * 24 + hour_start
        slice_end = day_offset * 24 + hour_end + 1

        wh_slice = [v for v in wave_heights[slice_start:slice_end] if v is not None]
        wd_slice = [v for v in wave_dirs[slice_start:slice_end] if v is not None]
        ws_slice = [v for v in wind_speeds_ms[slice_start:slice_end] if v is not None]
        wdir_slice = [v for v in wind_dirs[slice_start:slice_end] if v is not None]
        vis_slice = [v for v in visibilities[slice_start:slice_end] if v is not None]
        p_slice = [v for v in pressures[slice_start:slice_end] if v is not None]

        if not wh_slice or not ws_slice:
            logger.warning("[Weather] No valid data in requested time slice")
            return None

        avg_wave_h = round(sum(wh_slice) / len(wh_slice), 2)
        avg_wave_d = _average_circular(wd_slice) if wd_slice else 0.0
        avg_wind_ms = round(sum(ws_slice) / len(ws_slice), 2)
        avg_wind_kmh = round(avg_wind_ms * 3.6, 1)
        avg_wind_d = _average_circular(wdir_slice) if wdir_slice else 0.0
        avg_vis_km = round(sum(vis_slice) / len(vis_slice) / 1000, 1) if vis_slice else None
        avg_pressure = round(sum(p_slice) / len(p_slice), 1) if p_slice else None

        # Forecast valid time = first hour of slice
        valid_time = marine_times[slice_start] + "Z" if slice_start < len(marine_times) else retrieved_at

        logger.info(
            "[Weather] Retrieved: wave=%.2fm wind=%.1fkm/h sea=%s msl=%.1fhPa",
            avg_wave_h, avg_wind_kmh, _sea_state(avg_wave_h), avg_pressure or 0.0,
        )

        return MarineConditions(
            wave_height_m=avg_wave_h,
            wave_direction_deg=avg_wave_d,
            wind_speed_ms=avg_wind_ms,
            wind_speed_kmh=avg_wind_kmh,
            wind_direction_deg=avg_wind_d,
            sea_state=_sea_state(avg_wave_h),
            sst_celsius=None,
            visibility_km=avg_vis_km,
            pressure_msl_hpa=avg_pressure,
            forecast_time=valid_time,
            source_time=valid_time,
            retrieved_at=retrieved_at,
        )


    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("[Weather] Failed to parse Open-Meteo response: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public cached entry point
# ---------------------------------------------------------------------------

def fetch_marine_conditions(
    lat: float, lon: float, time_window: str, time_start_utc: str = ""
) -> Optional[MarineConditions]:
    """
    Return normalised MarineConditions for the given location and time window.

    Results are cached for CACHE_TTL_MARINE_S seconds.
    Returns None if all attempts fail (caller should activate fallback).
    """
    cache_key = (round(lat, 1), round(lon, 1), time_window)
    if cache_key in _marine_cache:
        logger.info("[Weather] Cache hit for %s", cache_key)
        return _marine_cache[cache_key]

    result = _fetch_open_meteo_marine(lat, lon, time_window, time_start_utc)
    if result is not None:
        _marine_cache[cache_key] = result
    return result
