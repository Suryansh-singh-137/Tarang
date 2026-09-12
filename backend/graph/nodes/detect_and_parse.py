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
# Static coastal gazetteer (Indian coastal towns + common PFZ region names)
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

def detect_and_parse(state: ORCAState) -> dict:
    """
    LangGraph node: detect language + parse intent from raw_query using Groq LLM.
    Falls back to deterministic rule-based parsing on failure/timeout.
    """
    raw = state["raw_query"]
    last_intent = state.get("last_parsed_intent")
    conversation_history = list(state.get("conversation_history") or [])

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
        
        # We must fill needs_risk based on query_type for backward compatibility in the pipeline
        needs_risk = res.query_type == "safety_check"
        
        # For explanations, handle explicitly
        if res.query_type == "risk_explanation":
            time_start_utc, time_end_utc = _resolve_time_range(res.time_window)
            
            parsed_intent = ParsedIntent(
                location_name=res.location_name or "Thoothukudi",
                lat=res.lat or GAZETTEER["thoothukudi"][0],
                lon=res.lon or GAZETTEER["thoothukudi"][1],
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
                "detected_language": res.detected_language,
                "parsed_intent": parsed_intent,
                "changed_fields": [],
                "conversation_history": new_history,
                "parse_method": "llm",
            }
            
        # Detect invalid location logic
        if res.location_name and res.lat is None and res.lon is None:
            # We matched the text but it wasn't in gazetteer
            invalid_intent = ParsedIntent(
                location_name="Unknown", lat=None, lon=None,
                time_window=res.time_window, time_start_utc="", time_end_utc="",
                query_type="general", needs_weather=False, needs_pfz=False,
                needs_hazard=False, needs_geofence=False, needs_risk=False,
            )
            return {
                "detected_language": res.detected_language,
                "parsed_intent": invalid_intent,
                "changed_fields": [],
                "final_answer_text": "I was unable to identify a recognised coastal location in your query. Please provide an Indian coastal location (e.g. Thoothukudi, Chennai, Kochi) and I will retrieve marine and safety information for you.",
                "parse_method": "llm",
            }

        # Resolve explicit UTC time range
        time_start_utc, time_end_utc = _resolve_time_range(res.time_window)

        # Default fallback if location completely omitted
        loc_name = res.location_name or "Thoothukudi"
        lat = res.lat or GAZETTEER["thoothukudi"][0]
        lon = res.lon or GAZETTEER["thoothukudi"][1]

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
            "detected_language": res.detected_language,
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

    detected_language = _detect_language(raw)
    location_name, lat, lon = _resolve_location(raw)
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

        # Use last time_window if not explicitly provided in this message
        _explicit_time = _extract_time_window(raw)
        if _explicit_time == "next_24h" and last_intent is not None:
            # "next_24h" is the default — if last intent had a real window, keep it
            time_window = last_intent.get("time_window", "next_24h")
        else:
            time_window = _explicit_time

        time_start_utc, time_end_utc = _resolve_time_range(time_window)

        parsed_intent: ParsedIntent = ParsedIntent(
            location_name=location_name or "Thoothukudi",
            lat=lat or (GAZETTEER.get("thoothukudi", (8.7642, 78.1348))[0]),
            lon=lon or (GAZETTEER.get("thoothukudi", (8.7642, 78.1348))[1]),
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
                "Please provide an Indian coastal location (e.g. Thoothukudi, Chennai, Kochi) "
                "and I will retrieve marine and safety information for you."
            ),
            "parse_method": "rule_based_fallback",
        }

    # ---- Milestone 5: Inherit location from previous turn if not in this query ----
    if location_name is None and last_intent is not None:
        location_name = last_intent.get("location_name")
        lat = last_intent.get("lat")
        lon = last_intent.get("lon")

    # If still no location, default to Thoothukudi (demo anchor)
    if location_name is None:
        location_name = "Thoothukudi"
        lat, lon = GAZETTEER["thoothukudi"]

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
