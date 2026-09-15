"""
location.service
----------------
Universal Dynamic Location & Marine Context Service for Tarang.

Fulfills PRD Goals:
- 3-tier geocoding: Local Gazetteer -> OpenWeather Geocoding API -> Nominatim OSM fallback.
- Offshore coordinate support (e.g. 13.02° N, 80.42° E) without requiring city name.
- Intelligent Marine Context classification: INLAND, COASTAL, OFFSHORE, UNKNOWN.
- Feature availability flags for Weather, Tides, Fishing Potential, Hazards, Trip Planning.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

import config
from tools.location_resolver import (
    GAZETTEER,
    _HARDCODED,
    COASTAL_STATES_UT,
    COASTAL_DISTRICTS,
    distance_to_nearest_coast_km,
    haversine_km,
    _nominatim_rate_limit,
)
from graph.nodes.ocean_agent import _PORT_TIDAL_BASELINES

logger = logging.getLogger("tarang.location.service")


def find_nearest_port(lat: float, lon: float) -> Tuple[str, float]:
    """Find nearest tidal port / harbour name and distance in km."""
    best_name = "Kochi"
    min_d = float("inf")
    for name, p_lat, p_lon, *_ in _PORT_TIDAL_BASELINES:
        d = haversine_km(lat, lon, p_lat, p_lon)
        if d < min_d:
            min_d = d
            best_name = name
    return best_name, min_d


def is_offshore_marine_point(lat: float, lon: float) -> bool:
    """
    Determine if a coordinate represents an offshore marine water point
    within the Indian Ocean, Arabian Sea, Bay of Bengal, or Andaman Sea.
    """
    # Indian marine EEZ bounding envelope approx: Lat 4.5°N - 24.5°N, Lon 64.0°E - 96.0°E
    if not (4.5 <= lat <= 24.5 and 64.0 <= lon <= 96.0):
        return False

    dist = distance_to_nearest_coast_km(lat, lon)

    # 1. South of Indian peninsula (Indian Ocean / Laccadive Sea)
    if lat < 8.1 and 68.0 <= lon <= 88.0:
        return True

    # 2. Bay of Bengal (East coast offshore waters):
    # - Tamil Nadu south & Palk Bay: Lat 8.1 - 10.5, Lon > 79.5
    if 8.1 <= lat <= 10.5 and lon >= 79.5 and dist > 2.0:
        return True
    # - Coromandel Coast (Chennai, Pondicherry): Lat 10.5 - 14.0, Lon >= 80.30
    if 10.5 < lat <= 14.0 and lon >= 80.30 and dist > 2.0:
        return True
    # - Andhra Pradesh / Godavari delta: Lat 14.0 - 17.5, Lon >= 80.35
    if 14.0 < lat <= 17.5 and lon >= 80.35 and dist > 2.0:
        return True
    # - North Andhra / Odisha / Bengal: Lat 17.5 - 22.0, Lon >= 83.4
    if 17.5 < lat <= 22.0 and lon >= 83.4 and dist > 2.0:
        return True
    # - Deep Bay of Bengal
    if lon > 85.0 and 8.0 <= lat <= 22.0:
        return True

    # 3. Arabian Sea (West coast offshore waters):
    # - Kerala coast: Lat 8.0 - 11.5, Lon <= 76.0
    if 8.0 <= lat <= 11.5 and lon <= 76.0 and dist > 2.0:
        return True
    # - Karnataka / Goa: Lat 11.5 - 15.5, Lon <= 74.5
    if 11.5 < lat <= 15.5 and lon <= 74.5 and dist > 2.0:
        return True
    # - Konkan / Mumbai: Lat 15.5 - 20.0, Lon <= 72.85
    if 15.5 < lat <= 20.0 and lon <= 72.85 and dist > 2.0:
        return True
    # - Gujarat / Kathiawar: Lat 20.0 - 23.5, Lon <= 70.0
    if 20.0 < lat <= 23.5 and lon <= 70.0 and dist > 2.0:
        return True
    # - Deep Arabian Sea
    if lon < 71.0 and 8.0 <= lat <= 22.0:
        return True

    # 4. Andaman & Nicobar Sea
    if lon >= 92.0 and 6.0 <= lat <= 14.5 and dist > 2.0:
        return True

    return False


def determine_marine_context(lat: float, lon: float, name: Optional[str] = None) -> Dict[str, Any]:
    """
    Determine marine context per PRD §11 & §12:
    - type: "inland" | "coastal" | "offshore" | "unknown"
    - isCoastal: bool
    - nearestPort: str
    - distanceToCoastKm: float
    - tideAvailable: bool
    - fishingDataAvailable: bool
    """
    dist_to_coast = distance_to_nearest_coast_km(lat, lon)
    nearest_port_name, _ = find_nearest_port(lat, lon)

    # 1. Check Offshore Marine Waters
    if is_offshore_marine_point(lat, lon):
        return {
            "type": "offshore",
            "is_coastal": False,
            "nearest_port": nearest_port_name,
            "distance_to_coast_km": round(dist_to_coast, 1),
            "tide_available": True,
            "fishing_data_available": True,
        }

    # 2. Check Inland Coordinate Envelope
    # Extreme north/central/inland of India (lat > 24.5 or dist > 50km)
    if lat > 24.5 or dist_to_coast > 50.0:
        return {
            "type": "inland",
            "is_coastal": False,
            "nearest_port": nearest_port_name,
            "distance_to_coast_km": round(dist_to_coast, 1),
            "tide_available": False,
            "fishing_data_available": False,
        }

    # 3. Intermediate check for coastal state / district proximity
    if dist_to_coast <= 35.0:
        return {
            "type": "coastal",
            "is_coastal": True,
            "nearest_port": nearest_port_name,
            "distance_to_coast_km": round(dist_to_coast, 1),
            "tide_available": True,
            "fishing_data_available": True,
        }

    # Default fallback if distance is between 35 and 50 km
    return {
        "type": "inland",
        "is_coastal": False,
        "nearest_port": nearest_port_name,
        "distance_to_coast_km": round(dist_to_coast, 1),
        "tide_available": False,
        "fishing_data_available": False,
    }


def search_locations(query: str, limit: int = 6) -> List[Dict[str, Any]]:
    """
    Multi-tier location search:
    Tier 1: Local Gazetteer exact/partial match.
    Tier 2: OpenWeather Geocoding API if key configured.
    Tier 3: Nominatim OSM search fallback.
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    results: List[Dict[str, Any]] = []
    seen_names: set[str] = set()

    # Tier 1: Local Gazetteer matches
    for place_key, (plat, plon) in GAZETTEER.items():
        if q == place_key or place_key.startswith(q) or q in place_key:
            display_title = place_key.title()
            if display_title not in seen_names:
                seen_names.add(display_title)
                results.append({
                    "name": display_title,
                    "display_name": f"{display_title}, India",
                    "lat": plat,
                    "lon": plon,
                    "state": "Coastal Region",
                    "country": "India",
                })
        if len(results) >= limit:
            return results

    # Tier 2: OpenWeather Geocoding API (PRD §8)
    if config.OPENWEATHER_API_KEY:
        try:
            url = f"{config.OPENWEATHER_GEO_URL}/direct"
            params = {
                "q": f"{query},IN",
                "limit": limit,
                "appid": config.OPENWEATHER_API_KEY,
            }
            with httpx.Client(timeout=4.0) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    ow_data = resp.json()
                    for item in ow_data:
                        name = item.get("name", "").strip()
                        state = item.get("state", "")
                        lat = float(item["lat"])
                        lon = float(item["lon"])
                        d_name = f"{name}, {state}, India" if state else f"{name}, India"
                        if name.lower() not in seen_names:
                            seen_names.add(name.lower())
                            results.append({
                                "name": name,
                                "display_name": d_name,
                                "lat": lat,
                                "lon": lon,
                                "state": state,
                                "country": item.get("country", "India"),
                            })
                        if len(results) >= limit:
                            return results
        except Exception as exc:
            logger.warning("[LocationService] OpenWeather Geocoding error: %s", exc)

    # Tier 3: Nominatim OSM search fallback
    _nominatim_rate_limit()
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": limit,
            "countrycodes": "in",
            "addressdetails": 1,
        }
        headers = {"User-Agent": "Tarang-MarineLocationService/2.0 (contact@tarang.app)"}
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                osm_data = resp.json()
                for item in osm_data:
                    name = item.get("name") or item.get("display_name", "").split(",")[0].strip()
                    lat = float(item["lat"])
                    lon = float(item["lon"])
                    addr = item.get("address", {})
                    state = addr.get("state") or addr.get("state_district") or ""
                    d_name = item.get("display_name", "")
                    # Clean up long display name: take first 3 segments
                    parts = [p.strip() for p in d_name.split(",") if p.strip()]
                    short_dname = ", ".join(parts[:3]) if len(parts) >= 3 else d_name

                    if name.lower() not in seen_names:
                        seen_names.add(name.lower())
                        results.append({
                            "name": name,
                            "display_name": short_dname,
                            "lat": lat,
                            "lon": lon,
                            "state": state,
                            "country": addr.get("country", "India"),
                        })
                    if len(results) >= limit:
                        return results
    except Exception as exc:
        logger.warning("[LocationService] Nominatim search error: %s", exc)

    return results


_SERVICE_REVERSE_CACHE: Dict[Tuple[float, float], Dict[str, Any]] = {}


def reverse_geocode(lat: float, lon: float) -> Dict[str, Any]:
    """
    Reverse geocode coordinates into a standardized location name and display name.
    Recognizes offshore marine coordinates (PRD §10).
    """
    cache_key = (round(lat, 3), round(lon, 3))
    if cache_key in _SERVICE_REVERSE_CACHE:
        return _SERVICE_REVERSE_CACHE[cache_key]

    # 1. Proximity check against local Gazetteer (< 4 km)
    for p_name, (plat, plon) in GAZETTEER.items():
        if haversine_km(lat, lon, plat, plon) < 4.0:
            res = {
                "name": p_name.title(),
                "display_name": f"{p_name.title()}, India",
                "lat": lat,
                "lon": lon,
                "state": "Coastal Region",
                "country": "India",
            }
            _SERVICE_REVERSE_CACHE[cache_key] = res
            return res

    # 2. Check if this is an offshore marine water coordinate
    if is_offshore_marine_point(lat, lon):
        coord_name = f"{lat:.2f}°N, {lon:.2f}°E"
        res = {
            "name": coord_name,
            "display_name": f"{coord_name} (Marine Location)",
            "lat": lat,
            "lon": lon,
            "state": "Offshore Waters",
            "country": "India",
        }
        _SERVICE_REVERSE_CACHE[cache_key] = res
        return res

    # 3. OpenWeather Reverse Geocoding API if key configured
    if config.OPENWEATHER_API_KEY:
        try:
            url = f"{config.OPENWEATHER_GEO_URL}/reverse"
            params = {
                "lat": lat,
                "lon": lon,
                "limit": 1,
                "appid": config.OPENWEATHER_API_KEY,
            }
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        item = data[0]
                        name = item.get("name", "").strip() or f"{lat:.2f}°N, {lon:.2f}°E"
                        state = item.get("state", "")
                        d_name = f"{name}, {state}, India" if state else f"{name}, India"
                        res = {
                            "name": name,
                            "display_name": d_name,
                            "lat": lat,
                            "lon": lon,
                            "state": state,
                            "country": item.get("country", "India"),
                        }
                        _SERVICE_REVERSE_CACHE[cache_key] = res
                        return res
        except Exception as exc:
            logger.warning("[LocationService] OpenWeather reverse geocode error: %s", exc)

    # 4. Nominatim OSM reverse geocode fallback (short timeout to prevent blocking)
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1,
        }
        headers = {"User-Agent": "Tarang-MarineLocationService/2.0 (contact@tarang.app)"}
        with httpx.Client(timeout=1.5) as client:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                addr = data.get("address", {})
                name = (
                    data.get("name")
                    or addr.get("city")
                    or addr.get("town")
                    or addr.get("village")
                    or addr.get("suburb")
                    or addr.get("county")
                    or f"{lat:.2f}°N, {lon:.2f}°E"
                )
                state = addr.get("state", "")
                country = addr.get("country", "India")
                d_name = f"{name}, {state}, {country}" if state else f"{name}, {country}"
                res = {
                    "name": name,
                    "display_name": d_name,
                    "lat": lat,
                    "lon": lon,
                    "state": state,
                    "country": country,
                }
                _SERVICE_REVERSE_CACHE[cache_key] = res
                return res
    except Exception as exc:
        logger.warning("[LocationService] Nominatim reverse geocode error: %s", exc)

    # Fallback to coordinate string
    coord_name = f"{lat:.2f}°N, {lon:.2f}°E"
    res = {
        "name": coord_name,
        "display_name": coord_name,
        "lat": lat,
        "lon": lon,
        "state": "",
        "country": "India",
    }
    _SERVICE_REVERSE_CACHE[cache_key] = res
    return res


def resolve_canonical_location(
    lat: float,
    lon: float,
    name: Optional[str] = None,
    source: str = "search"
) -> Dict[str, Any]:
    """
    Assemble the complete SelectedLocation + MarineContext object per PRD §11 & §12.
    """
    # If name is provided and already specific, keep it; otherwise reverse-geocode
    if name and not name.startswith("Location (") and not re.match(r"^\d+\.\d+°", name):
        loc_info = {
            "name": name,
            "display_name": f"{name}, India",
            "lat": lat,
            "lon": lon,
            "state": "",
            "country": "India",
        }
    else:
        loc_info = reverse_geocode(lat, lon)

    marine_ctx = determine_marine_context(lat, lon, name=loc_info["name"])

    return {
        "location": {
            "name": loc_info["name"],
            "display_name": loc_info.get("display_name") or loc_info["name"],
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "state": loc_info.get("state"),
            "country": loc_info.get("country", "India"),
            "source": source,
        },
        "marine_context": marine_ctx,
    }
