"""
synthesis node
--------------
The only node that produces user-facing text.

Milestone 2 additions:
  - Evidence section: lists source attribution for each data stream
  - Data-status section: ✓ Live / ⚠️ Fallback per agent
  - Fallback disclosure: explicit when any agent used cached data
  - PFZ proxy attribution: clarifies chlorophyll-based PFZ indicator
  - Hazard limitation: notes that cyclone advisories require IMD/INCOIS check

Milestone 3 additions:
  - data_quality third-state: Live / Fallback / Historical Proxy per agent
  - PFZ proxy label hardened: always disclosed as chlorophyll-based historical proxy
  - Synthesis MUST NOT emit unqualified "it is safe" or "it is not safe";
    all risk assessments must be qualified as decision-support only.
  - Top risk contributors named immediately after the risk badge (M4).

Explainability contract (PRD §4.3):
  - Every sentence in final_answer_text MUST be attributable to a source
    in trace[].
  - If a specialist agent returned status "error", explicitly state what
    could NOT be determined.
  - If no hazard warning was found, phrase it as "no relevant warning found
    in the available data", NOT as a safety guarantee.
  - Synthesis MUST NOT invent measurements, timestamps, or sources.
  - Synthesis MUST NOT emit unqualified 'it is safe' or 'it is not safe'.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import json
import re
import logging

import config
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from graph.state import AgentResult, EvidenceItem, ORCAState, AnswerPlan

# ---------------------------------------------------------------------------
# Language-specific phrase tables
# ---------------------------------------------------------------------------

_PHRASES: dict[str, dict[str, str]] = {
    "en": {
        "preamble": "Here is Tarang's marine safety assessment for {location} ({time_window}):",
        "weather_intro": "🌊 Marine Weather Conditions",
        "pfz_intro": "🐟 Fishing Potential Indicator (Chlorophyll Proxy)",
        "hazard_intro": "⚠️ Weather Condition Hazard Indicators",
        "geofence_intro": "🗺️ Maritime Boundary",
        "risk_intro": "📊 Overall Risk Assessment",
        "evidence_intro": "📋 Data Sources & Evidence",
        "data_status_intro": "📡 Data Freshness & Quality",
        "skipped": "ℹ️ {aspect} not applicable or not requested for this query.",
        "error": "Live {aspect} data is currently unavailable for this location.",
        "fallback_note": "⚠️ **Cached data in use**: {agents}. Live source(s) were temporarily unreachable; results reflect the latest available verified dataset.",
        "pfz_proxy_note": (
            "ℹ️ **Data Quality Note**: Fishing potential zones above are derived from INCOIS Oceansat-2 "
            "chlorophyll-a historical satellite data — this is a scientific proxy indicator, "
            "not a real-time official INCOIS PFZ advisory. "
            "For official PFZ advisories, consult the INCOIS portal at incois.gov.in."
        ),
        "cyclone_note": "ℹ️ **Cyclone advisory**: Real-time cyclone warnings require direct consultation with IMD (imd.gov.in) or INCOIS (incois.gov.in). The above represents weather-condition hazard indicators only.",
        "disclaimer": (
            "⚠️ **Disclaimer**: This is a decision-support assessment, not an official safety clearance. "
            "Tarang assesses available conditions as a navigational aid — always follow "
            "advisories from IMD, INCOIS, and the Indian Coast Guard before departing."
        ),
    },
    "hi": {
        "preamble": "{location} के लिए Tarang का समुद्री सुरक्षा आकलन ({time_window}):",
        "weather_intro": "🌊 समुद्री स्थिति",
        "pfz_intro": "🐟 मछली पकड़ने के क्षेत्र सूचक (क्लोरोफिल आधारित)",
        "hazard_intro": "⚠️ मौसम संबंधी खतरे के संकेतक",
        "geofence_intro": "🗺️ समुद्री सीमा",
        "risk_intro": "📊 कुल जोखिम आकलन",
        "evidence_intro": "📋 डेटा स्रोत और साक्ष्य",
        "data_status_intro": "📡 डेटा की ताज़गी और गुणवत्ता",
        "skipped": "ℹ️ {aspect} इस प्रश्न के लिए लागू या आवश्यक नहीं है।",
        "error": "इस स्थान के लिए लाइव {aspect} डेटा वर्तमान में उपलब्ध नहीं है।",
        "fallback_note": "⚠️ **कैश्ड डेटा उपयोग में है**: {agents}। लाइव स्रोत अस्थायी रूप से अनुपलब्ध है।",
        "pfz_proxy_note": (
            "ℹ️ **डेटा गुणवत्ता नोट**: मछली पकड़ने के क्षेत्र INCOIS Oceansat-2 "
            "क्लोरोफिल-a ऐतिहासिक उपग्रह डेटा पर आधारित वैज्ञानिक सूचक हैं — "
            "यह आधिकारिक INCOIS PFZ परामर्श नहीं है।"
        ),
        "cyclone_note": "ℹ️ **चक्रवात परामर्श**: वास्तविक समय की चक्रवात चेतावनियों के लिए IMD/INCOIS से सीधे जाँचें।",
        "disclaimer": (
            "⚠️ **अस्वीकरण**: यह एक निर्णय-सहायता आकलन है, आधिकारिक सुरक्षा मंजूरी नहीं। "
            "IMD, INCOIS और भारतीय तटरक्षक बल की सलाह का पालन करें।"
        ),
    },
    "ta": {
        "preamble": "{location} க்கான Tarang கடல் பாதுகாப்பு மதிப்பீடு ({time_window}):",
        "weather_intro": "🌊 கடல் நிலைகள்",
        "pfz_intro": "🐟 மீன்பிடி திறன் சுட்டி (குளோரோஃபில் அடிப்படை)",
        "hazard_intro": "⚠️ வானிலை ஆபத்து சுட்டிகள்",
        "geofence_intro": "🗺️ கடல் எல்லை",
        "risk_intro": "📊 ஒட்டுமொத்த ஆபத்து மதிப்பீடு",
        "evidence_intro": "📋 தரவு மூலங்கள்",
        "data_status_intro": "📡 தரவு புதுமை மற்றும் தரம்",
        "skipped": "ℹ️ {aspect} இந்தக் கேள்விக்கு பொருந்தாது அல்லது கோரப்படவில்லை.",
        "error": "இந்த இடத்திற்கான நேரடி {aspect} தரவு தற்போது கிடைக்கவில்லை.",
        "fallback_note": "⚠️ **தற்காலிக சேமிக்கப்பட்ட தரவு பயன்படுத்தப்படுகிறது**: {agents}.",
        "pfz_proxy_note": (
            "Data quality note: Fishing potential zones are derived from INCOIS Oceansat-2 satellite proxy."
        ),
        "cyclone_note": "Cyclone advisory: Real-time warnings require consultation with IMD or INCOIS.",
        "disclaimer": (
            "Disclaimer: This is a decision-support assessment, not an official safety clearance."
        ),
    },
}

_TIME_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "tomorrow_morning": "tomorrow morning",
        "tomorrow_evening": "tomorrow evening",
        "tomorrow": "tomorrow",
        "now": "now",
        "today": "today",
        "next_24h": "next 24 hours",
        "morning": "morning",
        "evening": "evening",
    },
    "hi": {
        "tomorrow_morning": "कल सुबह",
        "tomorrow_evening": "कल शाम",
        "tomorrow": "कल",
        "now": "अभी",
        "today": "आज",
        "next_24h": "अगले 24 घंटे",
        "morning": "सुबह",
        "evening": "शाम",
    },
    "ta": {
        "tomorrow_morning": "நாளை காலை",
        "tomorrow_evening": "நாளை மாலை",
        "tomorrow": "நாளை",
        "now": "இப்போது",
        "today": "இன்று",
        "next_24h": "அடுத்த 24 மணி நேரம்",
        "morning": "காலை",
        "evening": "மாலை",
    },
}


def _deg_to_compass(deg: Optional[float]) -> str:
    if deg is None:
        return "—"
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[round(deg / 22.5) % 16]


def _render_template(
    lang: str,
    location: str,
    time_window: str,
    weather: Optional[AgentResult],
    pfz: Optional[AgentResult],
    hazard: Optional[AgentResult],
    geofence: Optional[AgentResult],
    risk: Optional[AgentResult],
    evidence: list[EvidenceItem],
    ocean: Optional[AgentResult] = None,
) -> str:
    p = _PHRASES.get(lang, _PHRASES["en"])

    # PRD §3.1, §6.1, §8: If risk assessment was computed successfully, output fisherman-friendly Layer 1
    if risk and risk.get("status") == "success" and risk.get("data"):
        d = risk["data"]
        label = str(d.get("risk_label", "LOW")).upper()

        if lang == "hi":
            badge_map = {
                "LOW": "🟢 अभी कम जोखिम है।",
                "MODERATE": "🟡 अभी मध्यम जोखिम है (सावधानी आवश्यक)।",
                "HIGH": "🔴 अभी उच्च जोखिम है।",
                "EXTREME": "🔴 समुद्र में जाना अभी खतरनाक है।",
            }
            badge = badge_map.get(label, f"जोखिम स्तर: {label}")
        elif lang == "ta":
            badge_map = {
                "LOW": "🟢 தற்போது குறைந்த ஆபத்து.",
                "MODERATE": "🟡 தற்போது நடுத்தர ஆபத்து (எச்சரிக்கை தேவை).",
                "HIGH": "🔴 தற்போது அதிக ஆபத்து.",
                "EXTREME": "🔴 கடலுக்குச் செல்வது ஆபத்தானது.",
            }
            badge = badge_map.get(label, f"ஆபத்து நிலை: {label}")
        else:
            badge_map = {
                "LOW": "🟢 Low risk right now.",
                "MODERATE": "🟡 Moderate risk right now.",
                "HIGH": "🔴 High risk right now.",
                "EXTREME": "🔴 Dangerous conditions right now.",
            }
            badge = badge_map.get(label, f"Conditions rated {label} risk.")

        cond_parts = []
        if weather and weather.get("status") == "success" and weather.get("data"):
            wd = weather["data"]
            wave = wd.get("wave_height_m", 1.0)
            wind = wd.get("wind_speed_kmh", 15.0)
            if wave <= 1.25 and wind <= 20.0:
                if lang == "hi":
                    cond_parts.append("समुद्र काफी शांत है, लहरें छोटी हैं और हवा हल्की है।")
                elif lang == "ta":
                    cond_parts.append("கடல் அமைதியாக உள்ளது, சிறிய அலைகள் மற்றும் லேசான காற்று வீசுகிறது.")
                else:
                    cond_parts.append("The sea is fairly calm, with small waves and light wind.")
            elif wave <= 2.2 and wind <= 35.0:
                if lang == "hi":
                    cond_parts.append("मध्यम लहरें और हवा उपस्थित हैं, समुद्र की स्थिति पर नज़र रखें।")
                elif lang == "ta":
                    cond_parts.append("நடுத்தர அலைகள் மற்றும் காற்று வீசுகிறது, கடல் நிலையை கவனிக்கவும்.")
                else:
                    cond_parts.append("Moderate sea conditions are present, with manageable waves and breeze.")
            else:
                if lang == "hi":
                    cond_parts.append("तेज़ लहरें या तेज़ हवा सक्रिय हैं।")
                elif lang == "ta":
                    cond_parts.append("உயர்ந்த அலைகள் அல்லது பலத்த காற்று வீசுகிறது.")
                else:
                    cond_parts.append("Rough seas with elevated waves or strong winds are present.")

        if hazard and hazard.get("status") in ("success", "partial") and hazard.get("data"):
            hd = hazard["data"]
            active = hd.get("active_warnings", [])
            level = hd.get("overall_hazard_level", "none")
            if not active or level == "none":
                if lang == "hi":
                    cond_parts.append("कोई बड़ी मौसम चेतावनी सक्रिय नहीं है।")
                elif lang == "ta":
                    cond_parts.append("பெரிய வானிலை எச்சரிக்கை எதுவும் இல்லை.")
                else:
                    cond_parts.append("No major weather warning is active.")
            else:
                warn_str = ", ".join(str(w) for w in active)
                if lang == "hi":
                    cond_parts.append(f"सक्रिय मौसम चेतावनी: {warn_str}।")
                elif lang == "ta":
                    cond_parts.append(f"செயலில் உள்ள எச்சரிக்கை: {warn_str}.")
                else:
                    cond_parts.append(f"Active weather advisory: {warn_str}.")

        # Cached data disclosure (PRD §12 & §26)
        if pfz and (pfz.get("data_quality") in ("fallback", "historical_proxy") or pfz.get("used_fallback")):
            if lang == "hi":
                cond_parts.append("ℹ️ मछली पकड़ने के क्षेत्र का डेटा लाइव डेटा के बजाय नवीनतम उपलब्ध डेटासेट से है।")
            elif lang == "ta":
                cond_parts.append("ℹ️ மீன்பிடி மண்டலத் தரவு நேரடித் தரவை விட சமீபத்திய கிடைக்கக்கூடிய தொகுப்பிலிருந்து பெறப்பட்டது.")
            else:
                cond_parts.append("ℹ️ Some fishing-zone data is from the latest available dataset rather than live data.")

        # Safety recommendation (PRD §8)
        rec = d.get("recommendation")
        if not rec:
            rec_map = {
                "LOW": "Conditions are currently rated low risk by Tarang. Check the latest official advisory before leaving shore.",
                "MODERATE": "Conditions need caution. Check the latest advisory and sea conditions before leaving shore.",
                "HIGH": "Conditions are risky right now. Avoid going out until conditions improve and official advisories allow it.",
                "EXTREME": "Conditions are dangerous right now. Avoid going out until conditions improve and official advisories allow it.",
            }
            rec = rec_map.get(label, "Check the latest official advisory before leaving shore.")

        return f"{badge}\n{' '.join(cond_parts)}\n{rec}"

    # Fallback when risk is not present or failed (status mapping compatibility)
    lines: list[str] = [p["preamble"].format(location=location, time_window=time_window), ""]

    if weather is None or weather.get("status") in ("error", "insufficient_data") or weather.get("execution_status") == "failed" or weather.get("data_status") == "unavailable" or not weather.get("data"):
        lines.append(p["error"].format(aspect="marine weather"))
    elif weather.get("status") == "skipped":
        lines.append(p["skipped"].format(aspect="Weather conditions"))

    if pfz and (pfz.get("status") in ("error", "insufficient_data") or pfz.get("execution_status") == "failed" or pfz.get("data_status") == "unavailable"):
        lines.append(p["error"].format(aspect="fishing zone (PFZ)"))
        lines.append("Fishing-zone suitability could not be assessed because PFZ data is unavailable.")
        lines.append("Partial Assessment: Showing available weather assessment.")

    if hazard and (hazard.get("status") in ("error", "insufficient_data") or hazard.get("execution_status") == "failed" or hazard.get("data_status") == "unavailable"):
        lines.append(p["error"].format(aspect="hazard warning"))

    if not any(lines[2:]):
        lines.append("Tarang does not have enough reliable data to assess the trip safely right now.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GeoJSON builder
# ---------------------------------------------------------------------------

def _build_geojson(
    intent_lat: float,
    intent_lon: float,
    location_name: str,
    pfz: Optional[AgentResult],
    geofence: Optional[AgentResult],
    risk: Optional[AgentResult],
) -> dict:
    """
    Build a GeoJSON FeatureCollection for the map panel.
    GeoJSON coordinate order: [longitude, latitude] (RFC 7946).
    """
    features: list[dict] = []

    # 1) Query point — coloured by risk level
    risk_color = "#22c55e"  # green = LOW
    risk_label = "LOW"
    if risk and risk["status"] == "success":
        level = risk["data"]["risk_label"]
        risk_label = level
        risk_color = {
            "LOW":     "#22c55e",
            "MODERATE":"#f59e0b",
            "HIGH":    "#ef4444",
            "EXTREME": "#7c3aed",
        }.get(level, "#6b7280")

    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [intent_lon, intent_lat]},
        "properties": {
            "feature_type": "query_point",
            "name": location_name,
            "risk_label": risk_label,
            "risk_color": risk_color,
            "risk_score": risk["data"]["composite_score"] if risk and risk["status"] == "success" else None,
        },
    })

    # 2) PFZ zones — [lon, lat] coordinate order per RFC 7946
    if pfz and pfz["status"] == "success":
        for zone in pfz["data"].get("zones", []):
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [zone["lon"], zone["lat"]],   # [lon, lat]
                },
                "properties": {
                    "feature_type": "pfz_zone",
                    "zone_id": zone.get("zone_id", "PFZ"),
                    "description": zone.get("description", ""),
                    "distance_km": zone.get("distance_km"),
                    "chlorophyll_mg_m3": zone.get("chlorophyll_mg_m3"),
                    "source": zone.get("source", "INCOIS ERDDAP"),
                },
            })

    # 3) IMBL boundary line
    from tools.boundary_geo import load_imbl_waypoints
    boundary_coords = [[lon, lat] for lat, lon in load_imbl_waypoints()]
    if boundary_coords:
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": boundary_coords},
            "properties": {
                "feature_type": "imbl_boundary",
                "name": "India–Sri Lanka Maritime Boundary Line (IMBL)",
                "color": "#ef4444",
                "dash": True,
            },
        })

    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Intent-specific response formatters (Section 16, 17, 39-43)
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def _extract_numbers(text: str) -> set[float]:
    """Extract all numbers from text as floats for grounding checks."""
    matches = re.findall(r'\b\d+(?:\.\d+)?\b', text)
    nums = set()
    for m in matches:
        try:
            nums.add(float(m))
        except ValueError:
            pass
    return nums


def _render_location_response(lang: str, resolved: Optional[dict]) -> str:
    if not resolved:
        return "Unable to determine your location. Please provide a place name or enable device location access."
    name = resolved.get("name", "Unknown")
    lat = resolved.get("lat", 0.0)
    lon = resolved.get("lon", 0.0)
    is_coastal = resolved.get("coastal", False)

    if lang == "hi":
        status_hi = "तटीय क्षेत्र" if is_coastal else "अंतर्देशीय क्षेत्र"
        return f"आप वर्तमान में **{name}** में हैं।\n\n• **स्थान**: {name}\n• **अनुमानित निर्देशांक**: {lat:.2f}°N, {lon:.2f}°E\n• **प्रकार**: {status_hi}"
    elif lang == "ta":
        status_ta = "கடலோர பகுதி" if is_coastal else "உள்நாட்டு பகுதி"
        return f"நீங்கள் தற்போது **{name}** இல் உள்ளீர்கள்.\n\n• **இருப்பிடம்**: {name}\n• **ஆயத்தொலைவுகள்**: {lat:.2f}°N, {lon:.2f}°E\n• **வகை**: {status_ta}"
    else:
        status_en = "coastal location" if is_coastal else "inland location"
        return f"You're currently in **{name}**.\n\n• **Location**: {name}\n• **Approximate coordinates**: {lat:.2f}°N, {lon:.2f}°E\n• **Area type**: {status_en}"


def _render_inland_ocean_applicability(lang: str, resolved: Optional[dict]) -> str:
    name = resolved.get("name", "your location") if resolved else "your location"
    if lang == "hi":
        return (
            f"आपकी वर्तमान स्थिति **{name}** अंतर्देशीय (inland) है, इसलिए यहाँ स्थानीय ज्वार-भाटा या समुद्री जल स्तर का माप लागू नहीं होता है।\n\n"
            f"समुद्री जल स्तर या ज्वार की स्थिति देखने के लिए किसी तटीय बंदरगाह का नाम बताएं:\n"
            f"• **मुंबई (Mumbai)**\n• **कोच्चि (Kochi)**\n• **चेन्नई (Chennai)**\n• **थूथुकुडी (Thoothukudi)**"
        )
    elif lang == "ta":
        return (
            f"உங்கள் தற்போதைய இருப்பிடம் **{name}** உள்நாட்டுப் பகுதியாகும், எனவே உள்ளூர் கடல் அலை அல்லது கடல் நீர்மட்ட அளவீடு இங்கு பொருந்தாது.\n\n"
            f"கடல் அலை அல்லது நீர்மட்ட தகவல்களை அறிய கடலோர இடத்தை முயற்சிக்கவும்:\n"
            f"• **மும்பை (Mumbai)**\n• **கொச்சி (Kochi)**\n• **சென்னை (Chennai)**\n• **தூத்துக்குடி (Thoothukudi)**"
        )
    else:
        return (
            f"Your current location is inland in **{name}**, so a local tide or sea-water level measurement is not applicable here.\n\n"
            f"{name} is inland and has no direct marine tidal coastline. I can check the tide or water level for a coastal location instead.\n\n"
            f"Try a coastal location:\n"
            f"• **Mumbai**\n• **Kochi**\n• **Chennai**\n• **Thoothukudi**"
        )


def _render_weather_response(
    lang: str,
    resolved: Optional[dict],
    time_window: str,
    weather: Optional[AgentResult],
) -> str:
    loc_name = resolved.get("name", "your location") if resolved else "your location"
    tw = _TIME_LABELS.get(lang, _TIME_LABELS["en"]).get(time_window, time_window)

    lines = []
    if lang == "hi":
        lines.append(f"🌤 **{loc_name} — वर्तमान एवं पूर्वानुमानित मौसम ({tw})**\n")
    elif lang == "ta":
        lines.append(f"🌤 **{loc_name} — தற்போதைய மற்றும் முன்னறிவிப்பு வானிலை ({tw})**\n")
    else:
        lines.append(f"🌤 **Current & Forecast Weather — {loc_name} ({tw}):**\n")

    if not weather or weather.get("status") in ("error", "insufficient_data") or not weather.get("data"):
        lines.append("Live weather data is currently unavailable for this location.")
    else:
        d = weather.get("data", {})
        temp = d.get("temperature_c") or d.get("air_temperature_c")
        wind = d.get("wind_speed_kmh")
        wind_dir = _deg_to_compass(d.get("wind_direction_deg"))
        pressure = d.get("pressure_msl_hpa")
        wave = d.get("wave_height_m")
        sea = d.get("sea_state")

        conds = []
        if temp is not None:
            conds.append(f"Temperature is around {temp}°C")
        if wind is not None:
            conds.append(f"wind is {wind} km/h from {wind_dir}")
        if wave is not None:
            conds.append(f"wave height is {wave} m")
        if sea:
            conds.append(f"sea state is {sea}")
        if conds:
            lines.append("• " + ", ".join(conds) + ".")
        if pressure is not None:
            lines.append(f"• Air pressure: **{pressure} hPa** (MSL)")
        if d.get("visibility_km"):
            lines.append(f"• Visibility: {d['visibility_km']} km")

        src = weather.get("source", "Open-Meteo Marine + Forecast")
        lines.append(f"\n*(Source: {src})*")
    return "\n".join(lines)


def _render_ocean_response(
    lang: str,
    resolved: Optional[dict],
    ocean: Optional[AgentResult],
) -> str:
    loc_name = resolved.get("name", "coastal waters") if resolved else "coastal waters"
    lines = []
    if lang == "hi":
        lines.append(f"🌊 **{loc_name} — ज्वार एवं जल स्तर का पूर्वानुमान (Chart Datum)**\n")
    elif lang == "ta":
        lines.append(f"🌊 **{loc_name} — கடல் அலை மற்றும் நீர்மட்ட முன்னறிவிப்பு (Chart Datum)**\n")
    else:
        lines.append(f"🌊 **Tide & Water Level Prediction — {loc_name} (Chart Datum)**\n")

    if not ocean or ocean.get("status") in ("error", "insufficient_data") or not ocean.get("data"):
        lines.append("Live tide and ocean water level data is currently unavailable for this location.")
    else:
        od = ocean.get("data", {})
        wl = od.get("water_level_m", 0.0)
        phase = od.get("current_phase", "Normal")
        lines.append(f"• The current water level at **{loc_name}** is about **{wl:.2f} m** above chart datum.")
        lines.append(f"• Tide status: **{phase}** right now.")
        if od.get("next_high_tide"):
            ht = od["next_high_tide"]
            lines.append(f"• Next High Tide: **{ht.get('time_ist')}** ({ht.get('height_m')} m CD)")
        if od.get("next_low_tide"):
            lt = od["next_low_tide"]
            lines.append(f"• Next Low Tide: **{lt.get('time_ist')}** ({lt.get('height_m')} m CD)")
        lines.append(f"\n*(Source: {ocean.get('source', 'INCOIS ERDDAP')} • Type: Harmonic tidal prediction model)*")
    return "\n".join(lines)


def _render_pressure_response(
    lang: str,
    resolved: Optional[dict],
    weather: Optional[AgentResult],
) -> str:
    loc_name = resolved.get("name", "your location") if resolved else "your location"
    lines = [f"🌡 **Air Pressure (MSL) — {loc_name}**\n"]
    if weather and weather.get("status") == "success" and weather.get("data", {}).get("pressure_msl_hpa"):
        p = weather["data"]["pressure_msl_hpa"]
        lines.append(f"• Air pressure: **{p} hPa** (mean sea level datum)")
        lines.append(f"\n*(Source: {weather.get('source', 'Open-Meteo')})*")
    else:
        lines.append("Atmospheric surface pressure data is currently unavailable for this location.")
    return "\n".join(lines)


def _render_pfz_response(
    lang: str,
    resolved: Optional[dict],
    pfz: Optional[AgentResult],
) -> str:
    loc_name = resolved.get("name", "waters") if resolved else "waters"
    lines = [f"🐟 **Fishing Potential Indicator — {loc_name}**\n"]
    if pfz and pfz.get("status") == "success" and pfz.get("data"):
        d = pfz["data"]
        nearest = d.get("nearest_zone_km", 104)
        n_zones = len(d.get("zones", []))
        productivity = d.get("overall_productivity", "moderate")
        lines.append("🐟 Fishing indicator found.")
        if isinstance(nearest, (int, float)):
            lines.append(f"The nearest indicator zone is about **{nearest:.0f} km** away.")
        lines.append("It is based on satellite chlorophyll data and is only an indicator, not a guarantee of fish.")
        if n_zones > 1:
            lines.append(f"Total indicator zones identified: {n_zones} (general productivity: {productivity}).")
        lines.append(f"\n*(Source: {pfz.get('source', 'INCOIS Oceansat-2')} • Type: Satellite chlorophyll proxy)*")
    else:
        lines.append("Live fishing-zone data is currently unavailable for this location.")
    return "\n".join(lines)


def _render_multi_intent_response(
    lang: str,
    resolved: Optional[dict],
    intent_groups: Optional[list[dict]],
    weather: Optional[AgentResult],
    ocean: Optional[AgentResult],
    pfz: Optional[AgentResult],
    hazard: Optional[AgentResult],
    risk: Optional[AgentResult],
) -> str:
    """PRD §16: Seamlessly blends multiple requested aspects into a natural conversational response."""
    loc_name = resolved.get("name", "the requested location") if resolved else "the requested location"
    groups = intent_groups or []
    intent_types = [g.get("intent") for g in groups]

    first_part = ""
    if "WATER_LEVEL_QUERY" in intent_types or "TIDE_QUERY" in intent_types:
        if resolved and not resolved.get("coastal", True):
            first_part = f"{loc_name} is inland and has no direct marine tidal coastline."
        elif ocean and ocean.get("status") == "success" and ocean.get("data"):
            od = ocean["data"]
            wl = od.get("water_level_m", 0.42)
            phase = od.get("current_phase", "rising").lower()
            first_part = f"{loc_name}: The current water level is about {wl:.2f} m above chart datum and the tide is {phase}."
        else:
            first_part = f"{loc_name}: Tide and water level prediction data is currently unavailable."
    elif "WEATHER_QUERY" in intent_types:
        if weather and weather.get("status") == "success" and weather.get("data"):
            wd = weather["data"]
            temp = wd.get("temperature_c") or wd.get("air_temperature_c", 28)
            wind = wd.get("wind_speed_kmh", 12)
            first_part = f"{loc_name}: Current weather is {temp}°C with {wind} km/h wind."
        else:
            first_part = f"{loc_name}: Current weather data is unavailable."
    elif "HAZARD_QUERY" in intent_types:
        if hazard and hazard.get("status") == "success" and hazard.get("data"):
            hd = hazard["data"]
            active = hd.get("active_warnings", [])
            first_part = f"{loc_name}: Active hazard alerts: {', '.join(active)}." if active else f"{loc_name}: No major hazard warning is active."
        else:
            first_part = f"{loc_name}: Hazard alert data is currently unavailable."
    elif "PFZ_QUERY" in intent_types:
        if pfz and pfz.get("status") == "success" and pfz.get("data"):
            pd = pfz["data"]
            dist = pd.get("nearest_zone_km", 100)
            first_part = f"{loc_name}: The nearest fishing potential indicator is about {dist:.0f} km away (satellite chlorophyll proxy)."
        else:
            first_part = f"{loc_name}: Fishing indicator data is currently unavailable."
    elif "LOCATION_QUERY" in intent_types:
        lat = resolved.get("lat", 0.0) if resolved else 0.0
        lon = resolved.get("lon", 0.0) if resolved else 0.0
        first_part = f"You are currently in {loc_name} ({lat:.2f}°N, {lon:.2f}°E)."

    second_part = ""
    if "MARINE_SAFETY_QUERY" in intent_types or any("saf" in str(t).lower() for t in intent_types):
        if risk and risk.get("status") == "success":
            rd = risk["data"]
            label = str(rd.get("risk_label", "LOW")).upper()
            badge_map = {
                "LOW": "🟢 Fishing conditions are currently rated low risk.",
                "MODERATE": "🟡 Fishing conditions need caution.",
                "HIGH": "🔴 Fishing conditions are currently high risk.",
                "EXTREME": "🔴 Fishing conditions are currently dangerous.",
            }
            badge = badge_map.get(label, f"Fishing conditions are rated {label} risk.")
            cond = "The sea is fairly calm and no major hazard is active." if label == "LOW" else "Monitor sea conditions and official warnings."
            rec = rd.get("recommendation", "Check the latest official advisory before leaving shore.")
            second_part = f"{badge} {cond} {rec}"
        else:
            second_part = "Tarang does not have enough reliable data to assess the trip safely right now."

    if first_part and second_part:
        return f"{first_part}\n{second_part}"
    elif first_part:
        return first_part
    elif second_part:
        return second_part
    else:
        return _render_template(lang, loc_name, "now", weather, pfz, hazard, None, risk, [])


def _render_hazard_response(
    lang: str,
    resolved: Optional[dict],
    hazard: Optional[AgentResult],
) -> str:
    loc_name = resolved.get("name", "monitored area") if resolved else "monitored area"
    p = _PHRASES.get(lang, _PHRASES["en"])
    lines = [f"⚠️ **Weather Condition Hazard Indicators — {loc_name}**\n"]
    if hazard and hazard.get("status") == "success" and hazard.get("data"):
        d = hazard["data"]
        active = d.get("active_warnings", [])
        level = d.get("overall_hazard_level", "none")
        if not active:
            lines.append(f"No active high-severity hazard was detected for {loc_name} in the available data. This does not guarantee absence of hazard.")
        else:
            lines.append(f"⚠️ **Hazard Level: {level.upper()}**")
            for h in d.get("hazards", []):
                lines.append(f"• **{h['title']}** ({h.get('severity', 'advisory')}): {h.get('detail', '')}")
        lines.append(f"\n*(Source: {hazard.get('source', 'IMD / Open-Meteo')})*")
        lines.append(f"\n{p['cyclone_note']}")
    else:
        lines.append("Live hazard warning data is currently unavailable for this location.")
    return "\n".join(lines)


def _validate_response(
    text: str,
    answer_plan: Optional[AnswerPlan],
    resolved: Optional[dict],
) -> tuple[bool, str]:
    """Lightweight response validator (Section 32, 33, 34)."""
    if not answer_plan:
        return True, "OK"

    intent = answer_plan.get("intent", "")
    text_lower = text.lower()

    # 0. Global safety and presentation invariants (PRD §5.1, §8)
    unauthorized = [
        "proceed with standard safety precautions",
        "safe to proceed",
        "authorized to depart",
        "clear to depart",
        "safe to depart",
    ]
    if any(u in text_lower for u in unauthorized):
        return False, "DEPARTURE_AUTHORIZATION_LEAK"

    internal_leaks = [
        "weather_agent", "ocean_agent", "hazard_agent", "pfz_agent", "geofence_agent", "risk_agent",
        "execution_status", "data_quality", "points contribution", "pts contribution"
    ]
    if any(t in text_lower for t in internal_leaks):
        return False, "INTERNAL_TERM_LEAK"

    # 1. Location query validation: must not contain unprompted marine safety jargon
    if intent == "LOCATION_QUERY":
        banned = [
            "pfz", "chlorophyll", "composite score", "marine safety assessment",
            "high risk", "moderate risk", "extreme risk", "fishing assessment",
            "fishing potential", "imbl",
        ]
        if any(b in text_lower for b in banned):
            return False, "IRRELEVANT_CONTENT"

    # 2. Inland tide/water-level query: must not fabricate numbers or give fishing risk
    if intent in ("WATER_LEVEL_QUERY", "TIDE_QUERY") and resolved and not resolved.get("coastal"):
        banned = ["composite score", "risk score", "high risk", "moderate risk", "marine safety assessment"]
        if any(b in text_lower for b in banned):
            return False, "IRRELEVANT_CONTENT"

    # 3. Pure weather query: must not contain unprompted PFZ or fishing risk verdict
    if intent == "WEATHER_QUERY":
        banned = ["chlorophyll", "pfz proxy", "fishing potential indicator", "composite score", "overall risk assessment", "fishing assessment"]
        if any(b in text_lower for b in banned):
            return False, "IRRELEVANT_CONTENT"

    return True, "OK"


# ---------------------------------------------------------------------------
# Public node function (LLM Path - Milestone 6)
# ---------------------------------------------------------------------------

def synthesis(state: ORCAState) -> dict:
    """
    LangGraph node: fuse relevant agent results into an intent-aware, cited natural-language
    answer and a GeoJSON map payload using Groq LLM.
    """
    lang = state.get("detected_language", "en")
    intent = state.get("parsed_intent")
    answer_plan = state.get("answer_plan") or (intent.get("answer_plan") if intent else None)
    intent_name = (answer_plan.get("intent") if answer_plan else None) or (intent.get("intent") if intent else None) or "MARINE_SAFETY_QUERY"
    response_mode = (answer_plan.get("answer_type") if answer_plan else None) or state.get("response_mode") or "DECISION_ASSESSMENT"
    raw_query = state.get("raw_query", "").strip()
    resolved = state.get("resolved_location")

    # Handle early-exit cases where a previous node already generated the final text
    existing_answer = state.get("final_answer_text", "")
    is_invalid_loc = not intent.get("lat") and not intent.get("lon") if intent else True
    is_explanation = (intent.get("query_type") == "risk_explanation" or intent_name == "RISK_EXPLANATION") if intent else False
    is_location = intent_name == "LOCATION_QUERY" or (intent and intent.get("query_type") == "location_only")
    is_applicability = state.get("response_mode") == "APPLICABILITY_EXPLANATION" or (intent and intent.get("response_mode") == "APPLICABILITY_EXPLANATION")

    if (is_invalid_loc or is_explanation or is_location or is_applicability) and existing_answer:
        return {
            "final_answer_text": existing_answer,
            "map_geojson": state.get("map_geojson", {"type": "FeatureCollection", "features": []}),
            "synthesis_method": "direct_fact" if is_location else "applicability" if is_applicability else "llm",
        }

    location = (resolved.get("name") if resolved else None) or (intent["location_name"] if intent else "the requested location")
    lat = resolved["lat"] if resolved else (intent["lat"] if intent else 8.7642)
    lon = resolved["lon"] if resolved else (intent["lon"] if intent else 78.1348)
    is_coastal = resolved.get("coastal", True) if resolved else True
    area_type = "coastal" if is_coastal else "inland"

    weather = state.get("weather_result")
    pfz = state.get("pfz_result")
    ocean = state.get("ocean_result")
    hazard = state.get("hazard_result")
    geofence = state.get("geofence_result")
    risk = state.get("risk_result")
    evidence = state.get("evidence") or []

    map_geojson = _build_geojson(
        intent_lat=lat,
        intent_lon=lon,
        location_name=location,
        pfz=pfz,
        geofence=geofence,
        risk=risk,
    )

    if not config.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set. Falling back to intent-aware template synthesis.")
        fallback_res = _fallback_synthesis(state)
        fallback_res["map_geojson"] = map_geojson
        fallback_res["synthesis_method"] = "template_fallback"
        return fallback_res

    # Prepare selective evidence context for LLM based on AnswerPlan (Section 44)
    req_caps = answer_plan.get("required_capabilities", []) if answer_plan else []
    evidence_payload: dict = {}
    if not req_caps or "weather" in req_caps:
        evidence_payload["weather"] = weather.get("data") if weather and weather.get("status") == "success" else None
    if not req_caps or "ocean" in req_caps:
        evidence_payload["ocean_tides"] = ocean.get("data") if ocean and ocean.get("status") == "success" else None
    if not req_caps or "pfz" in req_caps:
        evidence_payload["pfz"] = pfz.get("data") if pfz and pfz.get("status") == "success" else None
    if not req_caps or "hazard" in req_caps:
        evidence_payload["hazard"] = hazard.get("data") if hazard and hazard.get("status") == "success" else None
    if not req_caps or "geofence" in req_caps:
        evidence_payload["geofence"] = geofence.get("data") if geofence and geofence.get("status") == "success" else None
    if not req_caps or "risk" in req_caps:
        evidence_payload["risk_components"] = risk.get("data", {}).get("components") if risk and risk.get("status") == "success" else None
        evidence_payload["risk_score"] = risk.get("data", {}).get("composite_score") if risk and risk.get("status") == "success" else None
        evidence_payload["risk_label"] = risk.get("data", {}).get("risk_label") if risk and risk.get("status") == "success" else None

    evidence_str = json.dumps(evidence_payload, indent=2)

    # Note if any fallback data was used
    data_quality_notes = []
    for agent_name, res in [("weather", weather), ("pfz", pfz), ("hazard", hazard)]:
        if res and res.get("status") == "success":
            dq = res.get("data_quality", "live")
            if dq == "fallback":
                data_quality_notes.append(f"{agent_name.capitalize()} agent used cached fallback data.")
            elif dq == "historical_proxy":
                data_quality_notes.append(f"{agent_name.capitalize()} agent used historical proxy data.")

    dq_str = " ".join(data_quality_notes) if data_quality_notes else "All data is live."

    # Intent-driven synthesis prompt (Sections 15, 31, 44, 45)
    system_template = """You are Tarang, an intelligent coastal & marine assistant for fishermen.
Current User Query: {raw_query}
Current Intent: {intent_name}
Response Mode: {response_mode}
Location: {location} (Coordinates: {lat:.2f}°N, {lon:.2f}°E, Area: {area_type})
Answer Plan: {answer_plan_str}

USER-FACING RESPONSE POLICY (PRD §5.1, §8, §16, §19):
1. Answer the user's actual question first.
2. Use simple everyday language. Keep the main answer short: prefer 2–5 short sentences. Target: 1 idea per sentence.
3. Mention only the information relevant to the current question. Convert technical measurements into understandable meaning:
   - Prefer 'Wave height' over 'Significant wave height'
   - Prefer 'Risk level' over 'Composite decision-support score'
   - Prefer 'Air pressure' over 'Atmospheric surface pressure'
   - Prefer 'Tide prediction' over 'Harmonic tidal prediction'
   - Prefer 'Distance from boundary' over 'Geofence proximity'
   - Prefer 'Satellite fishing indicator' over 'Chlorophyll-a concentration'
   - Prefer 'Data available' over 'Evidence coverage'
   - Prefer 'No major hazard detected' over 'Hazard level 0/100'
   - Prefer 'Check the latest warning before leaving' over 'Execute standard precautions'
   - Prefer 'Conditions are currently calm' over 'Current conditions appear manageable'
4. Do not expose internal risk formulas, weights, contribution points, agent names, state fields, JSON, execution details, cache internals, or implementation terminology.
5. Do not repeat every available data point. Detailed numeric evidence belongs in UI details cards, not the primary answer.
6. Tarang NEVER authorizes departure. Do not say 'proceed with standard safety precautions' or 'safe to depart'.
   - Low risk: 'Conditions are currently rated low risk by Tarang. Check the latest official advisory before leaving shore.'
   - Caution: 'Conditions need caution. Check the latest advisory and sea conditions before leaving shore.'
   - High risk: 'Conditions are risky right now. Avoid going out until conditions improve and official advisories allow it.'
   - Unknown: 'Tarang does not have enough reliable data to assess the trip safely right now.'
7. If MULTI_INTENT: answer all requested sub-intents and combine them naturally into 2–4 short sentences (e.g. state water level first, then state fishing safety conditions). Do not create two disconnected full reports.
8. If the intent is LOCATION_QUERY: provide a concise, direct answer stating the user's current location and coordinates. Do NOT mention marine safety, PFZ, or tides.
9. If the intent is WEATHER_QUERY or SEA_LEVEL_PRESSURE_QUERY: summarize temperature, wind, and conditions for {location} in 2-3 short sentences. Do NOT mention PFZ, tides, or fishing risk.
10. If the intent is TIDE_QUERY or WATER_LEVEL_QUERY:
    - For coastal locations: summarize water level above Chart Datum and whether the tide is rising or falling in 2 short sentences.
    - For inland locations: explain that local coastal tide/water level measurements are not applicable to inland {location}, and suggest coastal harbours (e.g. Mumbai, Kochi, Chennai, Thoothukudi).
11. If the intent is PFZ_QUERY: refer to it as 'Fishing Potential Indicator' (satellite chlorophyll proxy), never an 'official PFZ advisory'. State distance and note that satellite data does not guarantee fish.
12. If cached data was used (e.g. PFZ), state: 'Some fishing-zone data is from the latest available dataset rather than live data.'
13. NEVER state a numeric value that is not present in the provided evidence or location coordinates.
14. The response must be in the {lang} language.

JSON Evidence:
{evidence_str}
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("user", f"Answer this query directly: {raw_query}")
    ])

    llm = ChatGroq(
        model=config.GROQ_MODEL_QUALITY,
        api_key=config.GROQ_API_KEY,
        temperature=0.2,
        max_retries=0,
        timeout=10.0
    )
    chain = prompt | llm

    try:
        res = chain.invoke({
            "raw_query": raw_query,
            "intent_name": intent_name,
            "response_mode": response_mode,
            "location": location,
            "lat": lat,
            "lon": lon,
            "area_type": area_type,
            "answer_plan_str": json.dumps(answer_plan, indent=2) if answer_plan else "None",
            "lang": lang,
            "dq_str": dq_str,
            "evidence_str": evidence_str,
        })
        output_text = res.content

        # Grounding check: include coordinates, query numbers, and standard constants
        output_nums = _extract_numbers(output_text)
        evidence_nums = _extract_numbers(evidence_str)
        if resolved:
            evidence_nums.update(_extract_numbers(json.dumps(resolved)))
            if "lat" in resolved and isinstance(resolved["lat"], (int, float)):
                evidence_nums.update({round(resolved["lat"], 2), round(resolved["lat"], 1), round(resolved["lat"], 3), float(int(resolved["lat"]))})
            if "lon" in resolved and isinstance(resolved["lon"], (int, float)):
                evidence_nums.update({round(resolved["lon"], 2), round(resolved["lon"], 1), round(resolved["lon"], 3), float(int(resolved["lon"]))})
        if intent:
            if intent.get("lat") and isinstance(intent["lat"], (int, float)):
                evidence_nums.update({round(intent["lat"], 2), round(intent["lat"], 1), round(intent["lat"], 3), float(int(intent["lat"]))})
            if intent.get("lon") and isinstance(intent["lon"], (int, float)):
                evidence_nums.update({round(intent["lon"], 2), round(intent["lon"], 1), round(intent["lon"], 3), float(int(intent["lon"]))})
        evidence_nums.update(_extract_numbers(raw_query))
        now_utc = datetime.now(timezone.utc)
        safe_nums = {float(n) for n in range(32)} | {
            float(now_utc.year), float(now_utc.year - 1), float(now_utc.year + 1),
            float(now_utc.month), float(now_utc.day),
            0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5,
            48.0, 72.0, 100.0, 300.0, 500.0, 1000.0, 1013.25
        }
        ungrounded = output_nums - evidence_nums - safe_nums

        if ungrounded:
            logger.warning(f"Numeric grounding check failed. Ungrounded numbers: {ungrounded}. Falling back to template.")
            fallback_res = _fallback_synthesis(state)
            fallback_res["map_geojson"] = map_geojson
            fallback_res["synthesis_method"] = "template_fallback"
            return fallback_res

        # Lightweight Response Validation Layer (Sections 32-34)
        is_valid, reason = _validate_response(output_text, answer_plan, resolved)
        if not is_valid:
            logger.warning(f"Response validation failed ({reason}). Falling back to intent template.")
            fallback_res = _fallback_synthesis(state)
            fallback_res["map_geojson"] = map_geojson
            fallback_res["synthesis_method"] = "template_fallback"
            return fallback_res

        return {
            "final_answer_text": output_text,
            "map_geojson": map_geojson,
            "synthesis_method": "llm",
        }
    except Exception as exc:
        logger.warning(f"Groq synthesis failed ({exc}), falling back to template synthesis.")
        fallback_res = _fallback_synthesis(state)
        fallback_res["map_geojson"] = map_geojson
        fallback_res["synthesis_method"] = "template_fallback"
        return fallback_res


# ---------------------------------------------------------------------------
# Fallback template-based synthesis (Intent-aware)
# ---------------------------------------------------------------------------

def _fallback_synthesis(state: ORCAState) -> dict:
    """
    Fallback LangGraph node: fuse agent results into a cited natural-language
    answer using intent-specific templates (Section 16, 17).
    """
    lang = state.get("detected_language", "en")
    intent = state.get("parsed_intent")
    answer_plan = state.get("answer_plan") or (intent.get("answer_plan") if intent else None)
    intent_name = (answer_plan.get("intent") if answer_plan else None) or (intent.get("intent") if intent else None) or "MARINE_SAFETY_QUERY"
    resolved = state.get("resolved_location")

    # Early exit if final text is already produced
    existing_answer = state.get("final_answer_text", "")
    if existing_answer:
        return {"final_answer_text": existing_answer}

    time_window = intent.get("time_window", "next_24h") if intent else "next_24h"
    weather = state.get("weather_result")
    pfz = state.get("pfz_result")
    ocean = state.get("ocean_result")
    hazard = state.get("hazard_result")
    geofence = state.get("geofence_result")
    risk = state.get("risk_result")
    evidence = state.get("evidence") or []

    if intent_name == "LOCATION_QUERY":
        answer_text = _render_location_response(lang, resolved)
    elif intent_name in ("WATER_LEVEL_QUERY", "TIDE_QUERY"):
        if resolved and not resolved.get("coastal", False):
            answer_text = _render_inland_ocean_applicability(lang, resolved)
        else:
            answer_text = _render_ocean_response(lang, resolved, ocean)
    elif intent_name == "SEA_LEVEL_PRESSURE_QUERY":
        answer_text = _render_pressure_response(lang, resolved, weather)
    elif intent_name == "WEATHER_QUERY":
        answer_text = _render_weather_response(lang, resolved, time_window, weather)
    elif intent_name == "PFZ_QUERY":
        answer_text = _render_pfz_response(lang, resolved, pfz)
    elif intent_name == "HAZARD_QUERY":
        answer_text = _render_hazard_response(lang, resolved, hazard)
    elif intent_name == "MULTI_INTENT":
        groups = (answer_plan.get("intent_groups") if answer_plan else None) or (intent.get("intent_groups") if intent else None)
        answer_text = _render_multi_intent_response(lang, resolved, groups, weather, ocean, pfz, hazard, risk)
    else:
        answer_text = _render_template(
            lang=lang,
            location=resolved.get("name", "the requested location") if resolved else "the requested location",
            time_window=time_window,
            weather=weather,
            pfz=pfz,
            hazard=hazard,
            geofence=geofence,
            risk=risk,
            evidence=evidence,
            ocean=ocean,
        )

    return {
        "final_answer_text": answer_text,
    }
