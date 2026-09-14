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
        "weather_intro": "🌊 Marine Conditions",
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
    tw = _TIME_LABELS.get(lang, _TIME_LABELS["en"]).get(time_window, time_window)

    lines: list[str] = [p["preamble"].format(location=location, time_window=tw), ""]

    # ---- Risk badge (first, most important) ----
    if risk and risk["status"] == "success":
        d = risk["data"]
        badge_map = {
            "LOW":     "🟢 LOW RISK",
            "MODERATE":"🟡 MODERATE RISK",
            "HIGH":    "🔴 HIGH RISK",
            "EXTREME": "🔴🔴 EXTREME RISK",
        }
        badge = badge_map.get(d["risk_label"], d["risk_label"])
        lines.append(f"## {badge}")
        lines.append(f"**Risk score: {d['composite_score']}/100**  *(decision-support only — not an official safety clearance)*")

        # Milestone 4: Name the top 1-2 contributing factors
        components = d.get("components", [])
        if components:
            top = components[0]
            coverage = d.get("evidence_coverage", "?")
            top_label = top.get("label", "")
            top_contrib = top.get("contribution", 0)
            lines.append(
                f"*Primary risk driver: **{top_label}** "
                f"(contributing {top_contrib:.1f}/100 to the total). "
                f"Evidence coverage: {coverage} signal types.*"
            )
        lines.append("")

    # ---- Weather ----
    lines.append(f"**{p['weather_intro']}**")
    if weather is None or weather.get("status") in ("error", "insufficient_data") or weather.get("execution_status") == "failed" or weather.get("data_status") == "unavailable" or not weather.get("data"):
        lines.append(p["error"].format(aspect="marine weather"))
    elif weather.get("status") == "skipped":
        if weather.get("reason") == "INLAND_LOCATION":
            lines.append("Marine weather conditions are not applicable for this inland location.")
        else:
            lines.append(p["skipped"].format(aspect="Weather conditions"))
    else:
        d = weather["data"]
        wave = d.get("wave_height_m", "?")
        wind = d.get("wind_speed_kmh", "?")
        sea = d.get("sea_state", "?")
        wind_dir = _deg_to_compass(d.get("wind_direction_deg"))
        wave_dir = _deg_to_compass(d.get("wave_direction_deg"))
        lines.append(f"• Wave height: **{wave} m** ({wave_dir})")
        lines.append(f"• Wind speed: **{wind} km/h** ({wind_dir})")
        lines.append(f"• Sea state: **{sea}**")
        if d.get("pressure_msl_hpa"):
            lines.append(f"• Atmospheric surface pressure (MSL): **{d['pressure_msl_hpa']} hPa**")
        if d.get("visibility_km"):
            lines.append(f"• Visibility: {d['visibility_km']} km")
        lines.append(f"  *(Source: {weather['source']})*")
    lines.append("")

    # ---- Ocean Tides & Water Level ----
    if ocean and ocean.get("status") == "success" and ocean.get("data"):
        od = ocean.get("data", {})
        lines.append(f"**🌊 Ocean Tides & Water Level (Chart Datum)**")
        lines.append(f"• Current water level: **{od.get('water_level_m', 0.0):.2f} m** above CD ({od.get('current_phase', 'Normal')})")
        if od.get("next_high_tide"):
            lines.append(f"• Next High Tide: **{od['next_high_tide'].get('time_ist')}** ({od['next_high_tide'].get('height_m')} m CD)")
        if od.get("next_low_tide"):
            lines.append(f"• Next Low Tide: **{od['next_low_tide'].get('time_ist')}** ({od['next_low_tide'].get('height_m')} m CD)")
        if od.get("tidal_stream_knots"):
            lines.append(f"• Tidal Current: ~{od['tidal_stream_knots']} knots")
        lines.append(f"  *(Source: {ocean['source']})*")
        lines.append("")
    elif ocean and (ocean.get("status") in ("error", "insufficient_data") or ocean.get("execution_status") == "failed"):
        lines.append(f"**🌊 Ocean Tides & Water Level**")
        lines.append(p["error"].format(aspect="ocean tide"))
        lines.append("")

    # ---- PFZ ----
    if pfz and pfz.get("status") == "success" and pfz.get("data"):
        lines.append(f"**{p['pfz_intro']}**")
        d = pfz["data"]
        n_zones = len(d.get("zones", []))
        nearest = d.get("nearest_zone_km", "?")
        productivity = d.get("overall_productivity", "unknown")
        avg_chl = d.get("avg_chl")
        lines.append(f"• **{n_zones}** indicator zone(s) found")
        lines.append(f"• Nearest PFZ indicator: **{nearest:.0f} km** away")
        if avg_chl:
            lines.append(f"• Average chlorophyll-a: {avg_chl:.2f} mg/m³ (productivity: {productivity})")
        for z in d.get("zones", [])[:2]:
            lines.append(
                f"  – Zone at {z['lat']:.2f}°N, {z['lon']:.2f}°E "
                f"({z['distance_km']:.0f} km, CHL={z.get('chlorophyll_mg_m3', '?')} mg/m³)"
            )
        lines.append(f"  *(Source: {pfz['source']})*")
        lines.append(p["pfz_proxy_note"])
        lines.append("")
    elif pfz and (pfz.get("status") in ("error", "insufficient_data") or pfz.get("execution_status") == "failed" or pfz.get("data_status") == "unavailable"):
        lines.append(f"**{p['pfz_intro']}**")
        lines.append(p["error"].format(aspect="fishing zone (PFZ)"))
        lines.append("Fishing-zone suitability could not be assessed because PFZ data is unavailable.")
        lines.append("")

    # ---- Hazard ----
    if hazard and hazard.get("status") == "success" and hazard.get("data"):
        lines.append(f"**{p['hazard_intro']}**")
        d = hazard["data"]
        active = d.get("active_warnings", [])
        level = d.get("overall_hazard_level", "none")
        if not active:
            lines.append(
                f"No active high-severity hazard was detected for the monitored area "
                f"(as of {d.get('source_time', '—')}). "
                "This does not guarantee absence of hazard."
            )
        else:
            lines.append(f"⚠️ **Hazard level: {level.upper()}**")
            for h in d.get("hazards", []):
                lines.append(f"• **{h['title']}** ({h['severity']}): {h['detail']}")
        lines.append(f"  *(Source: {hazard['source']})*")
        lines.append(p["cyclone_note"])
        lines.append("")
    elif hazard and (hazard.get("status") in ("error", "insufficient_data") or hazard.get("execution_status") == "failed" or hazard.get("data_status") == "unavailable"):
        lines.append(f"**{p['hazard_intro']}**")
        lines.append(p["error"].format(aspect="hazard warning"))
        lines.append("")

    # ---- Geofence ----
    if geofence and geofence.get("status") == "success" and geofence.get("summary"):
        lines.append(f"**{p['geofence_intro']}**")
        lines.append(f"{geofence['summary']}  *(Source: {geofence['source']})*")
        lines.append("")
    elif geofence and geofence.get("status") == "error":
        lines.append(f"**{p['geofence_intro']}**")
        lines.append(p["error"].format(aspect="boundary"))
        lines.append("")

    # ---- Risk breakdown ----
    lines.append(f"**{p['risk_intro']}**")
    if risk is None or risk.get("status") in ("error", "insufficient_data") or risk.get("execution_status") == "failed" or risk.get("data_status") == "unavailable" or risk.get("data", {}).get("risk_label") == "UNKNOWN":
        lines.append("Assessment: **UNKNOWN** (insufficient critical marine data)")
        rec = risk.get("data", {}).get("recommendation") if risk and risk.get("data") else None
        if rec:
            lines.append(rec)
        else:
            lines.append("⚠️ Unable to determine safety. Do NOT venture to sea until live data is available.")
    elif risk.get("status") == "skipped":
        if risk.get("reason") == "INLAND_LOCATION":
            lines.append("Marine trip assessment is not applicable to inland locations.")
    else:
        d = risk["data"]
        cs = d.get("component_scores", {})
        lines.append(f"Assessment: **{d.get('risk_label')} RISK** ({d.get('composite_score')}/100)")
        for comp in d.get("components", []):
            lines.append(
                f"• **{comp['label']}**: {comp['component_score']:.0f}/100 "
                f"(Weight: {comp['weight']*100:.0f}%, Contribution: {comp['contribution']:.1f} pts)"
            )
        lines.append("")
        lines.append(f"{d.get('recommendation', '')}")
    lines.append("")

    # ---- Evidence section ----
    if evidence:
        lines.append(f"**{p['evidence_intro']}**")
        sources_seen: dict[str, list[str]] = {}
        for ev in evidence:
            src = ev.get("source", "Unknown")
            claim = ev.get("claim", "")
            if src not in sources_seen:
                sources_seen[src] = []
            sources_seen[src].append(claim)
        for src, claims in sources_seen.items():
            lines.append(f"• **{src}**")
            for claim in claims[:3]:
                lines.append(f"  – {claim}")
        lines.append("")

    # ---- Data freshness summary (PRD §19) ----
    live_count = 0
    cached_count = 0
    unavail_count = 0
    cached_names = []
    for agent_name, result_key in [
        ("Weather", weather), ("Ocean/Tides", ocean), ("PFZ", pfz), ("Hazard", hazard), ("Geofence", geofence)
    ]:
        if result_key and result_key.get("execution_status") == "success" and result_key.get("status") == "success":
            dq = result_key.get("data_status") or result_key.get("data_quality", "live")
            if dq == "live":
                live_count += 1
            else:
                cached_count += 1
                cached_names.append(agent_name.lower())
        elif result_key and (result_key.get("status") in ("error", "insufficient_data") or result_key.get("execution_status") == "failed" or result_key.get("data_status") == "unavailable"):
            unavail_count += 1

    lines.append(f"**{p['data_status_intro']}**")
    if unavail_count > 0 and live_count > 0:
        lines.append("• Overall Data Status: **Partial Assessment** (some live feeds currently unavailable)")
    elif cached_count > 0 and unavail_count == 0:
        lines.append("• Overall Data Status: **Using Cached Data**")
    elif live_count > 0 and unavail_count == 0:
        lines.append("• Overall Data Status: **Live** (Open-Meteo, INCOIS, IMD)")
    else:
        lines.append("• Overall Data Status: **Live marine data unavailable**")
    lines.append("")

    if cached_names:
        lines.append(p["fallback_note"].format(agents=", ".join(cached_names)))
        lines.append("")

    lines.append(p["disclaimer"])
    return "\n".join(lines)
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
        lines.append(f"🌤 **{loc_name} में मौसम स्थिति ({tw})**\n")
    elif lang == "ta":
        lines.append(f"🌤 **{loc_name} வானிலை நிலவரம் ({tw})**\n")
    else:
        lines.append(f"🌤 **Current weather in {loc_name} ({tw}):**\n")

    if not weather or weather.get("status") in ("error", "insufficient_data") or not weather.get("data"):
        lines.append("Live weather data is currently unavailable for this location.")
    else:
        d = weather.get("data", {})
        temp = d.get("temperature_c") or d.get("air_temperature_c")
        wind = d.get("wind_speed_kmh")
        wind_dir = _deg_to_compass(d.get("wind_direction_deg"))
        pressure = d.get("pressure_msl_hpa")
        wave = d.get("wave_height_m")
        rain = d.get("precipitation_mm", 0.0)

        if temp is not None:
            lines.append(f"• **Temperature**: {temp} °C")
        if wind is not None:
            lines.append(f"• **Wind speed**: {wind} km/h ({wind_dir})")
        if wave is not None:
            wave_dir = _deg_to_compass(d.get("wave_direction_deg"))
            lines.append(f"• **Wave height**: {wave} m ({wave_dir})")
        if rain is not None:
            lines.append(f"• **Precipitation**: {rain} mm")
        if pressure is not None:
            lines.append(f"• **Atmospheric surface pressure (MSL)**: {pressure} hPa")
        if d.get("sea_state"):
            lines.append(f"• **Sea state**: {d['sea_state']}")
        if d.get("visibility_km"):
            lines.append(f"• **Visibility**: {d['visibility_km']} km")

        src = weather.get("source", "Open-Meteo")
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
        lines.append(f"🌊 **{loc_name} — ज्वार एवं समुद्री जल स्तर (Chart Datum)**\n")
    elif lang == "ta":
        lines.append(f"🌊 **{loc_name} — கடல் அலை மற்றும் நீர்மட்டம் (Chart Datum)**\n")
    else:
        lines.append(f"🌊 **Tide & Water Level — {loc_name} (Chart Datum)**\n")

    if not ocean or ocean.get("status") in ("error", "insufficient_data") or not ocean.get("data"):
        lines.append("Live tide and ocean water level data is currently unavailable for this location.")
    else:
        od = ocean.get("data", {})
        wl = od.get("water_level_m", 0.0)
        phase = od.get("current_phase", "Normal")
        lines.append(f"• **Current phase**: {phase}")
        lines.append(f"• **Predicted water level**: **{wl:.2f} m** above Chart Datum")
        if od.get("next_high_tide"):
            ht = od["next_high_tide"]
            lines.append(f"• **Next High Tide**: {ht.get('time_ist')} ({ht.get('height_m')} m CD)")
        if od.get("next_low_tide"):
            lt = od["next_low_tide"]
            lines.append(f"• **Next Low Tide**: {lt.get('time_ist')} ({lt.get('height_m')} m CD)")
        if od.get("tidal_stream_knots"):
            lines.append(f"• **Tidal Stream**: ~{od['tidal_stream_knots']} knots")
        lines.append(f"\n*(Source: {ocean.get('source', 'INCOIS ERDDAP')} • Type: Harmonic prediction)*")
    return "\n".join(lines)


def _render_pressure_response(
    lang: str,
    resolved: Optional[dict],
    weather: Optional[AgentResult],
) -> str:
    loc_name = resolved.get("name", "your location") if resolved else "your location"
    lines = [f"🌡 **Mean Sea-Level Pressure (MSL) — {loc_name}**\n"]
    if weather and weather.get("status") == "success" and weather.get("data", {}).get("pressure_msl_hpa"):
        p = weather["data"]["pressure_msl_hpa"]
        lines.append(f"• **Atmospheric surface pressure**: **{p} hPa** (mean sea level datum)")
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
    p = _PHRASES.get(lang, _PHRASES["en"])
    lines = [f"🐟 **Fishing Potential Indicator (Chlorophyll Proxy) — {loc_name}**\n"]
    if pfz and pfz.get("status") == "success" and pfz.get("data"):
        d = pfz["data"]
        n_zones = len(d.get("zones", []))
        nearest = d.get("nearest_zone_km", "?")
        productivity = d.get("overall_productivity", "unknown")
        lines.append(f"• **{n_zones}** indicator zone(s) identified")
        if isinstance(nearest, (int, float)):
            lines.append(f"• Nearest PFZ indicator: **{nearest:.0f} km** away")
        if d.get("avg_chl"):
            lines.append(f"• Average chlorophyll-a: {d['avg_chl']:.2f} mg/m³ (productivity: {productivity})")
        for z in d.get("zones", [])[:2]:
            lines.append(f"  – Zone at {z['lat']:.2f}°N, {z['lon']:.2f}°E ({z.get('distance_km', 0):.0f} km away)")
        lines.append(f"\n*(Source: {pfz.get('source', 'INCOIS ERDDAP')})*")
        lines.append(f"\n{p['pfz_proxy_note']}")
    else:
        lines.append("Live fishing-zone data is currently unavailable for this location.")
    return "\n".join(lines)


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
    system_template = """You are Tarang, an intelligent agentic coastal & marine assistant.
Current User Query: {raw_query}
Current Intent: {intent_name}
Response Mode: {response_mode}
Location: {location} (Coordinates: {lat:.2f}°N, {lon:.2f}°E, Area: {area_type})
Answer Plan: {answer_plan_str}

STRICT INSTRUCTIONS:
1. The user's current query is authoritative. Answer the query DIRECTLY without defaulting to a generic marine safety assessment.
2. Only mention capabilities and data that are relevant to the current intent ({intent_name}).
3. If the intent is LOCATION_QUERY: provide a concise, direct answer stating the user's current location and coordinates. Do NOT mention marine safety, PFZ, or tides.
4. If the intent is WEATHER_QUERY or SEA_LEVEL_PRESSURE_QUERY: summarize temperature, wind, precipitation, MSL pressure, and conditions for {location}. Do NOT mention PFZ, tides, or fishing risk.
5. If the intent is TIDE_QUERY or WATER_LEVEL_QUERY:
   - For coastal locations: summarize water level above Chart Datum, current phase (rising/falling), next high/low tides, and prediction source.
   - For inland locations: politely explain that local coastal tide/water level measurements are not applicable to inland {location}, and suggest checking a coastal harbour (e.g. Mumbai, Kochi, Chennai, Thoothukudi). Never claim that sea level itself does not exist.
6. If the intent is PFZ_QUERY: discuss fishing zones, chlorophyll proxy indicator, and distance. Always refer to PFZ output as a 'chlorophyll-based fishing-potential proxy', never a 'PFZ advisory'.
7. If the intent is HAZARD_QUERY: discuss active weather condition hazard indicators. Always refer to hazard output as 'weather-condition hazard indicators', never an official 'cyclone warning'.
8. If the intent is MARINE_SAFETY_QUERY or TRIP_QUERY: evaluate conditions for fishing, state risk level as 'Tarang assesses conditions as [LABEL] risk based on current evidence', name top contributing factors, and append: 'Disclaimer: This is a decision-support assessment, not an official safety clearance. Always follow advisories from IMD, INCOIS, and the Indian Coast Guard.'
9. NEVER state a numeric value that is not present in the provided evidence or location coordinates.
10. The response must be in the {lang} language.

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
