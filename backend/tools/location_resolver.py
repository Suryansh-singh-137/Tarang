"""
location_resolver.py
--------------------
Two-tier location resolution for Tarang M8.

Tier 1: In-memory gazetteer (~70 major Indian coastal places, ports, harbours, islands).
         Bootstrapped from data/coastal_places.json on first import.
Tier 2: Nominatim OpenStreetMap geocoder (India-only, rate-limited, cached).

Resolution result includes:
  - location_name, latitude, longitude
  - source:     "gazetteer" | "geocoder" | "none"
  - status:     "success" | "inland" | "unresolved"
  - location_confidence: "high" | "medium" | "low"
  - location_source: same as source (alias for clarity)

The LLM MUST NOT invent coordinates. All coordinates come from this module.
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx
from cachetools import TTLCache

logger = logging.getLogger("tarang.location")

# ---------------------------------------------------------------------------
# Coastal States / Union Territories (for coastal validation)
# ---------------------------------------------------------------------------
COASTAL_STATES_UT: set[str] = {
    "gujarat", "maharashtra", "goa", "karnataka", "kerala",
    "tamil nadu", "andhra pradesh", "odisha", "west bengal",
    "andaman and nicobar", "andaman & nicobar", "lakshadweep",
    "puducherry", "pondicherry",
    "daman and diu", "dadra and nagar haveli and daman and diu",
    "dadra and nagar haveli", "dadra & nagar haveli",
}

# ---------------------------------------------------------------------------
# Gazetteer — populated from coastal_places.json + hardcoded essentials
# ---------------------------------------------------------------------------
# Format: {lowercase_name: (lat, lon)}
GAZETTEER: Dict[str, Tuple[float, float]] = {}

_PLACES_FILE = Path(__file__).parent.parent / "data" / "coastal_places.json"

# Hardcoded essentials (always available even if JSON file is missing)
_HARDCODED: Dict[str, Tuple[float, float]] = {
    "thoothukudi":       (8.7642, 78.1348),
    "tuticorin":         (8.7642, 78.1348),
    "chennai":           (13.0827, 80.2707),
    "mumbai":            (18.9388, 72.8354),
    "kochi":             (9.9312, 76.2673),
    "cochin":            (9.9312, 76.2673),
    "kolkata":           (22.5726, 88.3639),
    "visakhapatnam":     (17.6868, 83.2185),
    "vizag":             (17.6868, 83.2185),
    "mangaluru":         (12.8706, 74.8422),
    "mangalore":         (12.8706, 74.8422),
    "goa":               (15.4909, 73.8278),
    "port blair":        (11.6234, 92.7265),
    "kavaratti":         (10.5669, 72.6420),
    "thiruvananthapuram": (8.5241, 76.9366),
    "trivandrum":        (8.5241, 76.9366),
    "kozhikode":         (11.2588, 75.7804),
    "calicut":           (11.2588, 75.7804),
    "alappuzha":         (9.4981, 76.3388),
    "alleppey":          (9.4981, 76.3388),
    "kollam":            (8.8932, 76.6141),
    "kannur":            (11.8745, 75.3704),
    "puri":              (19.8135, 85.8312),
    "paradip":           (20.3200, 86.6108),
    "paradeep":          (20.3200, 86.6108),
    "karwar":            (14.8136, 74.1302),
    "diu":               (20.7141, 70.9889),
    "porbandar":         (21.6417, 69.6293),
    "rameswaram":        (9.2881, 79.3129),
    "rameshwaram":       (9.2881, 79.3129),
    "mandapam":          (9.2758, 79.1263),
    "nagapattinam":      (10.7672, 79.8449),
    "cuddalore":         (11.7480, 79.7714),
    "pondicherry":       (11.9416, 79.8083),
    "puducherry":        (11.9416, 79.8083),
    "kakinada":          (16.9891, 82.2475),
    "digha":             (21.6281, 87.5081),
    "sagar island":      (21.6500, 88.0800),
    "haldia":            (22.0667, 88.0786),
    "krishnapatnam":     (14.2500, 80.1167),
    "ennore":            (13.2140, 80.3244),
    "kanyakumari":       (8.0883, 77.5385),
    "ratnagiri":         (16.9944, 73.3000),
    "mahabalipuram":     (12.6269, 80.1927),
    "karaikal":          (10.9254, 79.8380),
    "nellore":           (14.4426, 79.9865),
    "machilipatnam":     (16.1875, 81.1389),
    "gopalpur":          (19.2680, 84.9020),
    "minicoy":           (8.2833, 73.0333),
    "agatti":            (10.8487, 72.1977),
    "bhavnagar":         (21.7645, 72.1519),
    "jamnagar":          (22.4707, 70.0577),
    "veraval":           (20.9019, 70.3630),
    "kandla":            (23.0333, 70.2167),
    "surat":             (21.1702, 72.8311),
    "daman":             (20.3974, 72.8328),
    "okha":              (22.4700, 69.0700),
    "dwarka":            (22.2394, 68.9679),
    "mandvi":            (22.8290, 69.3582),
    "udupi":             (13.3409, 74.7421),
    "bhatkal":           (13.9724, 74.5563),
    "kasaragod":         (12.4996, 74.9869),
    "varkala":           (8.7379, 76.7160),
    "beypore":           (11.1743, 75.8103),
    "ponnani":           (10.7750, 75.9250),
    "thalassery":        (11.7500, 75.4900),
    "tellicherry":       (11.7500, 75.4900),
    "ernakulam":         (9.9816, 76.2999),
    "malvan":            (16.0601, 73.4668),
    "alibag":            (18.6453, 72.8789),
    "mormugao":          (15.4083, 73.8003),
    "vasco da gama":     (15.3980, 73.8107),
    "vasco":             (15.3980, 73.8107),
    "panaji":            (15.4909, 73.8278),
    "havelock island":   (11.9792, 93.0086),
    "bhubaneswar":       (20.2961, 85.8245),
}

GAZETTEER.update(_HARDCODED)

# Load supplemental entries from coastal_places.json
try:
    if _PLACES_FILE.exists():
        _raw = json.loads(_PLACES_FILE.read_text(encoding="utf-8"))
        for _p in _raw.get("places", []):
            _key = _p["name"].lower()
            _coord = (float(_p["lat"]), float(_p["lon"]))
            GAZETTEER.setdefault(_key, _coord)
            for _alias in _p.get("aliases", []):
                GAZETTEER.setdefault(_alias.lower(), _coord)
        logger.info("Loaded %d gazetteer entries from coastal_places.json", len(GAZETTEER))
except Exception as _e:
    logger.warning("Could not load coastal_places.json: %s — using hardcoded entries", _e)

# ---------------------------------------------------------------------------
# In-memory Nominatim cache (24-hour TTL per entry, max 512 entries)
# ---------------------------------------------------------------------------
_GEOCODE_CACHE: TTLCache = TTLCache(maxsize=512, ttl=86400)
_REVERSE_CACHE: TTLCache = TTLCache(maxsize=512, ttl=86400)

# Rate limiting: Nominatim policy = max 1 req/s
_LAST_NOMINATIM_CALL: float = 0.0


def _nominatim_rate_limit() -> None:
    """Sleep if needed to respect Nominatim's 1 req/s policy."""
    global _LAST_NOMINATIM_CALL
    elapsed = time.monotonic() - _LAST_NOMINATIM_CALL
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _LAST_NOMINATIM_CALL = time.monotonic()


# ---------------------------------------------------------------------------
# Coastal Districts of India
# ---------------------------------------------------------------------------
COASTAL_DISTRICTS: set[str] = {
    # Gujarat
    "kutch", "kachchh", "morbi", "jamnagar", "devbhumi dwarka", "porbandar",
    "junagadh", "gir somnath", "amreli", "bhavnagar", "ahmedabad", "anand",
    "bharuch", "surat", "navsari", "valsad",
    # Maharashtra
    "palghar", "thane", "mumbai", "mumbai suburban", "mumbai city",
    "raigad", "ratnagiri", "sindhudurg",
    # Goa
    "north goa", "south goa", "goa",
    # Karnataka
    "uttara kannada", "north canara", "udupi", "dakshina kannada", "south canara",
    "kumta", "kumata", "honnavar", "bhatkal", "karwar", "ankola", "kundapura", "mangalore", "mangaluru",
    # Kerala
    "kasaragod", "kannur", "kozhikode", "malappuram", "thrissur",
    "ernakulam", "alappuzha", "kollam", "thiruvananthapuram",
    # Tamil Nadu
    "tiruvallur", "chennai", "chengalpattu", "viluppuram", "cuddalore",
    "mayiladuthurai", "nagapattinam", "tiruvarur", "thanjavur", "pudukkottai",
    "ramanathapuram", "thoothukudi", "tirunelveli", "kanniyakumari", "kanyakumari",
    "kalkulam", "rameswaram",
    # Andhra Pradesh
    "srikakulam", "vizianagaram", "visakhapatnam", "anakapalli", "kakinada",
    "konaseema", "dr. b.r. ambedkar konaseema", "west godavari", "krishna",
    "bapatla", "prakasam", "sri potti sriramulu nellore", "nellore", "tirupati",
    "nizampatnam", "gara",
    # Odisha
    "balasore", "baleshwar", "bhadrak", "kendrapara", "jagatsinghpur", "puri", "ganjam",
    "balaramgadi",
    # West Bengal
    "purba medinipur", "east midnapore", "south 24 parganas", "north 24 parganas",
    "howrah", "kolkata", "namkhana",
    # Islands & UTs (100% coastal)
    "andaman", "nicobar", "andaman and nicobar", "south andaman", "north and middle andaman", "nicobars",
    "diglipur", "port blair",
    "lakshadweep", "minicoy", "kavaratti", "agatti", "amini",
    "puducherry", "karaikal", "mahe", "yanam",
    "daman", "diu",
}


# ---------------------------------------------------------------------------
# Coastal validation helpers
# ---------------------------------------------------------------------------

def _is_coastal_address(address: Dict[str, str]) -> bool:
    """Return True if the Nominatim address is in a known Indian coastal state and district."""
    state = address.get("state", "").lower()
    county = address.get("county", "").lower()
    district = (address.get("state_district") or address.get("district") or "").lower()
    city = address.get("city", "").lower()
    town = address.get("town", "").lower()
    village = address.get("village", "").lower()

    # Direct coastal state match
    is_coastal_state = False
    for cs in COASTAL_STATES_UT:
        if cs in state:
            is_coastal_state = True
            break

    if not is_coastal_state:
        return False

    # Island UTs & Goa are entirely coastal
    if any(isl in state for isl in ["andaman", "nicobar", "lakshadweep", "daman", "diu", "goa", "puducherry"]):
        return True

    # Check coastal district / taluk
    addr_tokens = f"{county} {district} {city} {town} {village}"
    for cd in COASTAL_DISTRICTS:
        if cd in addr_tokens:
            return True

    return False


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Great Circle distance between two points in km."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def distance_to_nearest_coast_km(lat: float, lon: float) -> float:
    """Calculate distance in km to the nearest known Indian coastal point in GAZETTEER."""
    if not GAZETTEER:
        return 0.0
    return min(haversine_km(lat, lon, clat, clon) for clat, clon in GAZETTEER.values())


def location_is_coastal(lat: float, lon: float, name: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validate whether geographic coordinates belong to an Indian coastal location or marine waters.

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        name: Optional location name provided by caller/user

    Returns:
        (is_coastal, resolved_display_name, details_dict)
    """
    cache_key = f"{lat:.4f},{lon:.4f}"
    if cache_key in _REVERSE_CACHE:
        return _REVERSE_CACHE[cache_key]

    dist_to_coast_km = distance_to_nearest_coast_km(lat, lon)

    # Fast boundary envelope check:
    # India's marine waters, islands, and coastline span latitude ~6.0°N to ~24.5°N
    # Any coordinate north of 24.5°N in India (e.g. New Delhi 28.61°N) is inland.
    if lat > 24.5 or lat < 5.0 or lon < 65.0 or lon > 96.0:
        result = (False, name or f"Location ({lat:.2f}°N, {lon:.2f}°E)", {
            "reason": "outside_coastal_envelope",
            "distance_to_coast_km": dist_to_coast_km,
        })
        _REVERSE_CACHE[cache_key] = result
        return result

    _nominatim_rate_limit()

    try:
        with httpx.Client(timeout=6.0) as client:
            resp = client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "json", "addressdetails": 1},
                headers={"User-Agent": "Tarang-MarineSafetyApp/1.0 (contact@tarang.app)"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("[Location] Nominatim reverse lookup failed for (%.4f, %.4f): %s", lat, lon, exc)
        # Permissive fallback if geocoder fails
        result = (True, name or f"Location ({lat:.2f}°N, {lon:.2f}°E)", {
            "reason": "geocoder_unreachable_fallback",
            "distance_to_coast_km": dist_to_coast_km,
        })
        return result

    address = data.get("address", {})
    country_code = address.get("country_code", "").lower()
    state = address.get("state", "").lower()
    county = address.get("county", "").lower()
    district = (address.get("state_district") or address.get("district") or "").lower()
    display_name = (
        data.get("name")
        or address.get("city")
        or address.get("town")
        or address.get("village")
        or name
        or f"Location ({lat:.2f}°N, {lon:.2f}°E)"
    )

    # 1. Marine / offshore waters within Indian EEZ (Nominatim returns country_code 'in' with no inland state)
    if country_code == "in" and not state:
        result = (True, display_name or "Offshore Coastal Waters", {
            "reason": "marine_territorial_waters",
            "distance_to_coast_km": dist_to_coast_km,
        })
        _REVERSE_CACHE[cache_key] = result
        return result

    # 2. Foreign country outside Indian waters
    if country_code and country_code != "in":
        result = (False, display_name, {
            "reason": "foreign_country",
            "country": country_code,
            "distance_to_coast_km": dist_to_coast_km,
        })
        _REVERSE_CACHE[cache_key] = result
        return result

    # 3. State check: must be a coastal state or UT
    is_coastal_state = any(cs in state for cs in COASTAL_STATES_UT)
    if not is_coastal_state:
        result = (False, display_name, {
            "reason": "non_coastal_state",
            "state": state,
            "distance_to_coast_km": dist_to_coast_km,
        })
        _REVERSE_CACHE[cache_key] = result
        return result

    # 4. Island UTs & Goa are 100% coastal
    if any(isl in state for isl in ["andaman", "nicobar", "lakshadweep", "daman", "diu", "goa", "puducherry"]):
        result = (True, display_name, {
            "reason": "coastal_island_or_ut",
            "state": state,
            "distance_to_coast_km": dist_to_coast_km,
        })
        _REVERSE_CACHE[cache_key] = result
        return result

    # 5. Mainland coastal states: check coastal district / taluk
    addr_tokens = f"{county} {district} {address.get('city', '')} {address.get('town', '')} {address.get('village', '')} {display_name}".lower()
    is_coastal_dist = any(cd in addr_tokens for cd in COASTAL_DISTRICTS)
    if is_coastal_dist:
        result = (True, display_name, {
            "reason": "coastal_district",
            "state": state,
            "distance_to_coast_km": dist_to_coast_km,
        })
        _REVERSE_CACHE[cache_key] = result
        return result

    # Inland district within a coastal state (e.g. Bangalore, Madurai, Coimbatore, Pune, Nagpur)
    result = (False, display_name, {
        "reason": "inland_district_in_coastal_state",
        "state": state,
        "district": district or county,
        "distance_to_coast_km": dist_to_coast_km,
    })
    _REVERSE_CACHE[cache_key] = result
    return result



# ---------------------------------------------------------------------------
# Public resolver
# ---------------------------------------------------------------------------

def resolve_location(query: str) -> Dict[str, Any]:
    """
    Resolve a location query to coordinates using a two-tier system.

    Args:
        query: Raw text (e.g. "Kochi", "near Thoothukudi", "Is it safe in Diu?")

    Returns:
        {
            "location_name":      str,
            "latitude":           float | None,
            "longitude":          float | None,
            "source":             "gazetteer" | "geocoder" | "none",
            "location_source":    same as source,
            "status":             "success" | "inland" | "unresolved",
            "location_confidence": "high" | "medium" | "low",
        }
    """
    query_lower = query.lower().strip()

    # ── Tier 1: Gazetteer lookup ─────────────────────────────────────────────
    for place, (lat, lon) in GAZETTEER.items():
        if place in query_lower:
            logger.info("[Location] Gazetteer hit: '%s' → (%.4f, %.4f)", place, lat, lon)
            return {
                "location_name":       place.title(),
                "latitude":            lat,
                "longitude":           lon,
                "source":              "gazetteer",
                "location_source":     "gazetteer",
                "status":              "success",
                "location_confidence": "high",
            }

    # ── Cache lookup ─────────────────────────────────────────────────────────
    if query_lower in _GEOCODE_CACHE:
        logger.info("[Location] Cache hit for '%s'", query)
        return _GEOCODE_CACHE[query_lower]

    # Extract non-stopword tokens as search term candidate
    _STOP_WORDS = {
        "is", "it", "safe", "to", "fish", "right", "now", "today", "tomorrow", "can", "will",
        "how", "what", "where", "when", "should", "are", "do", "does", "i", "we", "the", "a",
        "an", "near", "in", "at", "for", "me", "my", "tell", "check", "please", "there", "any",
        "weather", "forecast", "sea", "state", "marine", "risk", "condition", "conditions",
        "mere", "yaha", "yahaan", "yahan", "idhar", "humare", "hamaare", "kya", "hai", "ka",
        "ki", "ke", "ko", "bata", "batao", "bataiye", "do", "de", "kaisa", "karke", "level",
        "sollu", "sollungal", "enga", "inge", "ingu", "eppadi", "irukku", "kadal", "mattai",
        "about", "then", "later", "morning", "evening", "afternoon", "night", "time", "next",
        "also", "and", "or", "so", "show", "give", "get", "view", "see", "info", "information",
        "report", "details", "tide", "tides", "water", "waves", "wind", "winds", "cyclone",
        "storm", "kal", "aaj", "subah", "shaam", "naale", "indru", "kaalai", "maalai",
        # Conversational follow-up and evaluation tokens (V2.2.1)
        "still", "that", "this", "why", "again", "yet", "recheck", "warning", "warnings",
        "alert", "alerts", "lightning", "rain", "pressure", "good", "bad", "okay", "ok",
        "fine", "high", "low", "moderate", "extreme", "score", "factor", "factors",
        "breakdown", "reason", "because", "explain", "explanation", "kyun", "kyon",
        "samjhao", "iska", "woh", "khatra", "tufan", "bijli",
    }
    tokens = [w for w in re.findall(r'\b[A-Za-z]+\b', query) if w.lower() not in _STOP_WORDS]
    if not tokens:
        logger.info("[Location] No candidate location tokens found in query: '%s'", query)
        return {
            "location_name":       "Unknown",
            "latitude":            None,
            "longitude":           None,
            "source":              "none",
            "location_source":     "none",
            "status":              "unresolved",
            "location_confidence": "low",
        }

    search_term = " ".join(tokens)

    _nominatim_rate_limit()

    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q":              search_term,
                    "format":         "json",
                    "limit":          1,
                    "countrycodes":   "in",
                    "addressdetails": 1,
                },
                headers={"User-Agent": "Tarang-MarineSafetyApp/1.0 (contact@tarang.app)"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("[Location] Nominatim request failed for '%s': %s", query, exc)
        _fail = {"location_name": query, "latitude": None, "longitude": None,
                 "source": "none", "location_source": "none",
                 "status": "unresolved", "location_confidence": "low"}
        _GEOCODE_CACHE[query_lower] = _fail
        return _fail

    if not data:
        logger.info("[Location] Nominatim: no results for '%s'", search_term)
        _result = {"location_name": query, "latitude": None, "longitude": None,
                   "source": "none", "location_source": "none",
                   "status": "unresolved", "location_confidence": "low"}
        _GEOCODE_CACHE[query_lower] = _result
        return _result

    hit = data[0]
    address = hit.get("address", {})
    country_code = address.get("country_code", "").lower()

    # Validate India
    if country_code != "in":
        _result = {"location_name": query, "latitude": None, "longitude": None,
                   "source": "none", "location_source": "none",
                   "status": "unresolved", "location_confidence": "low"}
        _GEOCODE_CACHE[query_lower] = _result
        return _result

    lat = float(hit["lat"])
    lon = float(hit["lon"])
    display_name = hit.get("name") or hit.get("display_name", query.title()).split(",")[0].strip()

    # Coastal check
    if not _is_coastal_address(address):
        logger.info("[Location] '%s' resolved to inland location", query)
        _result = {
            "location_name":       display_name,
            "latitude":            lat,
            "longitude":           lon,
            "source":              "geocoder",
            "location_source":     "geocoder",
            "status":              "inland",
            "location_confidence": "medium",
            "distance_to_coast_km": distance_to_nearest_coast_km(lat, lon),
        }
        _GEOCODE_CACHE[query_lower] = _result
        return _result

    _result = {
        "location_name":       display_name,
        "latitude":            lat,
        "longitude":           lon,
        "source":              "geocoder",
        "location_source":     "geocoder",
        "status":              "success",
        "location_confidence": "medium",  # geocoder is less certain than gazetteer
    }
    _GEOCODE_CACHE[query_lower] = _result
    logger.info("[Location] Nominatim resolved: '%s' → %s (%.4f, %.4f)", query, display_name, lat, lon)
    return _result
