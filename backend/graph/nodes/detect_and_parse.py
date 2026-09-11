"""
detect_and_parse node
---------------------
Detects query language and extracts structured intent from the raw user query.

Milestone 1: Uses a keyword-based heuristic instead of an LLM call.
              Replace the body of `_parse_with_llm()` in Milestone 2 to use
              Groq function-calling with a Pydantic schema.
"""

from __future__ import annotations

import re
from typing import Optional

from graph.state import ORCAState, ParsedIntent

# ---------------------------------------------------------------------------
# Static coastal gazetteer  (Indian coastal towns + common PFZ region names)
# Extend this dict before the demo with every location you plan to demo.
# lat/lon are approximate centroid values.
# ---------------------------------------------------------------------------
GAZETTEER: dict[str, tuple[float, float]] = {
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
    "kochi": (9.9312, 76.2673),
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
    "puri": (19.8103, 85.8314),
    "paradip": (20.3164, 86.6111),
    # West Bengal
    "digha": (21.6267, 87.5081),
    "sagar island": (21.6538, 88.0720),
    # Lakshadweep / A&N
    "port blair": (11.6234, 92.7265),
    "kavaratti": (10.5669, 72.6420),
}

# ---------------------------------------------------------------------------
# Language detection: keyword / script fingerprint heuristic
# ---------------------------------------------------------------------------
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")

# Hindi keywords (romanised)
_HINDI_ROMANISED = {
    "kal", "subah", "samudra", "jaana", "safe", "hai", "kya", "paas",
    "ke", "ke paas", "mausam", "machli", "machliyon", "aaj", "abhi",
    "tufan", "lehar", "surakshit",
}

# Tamil keywords (romanised)
_TAMIL_ROMANISED = {
    "kadal", "yarukku", "eppadi", "nallada", "naale", "indru",
    "mazhai", "paadhukaappu", "meen", "pidi",
}


def _detect_language(text: str) -> str:
    """Return BCP-47 language tag based on script/keyword heuristics."""
    if _DEVANAGARI_RE.search(text):
        return "hi"
    if _TAMIL_RE.search(text):
        return "ta"

    words = set(text.lower().split())
    hindi_overlap = words & _HINDI_ROMANISED
    tamil_overlap = words & _TAMIL_ROMANISED
    if hindi_overlap and len(hindi_overlap) >= len(tamil_overlap):
        return "hi"
    if tamil_overlap:
        return "ta"
    return "en"


# ---------------------------------------------------------------------------
# Gazetteer lookup
# ---------------------------------------------------------------------------

def _resolve_location(text: str) -> tuple[Optional[str], Optional[float], Optional[float]]:
    """Return (location_name, lat, lon) by fuzzy-matching the text against the gazetteer."""
    text_lower = text.lower()
    for place, (lat, lon) in GAZETTEER.items():
        if place in text_lower:
            return place.title(), lat, lon
    return None, None, None


# ---------------------------------------------------------------------------
# Time-window extraction
# ---------------------------------------------------------------------------
_TIME_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(kal|tomorrow|कल|நாளை)\b", re.I), "tomorrow"),
    (re.compile(r"\b(subah|morning|सुबह|காலை)\b", re.I), "morning"),
    (re.compile(r"\b(abhi|now|अभी|இப்போது)\b", re.I), "now"),
    (re.compile(r"\b(aaj|today|आज|இன்று)\b", re.I), "today"),
    (re.compile(r"\bnext\s+24\s*h\b", re.I), "next_24h"),
    (re.compile(r"\b(evening|shaam|शाम|மாலை)\b", re.I), "evening"),
]


def _extract_time_window(text: str) -> str:
    matches: list[str] = []
    for pattern, label in _TIME_PATTERNS:
        if pattern.search(text):
            matches.append(label)

    if "tomorrow" in matches and "morning" in matches:
        return "tomorrow_morning"
    if matches:
        return matches[0]
    return "next_24h"  # sensible default


# ---------------------------------------------------------------------------
# Query-type + needs_* flags
# ---------------------------------------------------------------------------

def _classify_query(text: str) -> tuple[str, dict[str, bool]]:
    """
    Returns (query_type, needs_flags_dict).

    query_type: "safety_check" | "pfz_lookup" | "general"
    """
    text_lower = text.lower()

    safety_keywords = {
        "safe", "safety", "jaana", "जाना", "surakshit", "सुरक्षित",
        "paadhukaappu", "risk", "danger", "खतरा", "hazard",
    }
    pfz_keywords = {
        "fish", "fishing", "pfz", "zone", "machli", "मछली", "meen",
        "மீன்", "மீன்பிடி", "machliyon", "fishing zone", "potential",
    }

    is_safety = bool(set(text_lower.split()) & safety_keywords) or any(
        kw in text_lower for kw in safety_keywords
    )
    is_pfz = bool(set(text_lower.split()) & pfz_keywords) or any(
        kw in text_lower for kw in pfz_keywords
    )

    # "fishing ke liye jaana safe hai?" → both PFZ and safety
    if is_safety and is_pfz:
        query_type = "safety_check"
        needs = {
            "needs_weather": True,
            "needs_pfz": True,
            "needs_hazard": True,
            "needs_geofence": True,
            "needs_risk": True,
        }
    elif is_safety:
        query_type = "safety_check"
        needs = {
            "needs_weather": True,
            "needs_pfz": False,
            "needs_hazard": True,
            "needs_geofence": True,
            "needs_risk": True,
        }
    elif is_pfz:
        query_type = "pfz_lookup"
        # Pure PFZ query → weather+geofence+risk NOT needed per §10 DoD
        needs = {
            "needs_weather": False,
            "needs_pfz": True,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
        }
    else:
        query_type = "general"
        needs = {
            "needs_weather": True,
            "needs_pfz": True,
            "needs_hazard": True,
            "needs_geofence": True,
            "needs_risk": True,
        }

    return query_type, needs


# ---------------------------------------------------------------------------
# Public node function
# ---------------------------------------------------------------------------

def detect_and_parse(state: ORCAState) -> dict:
    """
    LangGraph node: detect language + parse intent from raw_query.
    Returns a partial state dict to merge into ORCAState.
    """
    raw = state["raw_query"]

    detected_language = _detect_language(raw)
    location_name, lat, lon = _resolve_location(raw)
    time_window = _extract_time_window(raw)
    query_type, needs = _classify_query(raw)

    # If no location found, default to Thoothukudi (our demo anchor)
    if location_name is None:
        location_name = "Thoothukudi"
        lat, lon = GAZETTEER["thoothukudi"]

    parsed_intent: ParsedIntent = {
        "location_name": location_name,
        "lat": lat,
        "lon": lon,
        "time_window": time_window,
        "query_type": query_type,
        **needs,  # type: ignore[misc]
    }

    return {
        "detected_language": detected_language,
        "parsed_intent": parsed_intent,
    }
