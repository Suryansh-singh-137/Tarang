import requests
import logging
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static coastal gazetteer (Tier 1)
# ---------------------------------------------------------------------------
GAZETTEER: Dict[str, Tuple[float, float]] = {
    # Tamil Nadu
    "thoothukudi": (8.7642, 78.1348),
    "tuticorin": (8.7642, 78.1348),
    "thoothukudi coast": (8.7642, 78.1348),
    "rameswaram": (9.2881, 79.3129),
    "nagapattinam": (10.7672, 79.8449),
    "chennai": (13.0827, 80.2707),
    "kanyakumari": (8.0883, 77.5385),
    "cuddalore": (11.7480, 79.7714),
    "pondicherry": (11.9416, 79.8083),
    "mandapam": (9.2667, 79.1167),
    # Kerala
    "thiruvananthapuram": (8.5241, 76.9366),
    # "kochi" removed for testing Tier 2 geocoder fallback
    "kozhikode": (11.2588, 75.7804),
    "alappuzha": (9.4981, 76.3388),
    "kasaragod": (12.4996, 74.9869),
    # Karnataka
    "mangaluru": (12.9141, 74.8560),
    "karwar": (14.8160, 74.1240),
    # Andhra Pradesh
    "visakhapatnam": (17.6868, 83.2185),
    "kakinada": (16.9891, 82.2475),
    # Maharashtra / Goa
    "mumbai": (19.0760, 72.8777),
    "goa": (15.2993, 74.1240),
    "ratnagiri": (16.9944, 73.3000),
    # Odisha
    # "puri" removed for testing Tier 2 geocoder fallback
    "paradip": (20.3164, 86.6111),
    # West Bengal
    "digha": (21.6267, 87.5081),
    "sagar island": (21.6538, 88.0720),
    # Lakshadweep / A&N
    "port blair": (11.6234, 92.7265),
    "kavaratti": (10.5669, 72.6420),
}

# Coastal States / Union Territories in India for validation
COASTAL_STATES_UT = {
    "gujarat", "maharashtra", "goa", "karnataka", "kerala",
    "tamil nadu", "andhra pradesh", "odisha", "west bengal",
    "andaman and nicobar", "lakshadweep", "puducherry",
    "daman and diu", "dadra and nagar haveli"
}

# In-memory cache for Tier 2 geocoder results
_GEOCODE_CACHE: Dict[str, Dict[str, Any]] = {}

def is_coastal(address_details: Dict[str, str]) -> bool:
    """Check if the resolved address is in a coastal state."""
    state = address_details.get("state", "").lower()
    if not state:
        return True # Default to true if Nominatim doesn't return a state but returns result
    
    # Simple substring check (e.g., "Tamil Nadu" in "Tamil Nadu")
    for coastal_state in COASTAL_STATES_UT:
        if coastal_state in state:
            return True
    return False

def resolve_location(query: str) -> Dict[str, Any]:
    """
    Resolve a location name to coordinates using a two-tier system:
    Tier 1: Static Gazetteer
    Tier 2: Nominatim OSM Geocoding API
    
    Returns:
        dict: {
            "location_name": str,
            "latitude": float or None,
            "longitude": float or None,
            "source": "gazetteer" | "geocoder" | "none",
            "status": "success" | "inland" | "unresolved"
        }
    """
    query_lower = query.lower().strip()

    # Tier 1: Gazetteer lookup
    for place, (lat, lon) in GAZETTEER.items():
        if place in query_lower:
            return {
                "location_name": place.title(),
                "latitude": lat,
                "longitude": lon,
                "source": "gazetteer",
                "status": "success"
            }

    # Cache lookup
    if query_lower in _GEOCODE_CACHE:
        logger.info(f"Using cached geocode result for '{query}'")
        return _GEOCODE_CACHE[query_lower]

    # Tier 2: Nominatim Geocoder
    logger.info(f"Location '{query}' not in gazetteer. Querying Nominatim...")
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "in",
        "addressdetails": 1
    }
    headers = {
        "User-Agent": "Tarang-App"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            result = {
                "location_name": query,
                "latitude": None,
                "longitude": None,
                "source": "none",
                "status": "unresolved"
            }
            _GEOCODE_CACHE[query_lower] = result
            return result

        place = data[0]
        
        address = place.get("address", {})
        country_code = address.get("country_code", "").lower()
        
        if country_code != "in":
            result = {
                "location_name": query,
                "latitude": None,
                "longitude": None,
                "source": "none",
                "status": "unresolved"
            }
            return result

        lat = float(place.get("lat"))
        lon = float(place.get("lon"))
        display_name = place.get("name", query.title())
        
        # Coastal relevance check
        if not is_coastal(address):
            result = {
                "location_name": display_name,
                "latitude": lat,
                "longitude": lon,
                "source": "geocoder",
                "status": "inland"
            }
            _GEOCODE_CACHE[query_lower] = result
            return result

        result = {
            "location_name": display_name,
            "latitude": lat,
            "longitude": lon,
            "source": "geocoder",
            "status": "success"
        }
        _GEOCODE_CACHE[query_lower] = result
        return result

    except Exception as e:
        logger.error(f"Geocoding failed for '{query}': {e}")
        return {
            "location_name": query,
            "latitude": None,
            "longitude": None,
            "source": "none",
            "status": "unresolved"
        }
