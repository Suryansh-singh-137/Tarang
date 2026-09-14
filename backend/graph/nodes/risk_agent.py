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

Milestone 3: Emits data_quality = "live" (always — deterministic computation).

Milestone 4: Emits structured RiskComponent breakdown per factor so that
             synthesis and explain_risk can name top contributors in plain
             language without re-computing. Also emits evidence_coverage.

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
from graph.state import AgentResult, EvidenceItem, ORCAState, RiskComponent
from tools.data_validator import all_critical_data_available

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
    warnings_lower = [str(w).lower() for w in active_warnings]
    if "cyclone_warning" in warnings_lower:
        score = 100.0  # cyclone overrides everything
    elif any(w in warnings_lower for w in ["severe_lightning", "gale_warning", "storm_warning", "squall", "severe_hazard"]):
        score = max(score, 80.0)
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
            "Conditions are currently rated low risk by Tarang. Check the latest official advisory before leaving shore."
        ),
        "MODERATE": (
            "Conditions need caution. Check the latest advisory and sea conditions before leaving shore."
        ),
        "HIGH": (
            "Conditions are risky right now. Avoid going out until conditions improve and official advisories allow it."
        ),
        "EXTREME": (
            "Conditions are dangerous right now. Avoid going out until conditions improve and official advisories allow it."
        ),
        "UNKNOWN": (
            "Tarang does not have enough reliable data to assess the trip safely right now."
        ),
    }.get(risk_label, "Tarang does not have enough reliable data to assess the trip safely right now.")


# ---------------------------------------------------------------------------
# Public node function
# ---------------------------------------------------------------------------

def risk_agent(state: ORCAState) -> dict:
    """
    LangGraph node: compute deterministic weighted risk score.
    Uses real normalised values from weather, hazard, and geofence agents.

    Milestone 4: Builds structured RiskComponent list for explainability.
    """
    resolved = state.get("resolved_location")
    if not resolved or not resolved.get("coastal"):
        logger.info("[Risk] Skipped: resolved_location is missing or non-coastal")
        result: AgentResult = {
            "agent_name": "risk_agent",
            "status": "skipped",
            "execution_status": "skipped",
            "data_status": "unavailable",
            "location_used": None,
            "observed_at": None,
            "data": {},
            "source": "Tarang Composite Risk Model v1",
            "summary": "Risk assessment skipped: location is not a verified coastal zone.",
            "used_fallback": False,
            "data_quality": "unavailable",
            "timestamp": "",
            "error": None,
            "evidence": [],
        }
        return {"risk_result": result}

    lat = resolved["lat"]
    lon = resolved["lon"]
    location_used = {"lat": round(lat, 4), "lon": round(lon, 4)}

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    weather = state.get("weather_result")
    hazard  = state.get("hazard_result")
    geofence = state.get("geofence_result")
    dq_reports = state.get("data_quality_reports") or []
    logger.info(
        f"[TRACE][5] risk_agent dq_reports count={len(dq_reports)}: "
        f"{[{'agent': r.get('agent_name'), 'dq': r.get('data_quality'), 'fallback': r.get('used_fallback')} for r in dq_reports]}"
    )

    # -----------------------------------------------------------------------
    # M8 Phase F & V2.1: Fail-Closed Validation (PRD §10 & §20)
    # -----------------------------------------------------------------------
    weather_ok = (
        weather is not None
        and weather.get("execution_status") == "success"
        and weather.get("data_status") == "live"
        and bool(weather.get("data"))
        and weather.get("data", {}).get("wave_height_m") is not None
        and weather.get("data", {}).get("wind_speed_kmh") is not None
    )
    hazard_ok = (
        hazard is not None
        and hazard.get("execution_status") in ("success", "partial")
        and hazard.get("data_status") == "live"
        and bool(hazard.get("data"))
    )
    total_signals = 4
    critical_data_ok = weather_ok and hazard_ok and all_critical_data_available(dq_reports)
    logger.info(f"[TRACE][5] risk_agent critical_data_ok={critical_data_ok} (weather_ok={weather_ok}, hazard_ok={hazard_ok})")

    if not critical_data_ok:
        logger.warning("[Risk] CRITICAL DATA MISSING/UNAVAILABLE. Failing closed with UNKNOWN.")
        risk_assessment_payload = {
            "composite_score": None,
            "base_level": "UNKNOWN",
            "override_active": False,
            "override_reason": "Missing or unavailable critical marine weather/hazard data",
            "final_level": "UNKNOWN",
            "critical_hazard": False,
            "data_completeness": 0.0,
        }
        data = {
            **risk_assessment_payload,
            "risk_inputs_evaluated": f"0/{total_signals}",
            "risk_label": "UNKNOWN",
            "component_scores": {},
            "weights": config.RISK_WEIGHTS,
            "components": [],
            "evidence_coverage": "insufficient",
            "inputs": {},
            "recommendation": (
                "Tarang does not have enough reliable data to assess the trip safely right now."
            ),
            "data_sources_live": {
                "weather": weather_ok,
                "hazard": hazard_ok,
                "geofence": geofence.get("execution_status") == "success" if geofence else False,
            },
        }
        summary = "Risk assessment unavailable (UNKNOWN) due to missing or unavailable critical marine weather/hazard data."

        result: AgentResult = {
            "agent_name": "risk_agent",
            "status": "insufficient_data",
            "execution_status": "failed",
            "data_status": "unavailable",
            "location_used": location_used,
            "observed_at": retrieved_at,
            "data": data,
            "source": "Tarang Risk Model v1 (Fail-Closed)",
            "summary": summary,
            "used_fallback": False,
            "data_quality": "unavailable",
            "timestamp": retrieved_at,
            "error": "CRITICAL_DATA_UNAVAILABLE",
            "evidence": [],
        }

        current_trace = state.get("trace") or []
        return {
            "risk_result": result,
            "trace": current_trace + [result],
            "risk_sufficient_data": False,
            "risk_assessment": risk_assessment_payload,
        }

    # ---- Track how many signals are available (for evidence_coverage) ----
    available_signals = 0
    total_signals = 4

    # ---- Extract component values with safe defaults ----
    if weather and weather.get("status") == "success":
        wave_height_m  = weather["data"]["wave_height_m"]
        wind_speed_kmh = weather["data"]["wind_speed_kmh"]
        available_signals += 2  # wave + wind are separate signals
    else:
        wave_height_m  = 2.0
        wind_speed_kmh = 30.0

    active_warnings: list[str] = []
    if hazard and hazard.get("status") in ("success", "partial"):
        h_data = hazard.get("data")
        if isinstance(h_data, dict):
            hazard_level = str(h_data.get("overall_hazard_level") or h_data.get("hazard_level") or "none").lower()
            raw_act = h_data.get("active_warnings") or h_data.get("hazards") or []
            if isinstance(raw_act, list):
                for item in raw_act:
                    if isinstance(item, str):
                        active_warnings.append(item)
                    elif isinstance(item, dict):
                        for fld in ("type", "title", "severity", "name"):
                            if item.get(fld):
                                active_warnings.append(str(item[fld]))
            elif isinstance(raw_act, str):
                active_warnings.append(raw_act)
            if h_data.get("hazard"):
                active_warnings.append(str(h_data["hazard"]))
            if h_data.get("severe_active_hazard"):
                active_warnings.append("severe_hazard")
            available_signals += 1
        elif isinstance(h_data, str):
            active_warnings.append(h_data)
            available_signals += 1
    else:
        hazard_level    = "none"
        active_warnings = []

    dist_to_imbl_km = (
        geofence["data"]["distance_to_imbl_km"] if geofence and geofence.get("status") == "success" else 60.0
    )
    if geofence and geofence.get("status") == "success":
        available_signals += 1

    logger.info(
        "[Risk] Inputs: wave=%.2fm wind=%.1fkm/h hazard=%s boundary=%.1fkm",
        wave_height_m, wind_speed_kmh, hazard_level, dist_to_imbl_km,
    )

    # ---- Component scores ----
    weights = config.RISK_WEIGHTS
    raw_scores = {
        "wave_height":        _wave_score(wave_height_m),
        "wind_speed":         _wind_score(wind_speed_kmh),
        "hazard_level":       _hazard_score(hazard_level, active_warnings),
        "boundary_proximity": _boundary_proximity_score(dist_to_imbl_km),
    }

    # ---- Weighted composite ----
    composite = sum(raw_scores[k] * weights[k] for k in weights)
    composite = round(composite, 1)
    base_level = _risk_label(composite)

    # ---- PRD §7, §25: Deterministic Safety Override Logic ----
    override_active = False
    override_reason = None
    final_level = base_level
    critical_hazard = False

    warnings_lower = [str(w).lower() for w in active_warnings]
    is_extreme_hazard = (
        hazard_level == "extreme"
        or "cyclone_warning" in warnings_lower
        or any("cyclone" in w for w in warnings_lower)
    )
    is_high_hazard = (
        hazard_level == "high"
        or any(w in warnings_lower for w in ["severe_lightning", "gale_warning", "storm_warning", "squall", "severe_hazard"])
        or any("lightning" in w for w in warnings_lower)
        or any("gale" in w for w in warnings_lower)
        or any("storm" in w for w in warnings_lower)
        or any("squall" in w for w in warnings_lower)
        or any("severe" in w for w in warnings_lower)
    )
    is_moderate_hazard = (hazard_level == "moderate")

    if is_extreme_hazard:
        critical_hazard = True
        override_active = True
        override_reason = f"Active extreme hazard detected ({hazard_level})"
        final_level = "EXTREME"
    elif is_high_hazard:
        critical_hazard = True
        if base_level in ("LOW", "MODERATE"):
            override_active = True
            override_reason = f"Active high hazard advisory/warning ({hazard_level if hazard_level != 'none' else 'severe_hazard'})"
            final_level = "HIGH"
    elif is_moderate_hazard:
        if base_level == "LOW":
            override_active = True
            override_reason = "Moderate hazard advisory requires at least CAUTION"
            final_level = "MODERATE"

    # PRD §7 Mandatory Invariant: if severe_active_hazard, final_status != LOW
    if (critical_hazard or is_high_hazard or is_extreme_hazard) and final_level == "LOW":
        override_active = True
        override_reason = "Safety invariant: severe active hazard overrides LOW risk"
        final_level = "HIGH"

    label = final_level
    data_completeness = round(available_signals / total_signals, 2)

    logger.info(
        "[Risk] Score=%.1f (base=%s, final=%s, override=%s) signals=%d/%d",
        composite, base_level, final_level, override_active, available_signals, total_signals,
    )

    # ---- Milestone 4: Build structured RiskComponent breakdown ----
    component_meta = {
        "wave_height": {
            "label": "Wave Height",
            "raw_value": wave_height_m,
            "raw_unit": "m",
        },
        "wind_speed": {
            "label": "Wind Speed",
            "raw_value": wind_speed_kmh,
            "raw_unit": "km/h",
        },
        "hazard_level": {
            "label": "Hazard Level",
            "raw_value": hazard_level,
            "raw_unit": "category",
        },
        "boundary_proximity": {
            "label": "Boundary Proximity",
            "raw_value": dist_to_imbl_km,
            "raw_unit": "km",
        },
    }

    components: list[RiskComponent] = []
    for key, raw_score in raw_scores.items():
        w = weights[key]
        meta = component_meta[key]
        components.append(RiskComponent(
            label=meta["label"],
            raw_value=meta["raw_value"],
            raw_unit=meta["raw_unit"],
            component_score=raw_score,
            weight=w,
            contribution=round(raw_score * w, 2),
            max_possible=round(w * 100.0, 1),
        ))

    # Sort by contribution descending (highest contributor first)
    components.sort(key=lambda c: c["contribution"], reverse=True)

    evidence_coverage = f"{available_signals}/{total_signals}"

    data = {
        "composite_score": composite,
        "base_level": base_level,
        "final_level": final_level,
        "override_active": override_active,
        "override_reason": override_reason,
        "critical_hazard": critical_hazard,
        "data_completeness": data_completeness,
        "risk_inputs_evaluated": f"{available_signals}/{total_signals}",
        "risk_label": label,
        # Legacy flat component_scores kept for backward compatibility
        "component_scores": {k: v for k, v in raw_scores.items()},
        "weights": weights,
        # Milestone 4: structured breakdown
        "components": [dict(c) for c in components],
        "evidence_coverage": evidence_coverage,
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
        f"Top factor: {components[0]['label']} (contribution: {components[0]['contribution']:.1f}/100). "
        f"Risk inputs evaluated: {evidence_coverage}."
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
        "execution_status": "success",
        "data_status": "live",
        "location_used": location_used,
        "observed_at": retrieved_at,
        "data": data,
        "source": "Tarang Risk Model v1 (deterministic weighted formula)",
        "summary": summary,
        "used_fallback": False,
        "data_quality": "live",   # deterministic computation, always "live"
        "timestamp": retrieved_at,
        "error": None,
        "evidence": evidence,
    }

    current_trace = state.get("trace") or []
    current_evidence = state.get("evidence") or []
    risk_assessment_payload = {
        "composite_score": composite,
        "base_level": base_level,
        "override_active": override_active,
        "override_reason": override_reason,
        "final_level": final_level,
        "critical_hazard": critical_hazard,
        "data_completeness": data_completeness,
    }
    return {
        "risk_result": result,
        "trace": current_trace + [result],
        "evidence": current_evidence + evidence,
        "risk_sufficient_data": True,
        "risk_assessment": risk_assessment_payload,
    }
