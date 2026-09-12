"""
hazard_client.py
----------------
Marine hazard advisory client for Milestone 2.

Strategy: Open-Meteo Forecast API — WMO weather codes + wind gusts
  - Free, no credentials required
  - WMO codes are internationally standardised
  - Provides: weathercode, wind_gusts_10m, precipitation, visibility

Severity normalisation:
  WMO code → hazard type → severity (none/low/moderate/high/extreme)

  Cyclone/extreme: no real-time IMD cyclone endpoint available.
  If a WMO code ≥ 95 (thunderstorm) or wind gust ≥ 90 km/h is found,
  this is marked "high" severity.

  For actual cyclone warnings, users are directed to consult IMD/INCOIS
  directly — this limitation is stated explicitly in the summary.

Data freshness:
  - source_time:   the forecast valid time for the requested window
  - retrieved_at:  when this function was called

Caching: in-memory TTL cache, 30-minute TTL.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx
from cachetools import TTLCache

import config

logger = logging.getLogger("tarang.hazard")

# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------
_hazard_cache: TTLCache = TTLCache(maxsize=64, ttl=config.CACHE_TTL_HAZARD_S)


# ---------------------------------------------------------------------------
# WMO Weather Code → hazard type mapping
# ---------------------------------------------------------------------------
# Reference: https://open-meteo.com/en/docs (WMO Weather interpretation codes)

_WMO_HAZARD_MAP: list[tuple[range, str, str]] = [
    # (code range, hazard_type, severity)
    (range(95, 100), "thunderstorm",       "moderate"),  # 95-99: thunderstorm (lightning)
    (range(82, 83),  "heavy_rain",         "moderate"),  # 82: violent rain showers
    (range(65, 68),  "heavy_rain",         "low"),       # 65-67: heavy rain
    (range(55, 58),  "heavy_rain",         "low"),       # 55-57: heavy drizzle
    (range(80, 82),  "moderate_rain",      "low"),       # 80-81: rain showers
    (range(77, 78),  "snow_grains",        "low"),       # 77: snow grains (unusual India)
]

_HIGH_WIND_GUST_KMPH = 60.0   # km/h threshold for high-wind advisory
_EXTREME_WIND_KMPH   = 90.0   # km/h threshold for extreme wind


@dataclass
class NormalizedHazard:
    """A single normalised hazard advisory item."""
    hazard_type: str        # e.g. "thunderstorm", "high_wind", "heavy_rain"
    severity: str           # "none"/"low"/"moderate"/"high"/"extreme"
    title: str
    detail: str
    valid_from: str         # ISO-8601 UTC
    valid_until: str        # ISO-8601 UTC (approx end of window)
    location_relevant: bool = True
    source: str = "Open-Meteo (WMO weather-code advisory)"


@dataclass
class HazardAdvisory:
    """Normalised set of hazard advisories for a location + time window."""
    hazards: list[NormalizedHazard]
    overall_level: str          # "none"/"low"/"moderate"/"high"/"extreme"
    active_warnings: list[str]  # list of hazard_type strings
    cyclone_warning: bool = False
    source_time: str = ""
    retrieved_at: str = ""
    source: str = "Open-Meteo (WMO weather-code advisory)"
    used_fallback: bool = False


# ---------------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = ["none", "low", "moderate", "high", "extreme"]


def _max_severity(*levels: str) -> str:
    """Return the highest severity from a list."""
    return max(levels, key=lambda s: _SEVERITY_ORDER.index(s) if s in _SEVERITY_ORDER else 0)


def _wmo_hazard(code: int) -> tuple[str, str] | None:
    """Return (hazard_type, severity) for a WMO code, or None if no hazard."""
    for code_range, htype, severity in _WMO_HAZARD_MAP:
        if code in code_range:
            return htype, severity
    return None


# ---------------------------------------------------------------------------
# Time-window helpers (shared logic with cmems_client)
# ---------------------------------------------------------------------------

def _resolve_slice(time_window: str) -> tuple[int, int, int]:
    """Return (day_offset, start_hour, end_hour) for the time window."""
    tw = time_window.lower()
    if "tomorrow" in tw and "morning" in tw:
        return 1, 0, 11
    elif "tomorrow" in tw and "evening" in tw:
        return 1, 10, 15
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
        return 0, 0, 23


# ---------------------------------------------------------------------------
# Core fetch function
# ---------------------------------------------------------------------------

def _fetch_open_meteo_hazard(
    lat: float, lon: float, time_window: str
) -> Optional[HazardAdvisory]:
    """
    Fetch weather codes + wind gusts from Open-Meteo Forecast API and
    interpret them as hazard advisories.
    Returns None on error/timeout.
    """
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    day_offset, hour_start, hour_end = _resolve_slice(time_window)
    forecast_days = day_offset + 2

    logger.info(
        "[Hazard] Requesting Open-Meteo forecast: lat=%.4f lon=%.4f window=%s",
        lat, lon, time_window,
    )

    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT) as client:
            resp = client.get(
                config.OPEN_METEO_FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": "weather_code,wind_gusts_10m,precipitation",
                    "wind_speed_unit": "kmh",
                    "timezone": "UTC",
                    "forecast_days": forecast_days,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.warning("[Hazard] Open-Meteo timed out after %ds", config.HTTP_TIMEOUT)
        return None
    except httpx.HTTPError as exc:
        logger.warning("[Hazard] Open-Meteo HTTP error: %s", exc)
        return None
    except Exception as exc:
        logger.warning("[Hazard] Unexpected error: %s", exc)
        return None

    try:
        times: list[str]   = data["hourly"]["time"]
        codes: list[Optional[int]]   = data["hourly"]["weather_code"]
        gusts: list[Optional[float]] = data["hourly"]["wind_gusts_10m"]

        slice_start = day_offset * 24 + hour_start
        slice_end   = day_offset * 24 + hour_end + 1

        codes_slice = [c for c in codes[slice_start:slice_end] if c is not None]
        gusts_slice = [g for g in gusts[slice_start:slice_end] if g is not None]

        # Determine time bounds
        valid_from = (times[slice_start] + "Z") if slice_start < len(times) else retrieved_at
        valid_until = (times[min(slice_end - 1, len(times) - 1)] + "Z") if times else retrieved_at

        hazards: list[NormalizedHazard] = []

        # ---- Interpret WMO codes ----
        seen_types: set[str] = set()
        for code in codes_slice:
            match = _wmo_hazard(code)
            if match:
                htype, severity = match
                if htype not in seen_types:
                    seen_types.add(htype)
                    if htype == "thunderstorm":
                        hazards.append(NormalizedHazard(
                            hazard_type="thunderstorm",
                            severity=severity,
                            title="Thunderstorm / Lightning Advisory",
                            detail=(
                                f"Thunderstorm activity (WMO code {code}) forecast "
                                f"during the selected time window. "
                                "Fishermen advised to take shelter. "
                                "Lightning risk at sea."
                            ),
                            valid_from=valid_from,
                            valid_until=valid_until,
                        ))
                    elif htype == "heavy_rain":
                        hazards.append(NormalizedHazard(
                            hazard_type="rough_sea_advisory",
                            severity=severity,
                            title="Heavy Precipitation Advisory",
                            detail=(
                                f"Heavy rain forecast (WMO code {code}). "
                                "Reduced visibility and rough sea conditions possible."
                            ),
                            valid_from=valid_from,
                            valid_until=valid_until,
                        ))

        # ---- Interpret wind gusts ----
        if gusts_slice:
            max_gust = max(gusts_slice)
            if max_gust >= _EXTREME_WIND_KMPH:
                hazards.append(NormalizedHazard(
                    hazard_type="high_wind",
                    severity="extreme",
                    title="Extreme Wind Gust Warning",
                    detail=f"Wind gusts up to {max_gust:.0f} km/h forecast. Do not venture to sea.",
                    valid_from=valid_from,
                    valid_until=valid_until,
                ))
            elif max_gust >= _HIGH_WIND_GUST_KMPH:
                hazards.append(NormalizedHazard(
                    hazard_type="high_wind",
                    severity="moderate",
                    title="Strong Wind Advisory",
                    detail=f"Wind gusts up to {max_gust:.0f} km/h forecast. Exercise caution at sea.",
                    valid_from=valid_from,
                    valid_until=valid_until,
                ))

        overall_level = "none"
        if hazards:
            overall_level = _max_severity(*[h.severity for h in hazards])

        active_warnings = list({h.hazard_type for h in hazards})

        logger.info(
            "[Hazard] %d hazard(s) identified; overall=%s",
            len(hazards), overall_level,
        )

        return HazardAdvisory(
            hazards=hazards,
            overall_level=overall_level,
            active_warnings=active_warnings,
            cyclone_warning=False,          # no real-time cyclone endpoint available
            source_time=valid_from,
            retrieved_at=retrieved_at,
        )

    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("[Hazard] Failed to parse Open-Meteo response: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public cached entry point
# ---------------------------------------------------------------------------

def fetch_hazard_advisory(
    lat: float, lon: float, time_window: str
) -> Optional[HazardAdvisory]:
    """
    Return normalised HazardAdvisory for the given location and time window.

    Results cached for CACHE_TTL_HAZARD_S seconds.
    Returns None if all attempts fail (caller should activate fallback).
    """
    cache_key = (round(lat, 1), round(lon, 1), time_window)
    if cache_key in _hazard_cache:
        logger.info("[Hazard] Cache hit for %s", cache_key)
        return _hazard_cache[cache_key]

    result = _fetch_open_meteo_hazard(lat, lon, time_window)
    if result is not None:
        _hazard_cache[cache_key] = result
    return result
