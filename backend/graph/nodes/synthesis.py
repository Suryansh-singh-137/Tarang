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

Explainability contract (PRD §4.3):
  - Every sentence in final_answer_text MUST be attributable to a source
    in trace[].
  - If a specialist agent returned status "error", explicitly state what
    could NOT be determined.
  - If no hazard warning was found, phrase it as "no relevant warning found
    in the available data", NOT as a safety guarantee.
  - Synthesis MUST NOT invent measurements, timestamps, or sources.
"""

from __future__ import annotations

from typing import Optional

from graph.state import AgentResult, EvidenceItem, ORCAState

# ---------------------------------------------------------------------------
# Language-specific phrase tables
# ---------------------------------------------------------------------------

_PHRASES: dict[str, dict[str, str]] = {
    "en": {
        "preamble": "Here is Tarang's marine safety assessment for {location} ({time_window}):",
        "weather_intro": "🌊 Marine Conditions",
        "pfz_intro": "🐟 Fishing Zone Intelligence (PFZ)",
        "hazard_intro": "⚠️ Hazard Advisories",
        "geofence_intro": "🗺️ Maritime Boundary",
        "risk_intro": "📊 Overall Risk Assessment",
        "evidence_intro": "📋 Data Sources & Evidence",
        "data_status_intro": "📡 Data Freshness",
        "skipped": "ℹ️ {agent} was not needed for this query.",
        "error": "❌ {agent} encountered an error; {aspect} could not be determined.",
        "fallback_note": "⚠️ **Fallback data used**: {agents}. Live source(s) were unreachable. Results reflect the latest cached dataset.",
        "pfz_proxy_note": "ℹ️ PFZ zones are derived from INCOIS Oceansat-2 chlorophyll-a data (scientific proxy). For official PFZ advisories, consult the INCOIS portal directly.",
        "cyclone_note": "ℹ️ Cyclone warnings: real-time cyclone advisories require direct consultation with IMD (imd.gov.in) or INCOIS.",
        "disclaimer": (
            "⚠️ **Disclaimer**: This is a decision-support assessment, not an official safety clearance. "
            "Always follow advisories from IMD, INCOIS, and the Indian Coast Guard."
        ),
    },
    "hi": {
        "preamble": "{location} के लिए Tarang का समुद्री सुरक्षा आकलन ({time_window}):",
        "weather_intro": "🌊 समुद्री स्थिति",
        "pfz_intro": "🐟 मछली पकड़ने के क्षेत्र (PFZ)",
        "hazard_intro": "⚠️ खतरे की चेतावनियाँ",
        "geofence_intro": "🗺️ समुद्री सीमा",
        "risk_intro": "📊 कुल जोखिम आकलन",
        "evidence_intro": "📋 डेटा स्रोत और साक्ष्य",
        "data_status_intro": "📡 डेटा की ताज़गी",
        "skipped": "ℹ️ {agent} इस प्रश्न के लिए आवश्यक नहीं था।",
        "error": "❌ {agent} में त्रुटि हुई; {aspect} निर्धारित नहीं किया जा सका।",
        "fallback_note": "⚠️ **फ़ॉलबैक डेटा उपयोग किया गया**: {agents}। लाइव स्रोत उपलब्ध नहीं था।",
        "pfz_proxy_note": "ℹ️ PFZ क्षेत्र INCOIS Oceansat-2 क्लोरोफिल डेटा पर आधारित हैं।",
        "cyclone_note": "ℹ️ चक्रवात चेतावनियों के लिए IMD/INCOIS से सीधे जाँचें।",
        "disclaimer": (
            "⚠️ **अस्वीकरण**: यह एक निर्णय-सहायता आकलन है, आधिकारिक सुरक्षा मंजूरी नहीं। "
            "IMD, INCOIS और भारतीय तटरक्षक बल की सलाह का पालन करें।"
        ),
    },
    "ta": {
        "preamble": "{location} க்கான Tarang கடல் பாதுகாப்பு மதிப்பீடு ({time_window}):",
        "weather_intro": "🌊 கடல் நிலைகள்",
        "pfz_intro": "🐟 மீன்பிடி வலயங்கள் (PFZ)",
        "hazard_intro": "⚠️ அபாய எச்சரிக்கைகள்",
        "geofence_intro": "🗺️ கடல் எல்லை",
        "risk_intro": "📊 ஒட்டுமொத்த அபாய மதிப்பீடு",
        "evidence_intro": "📋 தரவு மூலங்கள்",
        "data_status_intro": "📡 தரவு புதுமை",
        "skipped": "ℹ️ {agent} இந்தக் கேள்விக்கு தேவையில்லை.",
        "error": "❌ {agent} பிழை ஏற்பட்டது; {aspect} தீர்மானிக்க முடியவில்லை.",
        "fallback_note": "⚠️ **தற்காலிக தரவு பயன்படுத்தப்பட்டது**: {agents}.",
        "pfz_proxy_note": "ℹ️ PFZ வலயங்கள் INCOIS Oceansat-2 குளோரோஃபில் தரவை அடிப்படையாகக் கொண்டவை.",
        "cyclone_note": "ℹ️ புயல் எச்சரிக்கைகளுக்கு IMD/INCOIS-ஐ நேரடியாக சரிபார்க்கவும்.",
        "disclaimer": (
            "⚠️ **மறுப்பு**: இது ஒரு முடிவு-ஆதரவு மதிப்பீடு, அதிகாரப்பூர்வ பாதுகாப்பு அனுமதி அல்ல. "
            "IMD, INCOIS மற்றும் இந்திய கடலோர காவலர் ஆலோசனைகளை பின்பற்றவும்."
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deg_to_compass(deg: Optional[float]) -> str:
    if deg is None:
        return "—"
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[round(deg / 22.5) % 16]


# ---------------------------------------------------------------------------
# Template renderer
# ---------------------------------------------------------------------------

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
        lines.append(f"**Risk score: {d['composite_score']}/100**  *(decision-support only)*")
        lines.append("")

    # ---- Weather ----
    lines.append(f"**{p['weather_intro']}**")
    if weather is None or weather["status"] == "error":
        lines.append(p["error"].format(agent="Weather agent", aspect="sea conditions"))
    elif weather["status"] == "skipped":
        lines.append(p["skipped"].format(agent="Weather agent"))
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
        if d.get("visibility_km"):
            lines.append(f"• Visibility: {d['visibility_km']} km")
        lines.append(f"  *(Source: {weather['source']})*")
        if weather.get("used_fallback"):
            lines.append("  ⚠️ *(Cached fallback — live data unavailable)*")
    lines.append("")

    # ---- PFZ ----
    lines.append(f"**{p['pfz_intro']}**")
    if pfz is None or pfz["status"] == "error":
        lines.append(p["error"].format(agent="PFZ agent", aspect="fishing zones"))
    elif pfz["status"] == "skipped":
        lines.append(p["skipped"].format(agent="PFZ agent"))
    else:
        d = pfz["data"]
        n_zones = len(d.get("zones", []))
        nearest = d.get("nearest_zone_km", "?")
        productivity = d.get("overall_productivity", "unknown")
        avg_chl = d.get("avg_chl")
        lines.append(f"• **{n_zones}** indicator zone(s) found")
        lines.append(f"• Nearest PFZ indicator: **{nearest:.0f} km** away")
        if avg_chl:
            lines.append(f"• Average chlorophyll-a: {avg_chl:.2f} mg/m³ (productivity: {productivity})")
        # List top 2 zones
        for z in d.get("zones", [])[:2]:
            lines.append(
                f"  – Zone at {z['lat']:.2f}°N, {z['lon']:.2f}°E "
                f"({z['distance_km']:.0f} km, CHL={z.get('chlorophyll_mg_m3', '?')} mg/m³)"
            )
        lines.append(f"  *(Source: {pfz['source']})*")
        if pfz.get("used_fallback"):
            lines.append("  ⚠️ *(Cached fallback — live INCOIS ERDDAP unavailable)*")
        lines.append(p["pfz_proxy_note"])
    lines.append("")

    # ---- Hazard ----
    lines.append(f"**{p['hazard_intro']}**")
    if hazard is None or hazard["status"] == "error":
        lines.append(p["error"].format(agent="Hazard agent", aspect="hazard advisories"))
        lines.append("Risk assessment proceeds without hazard intelligence.")
    elif hazard["status"] == "skipped":
        lines.append(p["skipped"].format(agent="Hazard agent"))
    else:
        d = hazard["data"]
        active = d.get("active_warnings", [])
        level = d.get("overall_hazard_level", "none")
        if not active:
            lines.append(
                f"No relevant hazard warning found in available data "
                f"(as of {d.get('source_time', '—')}). "
                "This does not guarantee absence of hazard."
            )
        else:
            lines.append(f"⚠️ **Hazard level: {level.upper()}**")
            for h in d.get("hazards", []):
                lines.append(f"• **{h['title']}** ({h['severity']}): {h['detail']}")
        lines.append(f"  *(Source: {hazard['source']})*")
        if hazard.get("used_fallback"):
            lines.append("  ⚠️ *(Cached fallback — live data unavailable)*")
        lines.append(p["cyclone_note"])
    lines.append("")

    # ---- Geofence ----
    lines.append(f"**{p['geofence_intro']}**")
    if geofence is None or geofence["status"] == "error":
        lines.append(p["error"].format(agent="Geofence agent", aspect="boundary data"))
    elif geofence["status"] == "skipped":
        lines.append(p["skipped"].format(agent="Geofence agent"))
    else:
        lines.append(f"{geofence['summary']}  *(Source: {geofence['source']})*")
    lines.append("")

    # ---- Risk breakdown ----
    lines.append(f"**{p['risk_intro']}**")
    if risk is None or risk["status"] == "error":
        lines.append(p["error"].format(agent="Risk agent", aspect="risk score"))
    elif risk["status"] == "skipped":
        lines.append(p["skipped"].format(agent="Risk agent"))
    else:
        d = risk["data"]
        cs = d["component_scores"]
        lines.append(f"Score: **{d['composite_score']}/100 ({d['risk_label']})**")
        lines.append(f"| Factor | Score |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Waves  | {cs['wave_height']:.0f}/100 |")
        lines.append(f"| Wind   | {cs['wind_speed']:.0f}/100 |")
        lines.append(f"| Hazards | {cs['hazard_level']:.0f}/100 |")
        lines.append(f"| Boundary proximity | {cs['boundary_proximity']:.0f}/100 |")
        lines.append(f"")
        lines.append(f"{d['recommendation']}")
    lines.append("")

    # ---- Evidence section ----
    if evidence:
        lines.append(f"**{p['evidence_intro']}**")
        # Group by source
        sources_seen: dict[str, list[str]] = {}
        for ev in evidence:
            src = ev.get("source", "Unknown")
            claim = ev.get("claim", "")
            if src not in sources_seen:
                sources_seen[src] = []
            sources_seen[src].append(claim)
        for src, claims in sources_seen.items():
            lines.append(f"• **{src}**")
            for claim in claims[:3]:  # max 3 claims per source for readability
                lines.append(f"  – {claim}")
        lines.append("")

    # ---- Data freshness ----
    lines.append(f"**{p['data_status_intro']}**")
    fallback_agents = []
    for agent, result_key in [
        ("Weather", weather), ("PFZ", pfz), ("Hazard", hazard), ("Geofence", geofence)
    ]:
        if result_key and result_key.get("status") == "success":
            fb = result_key.get("used_fallback", False)
            icon = "⚠️ Fallback" if fb else "✓ Live"
            lines.append(f"• {agent}: {icon}")
            if fb:
                fallback_agents.append(agent.lower())
        elif result_key and result_key.get("status") == "skipped":
            lines.append(f"• {agent}: ℹ️ Not required")
        elif result_key and result_key.get("status") == "error":
            lines.append(f"• {agent}: ❌ Unavailable")
            fallback_agents.append(agent.lower())
    lines.append("• Geospatial: ✓ Computed")
    lines.append("")

    # ---- Fallback disclosure ----
    if fallback_agents:
        lines.append(p["fallback_note"].format(agents=", ".join(fallback_agents)))
        lines.append("")

    lines.append(p["disclaimer"])
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
# Public node function
# ---------------------------------------------------------------------------

def synthesis(state: ORCAState) -> dict:
    """
    LangGraph node: fuse all agent results into a cited natural-language
    answer and a GeoJSON map payload.
    """
    lang = state.get("detected_language", "en")
    intent = state.get("parsed_intent")

    # Handle invalid-location case (detect_and_parse already set final_answer_text)
    if intent and not intent.get("lat") and not intent.get("lon"):
        existing_answer = state.get("final_answer_text", "")
        if existing_answer:
            return {
                "final_answer_text": existing_answer,
                "map_geojson": {"type": "FeatureCollection", "features": []},
            }

    location   = intent["location_name"] if intent else "the requested location"
    time_window = intent["time_window"]  if intent else "next_24h"
    lat = intent["lat"] if intent else 8.7642
    lon = intent["lon"] if intent else 78.1348

    weather  = state.get("weather_result")
    pfz      = state.get("pfz_result")
    hazard   = state.get("hazard_result")
    geofence = state.get("geofence_result")
    risk     = state.get("risk_result")
    evidence = state.get("evidence") or []

    answer_text = _render_template(
        lang=lang,
        location=location,
        time_window=time_window,
        weather=weather,
        pfz=pfz,
        hazard=hazard,
        geofence=geofence,
        risk=risk,
        evidence=evidence,
    )

    map_geojson = _build_geojson(
        intent_lat=lat,
        intent_lon=lon,
        location_name=location,
        pfz=pfz,
        geofence=geofence,
        risk=risk,
    )

    return {
        "final_answer_text": answer_text,
        "map_geojson": map_geojson,
    }
