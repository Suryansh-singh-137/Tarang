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
    breakdown using previously computed risk_result in state.

    No external API calls are made; this is a pure formatting node.
    """
    lang = state.get("detected_language", "en")
    risk = state.get("risk_result")

    # If no risk data from prior turn — inform the user gracefully
    if risk is None or risk.get("status") != "success":
        return {
            "final_answer_text": _NO_RISK_DATA.get(lang, _NO_RISK_DATA["en"]),
            "map_geojson": state.get("map_geojson", {"type": "FeatureCollection", "features": []}),
        }

    d = risk["data"]
    components = d.get("components", [])
    total = d.get("composite_score", 0.0)
    label = d.get("risk_label", "UNKNOWN")
    recommendation = d.get("recommendation", "")
    evidence_coverage = d.get("evidence_coverage", "?")

    lines: list[str] = [_INTROS.get(lang, _INTROS["en"]), ""]

    # Emit the coverage note
    if lang == "en":
        lines.append(f"*Evidence coverage: {evidence_coverage} data signal types used.*")
    elif lang == "hi":
        lines.append(f"*साक्ष्य कवरेज: {evidence_coverage} डेटा संकेत प्रकार उपयोग किए गए।*")
    else:
        lines.append(f"*சான்று கவரேஜ்: {evidence_coverage} தரவு சமிக்ஞை வகைகள் பயன்படுத்தப்பட்டன.*")
    lines.append("")

    templates = _FACTOR_TEMPLATES.get(lang, _FACTOR_TEMPLATES["en"])

    for comp in components:
        factor_label = comp.get("label", "")
        template = templates.get(factor_label)
        if template:
            try:
                raw_value = comp.get("raw_value", 0)
                # Format numeric raw values; pass string as-is
                if isinstance(raw_value, float):
                    raw_value_fmt = f"{raw_value:.2f}"
                else:
                    raw_value_fmt = str(raw_value)

                line = template.format(
                    raw_value=raw_value_fmt if not isinstance(raw_value, float) or factor_label == "Boundary Proximity" else raw_value,
                    raw_unit=comp.get("raw_unit", ""),
                    component_score=comp.get("component_score", 0),
                    weight_pct=comp.get("weight", 0) * 100,
                    contribution=comp.get("contribution", 0),
                )
                lines.append(line)
            except (KeyError, ValueError) as exc:
                logger.warning("[ExplainRisk] Format error for %s: %s", factor_label, exc)
        else:
            lines.append(
                f"• **{factor_label}**: score {comp.get('component_score', 0):.0f}/100 "
                f"→ contribution {comp.get('contribution', 0):.1f}"
            )

    total_fmt = _TOTALS.get(lang, _TOTALS["en"]).format(
        total=total, label=label, recommendation=recommendation
    )
    lines.append(total_fmt)
    lines.append(_DISCLAIMER.get(lang, _DISCLAIMER["en"]))

    answer_text = "\n".join(lines)
    logger.info("[ExplainRisk] Explanation generated for lang=%s, label=%s", lang, label)

    return {
        "final_answer_text": answer_text,
        "map_geojson": state.get("map_geojson", {"type": "FeatureCollection", "features": []}),
    }
