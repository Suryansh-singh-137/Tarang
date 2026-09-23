"""
wind_grid.py
------------
Fetch a spatial grid of wind vectors (speed + direction) for a given bounding box.

Uses the Open-Meteo Forecast API (free, reliable, no key needed).
Built for Tarang Marine Decision Support for Indian Coastal Fishermen.

Endpoint called:
  GET https://api.open-meteo.com/v1/forecast
  params: latitude, longitude, hourly=wind_speed_10m,wind_direction_10m,
          wind_speed_unit=kmh, forecast_days=1, timezone=UTC
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("tarang.wind_grid")

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_HEADERS = {"User-Agent": "TarangMarineAdvisor/1.0 (Indian Coastal Fishermen Safety)"}
_TIMEOUT_S = 8.0

# In-memory cache with 5-minute TTL to avoid redundant requests and rate limits
_CACHE: Dict[Tuple[float, float, float, float, int], Tuple[float, List[Dict[str, Any]]]] = {}
_CACHE_TTL = 300.0  # 5 minutes


def _normalize_bounds(
    lat_min: float, lat_max: float, lon_min: float, lon_max: float
) -> Tuple[float, float, float, float]:
    """Ensure coordinates are within valid geographic bounds and ordered."""
    if lat_min > lat_max:
        lat_min, lat_max = lat_max, lat_min
    if lon_min > lon_max:
        lon_min, lon_max = lon_max, lon_min

    lat_min = max(-85.0, min(85.0, lat_min))
    lat_max = max(-85.0, min(85.0, lat_max))
    lon_min = max(-180.0, min(180.0, lon_min))
    lon_max = max(-180.0, min(180.0, lon_max))

    # If bounds collapsed, add small buffer
    if abs(lat_max - lat_min) < 0.05:
        lat_min = max(-85.0, lat_min - 0.25)
        lat_max = min(85.0, lat_max + 0.25)
    if abs(lon_max - lon_min) < 0.05:
        lon_min = max(-180.0, lon_min - 0.25)
        lon_max = min(180.0, lon_max + 0.25)

    return (
        round(lat_min, 4),
        round(lat_max, 4),
        round(lon_min, 4),
        round(lon_max, 4),
    )


def _build_grid(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    grid_n: int,
) -> List[Tuple[float, float]]:
    """Return a flat list of (lat, lon) sample points on a grid_n x grid_n mesh."""
    grid_n = max(2, min(grid_n, 6))

    lat_step = (lat_max - lat_min) / (grid_n - 1) if grid_n > 1 else 0
    lon_step = (lon_max - lon_min) / (grid_n - 1) if grid_n > 1 else 0

    points: List[Tuple[float, float]] = []
    for i in range(grid_n):
        for j in range(grid_n):
            lat = round(lat_min + i * lat_step, 4)
            lon = round(lon_min + j * lon_step, 4)
            points.append((lat, lon))
    return points


def _average_circular(angles: List[float]) -> float:
    """Circular mean for direction values (handles 0/360 wrap correctly)."""
    if not angles:
        return 0.0
    sin_sum = sum(math.sin(math.radians(a)) for a in angles)
    cos_sum = sum(math.cos(math.radians(a)) for a in angles)
    return round((math.degrees(math.atan2(sin_sum, cos_sum)) + 360) % 360, 1)


async def _fetch_single_point(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
) -> Optional[Dict[str, Any]]:
    """Fetch wind data for one lat/lon point. Returns None on any error."""
    try:
        resp = await client.get(
            OPEN_METEO_FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "wind_speed_10m,wind_direction_10m",
                "wind_speed_unit": "kmh",
                "timezone": "UTC",
                "forecast_days": 1,
            },
            timeout=_TIMEOUT_S,
            headers=_HEADERS,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        hourly = data.get("hourly", {})
        speeds: List[float] = [v for v in (hourly.get("wind_speed_10m") or [])[:6] if v is not None]
        directions: List[float] = [v for v in (hourly.get("wind_direction_10m") or [])[:6] if v is not None]

        if not speeds:
            return None

        avg_speed = round(sum(speeds) / len(speeds), 1)
        avg_dir = _average_circular(directions) if directions else 0.0

        return {
            "lat": lat,
            "lon": lon,
            "speed_kmh": avg_speed,
            "direction_deg": avg_dir,
        }
    except Exception as exc:
        logger.debug("[WindGrid] Error fetching (%.3f, %.3f): %s", lat, lon, exc)
        return None


async def fetch_grid_async(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    grid_n: int = 4,
) -> List[Dict[str, Any]]:
    """Async: fetch all grid points concurrently with caching and bounds safety."""
    lat_min, lat_max, lon_min, lon_max = _normalize_bounds(lat_min, lat_max, lon_min, lon_max)
    grid_n = max(2, min(grid_n, 6))

    cache_key = (
        round(lat_min, 1),
        round(lat_max, 1),
        round(lon_min, 1),
        round(lon_max, 1),
        grid_n,
    )
    now = time.time()
    if cache_key in _CACHE:
        cached_time, cached_data = _CACHE[cache_key]
        if (now - cached_time) < _CACHE_TTL and cached_data:
            return cached_data

    points = _build_grid(lat_min, lat_max, lon_min, lon_max, grid_n)
    logger.info(
        "[WindGrid] Fetching %d points for bbox (%.2f-%.2f, %.2f-%.2f)",
        len(points), lat_min, lat_max, lon_min, lon_max,
    )

    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [_fetch_single_point(client, lat, lon) for lat, lon in points]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    clean_results: List[Dict[str, Any]] = []
    for r in results:
        if isinstance(r, dict) and "speed_kmh" in r:
            clean_results.append(r)

    if clean_results:
        _CACHE[cache_key] = (now, clean_results)

    return clean_results


def fetch_wind_grid(
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    grid_n: int = 4,
) -> List[Dict[str, Any]]:
    """Synchronous fallback wrapper."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    asyncio.run,
                    fetch_grid_async(lat_min, lat_max, lon_min, lon_max, grid_n),
                )
                return future.result(timeout=_TIMEOUT_S + 6)
        else:
            return loop.run_until_complete(fetch_grid_async(lat_min, lat_max, lon_min, lon_max, grid_n))
    except Exception as exc:
        logger.warning("[WindGrid] Fallback sync fetch failed: %s", exc)
        return []
