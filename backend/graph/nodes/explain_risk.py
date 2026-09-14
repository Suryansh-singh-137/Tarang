"""
explain_risk node
-----------------
Milestone 4: Handles queries that ask WHY the risk score is what it is.

Triggered when detect_and_parse sets query_type == "risk_explanation".

Key design requirements:
  - MUST NOT re-fetch any external APIs.
  - Reads previously computed risk_result, weather_result, pfz_result,
    hazard_result, geofence_result from state.
  - If no risk_result is available (e.g., first message asks "why?"),
    gracefully explains the scoring model instead.
  - Outputs to final_answer_text (via synthesis) in the detected language.

Output format: a structured breakdown of each risk component with:
  - The raw measured value
  - The component score (0–100)
  - The weight applied
  - The contribution to the total
  - Plain-language interpretation of each factor
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from graph.state import AgentResult, EvidenceItem, ORCAState

logger = logging.getLogger("tarang.explain_risk")


# ---------------------------------------------------------------------------
# Plain-language interpretation templates (per-language)
# ---------------------------------------------------------------------------

_INTROS: dict[str, str] = {
    "en": "Here is a breakdown of how Tarang calculated the risk score:",
    "hi": "यहाँ Tarang ने जोखिम स्कोर की गणना कैसे की, इसका विवरण है:",
    "ta": "Tarang எவ்வாறு ஆபத்து மதிப்பெண்ணை கணக்கிட்டது என்பதன் விளக்கம்:",
}

_FACTOR_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "Wave Height":
            "• **Wave Height** — measured at **{raw_value} m** ({raw_unit}) → "
            "component score {component_score:.0f}/100 × weight {weight_pct:.0f}% "
            "= **{contribution:.1f}** points contribution",
        "Wind Speed":
            "• **Wind Speed** — measured at **{raw_value} {raw_unit}** → "
            "component score {component_score:.0f}/100 × weight {weight_pct:.0f}% "
            "= **{contribution:.1f}** points contribution",
        "Hazard Level":
            "• **Hazard Level** — assessed as **{raw_value}** → "
            "component score {component_score:.0f}/100 × weight {weight_pct:.0f}% "
            "= **{contribution:.1f}** points contribution",
        "Boundary Proximity":
            "• **Boundary Proximity** — **{raw_value:.0f} km** from IMBL → "
            "component score {component_score:.0f}/100 × weight {weight_pct:.0f}% "
            "= **{contribution:.1f}** points contribution",
    },
    "hi": {
        "Wave Height":
            "• **लहर ऊंचाई** — मापा गया **{raw_value} m** → "
            "घटक स्कोर {component_score:.0f}/100 × भार {weight_pct:.0f}% "
            "= **{contribution:.1f}** अंक योगदान",
        "Wind Speed":
            "• **हवा की गति** — मापी गई **{raw_value} {raw_unit}** → "
            "घटक स्कोर {component_score:.0f}/100 × भार {weight_pct:.0f}% "
            "= **{contribution:.1f}** अंक योगदान",
        "Hazard Level":
            "• **खतरे का स्तर** — **{raw_value}** आंका गया → "
            "घटक स्कोर {component_score:.0f}/100 × भार {weight_pct:.0f}% "
            "= **{contribution:.1f}** अंक योगदान",
        "Boundary Proximity":
            "• **सीमा निकटता** — IMBL से **{raw_value:.0f} km** → "
            "घटक स्कोर {component_score:.0f}/100 × भार {weight_pct:.0f}% "
            "= **{contribution:.1f}** अंक योगदान",
    },
    "ta": {
        "Wave Height":
            "• **அலை உயரம்** — அளவிடப்பட்டது **{raw_value} m** → "
            "கூறு மதிப்பெண் {component_score:.0f}/100 × எடை {weight_pct:.0f}% "
            "= **{contribution:.1f}** புள்ளிகள் பங்களிப்பு",
        "Wind Speed":
            "• **காற்றின் வேகம்** — **{raw_value} {raw_unit}** → "
            "கூறு மதிப்பெண் {component_score:.0f}/100 × எடை {weight_pct:.0f}% "
            "= **{contribution:.1f}** புள்ளிகள் பங்களிப்பு",
        "Hazard Level":
            "• **ஆபத்து நிலை** — **{raw_value}** என மதிப்பிடப்பட்டது → "
            "கூறு மதிப்பெண் {component_score:.0f}/100 × எடை {weight_pct:.0f}% "
            "= **{contribution:.1f}** புள்ளிகள் பங்களிப்பு",
        "Boundary Proximity":
            "• **எல்லை நெருக்கம்** — IMBL-லிருந்து **{raw_value:.0f} km** → "
            "கூறு மதிப்பெண் {component_score:.0f}/100 × எடை {weight_pct:.0f}% "
            "= **{contribution:.1f}** புள்ளிகள் பங்களிப்பு",
    },
}

_TOTALS: dict[str, str] = {
    "en": "\n**Total: {total:.1f}/100 → {label}**\n\n{recommendation}",
    "hi": "\n**कुल: {total:.1f}/100 → {label}**\n\n{recommendation}",
    "ta": "\n**மொத்தம்: {total:.1f}/100 → {label}**\n\n{recommendation}",
}

_NO_RISK_DATA: dict[str, str] = {
    "en": (
        "No previous risk assessment is available to explain. "
        "Please ask a safety query first (e.g. 'Is it safe to fish near Thoothukudi tomorrow?') "
        "and then ask for an explanation."
    ),
    "hi": (
        "समझाने के लिए कोई पिछला जोखिम आकलन उपलब्ध नहीं है। "
        "पहले एक सुरक्षा प्रश्न पूछें (उदा. 'क्या कल तूतीकोरिन के पास मछली पकड़ना सुरक्षित है?') "
        "फिर स्पष्टीकरण मांगें।"
    ),
    "ta": (
        "விளக்க முந்தைய ஆபத்து மதிப்பீடு எதுவும் இல்லை. "
        "முதலில் ஒரு பாதுகாப்பு கேள்வியை கேளுங்கள் (எ.கா. 'நாளை தூத்துக்குடி அருகில் மீன்பிடிக்க பாதுகாப்பானதா?') "
        "பின்னர் விளக்கம் கேளுங்கள்."
    ),
}

_DISCLAIMER: dict[str, str] = {
    "en": (
        "\n⚠️ **Disclaimer**: This is a decision-support assessment, not an official safety clearance. "
        "Always follow advisories from IMD, INCOIS, and the Indian Coast Guard."
    ),
    "hi": (
        "\n⚠️ **अस्वीकरण**: यह एक निर्णय-सहायता आकलन है, आधिकारिक सुरक्षा मंजूरी नहीं।"
    ),
    "ta": (
        "\n⚠️ **மறுப்பு**: இது ஒரு முடிவு-ஆதரவு மதிப்பீடு, அதிகாரப்பூர்வ பாதுகாப்பு அனுமதி அல்ல."
    ),
}


# ---------------------------------------------------------------------------
# Public node function
# ---------------------------------------------------------------------------

def explain_risk(state: ORCAState) -> dict:
    """
    LangGraph node: produce a plain-language explanation of the risk score
    breakdown using previously computed risk_result or previous_marine_assessment in state.

    No external API calls are made; this is a pure formatting node.
    """
    lang = state.get("detected_language", "en")
    risk = state.get("risk_result")

    d = None
    if risk and risk.get("status") == "success" and isinstance(risk.get("data"), dict):
        d = risk["data"]
    elif state.get("previous_marine_assessment"):
        d = state["previous_marine_assessment"]
    elif state.get("last_results") and "risk_agent" in state["last_results"]:
        cached = state["last_results"]["risk_agent"]
        if cached.get("status") == "success" and isinstance(cached.get("data"), dict):
            d = cached["data"]

    # If no risk data from prior turn — inform the user gracefully
    if d is None:
        return {
            "final_answer_text": _NO_RISK_DATA.get(lang, _NO_RISK_DATA["en"]),
            "map_geojson": state.get("map_geojson", {"type": "FeatureCollection", "features": []}),
        }

    components = d.get("components", [])
    total = d.get("composite_score", 0.0)
    label = d.get("risk_label", "UNKNOWN").upper()
    recommendation = d.get("recommendation", "")

    # PRD §9: Generate simple, fisherman-friendly explanation
    if lang == "hi":
        if label == "LOW":
            intro = "जोखिम अभी कम है क्योंकि समुद्र शांत है।"
            cond = "लहरें छोटी हैं, हवा हल्की है और कोई बड़ी चेतावनी सक्रिय नहीं है।"
        elif label == "MODERATE":
            intro = "जोखिम मध्यम है और सावधानी बरतने की आवश्यकता है।"
            cond = "मध्यम लहरों या हवा के कारण समुद्र की स्थिति पर नज़र रखें।"
        elif label in ("HIGH", "EXTREME"):
            intro = "जोखिम अभी अधिक है। समुद्र में जाना खतरनाक हो सकता है।"
            cond = "प्रतिकूल लहरों, हवा या सक्रिय चेतावनी के कारण तट पर ही रहें।"
        else:
            intro = "वर्तमान में जोखिम की स्थिति का आकलन किया गया है।"
            cond = "कृपया आधिकारिक चेतावनी का पालन करें।"
        
        main_factor = ""
        if components:
            top_name = components[0].get("label", "लहर ऊंचाई")
            main_factor = f"स्कोर को प्रभावित करने वाला मुख्य कारक {top_name} है।"
        
        lines = [intro, cond]
        if main_factor:
            lines.append(main_factor)
        if recommendation:
            lines.append(recommendation)
        else:
            lines.append("तट छोड़ने से पहले नवीनतम आधिकारिक सलाह की जांच करें।")
    elif lang == "ta":
        if label == "LOW":
            intro = "கடல் அமைதியாக இருப்பதால் ஆபத்து தற்போது குறைவாக உள்ளது."
            cond = "அலைகள் சிறியவை, காற்று மென்மையானது மற்றும் பெரிய எச்சரிக்கை எதுவும் இல்லை."
        elif label == "MODERATE":
            intro = "ஆபத்து நடுத்தரமாக உள்ளது, கூடுதல் எச்சரிக்கை தேவை."
            cond = "நடுத்தர அலைகள் அல்லது காற்றின் காரணமாக கடல் நிலையை கண்காணிக்கவும்."
        elif label in ("HIGH", "EXTREME"):
            intro = "ஆபத்து தற்போது அதிகமாக உள்ளது. கடலுக்கு செல்வதை தவிர்க்கவும்."
            cond = "பாதகமான கடல் நிலை அல்லது செயலில் உள்ள எச்சரிக்கை காரணமாக கரையில் இருங்கள்."
        else:
            intro = "தற்போதைய ஆபத்து நிலை மதிப்பிடப்பட்டுள்ளது."
            cond = "அதிகாரப்பூர்வ எச்சரிக்கைகளை பின்பற்றவும்."

        main_factor = ""
        if components:
            top_name = components[0].get("label", "அலை உயரம்")
            main_factor = f"மதிப்பெண்ணை பாதிக்கும் முக்கிய காரணி {top_name} ஆகும்."

        lines = [intro, cond]
        if main_factor:
            lines.append(main_factor)
        if recommendation:
            lines.append(recommendation)
        else:
            lines.append("புறப்படுவதற்கு முன் அதிகாரப்பூர்வ ஆலோசனையை சரிபார்க்கவும்.")
    else:  # en (default)
        if label == "LOW":
            intro = "The risk is low because the sea is fairly calm right now."
            cond = "Waves are small, wind is light, and no major hazard is active."
        elif label == "MODERATE":
            intro = "The risk is currently moderate and conditions need caution."
            cond = "Moderate waves or winds require monitoring sea conditions closely."
        elif label in ("HIGH", "EXTREME"):
            intro = "The risk is currently high right now."
            cond = "Adverse conditions or active weather warnings make venturing out unsafe."
        else:
            intro = "Tarang does not have enough reliable data to assess the trip safely right now."
            cond = "Please consult local port authorities before leaving shore."

        main_factor = ""
        if components:
            top_name = components[0].get("label", "Wave Height")
            main_factor = f"The main factor affecting the score is {top_name}."

        lines = [intro, cond]
        if main_factor:
            lines.append(main_factor)

        if components:
            lines.append("\n**Risk Factor Breakdown:**")
            for comp in components:
                lbl = comp.get("label", "")
                tmpl = _FACTOR_TEMPLATES.get(lang, _FACTOR_TEMPLATES["en"]).get(lbl)
                if tmpl:
                    lines.append(tmpl.format(
                        raw_value=comp.get("raw_value", "?"),
                        raw_unit=comp.get("raw_unit", ""),
                        component_score=comp.get("component_score", 0),
                        weight_pct=comp.get("weight", 0) * 100,
                        contribution=comp.get("contribution", 0),
                    ))
                else:
                    lines.append(f"• **{lbl}**: {comp.get('component_score', 0):.0f}/100 ({comp.get('contribution', 0):.1f} pts)")

        if recommendation:
            lines.append("\n" + recommendation)
        else:
            lines.append("\nCheck the latest official advisory before leaving shore.")

    answer_text = "\n".join(lines)
    logger.info("[ExplainRisk] Simple explanation generated for lang=%s, label=%s, total=%.1f", lang, label, total)

    return {
        "final_answer_text": answer_text,
        "map_geojson": state.get("map_geojson", {"type": "FeatureCollection", "features": []}),
    }
