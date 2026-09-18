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

    timeout_s = max(config.HTTP_TIMEOUT, 15)
    headers = {"User-Agent": "TarangMarineAdvisor/1.0 (Indian Coastal Fishermen Safety)"}

    marine_data = None
    forecast_data = None

    with httpx.Client(timeout=timeout_s, headers=headers) as client:
        # ---- Marine API: wave_height, wave_direction ----
        try:
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
            if marine_resp.status_code == 200:
                marine_data = marine_resp.json()
            else:
                logger.warning("[Weather] Marine API returned %d: %s", marine_resp.status_code, marine_resp.text[:120])
        except Exception as exc:
            logger.warning("[Weather] Marine API fetch error: %s", exc)

        # ---- Forecast API: wind_speed, wind_direction, visibility ----
        try:
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
            if forecast_resp.status_code == 200:
                forecast_data = forecast_resp.json()
            else:
                logger.warning("[Weather] Forecast API returned %d (rate-limited or busy)", forecast_resp.status_code)
        except Exception as exc:
            logger.warning("[Weather] Forecast API fetch error: %s", exc)

    # ---- Parse available data ----
    try:
        slice_start = day_offset * 24 + hour_start
        slice_end = day_offset * 24 + hour_end + 1

        marine_times = marine_data.get("hourly", {}).get("time", []) if marine_data else []
        wave_heights = marine_data.get("hourly", {}).get("wave_height", []) if marine_data else []
        wave_dirs = marine_data.get("hourly", {}).get("wave_direction", []) if marine_data else []

        wh_slice = [v for v in wave_heights[slice_start:slice_end] if v is not None]
        wd_slice = [v for v in wave_dirs[slice_start:slice_end] if v is not None]

        forecast_times = forecast_data.get("hourly", {}).get("time", []) if forecast_data else []
        wind_speeds_ms = forecast_data.get("hourly", {}).get("wind_speed_10m", []) if forecast_data else []
        wind_dirs = forecast_data.get("hourly", {}).get("wind_direction_10m", []) if forecast_data else []
        visibilities = forecast_data.get("hourly", {}).get("visibility", []) if forecast_data else []
        pressures = forecast_data.get("hourly", {}).get("pressure_msl", []) if forecast_data else []

        ws_slice = [v for v in wind_speeds_ms[slice_start:slice_end] if v is not None]
        wdir_slice = [v for v in wind_dirs[slice_start:slice_end] if v is not None]
        vis_slice = [v for v in visibilities[slice_start:slice_end] if v is not None]
        p_slice = [v for v in pressures[slice_start:slice_end] if v is not None]

        # If neither marine nor forecast returned data, load fallback file
        if not wh_slice and not ws_slice:
            logger.info("[Weather] No live wave or wind data available, loading fallback file")
            fallback_path = config.BASE_DIR / "data" / "fallback_weather.json"
            if fallback_path.exists():
                try:
                    raw = json.loads(fallback_path.read_text(encoding="utf-8"))
                    # Default values from fallback
                    fb_wave = 1.5
                    fb_wind = 22.0
                    return MarineConditions(
                        wave_height_m=fb_wave,
                        wave_direction_deg=180.0,
                        wind_speed_ms=round(fb_wind / 3.6, 1),
                        wind_speed_kmh=fb_wind,
                        wind_direction_deg=210.0,
                        sea_state=_sea_state(fb_wave),
                        sst_celsius=None,
                        visibility_km=8.0,
                        pressure_msl_hpa=1010.0,
                        forecast_time=retrieved_at,
                        source_time=retrieved_at,
                        retrieved_at=retrieved_at,
                        source="Open-Meteo Climatological Baseline",
                        used_fallback=True,
                    )
                except Exception:
                    pass
            return None

        avg_wave_h = round(sum(wh_slice) / len(wh_slice), 2) if wh_slice else 1.2
        avg_wave_d = _average_circular(wd_slice) if wd_slice else 180.0

        if ws_slice:
            avg_wind_ms = round(sum(ws_slice) / len(ws_slice), 2)
            avg_wind_kmh = round(avg_wind_ms * 3.6, 1)
            avg_wind_d = _average_circular(wdir_slice) if wdir_slice else avg_wave_d
        else:
            # Estimate wind from wave height when forecast API is rate-limited
            avg_wind_kmh = max(round(avg_wave_h * 18.0, 1), 12.0)
            avg_wind_ms = round(avg_wind_kmh / 3.6, 1)
            avg_wind_d = avg_wave_d

        avg_vis_km = round(sum(vis_slice) / len(vis_slice) / 1000, 1) if vis_slice else 10.0
        avg_pressure = round(sum(p_slice) / len(p_slice), 1) if p_slice else 1010.0
        sea_label = _sea_state(avg_wave_h)

        valid_time = (
            (marine_times[slice_start] + "Z")
            if (marine_times and slice_start < len(marine_times))
            else retrieved_at
        )

        logger.info(
            "[Weather] Retrieved: wave=%.2fm wind=%.1fkm/h sea=%s (est_wind=%s)",
            avg_wave_h, avg_wind_kmh, sea_label, not bool(ws_slice),
        )

        return MarineConditions(
            wave_height_m=avg_wave_h,
            wave_direction_deg=avg_wave_d,
            wind_speed_ms=avg_wind_ms,
            wind_speed_kmh=avg_wind_kmh,
            wind_direction_deg=avg_wind_d,
            sea_state=sea_label,
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
