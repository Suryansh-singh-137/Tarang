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
from graph.state import ORCAState, ParsedIntent
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

def _classify_query(text: str) -> tuple[str, dict[str, bool]]:
    """
    Returns (query_type, needs_flags_dict).
    query_type: "safety_check" | "pfz_lookup" | "hazard_only" | "weather_only" |
                "risk_explanation" | "general"
    """
    # Milestone 4: check for explanation intent first (takes priority)
    if _is_risk_explanation(text):
        return "risk_explanation", {
            "needs_weather": False,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
        }

    text_lower = text.lower()

    safety_keywords = {
        "safe", "safety", "jaana", "जाना", "surakshit", "सुरक्षित",
        "paadhukaappu", "risk", "danger", "खतरा", "hazard",
    }
    pfz_keywords = {
        "fish", "fishing", "pfz", "zone", "machli", "मछली", "meen",
        "மீன்", "மீன்பிடி", "machliyon", "fishing zone", "potential",
    }
    hazard_keywords = {
        "cyclone", "storm", "lightning", "warning", "alert", "dangerous",
        "tufan", "तूफान", "bijli", "बिजली", "advisory", "khatra",
    }
    weather_keywords = {
        "weather", "wave", "wind", "sea", "ocean", "condition", "forecast",
        "mausam", "lehar", "samudra", "தரங்கு", "அலை",
    }

    is_safety = bool(set(text_lower.split()) & safety_keywords) or any(
        kw in text_lower for kw in safety_keywords
    )
    is_pfz = bool(set(text_lower.split()) & pfz_keywords) or any(
        kw in text_lower for kw in pfz_keywords
    )
    is_hazard = bool(set(text_lower.split()) & hazard_keywords) or any(
        kw in text_lower for kw in hazard_keywords
    )
    is_weather = bool(set(text_lower.split()) & weather_keywords) or any(
        kw in text_lower for kw in weather_keywords
    )

    # "fishing ke liye jaana safe hai?" → both PFZ and safety
    if is_safety and is_pfz:
        return "safety_check", {
            "needs_weather": True,
            "needs_pfz": True,
            "needs_hazard": True,
            "needs_geofence": True,
            "needs_risk": True,
            "needs_ocean": True,
        }
    elif is_safety:
        return "safety_check", {
            "needs_weather": True,
            "needs_pfz": False,
            "needs_hazard": True,
            "needs_geofence": True,
            "needs_risk": True,
            "needs_ocean": True,
        }
    elif is_pfz:
        # Pure PFZ query — no weather/hazard/risk needed
        return "pfz_lookup", {
            "needs_weather": False,
            "needs_pfz": True,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": False,
        }
    elif is_hazard:
        return "hazard_only", {
            "needs_weather": True,
            "needs_pfz": False,
            "needs_hazard": True,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": False,
        }
    elif is_weather:
        return "weather_only", {
            "needs_weather": True,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
            "needs_ocean": True,
        }
    else:
        return "general", {
            "needs_weather": True,
            "needs_pfz": True,
            "needs_hazard": True,
            "needs_geofence": True,
            "needs_risk": True,
            "needs_ocean": True,
        }


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
    query_type, needs = _classify_query(raw)

    # Check for tides / water level keywords
    raw_lower = raw.lower()
    needs_ocean = any(w in raw_lower for w in [
        "tide", "tides", "water level", "sea level", "jwar", "bhata", "alahi", "high tide", "low tide"
    ])
    needs["needs_ocean"] = needs_ocean

    logger.info(
        "[DetectAndParse] Mode=%s Resolved=%s QLoc=%s Lang=%s",
        mode, resolved.get("name") if resolved else None, q_loc.get("source"), detected_lang
    )

    # 6. Early-Exit Case A: User asked for "here" / "near me" but device location is missing
    if mode == "DEVICE" and resolved is None:
        clarification_text = _get_relative_missing_clarification_text(detected_lang)
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
        }

    # 7. Early-Exit Case B: Completely Unresolved Location
    if resolved is None:
        clarification_text = _get_location_clarification_text(detected_lang)
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
        }

    # 8. Applicability Check (PRD §4–§9)
    from location.applicability import check_applicability
    app_res = check_applicability(resolved, raw)

    if not resolved["coastal"]:
        dist_km = resolved.get("nearest_coast_km")

        # PRD §8: If user specifically asked for weather inland ("What's the weather here in Delhi?")
        # Weather agent MUST run!
        raw_lower = raw.lower()
        is_explicit_weather = (
            query_type in ("weather_only", "weather")
            or any(w in raw_lower for w in ["weather", "mausam", "வானிலை", "temperature", "wind"])
        ) and not any(w in raw_lower for w in ["fish", "machli", "zone", "pfz", "tide", "jwar", "மீன்"])

        if is_explicit_weather:
            # Allow weather agent to run for inland location!
            inland_intent: ParsedIntent = ParsedIntent(
                location_name=resolved["name"],
                lat=resolved["lat"],
                lon=resolved["lon"],
                time_window=time_window,
                time_start_utc=time_start_utc,
                time_end_utc=time_end_utc,
                query_type="weather_only",
                needs_weather=True,
                needs_pfz=False,
                needs_hazard=False,
                needs_geofence=False,
                needs_risk=False,
                needs_ocean=False,
                location_status="inland",
                distance_to_coast_km=dist_km,
            )
            changed_fields = _compute_changed_fields(inland_intent, last_intent)
            new_history = (conversation_history + [{"role": "user", "content": raw}])[
                -config.MAX_CONVERSATION_TURNS:
            ]
            return {
                "detected_language": detected_lang,
                "parsed_intent": inland_intent,
                "device_location": device_loc,
                "query_location": q_loc,
                "resolved_location": resolved,
                "location_mode": mode,
                "changed_fields": changed_fields,
                "conversation_history": new_history,
                "last_parsed_intent": inland_intent,
                "parse_method": "rule_based_fallback",
            }
        else:
            # User asked about marine fishing / trip / ocean at an inland location (PRD §9, §35, §54)
            inland_text = _get_inland_clarification_text(
                detected_lang,
                resolved["name"],
                resolved["lat"],
                resolved["lon"],
                dist_km,
            )
            inland_intent: ParsedIntent = {
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
            }
            return {
                "detected_language": detected_lang,
                "parsed_intent": inland_intent,
                "device_location": device_loc,
                "query_location": q_loc,
                "resolved_location": resolved,
                "location_mode": mode,
                "changed_fields": [],
                "final_answer_text": inland_text,
                "parse_method": "rule_based_fallback",
            }

    # 9. Case D: Coastal Location Verified
    loc_name = resolved["name"]
    lat = resolved["lat"]
    lon = resolved["lon"]

    # Special case: risk explanation
    if query_type == "risk_explanation":
        needs_weather = False
        needs_pfz = False
        needs_hazard = False
        needs_geofence = False
        needs_risk = False
    else:
        needs_weather = needs.get("needs_weather", True)
        needs_pfz = needs.get("needs_pfz", True)
        needs_hazard = needs.get("needs_hazard", True)
        needs_geofence = needs.get("needs_geofence", True)
        needs_risk = needs.get("needs_risk", True)

    new_intent: ParsedIntent = ParsedIntent(
        location_name=loc_name,
        lat=lat,
        lon=lon,
        time_window=time_window,
        time_start_utc=time_start_utc,
        time_end_utc=time_end_utc,
        query_type=query_type,
        needs_weather=needs_weather,
        needs_pfz=needs_pfz,
        needs_hazard=needs_hazard,
        needs_geofence=needs_geofence,
        needs_risk=needs_risk,
        needs_ocean=needs_ocean,
        location_status="coastal",
        distance_to_coast_km=resolved.get("nearest_coast_km", 0.0),
    )

    changed_fields = _compute_changed_fields(new_intent, last_intent)
    new_history = (conversation_history + [{"role": "user", "content": raw}])[
        -config.MAX_CONVERSATION_TURNS:
    ]

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
    }

