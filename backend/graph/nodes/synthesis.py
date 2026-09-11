"""
synthesis node
--------------
The only node that produces user-facing text.

Milestone 1: Uses a template-based synthesis (no LLM call) so the full graph
             can be exercised without an API key.
             Milestone 2: Replace `_render_template()` with a Groq call
             (larger model) that is tightly constrained to cite only facts
             present in the AgentResult payloads.

Explainability contract (PRD §4.3):
  - Every sentence in final_answer_text MUST be attributable to a source
    in trace[].
  - If a specialist agent returned status "error", explicitly state what
    could NOT be determined.
  - If no hazard warning was found, phrase it as "no relevant warning found
    in the available data", NOT as a safety guarantee.
"""

from __future__ import annotations

from typing import Optional

from graph.state import AgentResult, ORCAState

# ---------------------------------------------------------------------------
# Language-specific phrase tables (Milestone 1 template approach)
# ---------------------------------------------------------------------------

_PHRASES: dict[str, dict[str, str]] = {
    "en": {
        "preamble": "Here is ORCA's sea-safety assessment for {location} ({time_window}):",
        "weather_intro": "🌊 Weather & Sea Conditions",
        "pfz_intro": "🐟 Potential Fishing Zones (PFZ)",
        "hazard_intro": "⚠️ Hazard Advisories",
        "geofence_intro": "🗺️ Maritime Boundary",
        "risk_intro": "📊 Overall Risk Assessment",
        "skipped": "ℹ️ {agent} was not needed for this query.",
        "error": "❌ {agent} encountered an error; {aspect} could not be determined.",
        "disclaimer": (
            "⚠️ This is a decision-support assessment, not an official safety clearance. "
            "Always follow advisories from IMD, INCOIS, and the Indian Coast Guard."
        ),
    },
    "hi": {
        "preamble": "{location} के लिए ORCA का समुद्री सुरक्षा आकलन ({time_window}):",
        "weather_intro": "🌊 मौसम और समुद्री स्थिति",
        "pfz_intro": "🐟 संभावित मछली पकड़ने के क्षेत्र (PFZ)",
        "hazard_intro": "⚠️ खतरे की चेतावनियाँ",
        "geofence_intro": "🗺️ समुद्री सीमा",
        "risk_intro": "📊 कुल जोखिम आकलन",
        "skipped": "ℹ️ {agent} इस प्रश्न के लिए आवश्यक नहीं था।",
        "error": "❌ {agent} में त्रुटि हुई; {aspect} निर्धारित नहीं किया जा सका।",
        "disclaimer": (
            "⚠️ यह एक निर्णय-सहायता आकलन है, आधिकारिक सुरक्षा मंजूरी नहीं। "
            "IMD, INCOIS और भारतीय तटरक्षक बल की सलाह का पालन करें।"
        ),
    },
    "ta": {
        "preamble": "{location} க்கான ORCA கடல் பாதுகாப்பு மதிப்பீடு ({time_window}):",
        "weather_intro": "🌊 வானிலை மற்றும் கடல் நிலைகள்",
        "pfz_intro": "🐟 சாத்தியமான மீன்பிடி வலயங்கள் (PFZ)",
        "hazard_intro": "⚠️ அபாய எச்சரிக்கைகள்",
        "geofence_intro": "🗺️ கடல் எல்லை",
        "risk_intro": "📊 ஒட்டுமொத்த அபாய மதிப்பீடு",
        "skipped": "ℹ️ {agent} இந்தக் கேள்விக்கு தேவையில்லை.",
        "error": "❌ {agent} பிழை ஏற்பட்டது; {aspect} தீர்மானிக்க முடியவில்லை.",
        "disclaimer": (
            "⚠️ இது ஒரு முடிவு-ஆதரவு மதிப்பீடு, அதிகாரப்பூர்வ பாதுகாப்பு அனுமதி அல்ல. "
            "IMD, INCOIS மற்றும் இந்திய கடலோர காவலர் ஆலோசனைகளை பின்பற்றவும்."
        ),
    },
}

_TIME_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "tomorrow_morning": "tomorrow morning",
        "tomorrow": "tomorrow",
        "now": "now",
        "today": "today",
        "next_24h": "next 24 hours",
        "morning": "morning",
        "evening": "evening",
    },
    "hi": {
        "tomorrow_morning": "कल सुबह",
        "tomorrow": "कल",
        "now": "अभी",
        "today": "आज",
        "next_24h": "अगले 24 घंटे",
        "morning": "सुबह",
        "evening": "शाम",
    },
    "ta": {
        "tomorrow_morning": "நாளை காலை",
        "tomorrow": "நாளை",
        "now": "இப்போது",
        "today": "இன்று",
        "next_24h": "அடுத்த 24 மணி நேரம்",
        "morning": "காலை",
        "evening": "மாலை",
    },
}


# ---------------------------------------------------------------------------
# Template renderer (Milestone 1 — replace with LLM call in Milestone 2)
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
) -> str:
    p = _PHRASES.get(lang, _PHRASES["en"])
    tw = _TIME_LABELS.get(lang, _TIME_LABELS["en"]).get(time_window, time_window)

    lines: list[str] = [p["preamble"].format(location=location, time_window=tw), ""]

    # --- Weather ---
    lines.append(f"**{p['weather_intro']}**")
    if weather is None:
        lines.append(p["error"].format(agent="weather_agent", aspect="sea conditions"))
    elif weather["status"] == "skipped":
        lines.append(p["skipped"].format(agent="weather_agent"))
    elif weather["status"] == "error":
        lines.append(p["error"].format(agent="weather_agent", aspect="sea conditions"))
    else:
        d = weather["data"]
        lines.append(f"{weather['summary']}  *(Source: {weather['source']})*")
        if d.get("used_fallback") or weather.get("used_fallback"):
            lines.append("  _(cached fallback data)_")
    lines.append("")

    # --- PFZ ---
    lines.append(f"**{p['pfz_intro']}**")
    if pfz is None:
        lines.append(p["skipped"].format(agent="pfz_agent"))
    elif pfz["status"] == "skipped":
        lines.append(p["skipped"].format(agent="pfz_agent"))
    elif pfz["status"] == "error":
        lines.append(p["error"].format(agent="pfz_agent", aspect="fishing zones"))
    else:
        lines.append(f"{pfz['summary']}  *(Source: {pfz['source']})*")
    lines.append("")

    # --- Hazard ---
    lines.append(f"**{p['hazard_intro']}**")
    if hazard is None:
        lines.append(p["error"].format(agent="hazard_agent", aspect="hazard advisories"))
    elif hazard["status"] == "skipped":
        lines.append(p["skipped"].format(agent="hazard_agent"))
    elif hazard["status"] == "error":
        lines.append(p["error"].format(agent="hazard_agent", aspect="hazard advisories"))
    else:
        lines.append(f"{hazard['summary']}  *(Source: {hazard['source']})*")
    lines.append("")

    # --- Geofence ---
    lines.append(f"**{p['geofence_intro']}**")
    if geofence is None:
        lines.append(p["error"].format(agent="geofence_agent", aspect="boundary data"))
    elif geofence["status"] == "skipped":
        lines.append(p["skipped"].format(agent="geofence_agent"))
    elif geofence["status"] == "error":
        lines.append(p["error"].format(agent="geofence_agent", aspect="boundary data"))
    else:
        lines.append(f"{geofence['summary']}  *(Source: {geofence['source']})*")
    lines.append("")

    # --- Risk ---
    lines.append(f"**{p['risk_intro']}**")
    if risk is None:
        lines.append(p["error"].format(agent="risk_agent", aspect="risk score"))
    elif risk["status"] == "skipped":
        lines.append(p["skipped"].format(agent="risk_agent"))
    elif risk["status"] == "error":
        lines.append(p["error"].format(agent="risk_agent", aspect="risk score"))
    else:
        d = risk["data"]
        lines.append(
            f"Score: **{d['composite_score']}/100 ({d['risk_label']})**  "
            f"*(Source: {risk['source']})*"
        )
        lines.append(f"{d['recommendation']}")
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
    Includes:
      - Query point (with risk colour)
      - PFZ zone points
      - IMBL boundary line (simplified from geofence data)
    """
    features: list[dict] = []

    # 1) Query point — coloured by risk level
    risk_color = "#22c55e"  # green = LOW
    risk_label = "LOW"
    if risk and risk["status"] == "success":
        level = risk["data"]["risk_label"]
        risk_label = level
        risk_color = {
            "LOW": "#22c55e",
            "MODERATE": "#f59e0b",
            "HIGH": "#ef4444",
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

    # 2) PFZ zones
    if pfz and pfz["status"] == "success":
        for zone in pfz["data"].get("zones", []):
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [zone["lon"], zone["lat"]],
                },
                "properties": {
                    "feature_type": "pfz_zone",
                    "zone_id": zone["zone_id"],
                    "description": zone["description"],
                    "distance_km": zone["distance_km"],
                    "chlorophyll_mg_m3": zone.get("chlorophyll_mg_m3"),
                    "sst_celsius": zone.get("sst_celsius"),
                },
            })

    # 3) IMBL boundary line (simplified waypoints)
    from graph.nodes.geofence_agent import _IMBL_WAYPOINTS, _load_boundary_waypoints
    boundary_coords = [[lon, lat] for lat, lon in _load_boundary_waypoints()]
    if boundary_coords:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": boundary_coords,
            },
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
    location = intent["location_name"] if intent else "the requested location"
    time_window = intent["time_window"] if intent else "next_24h"
    lat = intent["lat"] if intent else 8.7642
    lon = intent["lon"] if intent else 78.1348

    weather = state.get("weather_result")
    pfz = state.get("pfz_result")
    hazard = state.get("hazard_result")
    geofence = state.get("geofence_result")
    risk = state.get("risk_result")

    answer_text = _render_template(
        lang=lang,
        location=location,
        time_window=time_window,
        weather=weather,
        pfz=pfz,
        hazard=hazard,
        geofence=geofence,
        risk=risk,
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
