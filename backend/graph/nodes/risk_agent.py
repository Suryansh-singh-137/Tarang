"""
risk_agent node
---------------
Computes a deterministic, weighted risk score from weather, hazard, and
geofence signals. PFZ data is used for fishing-opportunity context only —
NOT as a direct safety signal.

This node MUST NOT call an LLM. The formula is transparent and
all component scores are exposed in `data` so the UI trace panel can show
why the score is what it is.

Milestone 2: Updated to emit new AgentResult fields (timestamp, error, evidence)
             and to source weights from config.py.

Risk scale: 0.0 (safe) → 100.0 (extreme risk)
  0-25:  LOW    — generally manageable conditions
  26-50: MODERATE — exercise caution
  51-75: HIGH   — avoid if possible
  76-100: EXTREME — do not go to sea

Weights (sourced from config.RISK_WEIGHTS, must sum to 1.0):
  wave_height:       0.30
  wind_speed:        0.20
  hazard_level:      0.30
  boundary_proximity: 0.20
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import config
from graph.state import AgentResult, EvidenceItem, ORCAState

logger = logging.getLogger("tarang.risk")

# ---------------------------------------------------------------------------
# Component scorers (each returns 0.0–100.0)
# ---------------------------------------------------------------------------

def _wave_score(wave_height_m: float) -> float:
    """0 m → 0; 1 m → 20; 2 m → 50; 3 m → 75; ≥4 m → 100"""
    if wave_height_m <= 0.5:
        return 0.0
    elif wave_height_m <= 1.25:
        return 20.0
    elif wave_height_m <= 2.0:
        return 40.0
    elif wave_height_m <= 2.5:
        return 60.0
    elif wave_height_m <= 3.5:
        return 80.0
    else:
        return 100.0


def _wind_score(wind_speed_kmh: float) -> float:
    """Beaufort-aligned thresholds."""
    if wind_speed_kmh < 20:
        return 0.0
    elif wind_speed_kmh < 30:
        return 25.0
    elif wind_speed_kmh < 40:
        return 50.0
    elif wind_speed_kmh < 55:
        return 75.0
    else:
        return 100.0


def _hazard_score(overall_hazard_level: str, active_warnings: list) -> float:
    """Map qualitative hazard level + cyclone flag to 0–100."""
    base: dict[str, float] = {
        "none": 0.0,
        "low": 25.0,
        "moderate": 55.0,
        "high": 80.0,
        "extreme": 100.0,
    }
    score = base.get(overall_hazard_level, 0.0)
    if "cyclone_warning" in active_warnings:
        score = 100.0  # cyclone overrides everything
    return score


def _boundary_proximity_score(dist_km: float) -> float:
    """Shorter distance → higher score."""
    if dist_km >= 50:
        return 0.0
    elif dist_km >= 30:
        return 20.0
    elif dist_km >= 20:
        return 40.0
    elif dist_km >= 10:
        return 70.0
    else:
        return 100.0


def _risk_label(score: float) -> str:
    if score <= 25:
        return "LOW"
    elif score <= 50:
        return "MODERATE"
    elif score <= 75:
        return "HIGH"
    else:
        return "EXTREME"


def _recommendation(risk_label: str) -> str:
    return {
        "LOW": (
            "Conditions appear manageable. Proceed with standard safety precautions. "
            "This is a decision-support assessment, not an official safety clearance."
        ),
        "MODERATE": (
            "Exercise caution. Monitor conditions closely before and during the voyage. "
            "This is a decision-support assessment, not an official safety clearance."
        ),
        "HIGH": (
            "Conditions are adverse. Avoid venturing to sea if possible. "
            "Consult IMD/INCOIS advisories before departure. "
            "This is a decision-support assessment, not an official safety clearance."
        ),
        "EXTREME": (
            "Do NOT go to sea. Conditions are dangerous. "
            "Follow all official advisories from IMD / INCOIS / Coast Guard. "
            "This is a decision-support assessment, not an official safety clearance."
        ),
    }[risk_label]


# ---------------------------------------------------------------------------
# Public node function
# ---------------------------------------------------------------------------

def risk_agent(state: ORCAState) -> dict:
    """
    LangGraph node: compute deterministic weighted risk score.
    Uses real normalised values from weather, hazard, and geofence agents.
    """
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    weather = state.get("weather_result")
    hazard  = state.get("hazard_result")
    geofence = state.get("geofence_result")

    # ---- Extract component values with safe defaults ----
    wave_height_m  = (weather["data"]["wave_height_m"]  if weather else 2.0)
    wind_speed_kmh = (weather["data"]["wind_speed_kmh"] if weather else 30.0)

    if hazard:
        hazard_level    = hazard["data"].get("overall_hazard_level", "none")
        active_warnings = hazard["data"].get("active_warnings", [])
    else:
        hazard_level    = "none"
        active_warnings = []

    dist_to_imbl_km = (
        geofence["data"]["distance_to_imbl_km"] if geofence else 60.0
    )

    logger.info(
        "[Risk] Inputs: wave=%.2fm wind=%.1fkm/h hazard=%s boundary=%.1fkm",
        wave_height_m, wind_speed_kmh, hazard_level, dist_to_imbl_km,
    )

    # ---- Component scores ----
    component_scores = {
        "wave_height":        _wave_score(wave_height_m),
        "wind_speed":         _wind_score(wind_speed_kmh),
        "hazard_level":       _hazard_score(hazard_level, active_warnings),
        "boundary_proximity": _boundary_proximity_score(dist_to_imbl_km),
    }

    # ---- Weighted composite (sourced from config) ----
    weights = config.RISK_WEIGHTS
    composite = sum(component_scores[k] * weights[k] for k in weights)
    composite = round(composite, 1)
    label = _risk_label(composite)

    logger.info("[Risk] Score=%.1f (%s)", composite, label)

    data = {
        "composite_score": composite,
        "risk_label": label,
        "component_scores": component_scores,
        "weights": weights,
        "inputs": {
            "wave_height_m":      wave_height_m,
            "wind_speed_kmh":     wind_speed_kmh,
            "hazard_level":       hazard_level,
            "active_warnings":    active_warnings,
            "distance_to_imbl_km": dist_to_imbl_km,
        },
        "recommendation": _recommendation(label),
        # Disclose if any upstream agent used fallback
        "data_sources_live": {
            "weather": not (weather["used_fallback"] if weather else True),
            "hazard":  not (hazard["used_fallback"]  if hazard  else True),
            "geofence": not (geofence["used_fallback"] if geofence else True),
        },
    }

    summary = (
        f"Overall decision-support risk score: {composite}/100 ({label}). "
        f"Components — waves: {component_scores['wave_height']:.0f}, "
        f"wind: {component_scores['wind_speed']:.0f}, "
        f"hazards: {component_scores['hazard_level']:.0f}, "
        f"boundary: {component_scores['boundary_proximity']:.0f}."
    )

    evidence: list[EvidenceItem] = [
        EvidenceItem(
            claim=f"Composite decision-support risk score: {composite}/100 ({label})",
            value=composite,
            unit="/100",
            source="Tarang Risk Model v1 (deterministic weighted formula)",
            source_time=retrieved_at,
            retrieved_at=retrieved_at,
            location=None,
        )
    ]

    result: AgentResult = {
        "agent_name": "risk_agent",
        "status": "success",
        "data": data,
        "source": "Tarang Risk Model v1 (deterministic weighted formula)",
        "summary": summary,
        "used_fallback": False,
        "timestamp": retrieved_at,
        "error": None,
        "evidence": evidence,
    }

    current_trace = state.get("trace") or []
    current_evidence = state.get("evidence") or []
    return {
        "risk_result": result,
        "trace": current_trace + [result],
        "evidence": current_evidence + evidence,
    }
