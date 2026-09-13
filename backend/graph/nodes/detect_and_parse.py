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

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal
import logging

from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

import config
from graph.state import ORCAState, ParsedIntent
from tools.location_resolver import resolve_location, GAZETTEER, location_is_coastal

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
        }
    elif is_safety:
        return "safety_check", {
            "needs_weather": True,
            "needs_pfz": False,
            "needs_hazard": True,
            "needs_geofence": True,
            "needs_risk": True,
        }
    elif is_pfz:
        # Pure PFZ query — no weather/hazard/risk needed
        return "pfz_lookup", {
            "needs_weather": False,
            "needs_pfz": True,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
        }
    elif is_hazard:
        return "hazard_only", {
            "needs_weather": True,
            "needs_pfz": False,
            "needs_hazard": True,
            "needs_geofence": False,
            "needs_risk": False,
        }
    elif is_weather:
        return "weather_only", {
            "needs_weather": True,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
        }
    else:
        return "general", {
            "needs_weather": True,
            "needs_pfz": True,
            "needs_hazard": True,
            "needs_geofence": True,
            "needs_risk": True,
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


def _get_inland_clarification_text(lang: str, loc_name: Optional[str] = None) -> str:
    """Return clarification prompt when location is determined to be inland."""
    name_str = f"'{loc_name}'" if loc_name else "Your current location"
    if lang == "ta":
        return f"{name_str} கடற்கரை இல்லாத உள்நாட்டு பகுதியாக தெரிகிறது. தயவுசெய்து ஒரு இந்திய கடலோர பகுதியை (எ.கா. தூத்துக்குடி, சென்னை, மும்பை) குறிப்பிடவும், நான் உங்களுக்கான கடல் மற்றும் பாதுகாப்பு தகவல்களை வழங்குகிறேன்."
    elif lang == "hi":
        return f"{name_str} एक अंतर्देशीय (गैर-तटीय) स्थान प्रतीत होता है। कृपया किसी भारतीय तटीय स्थान (जैसे थूथुकुडी, चेन्नई, मुंबई) का नाम बताएं, और मैं आपके लिए समुद्री और सुरक्षा जानकारी प्राप्त करूँगा।"
    else:
        return f"The location {name_str} appears to be inland. Please provide an Indian coastal location (e.g. Thoothukudi, Chennai, Mumbai) and I will retrieve marine and safety information for you."

def detect_and_parse(state: ORCAState) -> dict:
    """
    LangGraph node: detect language + parse intent from raw_query using Groq LLM.
    Falls back to deterministic rule-based parsing on failure/timeout.
    """
    raw = state["raw_query"]
    last_intent = state.get("last_parsed_intent")
    conversation_history = list(state.get("conversation_history") or [])
    language_override = state.get("language_override")

    if not config.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set. Falling back to rule-based parser.")
        return _fallback_parse(state)

    # Prepare context
    history_text = "\n".join([f"{t['role']}: {t['content']}" for t in conversation_history])
    gazetteer_list = ", ".join([f"{k.title()} ({v[0]}, {v[1]})" for k, v in GAZETTEER.items()])
    
    system_prompt = f"""You are a marine safety intent parser. Extract structured intent from the user query.
The query may be in English, Hindi (including Romanised), or Tamil (including Romanised).
    
RULES:
1. Resolve location names to lat/lon ONLY from this gazetteer list: {gazetteer_list}. 
   If the location isn't in this list, return location_name as the raw extracted text and leave lat/lon null.
2. If there is conversation history, inherit the location and/or time_window from the last intent if they are not explicitly changed in the new query.
3. Classify the query_type accurately. "risk_explanation" is when asking WHY the risk score is what it is (explain the factors).

Last Intent Context:
{last_intent if last_intent else 'None'}

Conversation History:
{history_text if history_text else 'None'}
"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{query}")
    ])
    
    llm = ChatGroq(
        model=config.GROQ_MODEL_FAST, 
        api_key=config.GROQ_API_KEY, 
        temperature=0, 
        max_retries=0, 
        timeout=4.0
    )
    structured_llm = llm.with_structured_output(ParsedIntentSchema)
    chain = prompt | structured_llm
    
    try:
        res: ParsedIntentSchema = chain.invoke({"query": raw})
        
        # Determine language: manual override takes precedence over LLM auto-detection
        detected_lang = language_override if language_override in ("en", "hi", "ta") else res.detected_language

        # We must fill needs_risk based on query_type for backward compatibility in the pipeline
        needs_risk = res.query_type == "safety_check"
        
        # For explanations, handle explicitly
        if res.query_type == "risk_explanation":
            time_start_utc, time_end_utc = _resolve_time_range(res.time_window)
            
            loc_name = res.location_name
            lat = res.lat
            lon = res.lon

            if loc_name is None and last_intent is not None and last_intent.get("location_name"):
                loc_name = last_intent.get("location_name")
                lat = last_intent.get("lat")
                lon = last_intent.get("lon")

            user_loc = state.get("user_location")
            if (loc_name is None or lat is None or lon is None) and user_loc and user_loc.get("lat") is not None and user_loc.get("lon") is not None:
                lat = float(user_loc["lat"])
                lon = float(user_loc["lon"])
                loc_name = user_loc.get("name") or f"Location ({lat:.2f}°N, {lon:.2f}°E)"

            if loc_name is None or lat is None or lon is None:
                clarification_text = _get_location_clarification_text(detected_lang)
                unresolved_intent = ParsedIntent(
                    location_name=None,
                    lat=None,
                    lon=None,
                    time_window=res.time_window,
                    time_start_utc="",
                    time_end_utc="",
                    query_type="general",
                    needs_weather=False,
                    needs_pfz=False,
                    needs_hazard=False,
                    needs_geofence=False,
                    needs_risk=False,
                )
                return {
                    "detected_language": detected_lang,
                    "parsed_intent": unresolved_intent,
                    "changed_fields": [],
                    "final_answer_text": clarification_text,
                    "parse_method": "llm",
                }

            parsed_intent = ParsedIntent(
                location_name=loc_name,
                lat=lat,
                lon=lon,
                time_window=res.time_window,
                time_start_utc=time_start_utc,
                time_end_utc=time_end_utc,
                query_type="risk_explanation",
                needs_weather=False,
                needs_pfz=False,
                needs_hazard=False,
                needs_geofence=False,
                needs_risk=False,
            )
            
            new_history = (conversation_history + [{"role": "user", "content": raw}])[-config.MAX_CONVERSATION_TURNS:]
            return {
                "detected_language": detected_lang,
                "parsed_intent": parsed_intent,
                "changed_fields": [],
                "conversation_history": new_history,
                "parse_method": "llm",
            }
            
        # Detect invalid location logic
        if res.location_name and res.lat is None and res.lon is None:
            # We matched the text but it wasn't in gazetteer. Let's use the Tier 2 geocoder.
            loc_result = resolve_location(res.location_name)
            
            if loc_result["status"] == "success":
                res.location_name = loc_result["location_name"]
                res.lat = loc_result["latitude"]
                res.lon = loc_result["longitude"]
            elif loc_result["status"] == "inland":
                invalid_intent = ParsedIntent(
                    location_name="Unknown", lat=None, lon=None,
                    time_window=res.time_window, time_start_utc="", time_end_utc="",
                    query_type="general", needs_weather=False, needs_pfz=False,
                    needs_hazard=False, needs_geofence=False, needs_risk=False,
                )
                return {
                    "detected_language": detected_lang,
                    "parsed_intent": invalid_intent,
                    "changed_fields": [],
                    "final_answer_text": f"The location '{res.location_name}' appears to be inland. Please provide an Indian coastal location (e.g. Thoothukudi, Chennai, Mumbai) and I will retrieve marine and safety information for you.",
                    "parse_method": "llm",
                }
            else:
                invalid_intent = ParsedIntent(
                    location_name="Unknown", lat=None, lon=None,
                    time_window=res.time_window, time_start_utc="", time_end_utc="",
                    query_type="general", needs_weather=False, needs_pfz=False,
                    needs_hazard=False, needs_geofence=False, needs_risk=False,
                )
                return {
                    "detected_language": detected_lang,
                    "parsed_intent": invalid_intent,
                    "changed_fields": [],
                    "final_answer_text": "I was unable to identify a recognised coastal location in your query. Please provide an Indian coastal location (e.g. Thoothukudi, Chennai, Mumbai) and I will retrieve marine and safety information for you.",
                    "parse_method": "llm",
                }

        # Resolve explicit UTC time range
        time_start_utc, time_end_utc = _resolve_time_range(res.time_window)

        # Location resolution: extracted from query -> multi-turn last_intent -> user_location
        loc_name = res.location_name
        lat = res.lat
        lon = res.lon

        if loc_name is None and last_intent is not None and last_intent.get("location_name"):
            loc_name = last_intent.get("location_name")
            lat = last_intent.get("lat")
            lon = last_intent.get("lon")

        user_loc = state.get("user_location")
        if (loc_name is None or lat is None or lon is None) and user_loc and user_loc.get("lat") is not None and user_loc.get("lon") is not None:
            lat = float(user_loc["lat"])
            lon = float(user_loc["lon"])
            loc_name = user_loc.get("name") or f"Location ({lat:.2f}°N, {lon:.2f}°E)"

        # Coastal-validity check on all resolved coordinates (browser geolocation or text)
        if lat is not None and lon is not None:
            is_coastal, verified_name, meta = location_is_coastal(lat, lon, loc_name)
            if not is_coastal:
                logger.info("[Location] Coordinates (%.4f, %.4f) '%s' flagged as inland: %s", lat, lon, loc_name, meta)
                inland_intent = ParsedIntent(
                    location_name=verified_name or loc_name or "Inland",
                    lat=None,
                    lon=None,
                    time_window=res.time_window,
                    time_start_utc="",
                    time_end_utc="",
                    query_type="general",
                    needs_weather=False,
                    needs_pfz=False,
                    needs_hazard=False,
                    needs_geofence=False,
                    needs_risk=False,
                )
                inland_text = _get_inland_clarification_text(detected_lang, verified_name or loc_name)
                return {
                    "detected_language": detected_lang,
                    "parsed_intent": inland_intent,
                    "changed_fields": [],
                    "final_answer_text": inland_text,
                    "parse_method": "llm",
                }
            loc_name = verified_name or loc_name

        # If STILL no resolvable location: DO NOT DEFAULT TO THOOTHUKUDI!
        if loc_name is None or lat is None or lon is None:
            unresolved_intent = ParsedIntent(
                location_name=None,
                lat=None,
                lon=None,
                time_window=res.time_window,
                time_start_utc="",
                time_end_utc="",
                query_type="general",
                needs_weather=False,
                needs_pfz=False,
                needs_hazard=False,
                needs_geofence=False,
                needs_risk=False,
            )
            clarification_text = _get_location_clarification_text(detected_lang)
            return {
                "detected_language": detected_lang,
                "parsed_intent": unresolved_intent,
                "changed_fields": [],
                "final_answer_text": clarification_text,
                "parse_method": "llm",
            }

        new_intent = ParsedIntent(
            location_name=loc_name,
            lat=lat,
            lon=lon,
            time_window=res.time_window,
            time_start_utc=time_start_utc,
            time_end_utc=time_end_utc,
            query_type=res.query_type, # type: ignore
            needs_weather=res.needs_weather,
            needs_pfz=res.needs_pfz,
            needs_hazard=res.needs_hazard,
            needs_geofence=res.needs_geofence,
            needs_risk=needs_risk,
        )

        changed_fields = _compute_changed_fields(new_intent, last_intent)
        new_history = (conversation_history + [{"role": "user", "content": raw}])[-config.MAX_CONVERSATION_TURNS:]

        return {
            "detected_language": detected_lang,
            "parsed_intent": new_intent,
            "changed_fields": changed_fields,
            "conversation_history": new_history,
            "parse_method": "llm",
        }
        
    except Exception as exc:
        logger.warning(f"Groq parse failed ({exc}), falling back to rule-based parser.")
        return _fallback_parse(state)


# ---------------------------------------------------------------------------
# Fallback rule-based parsing (Pre-M6 logic)
# ---------------------------------------------------------------------------

def _fallback_parse(state: ORCAState) -> dict:
    """
    LangGraph node: detect language + parse intent from raw_query.
    Returns a partial state dict to merge into ORCAState.

    Milestone 2:
      - Resolves time_window → explicit UTC time range
      - Flags invalid locations rather than silently defaulting

    Milestone 4:
      - Classifies "risk_explanation" queries before other checks

    Milestone 5:
      - Inherits location/time from last_parsed_intent when not explicitly provided
      - Produces changed_fields to enable selective agent re-invocation
      - Caps conversation_history to config.MAX_CONVERSATION_TURNS
    """
    raw = state["raw_query"]
    language_override = state.get("language_override")
    detected_language = language_override if language_override in ("en", "hi", "ta") else _detect_language(raw)
    
    loc_result = resolve_location(raw)
    location_name = loc_result["location_name"] if loc_result["status"] == "success" else None
    lat = loc_result["latitude"] if loc_result["status"] == "success" else None
    lon = loc_result["longitude"] if loc_result["status"] == "success" else None
    loc_status = loc_result["status"]
    
    time_window = _extract_time_window(raw)
    query_type, needs = _classify_query(raw)

    # ---- Milestone 5: Get multi-turn context ----
    last_intent: Optional[ParsedIntent] = state.get("last_parsed_intent")
    conversation_history = list(state.get("conversation_history") or [])

    # ---- Milestone 4: Handle risk_explanation early ----
    # For explanations, we reuse the last known location if no new one given
    if query_type == "risk_explanation":
        if location_name is None and last_intent is not None:
            location_name = last_intent.get("location_name")
            lat = last_intent.get("lat")
            lon = last_intent.get("lon")

        # Check user geolocation
        user_loc = state.get("user_location")
        if (location_name is None or lat is None or lon is None) and user_loc and user_loc.get("lat") is not None and user_loc.get("lon") is not None:
            lat = float(user_loc["lat"])
            lon = float(user_loc["lon"])
            location_name = user_loc.get("name") or f"Location ({lat:.2f}°N, {lon:.2f}°E)"

        if lat is not None and lon is not None:
            is_coastal, verified_name, meta = location_is_coastal(lat, lon, location_name)
            if not is_coastal:
                inland_intent: ParsedIntent = {
                    "location_name": verified_name or location_name or "Inland",
                    "lat": None,
                    "lon": None,
                    "time_window": time_window,
                    "time_start_utc": "",
                    "time_end_utc": "",
                    "query_type": "general",
                    "needs_weather": False,
                    "needs_pfz": False,
                    "needs_hazard": False,
                    "needs_geofence": False,
                    "needs_risk": False,
                }
                inland_text = _get_inland_clarification_text(detected_language, verified_name or location_name)
                return {
                    "detected_language": detected_language,
                    "parsed_intent": inland_intent,
                    "changed_fields": [],
                    "final_answer_text": inland_text,
                    "parse_method": "rule_based_fallback",
                }
            location_name = verified_name or location_name

        if location_name is None or lat is None or lon is None:
            clarification_text = _get_location_clarification_text(detected_language)
            invalid_intent: ParsedIntent = {
                "location_name": None,
                "lat": None,
                "lon": None,
                "time_window": time_window,
                "time_start_utc": "",
                "time_end_utc": "",
                "query_type": "general",
                "needs_weather": False,
                "needs_pfz": False,
                "needs_hazard": False,
                "needs_geofence": False,
                "needs_risk": False,
            }
            return {
                "detected_language": detected_language,
                "parsed_intent": invalid_intent,
                "changed_fields": [],
                "final_answer_text": clarification_text,
                "parse_method": "rule_based_fallback",
            }

        # Use last time_window if not explicitly provided in this message
        _explicit_time = _extract_time_window(raw)
        if _explicit_time == "next_24h" and last_intent is not None:
            # "next_24h" is the default — if last intent had a real window, keep it
            time_window = last_intent.get("time_window", "next_24h")
        else:
            time_window = _explicit_time

        time_start_utc, time_end_utc = _resolve_time_range(time_window)

        parsed_intent: ParsedIntent = ParsedIntent(
            location_name=location_name,
            lat=lat,
            lon=lon,
            time_window=time_window,
            time_start_utc=time_start_utc,
            time_end_utc=time_end_utc,
            query_type="risk_explanation",
            **needs,  # type: ignore[misc]
        )

        # Cap conversation history
        new_history = (conversation_history + [{"role": "user", "content": raw}])[
            -config.MAX_CONVERSATION_TURNS:
        ]

        return {
            "detected_language": detected_language,
            "parsed_intent": parsed_intent,
            "changed_fields": [],
            "conversation_history": new_history,
            "parse_method": "rule_based_fallback",
        }

    # ---- Detect fictional/invalid locations ----
    if loc_status == "inland":
        invalid_intent: ParsedIntent = {
            "location_name": "Unknown",
            "lat": None,
            "lon": None,
            "time_window": time_window,
            "time_start_utc": "",
            "time_end_utc": "",
            "query_type": "general",
            "needs_weather": False,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
        }
        return {
            "detected_language": detected_language,
            "parsed_intent": invalid_intent,
            "changed_fields": [],
            "final_answer_text": (
                "The requested location appears to be inland. "
                "Please provide an Indian coastal location (e.g. Thoothukudi, Chennai, Mumbai) "
                "and I will retrieve marine and safety information for you."
            ),
            "parse_method": "rule_based_fallback",
        }
        
    if _is_invalid_location(raw) and location_name is None:
        invalid_intent: ParsedIntent = {
            "location_name": "Unknown",
            "lat": None,
            "lon": None,
            "time_window": time_window,
            "time_start_utc": "",
            "time_end_utc": "",
            "query_type": "general",
            "needs_weather": False,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
        }
        return {
            "detected_language": detected_language,
            "parsed_intent": invalid_intent,
            "changed_fields": [],
            "final_answer_text": (
                "I was unable to identify a recognised coastal location in your query. "
                "Please provide an Indian coastal location (e.g. Thoothukudi, Chennai, Mumbai) "
                "and I will retrieve marine and safety information for you."
            ),
            "parse_method": "rule_based_fallback",
        }

    # ---- Milestone 5: Inherit location from previous turn if not in this query ----
    if location_name is None and last_intent is not None:
        location_name = last_intent.get("location_name")
        lat = last_intent.get("lat")
        lon = last_intent.get("lon")

    # If still no location, check browser geolocation in state
    user_loc = state.get("user_location")
    if (location_name is None or lat is None or lon is None) and user_loc and user_loc.get("lat") is not None and user_loc.get("lon") is not None:
        lat = float(user_loc["lat"])
        lon = float(user_loc["lon"])
        location_name = user_loc.get("name") or f"Location ({lat:.2f}°N, {lon:.2f}°E)"

    # Coastal validity check on resolved coordinates
    if lat is not None and lon is not None:
        is_coastal, verified_name, meta = location_is_coastal(lat, lon, location_name)
        if not is_coastal:
            logger.info("[Location] Fallback: coordinates (%.4f, %.4f) '%s' flagged inland: %s", lat, lon, location_name, meta)
            inland_intent: ParsedIntent = {
                "location_name": verified_name or location_name or "Inland",
                "lat": None,
                "lon": None,
                "time_window": time_window,
                "time_start_utc": "",
                "time_end_utc": "",
                "query_type": "general",
                "needs_weather": False,
                "needs_pfz": False,
                "needs_hazard": False,
                "needs_geofence": False,
                "needs_risk": False,
            }
            inland_text = _get_inland_clarification_text(detected_language, verified_name or location_name)
            return {
                "detected_language": detected_language,
                "parsed_intent": inland_intent,
                "changed_fields": [],
                "final_answer_text": inland_text,
                "parse_method": "rule_based_fallback",
            }
        location_name = verified_name or location_name

    # If still no location: DO NOT DEFAULT TO THOOTHUKUDI!
    if location_name is None or lat is None or lon is None:
        unresolved_intent: ParsedIntent = {
            "location_name": None,
            "lat": None,
            "lon": None,
            "time_window": time_window,
            "time_start_utc": "",
            "time_end_utc": "",
            "query_type": "general",
            "needs_weather": False,
            "needs_pfz": False,
            "needs_hazard": False,
            "needs_geofence": False,
            "needs_risk": False,
        }
        clarification_text = _get_location_clarification_text(detected_language)
        return {
            "detected_language": detected_language,
            "parsed_intent": unresolved_intent,
            "changed_fields": [],
            "final_answer_text": clarification_text,
            "parse_method": "rule_based_fallback",
        }

    # ---- Milestone 5: Inherit time_window from last turn if this query uses default ----
    # Only inherit if the new query has no explicit temporal signal
    _explicit_time = _extract_time_window(raw)
    _has_explicit_time = any(pat.search(raw) for pat, _ in _TIME_PATTERNS)
    if not _has_explicit_time and last_intent is not None:
        time_window = last_intent.get("time_window", "next_24h")
    else:
        time_window = _explicit_time

    # Resolve explicit UTC time range
    time_start_utc, time_end_utc = _resolve_time_range(time_window)

    new_intent = ParsedIntent(
        location_name=location_name,
        lat=lat,
        lon=lon,
        time_window=time_window,
        time_start_utc=time_start_utc,
        time_end_utc=time_end_utc,
        query_type=query_type,
        **needs,  # type: ignore[misc]
    )

    # ---- Compute changed_fields (M5) ----
    changed_fields = _compute_changed_fields(new_intent, last_intent)

    # Cap conversation history
    new_history = (conversation_history + [{"role": "user", "content": raw}])[
        -config.MAX_CONVERSATION_TURNS:
    ]

    return {
        "detected_language": detected_language,
        "parsed_intent": new_intent,
        "changed_fields": changed_fields,
        "conversation_history": new_history,
        "parse_method": "rule_based_fallback",
    }
