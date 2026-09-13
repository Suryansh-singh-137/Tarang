"""
gdacs_client.py
---------------
GDACS (Global Disaster Alert and Coordination System) cyclone intelligence
client for Tarang M8.

Source: https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH
        (Confirmed working — returns GeoJSON FeatureCollection)

Role in the hazard hierarchy:
  TIER 2 (secondary situational awareness)

  IMD official warnings   [TIER 1 — authoritative for India]
         ↓
  GDACS cyclone events    [TIER 2 — global awareness]
         ↓
  Open-Meteo WMO codes    [TIER 3 — operational forecast proxy]
         ↓
  Fallback JSON           [TIER 5]

GDACS data NEVER overrides an official IMD warning.
GDACS provides cyclone situational awareness: name, position, wind speed,
alert level. Spatial relevance is computed here — only cyclones within
config.GDACS_SEARCH_RADIUS_KM of the query point are returned as hazards.
Distant cyclones (even if active) are NOT flagged to the user unless they
are within the relevance radius.

Caching: in-memory 10-minute TTL.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from cachetools import TTLCache

import config

logger = logging.getLogger("tarang.gdacs")

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_gdacs_cache: TTLCache = TTLCache(maxsize=32, ttl=config.CACHE_TTL_GDACS_S)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class GDACSTCEvent:
    """A single GDACS tropical cyclone event, spatially filtered."""
    event_id:       int
    name:           str             # e.g. "NORBERT-26"
    lat:            float           # current cyclone centroid latitude
    lon:            float           # current cyclone centroid longitude
    wind_speed_kmh: float           # from severitydata.severity
    alert_level:    str             # "Green" | "Orange" | "Red"
    from_date:      str             # ISO-8601 start of event
    to_date:        str             # ISO-8601 end / last update
    distance_km:    float           # distance from query point to cyclone centroid
    geometry_url:   Optional[str]   # URL to fetch detailed geometry polygon
    source:         str = "GDACS (UN global disaster alert)"


@dataclass
class GDACSTCResult:
    """Aggregated GDACS cyclone query result."""
    events:          list[GDACSTCEvent]
    query_lat:       float
    query_lon:       float
    search_radius_km: float
    retrieved_at:    str
    source:          str = "GDACS (UN global disaster alert)"
    used_fallback:   bool = False


# ---------------------------------------------------------------------------
# Haversine helper
# ---------------------------------------------------------------------------
_R = 6371.0

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Core fetch
# ---------------------------------------------------------------------------

def _fetch_gdacs_cyclones(
    query_lat: float,
    query_lon: float,
    radius_km: float,
    alert_levels: str = "Orange,Red",
) -> Optional[GDACSTCResult]:
    """
    Query GDACS for active tropical cyclones (TC) and filter by proximity.

    Args:
        query_lat:    User's query latitude
        query_lon:    User's query longitude
        radius_km:    Maximum distance (km) to consider a cyclone relevant
        alert_levels: Comma-separated GDACS alert levels to query

    Returns:
        GDACSTCResult with only spatially relevant events, or None on error.
    """
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Look back 14 days to catch slow-moving systems
    from_date_str = (
        datetime.now(timezone.utc).replace(
            day=max(1, datetime.now(timezone.utc).day - 14)
        ).strftime("%Y-%m-%d")
    )

    logger.info(
        "[GDACS] Querying cyclones for lat=%.4f lon=%.4f radius=%.0fkm alertlevels=%s",
        query_lat, query_lon, radius_km, alert_levels,
    )

    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT) as client:
            resp = client.get(
                config.GDACS_BASE_URL,
                params={
                    "eventtype":   "TC",
                    "fromDate":    from_date_str,
                    "toDate":      today,
                    "alertlevel":  alert_levels,
                },
                headers={"User-Agent": "Tarang-MarineSafetyApp/1.0"},
            )
            resp.raise_for_status()
            geojson = resp.json()
    except httpx.TimeoutException:
        logger.warning("[GDACS] Request timed out after %ds", config.HTTP_TIMEOUT)
        return None
    except httpx.HTTPError as exc:
        logger.warning("[GDACS] HTTP error: %s", exc)
        return None
    except Exception as exc:
        logger.warning("[GDACS] Unexpected error: %s", exc)
        return None

    features = geojson.get("features", [])
    if not features:
        logger.info("[GDACS] No TC events returned for date range")
        return GDACSTCResult(
            events=[], query_lat=query_lat, query_lon=query_lon,
            search_radius_km=radius_km, retrieved_at=retrieved_at,
        )

    relevant_events: list[GDACSTCEvent] = []

    for feat in features:
        props = feat.get("properties", {})
        geom  = feat.get("geometry", {})

        # Filter to TC only (API may return mixed types)
        if props.get("eventtype") != "TC":
            continue

        coords = geom.get("coordinates", [])
        if not coords or len(coords) < 2:
            continue

        tc_lon, tc_lat = float(coords[0]), float(coords[1])
        distance = _haversine(query_lat, query_lon, tc_lat, tc_lon)

        if distance > radius_km:
            logger.debug(
                "[GDACS] TC '%s' at %.0f km — outside radius (%.0f km), skipping",
                props.get("eventname", "unknown"), distance, radius_km,
            )
            continue

        severity = props.get("severitydata", {})
        wind_speed = float(severity.get("severity", 0.0))

        event = GDACSTCEvent(
            event_id=props.get("eventid", 0),
            name=props.get("eventname") or props.get("name", "Unknown TC"),
            lat=tc_lat,
            lon=tc_lon,
            wind_speed_kmh=wind_speed,
            alert_level=props.get("alertlevel", "Unknown"),
            from_date=props.get("fromdate", ""),
            to_date=props.get("todate", ""),
            distance_km=round(distance, 1),
            geometry_url=props.get("url", {}).get("geometry"),
        )
        relevant_events.append(event)
        logger.info(
            "[GDACS] TC '%s' RELEVANT: %.0f km away, wind=%.0f km/h, alert=%s",
            event.name, distance, wind_speed, event.alert_level,
        )

    logger.info(
        "[GDACS] %d/%d TC events within %.0f km of query",
        len(relevant_events), len([f for f in features if f.get("properties", {}).get("eventtype") == "TC"]),
        radius_km,
    )

    return GDACSTCResult(
        events=relevant_events,
        query_lat=query_lat,
        query_lon=query_lon,
        search_radius_km=radius_km,
        retrieved_at=retrieved_at,
    )


# ---------------------------------------------------------------------------
# Public cached entry point
# ---------------------------------------------------------------------------

def fetch_active_cyclones(
    query_lat:  float,
    query_lon:  float,
    radius_km:  Optional[float] = None,
) -> Optional[GDACSTCResult]:
    """
    Return active tropical cyclones within radius_km of the query point.

    Results cached for CACHE_TTL_GDACS_S seconds (10 min).

    Args:
        query_lat: Latitude of the user's query location
        query_lon: Longitude of the user's query location
        radius_km: Search radius in km (default: config.GDACS_SEARCH_RADIUS_KM)

    Returns:
        GDACSTCResult with spatially relevant events, or None on error.
    """
    if radius_km is None:
        radius_km = config.GDACS_SEARCH_RADIUS_KM

    cache_key = (round(query_lat, 1), round(query_lon, 1), round(radius_km, -1))
    if cache_key in _gdacs_cache:
        logger.info("[GDACS] Cache hit for %s", cache_key)
        return _gdacs_cache[cache_key]

    result = _fetch_gdacs_cyclones(
        query_lat, query_lon, radius_km,
        alert_levels=config.GDACS_ALERT_LEVELS,
    )

    if result is not None:
        _gdacs_cache[cache_key] = result

    return result
