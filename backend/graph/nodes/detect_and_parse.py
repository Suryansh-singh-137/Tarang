"""
detect_and_parse node
---------------------
Detects query language and extracts structured intent from the raw user query.

Milestone 2 additions:
  - Resolves time_window label into explicit UTC time range (time_start_utc, time_end_utc).
  - Handles "invalid location" detection (unknown place → controlled error response).
  - Handles "kal shaam" (tomorrow evening) pattern.

Milestone 4 additions:
  - Classifies "risk_explanation" query type (why is the risk X, explain the score, etc.).

Milestone 5 additions:
  - Multi-turn intent inheritance: when conversation_history is non-empty, inherits
    location and/or time_window from last_parsed_intent if not explicitly changed.
  - Produces changed_fields list to drive selective agent re-invocation.
  - Caps conversation_history at MAX_CONVERSATION_TURNS.

Language detection uses script fingerprinting + keyword overlap heuristics.
Location resolution uses a static coastal gazetteer.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal
import logging

from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

import config
from graph.state import ORCAState, ParsedIntent, AnswerPlan, ResponseMode
from location.resolver import LocationResolver
from location.models import DeviceLocation, QueryLocation, ResolvedLocation, LocationMode
from session.session_store import get_or_create_session
from tools.location_resolver import resolve_location, GAZETTEER, location_is_coastal, distance_to_nearest_coast_km


# ---------------------------------------------------------------------------
# Timezone offset for India (IST = UTC+5:30)
# ---------------------------------------------------------------------------
_IST_OFFSET = timedelta(hours=5, minutes=30)


def _now_ist() -> datetime:
    """Return current time as an IST-aware datetime."""
    return datetime.now(timezone.utc) + _IST_OFFSET


def _to_utc_iso(dt_ist: datetime) -> str:
    """Convert an IST datetime to a UTC ISO-8601 string."""
    dt_utc = dt_ist - _IST_OFFSET
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Time-window → explicit UTC range resolver
# ---------------------------------------------------------------------------

def _resolve_time_range(time_window: str) -> tuple[str, str]:
    """
    Convert a time_window label into (start_utc, end_utc) ISO-8601 strings.

    All natural-language times are interpreted in IST (Asia/Kolkata) then
    converted to UTC for downstream API calls.

    Returns:
        (time_start_utc, time_end_utc) as ISO-8601 UTC strings
    """
    now_ist = _now_ist()
    today_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_ist = today_ist + timedelta(days=1)

    tw = time_window.lower()

    if tw == "tomorrow_morning":
        start = tomorrow_ist.replace(hour=6, minute=0)
        end   = tomorrow_ist.replace(hour=12, minute=0)
    elif tw == "tomorrow_evening":
        start = tomorrow_ist.replace(hour=16, minute=0)
        end   = tomorrow_ist.replace(hour=20, minute=0)
    elif tw == "tomorrow":
        start = tomorrow_ist.replace(hour=0, minute=0)
        end   = tomorrow_ist.replace(hour=23, minute=59)
    elif tw == "morning":
        start = today_ist.replace(hour=6, minute=0)
        end   = today_ist.replace(hour=12, minute=0)
    elif tw == "evening":
        start = today_ist.replace(hour=16, minute=0)
        end   = today_ist.replace(hour=20, minute=0)
    elif tw == "now":
        start = now_ist
        end   = now_ist + timedelta(hours=3)
    elif tw == "today":
        start = today_ist
        end   = today_ist.replace(hour=23, minute=59)
    else:  # next_24h (default)
        start = now_ist
        end   = now_ist + timedelta(hours=24)

    return _to_utc_iso(start), _to_utc_iso(end)



# ---------------------------------------------------------------------------
# Language detection: keyword / script fingerprint heuristic
# ---------------------------------------------------------------------------
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")

# Hindi keywords (romanised)
_HINDI_ROMANISED = {
    "kal", "subah", "samudra", "jaana", "safe", "hai", "kya", "paas",
    "ke", "ke paas", "mausam", "machli", "machliyon", "aaj", "abhi",
    "tufan", "lehar", "surakshit", "shaam", "kyun", "batao", "kyon",
    "bata", "samjhao", "kya", "iska", "woh",
}

# Tamil keywords (romanised)
_TAMIL_ROMANISED = {
    "kadal", "yarukku", "eppadi", "nallada", "naale", "indru",
    "mazhai", "paadhukaappu", "meen", "pidi", "yen", "vitham",
}


# Common English stop words that imply English — if these dominate, don't classify as Hindi
_ENGLISH_STOP_WORDS = {
    "is", "it", "to", "go", "the", "are", "there", "any", "near", "for",
    "safe", "safety", "fishing", "weather", "sea", "ocean", "conditions",
    "waves", "winds", "what", "when", "how", "alerts", "warnings", "storm",
    "will", "tomorrow", "morning", "evening", "today", "now", "next",
    "why", "explain", "because", "reason", "score", "risk",
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
    english_overlap = words & _ENGLISH_STOP_WORDS

    # If English stop words dominate, it's English
    if len(english_overlap) >= len(hindi_overlap) and len(english_overlap) > 0:
        return "en"
    if hindi_overlap and len(hindi_overlap) > len(tamil_overlap):
        return "hi"
    if tamil_overlap:
        return "ta"
    return "en"





# ---------------------------------------------------------------------------
# Time-window extraction (label only — UTC resolution happens after)
# ---------------------------------------------------------------------------
_TIME_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(kal|tomorrow|कल|நாளை)\b", re.I), "tomorrow"),
    (re.compile(r"\b(subah|morning|सुबह|காலை)\b", re.I), "morning"),
    (re.compile(r"\b(shaam|evening|शाम|மாலை)\b", re.I), "evening"),
    (re.compile(r"\b(abhi|now|अभी|இப்போது)\b", re.I), "now"),
    (re.compile(r"\b(aaj|today|आज|இன்று)\b", re.I), "today"),
    (re.compile(r"\bnext\s+24\s*h\b", re.I), "next_24h"),
]


def _extract_time_window(text: str) -> str:
    matches: list[str] = []
    for pattern, label in _TIME_PATTERNS:
        if pattern.search(text):
            matches.append(label)

    if "tomorrow" in matches and "morning" in matches:
        return "tomorrow_morning"
    if "tomorrow" in matches and "evening" in matches:
        return "tomorrow_evening"
    if matches:
        return matches[0]
    return "next_24h"  # sensible default


# ---------------------------------------------------------------------------
# Risk-explanation query detection (Milestone 4)
# ---------------------------------------------------------------------------

_EXPLAIN_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(why|explain|reason|because|breakdown|how.*calculated|what.*factors)\b", re.I),
    re.compile(r"\b(kyun|kyon|samjhao|batao|kyon|iska|woh)\b", re.I),   # Hindi romanised
    re.compile(r"\b(yen|vitham|eppadi)\b", re.I),                         # Tamil romanised
    re.compile(r"[\u0915\u094D\u092F\u0942\u0928]"),                      # Devanagari कयून/कयों
    re.compile(r"explain.*risk|risk.*explain|score.*why|why.*score", re.I),
]


def _is_risk_explanation(text: str) -> bool:
    """Return True if the query is asking WHY the risk score is what it is."""
    return any(pat.search(text) for pat in _EXPLAIN_PATTERNS)


# ---------------------------------------------------------------------------
# Query-type + needs_* flags
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Fine-grained Intent Classification (V2.2 Conversational Pipeline)
# ---------------------------------------------------------------------------

_LOCATION_QUERY_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(what('?s| is)? (my|our|this|the current) location|where am i|where are we|what is this place|my current location|current location|tell me my location|show my location|what is my current location)\b", re.I),
    re.compile(r"^\s*my location\s*$", re.I),
    re.compile(r"\b(coordinates|my coordinates|gps coordinates|latitude|longitude|lat\s*lon)\b", re.I),
    re.compile(r"\b(mera|meri) location\b", re.I),
    re.compile(r"\b(kahan (hoon|hu|hai|hain)|main kahan|hum kahan|mera sthan|sthan kya hai|sthan batao)\b", re.I),
    re.compile(r"\b(en idam|naan enge|idam enna|engae irukkiren|enathu idam)\b", re.I),
    re.compile(r"[\u0915\u0939\u093E\u0901][\u0939\u0948\u0902]?"),  # कहाँ / स्थान
]

_PRESSURE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(sea\s*level\s*pressure|msl\s*pressure|mean\s*sea\s*level\s*pressure|barometric\s*pressure|atmospheric\s*pressure|surface\s*pressure)\b", re.I),
    re.compile(r"\b(vayu\s*dabav|samudra\s*tal\s*dabav|hawa\s*ka\s*dabav)\b", re.I),
]

_WATER_LEVEL_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(water\s*level|sea\s*level|sea\s*water\s*level|chart\s*datum|samudra\s*jal\s*star|kadal\s*neer\s*mattam)\b", re.I),
]

_TIDE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(tide|tides|high\s*tide|low\s*tide|tidal|jwar|bhata|alahi|lehar\s*star)\b", re.I),
    re.compile(r"\b(jwar-bhata|jwar\s*bhata)\b", re.I),
]

_BOUNDARY_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(boundary|border|imbl|sri\s*lanka|international\s*waters|maritime\s*limit|seema)\b", re.I),
]

_FOLLOWUP_PREFIX_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*(what\s+about|how\s+about|aur\s+kal|aur\s+aaj|and\s+tomorrow|and\s+today|what\s+for)\b", re.I),
]

_RECHECK_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(still\s+safe|safe\s+now|recheck|check\s+again|is\s+it\s+still|kya\s+abhi\s+bhi|update\s+safety|still\s+okay|still\s+good|now\s+safe)\b", re.I),
]



def classify_query_intent(
    text: str,
    last_intent: Optional[ParsedIntent] = None,
) -> tuple[str, str, dict[str, bool], str]:
    """
    Returns (intent_name, query_type, needs_dict, response_mode).

    Intents:
      - LOCATION_QUERY
      - WEATHER_QUERY
      - TIDE_QUERY
      - WATER_LEVEL_QUERY
      - SEA_LEVEL_PRESSURE_QUERY
      - PFZ_QUERY
      - HAZARD_QUERY
      - BOUNDARY_QUERY
      - MARINE_SAFETY_QUERY
      - TRIP_QUERY
      - RISK_EXPLANATION
      - GENERAL_FOLLOWUP
    """
    text_lower = text.lower().strip()

    # 1. Explanation intent (takes precedence)
    if _is_risk_explanation(text):
        return "RISK_EXPLANATION", "risk_explanation", {
            "needs_weather": False,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": False,
        }, "DIRECT_FACT"

    # 2. Location query (Section 7, 8, 27: hard bypass for location inquiries)
    if any(pat.search(text) for pat in _LOCATION_QUERY_PATTERNS):
        return "LOCATION_QUERY", "location_only", {
            "needs_weather": False,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": False,
        }, "DIRECT_FACT"

    # 3. Sea-level atmospheric pressure query (Section 10)
    if any(pat.search(text) for pat in _PRESSURE_PATTERNS):
        return "SEA_LEVEL_PRESSURE_QUERY", "weather_only", {
            "needs_weather": True,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": False,
        }, "DATA_SUMMARY"

    # 4. Local water level / tide query (Section 10, 28)
    is_water_level = any(pat.search(text) for pat in _WATER_LEVEL_PATTERNS)
    is_tide = any(pat.search(text) for pat in _TIDE_PATTERNS)
    if is_water_level and not any(kw in text_lower for kw in ["safe", "safety", "jaana", "surakshit", "fish", "machli"]):
        return "WATER_LEVEL_QUERY", "ocean_tide", {
            "needs_weather": False,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": True,
        }, "DATA_SUMMARY"
    if is_tide and not any(kw in text_lower for kw in ["safe", "safety", "jaana", "surakshit"]):
        return "TIDE_QUERY", "ocean_tide", {
            "needs_weather": False,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": True,
        }, "DATA_SUMMARY"

    # 5. Maritime boundary query
    if any(pat.search(text) for pat in _BOUNDARY_PATTERNS) and not any(kw in text_lower for kw in ["safe", "safety", "fish"]):
        return "BOUNDARY_QUERY", "general", {
            "needs_weather": False,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": True,
            "needs_risk": False,
            "needs_ocean": False,
        }, "DATA_SUMMARY"

    _TRIP_SAFETY_PATTERNS = [
        re.compile(r"\b(can i go|can we go|should i go|should we go|okay to go|safe to go|go out|head out|sail out|going out|venture out|go to sea|head to sea|out to sea)\b", re.I),
        re.compile(r"\b(kya main ja sakta|kya hum ja sakte|jaana sahi hai|jaana theek hai|samundar mein utarna)\b", re.I),
    ]

    safety_keywords = {
        "safe", "safety", "jaana", "जाना", "surakshit", "सुरक्षित",
        "paadhukaappu", "risk", "danger", "खतरा", "hazard", "suitability",
        "venture", "trip", "craft", "boat", "sail",
    }
    pfz_keywords = {
        "fish", "fishing", "pfz", "zone", "machli", "मछली", "meen",
        "மீன்", "மீன்பிடி", "machliyon", "fishing zone", "potential",
        "chlorophyll",
    }
    hazard_keywords = {
        "cyclone", "storm", "lightning", "warning", "alert", "dangerous",
        "tufan", "तूफान", "bijli", "बिजली", "advisory", "khatra",
    }
    weather_keywords = {
        "weather", "wave", "wind", "sea state", "ocean condition", "condition", "forecast",
        "mausam", "lehar", "samudra", "தரங்கு", "அலை", "temperature", "rain",
        "rainfall", "baarish", "hawa",
    }

    words = set(text_lower.split())
    is_trip_pattern = any(p.search(text) for p in _TRIP_SAFETY_PATTERNS)
    is_safety = is_trip_pattern or bool(words & safety_keywords) or any(kw in text_lower for kw in safety_keywords)
    is_pfz = bool(words & pfz_keywords) or any(kw in text_lower for kw in pfz_keywords)
    is_hazard = bool(words & hazard_keywords) or any(kw in text_lower for kw in hazard_keywords)
    is_weather = bool(words & weather_keywords) or any(kw in text_lower for kw in weather_keywords)

    # 6. Safety check takes priority when safety keywords are explicitly present
    if is_safety:
        return "MARINE_SAFETY_QUERY", "safety_check", {
            "needs_weather": True,
            "needs_pfz": True,
            "needs_hazard": True,
            "needs_geofence": True,
            "needs_risk": True,
            "needs_ocean": True,
        }, "DECISION_ASSESSMENT"

    # 7. Pure PFZ lookup (no safety asked)
    if is_pfz:
        return "PFZ_QUERY", "pfz_lookup", {
            "needs_weather": False,
            "needs_pfz": True,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": False,
        }, "DATA_SUMMARY"

    # 8. Pure Hazard lookup (no safety asked)
    if is_hazard:
        return "HAZARD_QUERY", "hazard_only", {
            "needs_weather": True,
            "needs_pfz": False,
            "needs_hazard": True,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": False,
        }, "DATA_SUMMARY"

    # 9. Pure Weather lookup (no safety asked)
    if is_weather:
        return "WEATHER_QUERY", "weather_only", {
            "needs_weather": True,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": False,
        }, "DATA_SUMMARY"

    # 10. Follow-up inheritance (e.g. "what about tomorrow?", "what about here?")
    is_followup = any(pat.search(text) for pat in _FOLLOWUP_PREFIX_PATTERNS) or text_lower in ("tomorrow", "here", "kal", "yahan")
    if is_followup and last_intent is not None:
        if isinstance(last_intent, str):
            prior_intent = last_intent
            prior_qtype = (
                "weather_only" if last_intent in ("WEATHER_QUERY", "SEA_LEVEL_PRESSURE_QUERY")
                else "safety_check" if last_intent in ("MARINE_SAFETY_QUERY", "TRIP_QUERY")
                else "ocean_tide" if last_intent in ("TIDE_QUERY", "WATER_LEVEL_QUERY")
                else "pfz_lookup" if last_intent == "PFZ_QUERY"
                else "general"
            )
            prior_needs = {
                "needs_weather": last_intent in ("WEATHER_QUERY", "SEA_LEVEL_PRESSURE_QUERY", "MARINE_SAFETY_QUERY", "TRIP_QUERY"),
                "needs_pfz": last_intent in ("PFZ_QUERY", "MARINE_SAFETY_QUERY", "TRIP_QUERY"),
                "needs_hazard": last_intent in ("HAZARD_QUERY", "MARINE_SAFETY_QUERY", "TRIP_QUERY"),
                "needs_geofence": last_intent in ("BOUNDARY_QUERY", "MARINE_SAFETY_QUERY", "TRIP_QUERY"),
                "needs_risk": last_intent in ("MARINE_SAFETY_QUERY", "TRIP_QUERY"),
                "needs_ocean": last_intent in ("TIDE_QUERY", "WATER_LEVEL_QUERY", "MARINE_SAFETY_QUERY", "TRIP_QUERY"),
            }
            prior_mode = "specialist_card" if prior_qtype != "safety_check" else "safety_assessment"
            return prior_intent, prior_qtype, prior_needs, prior_mode
        elif last_intent.get("intent") or last_intent.get("intent_name"):
            prior_intent = last_intent.get("intent") or last_intent.get("intent_name") or "MARINE_SAFETY_QUERY"
            prior_qtype = last_intent.get("query_type", "general")
            prior_needs = {
                "needs_weather": last_intent.get("needs_weather", True),
                "needs_pfz": last_intent.get("needs_pfz", False),
                "needs_hazard": last_intent.get("needs_hazard", False),
                "needs_geofence": last_intent.get("needs_geofence", False),
                "needs_risk": last_intent.get("needs_risk", False),
                "needs_ocean": last_intent.get("needs_ocean", False),
            }
            prior_mode = last_intent.get("response_mode", "specialist_card")
            return prior_intent, prior_qtype, prior_needs, prior_mode

    # Default fallback: general marine safety check
    return "MARINE_SAFETY_QUERY", "general", {
        "needs_weather": True,
        "needs_pfz": True,
        "needs_hazard": True,
        "needs_geofence": True,
        "needs_risk": True,
        "needs_ocean": True,
    }, "DECISION_ASSESSMENT"


def _classify_query(text: str) -> tuple[str, dict[str, bool]]:
    """Backward compatibility wrapper for legacy callers."""
    _, q_type, needs, _ = classify_query_intent(text)
    return q_type, needs


# ---------------------------------------------------------------------------
# Invalid-location detection
# ---------------------------------------------------------------------------

_INVALID_LOCATION_HINTS = {
    "atlantis", "wakanda", "narnia", "gotham", "mordor", "hogwarts",
    "middle earth", "el dorado",
}


def _is_invalid_location(text: str) -> bool:
    """Return True if the text contains a clearly fictional place name."""
    text_lower = text.lower()
    return any(hint in text_lower for hint in _INVALID_LOCATION_HINTS)


# ---------------------------------------------------------------------------
# Multi-turn: compute changed_fields (Milestone 5)
# ---------------------------------------------------------------------------

def _compute_changed_fields(
    new_intent: ParsedIntent,
    last_intent: Optional[ParsedIntent],
) -> list[str]:
    """
    Compare new_intent against last_intent and return the list of
    ParsedIntent fields that changed.

    Returns an empty list if last_intent is None or if nothing changed.
    """
    if last_intent is None:
        return []

    changed: list[str] = []
    for field in ["location_name", "lat", "lon", "time_window", "time_start_utc", "time_end_utc"]:
        if new_intent.get(field) != last_intent.get(field):  # type: ignore[literal-required]
            changed.append(field)
    return changed


# ---------------------------------------------------------------------------
# Pydantic schema for Groq structured output (Milestone 6)
# ---------------------------------------------------------------------------

class ParsedIntentSchema(BaseModel):
    detected_language: Literal["en", "hi", "ta"] = Field(description="BCP-47 language code: 'en' for English, 'hi' for Hindi (including romanised), 'ta' for Tamil (including romanised)")
    location_name: Optional[str] = Field(description="Recognized location name exactly matching a gazetteer entry, or raw text if unknown. Null if missing.")
    lat: Optional[float] = Field(description="Latitude of the location from the gazetteer. Null if unknown.")
    lon: Optional[float] = Field(description="Longitude of the location from the gazetteer. Null if unknown.")
    time_window: Literal["now", "today", "tomorrow_morning", "tomorrow_evening", "next_24h"] = Field(description="The requested time window")
    query_type: Literal["safety_check", "pfz_lookup", "hazard_only", "weather_only", "risk_explanation", "general"] = Field(description="The type of query")
    needs_weather: bool = Field(description="Whether weather data is needed")
    needs_pfz: bool = Field(description="Whether PFZ data is needed")
    needs_hazard: bool = Field(description="Whether hazard data is needed")
    needs_geofence: bool = Field(description="Whether geofence data is needed")

# ---------------------------------------------------------------------------
# Public node function (LLM Path - Milestone 6)
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

def _get_location_clarification_text(lang: str) -> str:
    """Return clarification prompt when coastal location cannot be resolved."""
    if lang == "ta":
        return "நீங்கள் எந்த கடலோரப் பகுதி அல்லது துறைமுகத்தில் மீன்பிடிக்க திட்டமிட்டுள்ளீர்கள் என்று குறிப்பிடவும் (எ.கா. தூத்துக்குடி, ராமேஸ்வரம், கொச்சி, அல்லது விசாகப்பட்டினம்), அல்லது உங்கள் பகுதி தகவல்களை அறிய இருப்பிட அனுமதியை இயக்கவும்."
    elif lang == "hi":
        return "कृपया बताएं कि आप किस तटीय क्षेत्र या बंदरगाह के पास मछली पकड़ने की योजना बना रहे हैं (जैसे थूथुकुडी, रामेश्वरम, कोच्चि, या विशाखापट्टनम), अथवा अपना स्थान साझा करें ताकि मैं स्थानीय समुद्री सुरक्षा की जानकारी दे सकूँ।"
    else:
        return "I could not determine your coastal location. Please specify which harbour or coastal area you are planning to fish near (e.g., Thoothukudi, Rameswaram, Kochi, or Visakhapatnam), or enable device location access so I can assess conditions in your local waters."


def _get_relative_missing_clarification_text(lang: str) -> str:
    """Return prompt when user asks for 'here' / 'near me' but device location is unavailable."""
    if lang == "hi":
        return "आपकी क्वेरी में 'यहाँ' / 'मेरे पास' की स्थिति पूछी गई है, लेकिन डिवाइस स्थान की अनुमति उपलब्ध नहीं है। कृपया ब्राउज़र में स्थान अनुमति सक्षम करें अथवा अपने तटीय शहर (जैसे कोच्चि, मुंबई, थूथुकुडी) का नाम बताएं।"
    elif lang == "ta":
        return "உங்கள் வினவல் 'இங்கே' / 'அருகில்' உள்ள நிலவரத்தைக் கேட்கிறது, ஆனால் சாதன இருப்பிட அனுமதி கிடைக்கவில்லை. தயவுசெய்து சாதன இருப்பிட அனுமதியை வழங்கவும் அல்லது உங்கள் கடலோர நகரத்தைக் குறிப்பிடவும் (எ.கா. கொச்சி, மும்பை, தூத்துக்குடி)."
    else:
        return "You asked for conditions 'here', but device location access is not available. Please allow location access in your browser or specify your coastal town (e.g. Kochi, Mumbai, Thoothukudi)."


def _get_inland_clarification_text(
    lang: str,
    loc_name: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    dist_km: Optional[float] = None,
) -> str:
    """
    Return user-facing clarification prompt when location is inland (PRD §9, §35).
    """
    if dist_km is None and lat is not None and lon is not None:
        dist_km = distance_to_nearest_coast_km(lat, lon)

    dist_str = f"~{round(dist_km / 10) * 10:.0f}" if dist_km is not None else "~300+"
    display_name = loc_name if loc_name and not loc_name.startswith("Location (") else "your current location"

    if lang == "hi":
        return (
            f"📍 **{display_name}**\n\n"
            f"### मत्स्य पालन आकलन (Fishing Assessment)\n\n"
            f"आपकी वर्तमान स्थिति अंतर्देशीय है, इसलिए यहाँ समुद्री मत्स्य क्षेत्र और ज्वार की स्थिति लागू नहीं होती है।\n\n"
            f"• **निकटतम समुद्र तट**: {dist_str} किमी\n"
            f"• **मत्स्य क्षेत्र (PFZ)**: इस स्थान पर लागू नहीं\n"
            f"• **ज्वार-भाटा (Tides)**: इस स्थान पर लागू नहीं\n\n"
            f"मत्स्य पालन की स्थिति जांचने के लिए किसी तटीय स्थान (जैसे कोच्चि, मुंबई, चेन्नई, थूथुकुडी) का चयन करें।"
        )
    elif lang == "ta":
        return (
            f"📍 **{display_name}**\n\n"
            f"### மீன்பிடி மதிப்பீடு (Fishing Assessment)\n\n"
            f"உங்கள் தற்போதைய இருப்பிடம் உள்நாட்டுப் பகுதியாகும், எனவே அருகிலுள்ள கடல் மீன்பிடி மண்டலங்கள் மற்றும் அலை நிலைகள் இங்கு பொருந்தாது.\n\n"
            f"• **அருகிலுள்ள கடற்கரை**: {dist_str} கி.மீ\n"
            f"• **மீன்பிடி மண்டலங்கள்**: இந்த இடத்தில் பொருந்தாது\n"
            f"• **கடல் அலைகள் (Tides)**: இந்த இடத்தில் பொருந்தாது\n\n"
            f"மீன்பிடி நிலைமைகளை சரிபார்க்க ஒரு கடலோர இடத்தை (எ.கா. கொச்சி, சென்னை, தூத்துக்குடி) தேர்வு செய்யவும்."
        )
    else:
        return (
            f"📍 **{display_name}**\n\n"
            f"### Fishing Assessment\n\n"
            f"Marine fishing conditions aren't applicable to your current inland location.\n\n"
            f"• **Nearest coastline**: {dist_str} km\n"
            f"• **Fishing zones**: Not applicable at this location\n"
            f"• **Tides**: Not applicable at this location\n\n"
            f"Choose a coastal location (such as Kochi, Mumbai, or Thoothukudi) to check fishing conditions."
        )


def detect_and_parse(state: ORCAState) -> dict:
    """
    LangGraph node: detect language + parse intent from raw_query.
    Enforces V2 single-source-of-truth architecture using LocationResolver and SessionStore.
    """
    raw = state.get("raw_query", "").strip()
    last_intent = state.get("last_parsed_intent")
    conversation_history = list(state.get("conversation_history") or [])
    language_override = state.get("language_override")

    # 1. Authoritative Server-Side Session
    conv_id = state.get("conversation_id") or "default"
    session = get_or_create_session(conv_id)

    # 2. Extract Device Location
    device_loc: Optional[DeviceLocation] = state.get("device_location")
    if not device_loc and state.get("user_location"):
        u_loc = state["user_location"]
        if u_loc.get("lat") is not None and u_loc.get("lon") is not None:
            device_loc = {
                "lat": float(u_loc["lat"]),
                "lon": float(u_loc["lon"]),
                "accuracy": u_loc.get("accuracy"),
                "captured_at": u_loc.get("captured_at"),
                "permission_status": "granted",
            }
    if device_loc:
        session.device_location = device_loc
    elif session.device_location:
        device_loc = session.device_location

    # 3. Single-Source-of-Truth Location Resolution
    mode, q_loc, resolved = LocationResolver.resolve(raw, device_loc, session)

    # 4. Language Detection
    detected_lang = language_override if language_override in ("en", "hi", "ta") else _detect_language(raw)

    # 5. Temporal Extraction & Intent Classification
    _explicit_time = _extract_time_window(raw)
    _has_explicit_time = any(pat.search(raw) for pat, _ in _TIME_PATTERNS)
    if not _has_explicit_time and last_intent is not None and last_intent.get("time_window"):
        time_window = last_intent["time_window"]
    else:
        time_window = _explicit_time

    time_start_utc, time_end_utc = _resolve_time_range(time_window)
    intent_name, query_type, needs, response_mode = classify_query_intent(raw, last_intent)

    logger.info(
        "[DetectAndParse] Mode=%s Resolved=%s QLoc=%s Lang=%s Intent=%s QType=%s",
        mode, resolved.get("name") if resolved else None, q_loc.get("source"), detected_lang, intent_name, query_type
    )

    # 6. Early-Exit Case A: User asked for "here" / "near me" but device location is missing
    if mode == "DEVICE" and resolved is None:
        clarification_text = _get_relative_missing_clarification_text(detected_lang)
        unresolved_plan: AnswerPlan = {
            "intent": intent_name,
            "answer_type": "ClarificationCard",
            "requested_location": None,
            "resolved_location": None,
            "required_capabilities": [],
            "should_answer_directly": True,
            "should_explain_applicability": False,
            "should_show_data": False,
            "should_show_recommendation": False,
            "should_show_warning": False,
            "should_offer_followup": False,
        }
        unresolved_intent: ParsedIntent = {
            "location_name": None,
            "lat": None,
            "lon": None,
            "time_window": time_window,
            "time_start_utc": "",
            "time_end_utc": "",
            "query_type": query_type,
            "needs_weather": False,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": False,
            "location_status": "unresolved",
            "intent": intent_name,
            "response_mode": "CLARIFICATION",
            "answer_plan": unresolved_plan,
        }
        return {
            "detected_language": detected_lang,
            "parsed_intent": unresolved_intent,
            "device_location": device_loc,
            "query_location": q_loc,
            "resolved_location": None,
            "location_mode": mode,
            "changed_fields": [],
            "final_answer_text": clarification_text,
            "parse_method": "rule_based_fallback",
            "intent": intent_name,
            "response_mode": "CLARIFICATION",
            "answer_plan": unresolved_plan,
            "query_signature": {
                "intent": intent_name,
                "location": None,
                "time_context": time_window,
                "relevant_capabilities": [],
            },
        }

    # 7. Early-Exit Case B: Completely Unresolved Location
    if resolved is None:
        clarification_text = _get_location_clarification_text(detected_lang)
        unresolved_plan = {
            "intent": intent_name,
            "answer_type": "ClarificationCard",
            "requested_location": None,
            "resolved_location": None,
            "required_capabilities": [],
            "should_answer_directly": True,
            "should_explain_applicability": False,
            "should_show_data": False,
            "should_show_recommendation": False,
            "should_show_warning": False,
            "should_offer_followup": False,
        }
        unresolved_intent = {
            "location_name": None,
            "lat": None,
            "lon": None,
            "time_window": time_window,
            "time_start_utc": "",
            "time_end_utc": "",
            "query_type": query_type,
            "needs_weather": False,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": False,
            "location_status": "unresolved",
            "intent": intent_name,
            "response_mode": "CLARIFICATION",
            "answer_plan": unresolved_plan,
        }
        return {
            "detected_language": detected_lang,
            "parsed_intent": unresolved_intent,
            "device_location": device_loc,
            "query_location": q_loc,
            "resolved_location": None,
            "location_mode": mode,
            "changed_fields": [],
            "final_answer_text": clarification_text,
            "parse_method": "rule_based_fallback",
            "intent": intent_name,
            "response_mode": "CLARIFICATION",
            "answer_plan": unresolved_plan,
            "query_signature": {
                "intent": intent_name,
                "location": None,
                "time_context": time_window,
                "relevant_capabilities": [],
            },
        }

    # 8. Case C: Direct Location Query (Sections 7, 8, 18, 27)
    # Hard rule: LOCATION_QUERY completely bypasses marine synthesis and specialist agents
    if intent_name == "LOCATION_QUERY":
        loc_name = resolved["name"]
        lat = resolved["lat"]
        lon = resolved["lon"]
        is_coastal = resolved.get("coastal", False)

        if detected_lang == "hi":
            status_hi = "तटीय क्षेत्र" if is_coastal else "अंतर्देशीय क्षेत्र"
            loc_text = f"आप वर्तमान में **{loc_name}** में हैं। आपका अनुमानित स्थान {lat:.2f}°N, {lon:.2f}°E ({status_hi}) है।"
        elif detected_lang == "ta":
            status_ta = "கடலோர பகுதி" if is_coastal else "உள்நாட்டு பகுதி"
            loc_text = f"நீங்கள் தற்போது **{loc_name}** இல் உள்ளீர்கள். உங்கள் தோராயமான இருப்பிடம் {lat:.2f}°N, {lon:.2f}°E ({status_ta}) ஆகும்."
        else:
            status_en = "coastal" if is_coastal else "inland"
            loc_text = f"You're currently in **{loc_name}**. Your approximate location is {lat:.2f}°N, {lon:.2f}°E ({status_en} location)."

        loc_plan: AnswerPlan = {
            "intent": "LOCATION_QUERY",
            "intent_name": "LOCATION_QUERY",
            "answer_type": "LocationCard",
            "presentation_hint": "location_card",
            "primary_capability": "location_reporting",
            "required_capabilities": ["location_context"],
            "required_agents": [],
            "response_mode": "factual_direct",
            "location_scope": "device" if mode == "DEVICE" else "explicit",
            "evidence_needed": [],
            "requested_location": loc_name,
            "resolved_location": resolved,
            "should_answer_directly": True,
            "should_explain_applicability": False,
            "should_show_data": False,
            "should_show_recommendation": False,
            "should_show_warning": False,
            "should_offer_followup": True,
        }
        loc_intent: ParsedIntent = {
            "location_name": loc_name,
            "lat": lat,
            "lon": lon,
            "time_window": time_window,
            "time_start_utc": time_start_utc,
            "time_end_utc": time_end_utc,
            "query_type": "location_only",
            "needs_weather": False,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": False,
            "location_status": "coastal" if is_coastal else "inland",
            "distance_to_coast_km": resolved.get("nearest_coast_km", 0.0),
            "intent": "LOCATION_QUERY",
            "intent_name": "LOCATION_QUERY",
            "response_mode": "factual_direct",
            "answer_plan": loc_plan,
        }
        changed_fields = _compute_changed_fields(loc_intent, last_intent)
        new_history = (conversation_history + [{"role": "user", "content": raw}])[-config.MAX_CONVERSATION_TURNS:]
        query_sig = {
            "intent": "LOCATION_QUERY",
            "location": loc_name,
            "time_context": time_window,
            "relevant_capabilities": ["location_context"],
        }
        return {
            "detected_language": detected_lang,
            "parsed_intent": loc_intent,
            "device_location": device_loc,
            "query_location": q_loc,
            "resolved_location": resolved,
            "location_mode": mode,
            "changed_fields": changed_fields,
            "conversation_history": new_history,
            "last_parsed_intent": loc_intent,
            "final_answer_text": loc_text,
            "parse_method": "rule_based_fallback",
            "intent": "LOCATION_QUERY",
            "intent_name": "LOCATION_QUERY",
            "response_mode": "factual_direct",
            "answer_plan": loc_plan,
            "query_signature": query_sig,
        }

    # 9. Case D: Inland Location Handling (PRD §4–§9, §11, §28, §35, §54)
    if not resolved["coastal"]:
        dist_km = resolved.get("nearest_coast_km")

        # 9a. Local Tide / Water Level Query inland -> Scientific inapplicability explanation (Section 11, 28)
        if intent_name in ("WATER_LEVEL_QUERY", "TIDE_QUERY"):
            if detected_lang == "hi":
                inland_ocean_text = (
                    f"आपकी वर्तमान स्थिति **{resolved['name']}** अंतर्देशीय (inland) है, इसलिए यहाँ स्थानीय ज्वार-भाटा या समुद्री जल स्तर का माप लागू नहीं होता है।\n\n"
                    f"समुद्री जल स्तर या ज्वार की स्थिति देखने के लिए किसी तटीय बंदरगाह का नाम बताएं:\n"
                    f"• **मुंबई (Mumbai)**\n• **कोच्चि (Kochi)**\n• **चेन्नई (Chennai)**\n• **थूथुकुडी (Thoothukudi)**"
                )
            elif detected_lang == "ta":
                inland_ocean_text = (
                    f"உங்கள் தற்போதைய இருப்பிடம் **{resolved['name']}** உள்நாட்டுப் பகுதியாகும், எனவே உள்ளூர் கடல் அலை அல்லது கடல் நீர்மட்ட அளவீடு இங்கு பொருந்தாது.\n\n"
                    f"கடல் அலை அல்லது நீர்மட்ட தகவல்களை அறிய கடலோர இடத்தை முயற்சிக்கவும்:\n"
                    f"• **மும்பை (Mumbai)**\n• **கொச்சி (Kochi)**\n• **சென்னை (Chennai)**\n• **தூத்துக்குடி (Thoothukudi)**"
                )
            else:
                inland_ocean_text = (
                    f"Your current location is inland in **{resolved['name']}**, so a local tide or sea-water level measurement is not applicable here.\n\n"
                    f"{resolved['name']} is inland and has no direct marine tidal coastline. I can check the tide or water level for a coastal location instead.\n\n"
                    f"Try a coastal location:\n"
                    f"• **Mumbai**\n• **Kochi**\n• **Chennai**\n• **Thoothukudi**"
                )

            inland_ocean_plan: AnswerPlan = {
                "intent": intent_name,
                "intent_name": intent_name,
                "answer_type": "ApplicabilityCard",
                "presentation_hint": "applicability_card",
                "primary_capability": "inland_marine_explanation",
                "required_capabilities": ["ocean"],
                "required_agents": [],
                "response_mode": "applicability_explanation",
                "location_scope": "inland",
                "evidence_needed": [],
                "requested_location": resolved["name"],
                "resolved_location": resolved,
                "should_answer_directly": True,
                "should_explain_applicability": True,
                "should_show_data": False,
                "should_show_recommendation": False,
                "should_show_warning": False,
                "should_offer_followup": True,
            }
            inland_ocean_intent: ParsedIntent = {
                "location_name": resolved["name"],
                "lat": resolved["lat"],
                "lon": resolved["lon"],
                "time_window": time_window,
                "time_start_utc": "",
                "time_end_utc": "",
                "query_type": "ocean_tide",
                "needs_weather": False,
                "needs_pfz": False,
                "needs_hazard": False,
                "needs_geofence": False,
                "needs_risk": False,
                "needs_ocean": False,
                "location_status": "inland",
                "distance_to_coast_km": dist_km,
                "intent": intent_name,
                "intent_name": intent_name,
                "response_mode": "applicability_explanation",
                "answer_plan": inland_ocean_plan,
            }
            changed_fields = _compute_changed_fields(inland_ocean_intent, last_intent)
            new_history = (conversation_history + [{"role": "user", "content": raw}])[-config.MAX_CONVERSATION_TURNS:]
            query_sig = {
                "intent": intent_name,
                "location": resolved["name"],
                "time_context": time_window,
                "relevant_capabilities": ["ocean"],
            }
            return {
                "detected_language": detected_lang,
                "parsed_intent": inland_ocean_intent,
                "device_location": device_loc,
                "query_location": q_loc,
                "resolved_location": resolved,
                "location_mode": mode,
                "changed_fields": changed_fields,
                "conversation_history": new_history,
                "last_parsed_intent": inland_ocean_intent,
                "final_answer_text": inland_ocean_text,
                "parse_method": "rule_based_fallback",
                "intent": intent_name,
                "intent_name": intent_name,
                "response_mode": "applicability_explanation",
                "answer_plan": inland_ocean_plan,
                "query_signature": query_sig,
            }

        # 9b. Weather or MSL Pressure query inland -> Weather agent MUST run (PRD §8, Section 9)
        elif intent_name in ("WEATHER_QUERY", "SEA_LEVEL_PRESSURE_QUERY"):
            weather_plan: AnswerPlan = {
                "intent": intent_name,
                "intent_name": intent_name,
                "answer_type": "WeatherCard",
                "presentation_hint": "weather_card",
                "primary_capability": "weather_inquiry",
                "required_capabilities": ["weather"],
                "required_agents": ["weather_agent"],
                "response_mode": "specialist_card",
                "location_scope": "inland",
                "evidence_needed": ["temperature", "wind_speed", "surface_pressure"],
                "requested_location": resolved["name"],
                "resolved_location": resolved,
                "should_answer_directly": True,
                "should_explain_applicability": False,
                "should_show_data": True,
                "should_show_recommendation": False,
                "should_show_warning": False,
                "should_offer_followup": True,
            }
            inland_weather_intent: ParsedIntent = {
                "location_name": resolved["name"],
                "lat": resolved["lat"],
                "lon": resolved["lon"],
                "time_window": time_window,
                "time_start_utc": time_start_utc,
                "time_end_utc": time_end_utc,
                "query_type": "weather_only",
                "needs_weather": True,
                "needs_pfz": False,
                "needs_hazard": False,
                "needs_geofence": False,
                "needs_risk": False,
                "needs_ocean": False,
                "location_status": "inland",
                "distance_to_coast_km": dist_km,
                "intent": intent_name,
                "intent_name": intent_name,
                "response_mode": "specialist_card",
                "answer_plan": weather_plan,
            }
            changed_fields = _compute_changed_fields(inland_weather_intent, last_intent)
            new_history = (conversation_history + [{"role": "user", "content": raw}])[-config.MAX_CONVERSATION_TURNS:]
            query_sig = {
                "intent": intent_name,
                "location": resolved["name"],
                "time_context": time_window,
                "relevant_capabilities": ["weather"],
            }
            return {
                "detected_language": detected_lang,
                "parsed_intent": inland_weather_intent,
                "device_location": device_loc,
                "query_location": q_loc,
                "resolved_location": resolved,
                "location_mode": mode,
                "changed_fields": changed_fields,
                "conversation_history": new_history,
                "last_parsed_intent": inland_weather_intent,
                "parse_method": "rule_based_fallback",
                "intent": intent_name,
                "intent_name": intent_name,
                "response_mode": "specialist_card",
                "answer_plan": weather_plan,
                "query_signature": query_sig,
            }

        # 9c. PFZ Query inland -> Specific inapplicability (Section 26)
        elif intent_name == "PFZ_QUERY":
            dist_str = f"~{round(dist_km / 10) * 10:.0f}" if dist_km is not None else "~300+"
            if detected_lang == "hi":
                inland_pfz_text = (
                    f"आपकी वर्तमान स्थिति **{resolved['name']}** अंतर्देशीय (inland) है ({dist_str} किमी समुद्र तट से दूर)। यहाँ समुद्री मत्स्य संभावित क्षेत्र (PFZ) लागू नहीं होता है।\n\n"
                    f"मत्स्य संभावित क्षेत्र देखने के लिए किसी तटीय स्थान (जैसे कोच्चि, मुंबई, चेन्नई, थूथुकुडी) का चयन करें।"
                )
            elif detected_lang == "ta":
                inland_pfz_text = (
                    f"உங்கள் தற்போதைய இருப்பிடம் **{resolved['name']}** உள்நாட்டுப் பகுதியாகும் (கடற்கரையிலிருந்து {dist_str} கி.மீ). கடல் மீன்பிடி மண்டலங்கள் (PFZ) இங்கு பொருந்தாது.\n\n"
                    f"மீன்பிடி மண்டலங்களை சரிபார்க்க ஒரு கடலோர இடத்தை (எ.கா. கொச்சி, சென்னை, தூத்துக்குடி) தேர்வு செய்யவும்."
                )
            else:
                inland_pfz_text = (
                    f"You're currently in **{resolved['name']}**, which is inland ({dist_str} km from the nearest coast). Marine potential fishing zones (PFZ) are not applicable at this location.\n\n"
                    f"Choose a coastal location (such as Kochi, Mumbai, Chennai, or Thoothukudi) to check fishing zones."
                )
            inland_pfz_plan: AnswerPlan = {
                "intent": "PFZ_QUERY",
                "intent_name": "PFZ_QUERY",
                "answer_type": "ApplicabilityCard",
                "presentation_hint": "applicability_card",
                "primary_capability": "inland_marine_explanation",
                "required_capabilities": ["pfz"],
                "required_agents": [],
                "response_mode": "applicability_explanation",
                "location_scope": "inland",
                "evidence_needed": [],
                "requested_location": resolved["name"],
                "resolved_location": resolved,
                "should_answer_directly": True,
                "should_explain_applicability": True,
                "should_show_data": False,
                "should_show_recommendation": False,
                "should_show_warning": False,
                "should_offer_followup": True,
            }
            inland_pfz_intent: ParsedIntent = {
                "location_name": resolved["name"],
                "lat": resolved["lat"],
                "lon": resolved["lon"],
                "time_window": time_window,
                "time_start_utc": "",
                "time_end_utc": "",
                "query_type": "pfz_lookup",
                "needs_weather": False,
                "needs_pfz": False,
                "needs_hazard": False,
                "needs_geofence": False,
                "needs_risk": False,
                "needs_ocean": False,
                "location_status": "inland",
                "distance_to_coast_km": dist_km,
                "intent": "PFZ_QUERY",
                "intent_name": "PFZ_QUERY",
                "response_mode": "applicability_explanation",
                "answer_plan": inland_pfz_plan,
            }
            changed_fields = _compute_changed_fields(inland_pfz_intent, last_intent)
            new_history = (conversation_history + [{"role": "user", "content": raw}])[-config.MAX_CONVERSATION_TURNS:]
            query_sig = {
                "intent": "PFZ_QUERY",
                "location": resolved["name"],
                "time_context": time_window,
                "relevant_capabilities": ["pfz"],
            }
            return {
                "detected_language": detected_lang,
                "parsed_intent": inland_pfz_intent,
                "device_location": device_loc,
                "query_location": q_loc,
                "resolved_location": resolved,
                "location_mode": mode,
                "changed_fields": changed_fields,
                "conversation_history": new_history,
                "last_parsed_intent": inland_pfz_intent,
                "final_answer_text": inland_pfz_text,
                "parse_method": "rule_based_fallback",
                "intent": "PFZ_QUERY",
                "intent_name": "PFZ_QUERY",
                "response_mode": "applicability_explanation",
                "answer_plan": inland_pfz_plan,
                "query_signature": query_sig,
            }

        # 9d. General marine safety query inland (PRD §9, §35, §54)
        else:
            inland_text = _get_inland_clarification_text(
                detected_lang,
                resolved["name"],
                resolved["lat"],
                resolved["lon"],
                dist_km,
            )
            inland_safety_plan: AnswerPlan = {
                "intent": "MARINE_SAFETY_QUERY",
                "intent_name": "MARINE_SAFETY_QUERY",
                "answer_type": "ApplicabilityCard",
                "presentation_hint": "applicability_card",
                "primary_capability": "inland_marine_explanation",
                "required_capabilities": ["marine_safety"],
                "required_agents": [],
                "response_mode": "applicability_explanation",
                "location_scope": "inland",
                "evidence_needed": [],
                "requested_location": resolved["name"],
                "resolved_location": resolved,
                "should_answer_directly": True,
                "should_explain_applicability": True,
                "should_show_data": False,
                "should_show_recommendation": False,
                "should_show_warning": False,
                "should_offer_followup": True,
            }
            inland_safety_intent: ParsedIntent = {
                "location_name": resolved["name"],
                "lat": resolved["lat"],
                "lon": resolved["lon"],
                "time_window": time_window,
                "time_start_utc": "",
                "time_end_utc": "",
                "query_type": query_type,
                "needs_weather": False,
                "needs_pfz": False,
                "needs_hazard": False,
                "needs_geofence": False,
                "needs_risk": False,
                "needs_ocean": False,
                "location_status": "inland",
                "distance_to_coast_km": dist_km,
                "intent": intent_name,
                "intent_name": intent_name,
                "response_mode": "applicability_explanation",
                "answer_plan": inland_safety_plan,
            }
            query_sig = {
                "intent": intent_name,
                "location": resolved["name"],
                "time_context": time_window,
                "relevant_capabilities": ["marine_safety"],
            }
            return {
                "detected_language": detected_lang,
                "parsed_intent": inland_safety_intent,
                "device_location": device_loc,
                "query_location": q_loc,
                "resolved_location": resolved,
                "location_mode": mode,
                "changed_fields": [],
                "final_answer_text": inland_text,
                "parse_method": "rule_based_fallback",
                "intent": intent_name,
                "intent_name": intent_name,
                "response_mode": "applicability_explanation",
                "answer_plan": inland_safety_plan,
                "query_signature": query_sig,
            }

    # 10. Case E: Coastal Location Verified
    loc_name = resolved["name"]
    lat = resolved["lat"]
    lon = resolved["lon"]

    # Assign answer card type and capability requirements based on intent
    if intent_name in ("WEATHER_QUERY", "SEA_LEVEL_PRESSURE_QUERY"):
        card_type = "WeatherCard"
        pres_hint = "weather_card"
        required_caps = ["weather"]
        required_agents = ["weather_agent"]
        resp_mode_str = "specialist_card"
    elif intent_name in ("TIDE_QUERY", "WATER_LEVEL_QUERY"):
        card_type = "OceanCard"
        pres_hint = "ocean_card"
        required_caps = ["ocean"]
        required_agents = ["ocean_agent"]
        resp_mode_str = "specialist_card"
    elif intent_name == "PFZ_QUERY":
        card_type = "PFZCard"
        pres_hint = "pfz_card"
        required_caps = ["pfz"]
        required_agents = ["pfz_agent"]
        resp_mode_str = "specialist_card"
    elif intent_name == "HAZARD_QUERY":
        card_type = "HazardCard"
        pres_hint = "hazard_card"
        required_caps = ["hazard"]
        required_agents = ["hazard_agent"]
        resp_mode_str = "specialist_card"
    elif intent_name == "BOUNDARY_QUERY":
        card_type = "SafetyCard"
        pres_hint = "safety_card"
        required_caps = ["geofence"]
        required_agents = ["geofence_agent"]
        resp_mode_str = "specialist_card"
    elif intent_name == "RISK_EXPLANATION":
        card_type = "SafetyCard"
        pres_hint = "safety_card"
        required_caps = ["risk"]
        required_agents = ["risk_agent"]
        resp_mode_str = "safety_assessment"
    else:  # MARINE_SAFETY_QUERY / TRIP_QUERY / general
        card_type = "SafetyCard"
        pres_hint = "safety_card"
        required_caps = ["weather", "pfz", "ocean", "hazard", "geofence", "risk"]
        required_agents = ["weather_agent", "pfz_agent", "ocean_agent", "hazard_agent", "geofence_agent", "risk_agent"]
        resp_mode_str = "safety_assessment"

    coastal_plan: AnswerPlan = {
        "intent": intent_name,
        "intent_name": intent_name,
        "answer_type": card_type,
        "presentation_hint": pres_hint,
        "primary_capability": "marine_safety_assessment" if intent_name in ("MARINE_SAFETY_QUERY", "TRIP_QUERY") else card_type.lower(),
        "requested_location": loc_name,
        "resolved_location": resolved,
        "required_capabilities": required_caps,
        "required_agents": required_agents,
        "response_mode": resp_mode_str,
        "location_scope": "device" if mode == "DEVICE" else "inherited" if mode == "INHERITED" else "explicit",
        "evidence_needed": required_caps,
        "should_answer_directly": True,
        "should_explain_applicability": False,
        "should_show_data": True,
        "should_show_recommendation": intent_name in ("MARINE_SAFETY_QUERY", "TRIP_QUERY"),
        "should_show_warning": intent_name in ("MARINE_SAFETY_QUERY", "TRIP_QUERY", "HAZARD_QUERY"),
        "should_offer_followup": True,
    }

    new_intent: ParsedIntent = ParsedIntent(
        location_name=loc_name,
        lat=lat,
        lon=lon,
        time_window=time_window,
        time_start_utc=time_start_utc,
        time_end_utc=time_end_utc,
        query_type=query_type,
        needs_weather=needs.get("needs_weather", False),
        needs_pfz=needs.get("needs_pfz", False),
        needs_hazard=needs.get("needs_hazard", False),
        needs_geofence=needs.get("needs_geofence", False),
        needs_risk=needs.get("needs_risk", False),
        needs_ocean=needs.get("needs_ocean", False),
        location_status="coastal",
        distance_to_coast_km=resolved.get("nearest_coast_km", 0.0),
        intent=intent_name,
        intent_name=intent_name,
        response_mode=resp_mode_str,
        answer_plan=coastal_plan,
    )

    is_recheck = any(p.search(raw) for p in _RECHECK_PATTERNS)
    changed_fields = _compute_changed_fields(new_intent, last_intent)
    if is_recheck and "recheck" not in changed_fields:
        changed_fields.append("recheck")

    new_history = (conversation_history + [{"role": "user", "content": raw}])[
        -config.MAX_CONVERSATION_TURNS:
    ]
    query_sig = {
        "intent": intent_name,
        "location": loc_name,
        "time_context": time_window,
        "relevant_capabilities": required_caps,
    }

    return {
        "detected_language": detected_lang,
        "parsed_intent": new_intent,
        "device_location": device_loc,
        "query_location": q_loc,
        "resolved_location": resolved,
        "location_mode": mode,
        "changed_fields": changed_fields,
        "conversation_history": new_history,
        "parse_method": "rule_based_fallback",
        "intent": intent_name,
        "intent_name": intent_name,
        "response_mode": resp_mode_str,
        "answer_plan": coastal_plan,
        "query_signature": query_sig,
        "is_recheck": is_recheck,
    }

