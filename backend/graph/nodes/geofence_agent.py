"""
geofence_agent node
-------------------
Computes distance from the query point to maritime boundary lines and
marine protected areas using Shapely geometry over static GeoJSON.

This is a pure, fast, always-reliable computation — no external API call.

Milestone 2: Updated to use tools/boundary_geo.py helpers and to emit
             the new AgentResult fields (timestamp, error, evidence).
"""

from __future__ import annotations
import os

import logging
from datetime import datetime, timezone

from graph.state import AgentResult, EvidenceItem, ORCAState
from tools.boundary_geo import distance_to_polyline, load_imbl_waypoints

logger = logging.getLogger("tarang.geofence")

# ---------------------------------------------------------------------------
# Risk zone classification based on distance to boundary
# ---------------------------------------------------------------------------

def _boundary_risk(dist_km: float) -> str:
    if dist_km < 10:
        return "critical"
    elif dist_km < 20:
        return "high"
    elif dist_km < 40:
        return "moderate"
    else:
        return "low"


# ---------------------------------------------------------------------------
# Public node function
# ---------------------------------------------------------------------------

def geofence_agent(state: ORCAState) -> dict:
    """
    LangGraph node: compute geospatial distances to maritime boundaries.
    Evaluates proximity to all 7 international maritime boundaries, detects foreign
    water breaches, and dispatches emergency WhatsApp alerts if breached.
    """
    from tools.boundary_geo import evaluate_maritime_geofence
    from tools.whatsapp_sender import send_geofence_breach_alert_throttled

    resolved = state.get("resolved_location")
    if not resolved or not resolved.get("coastal"):
        logger.info("[Geofence] Skipped: resolved_location is missing or non-coastal")
        result: AgentResult = {
            "agent_name": "geofence_agent",
            "status": "skipped",
            "execution_status": "skipped",
            "data_status": "unavailable",
            "location_used": None,
            "observed_at": None,
            "data": {},
            "source": "IMBL Boundary",
            "summary": "Geofence assessment skipped: location is not a verified coastal zone.",
            "used_fallback": False,
            "data_quality": "unavailable",
            "timestamp": "",
            "error": None,
            "evidence": [],
        }
        return {"geofence_result": result}

    lat = resolved["lat"]
    lon = resolved["lon"]
    location_name = resolved.get("name", "Coastal Location")
    location_used = {"lat": round(lat, 4), "lon": round(lon, 4)}

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Evaluate against all 7 international maritime boundaries
    eval_geo = evaluate_maritime_geofence(lat, lon, location_name=location_name)
    is_breached = bool(eval_geo.get("is_breached", False))
    dist_to_imbl_km = float(eval_geo.get("distance_km", 0.0))
    boundary_name = str(eval_geo.get("boundary_name", "India–Sri Lanka Maritime Boundary Line (IMBL)"))
    sector = str(eval_geo.get("sector", "Territorial Border Sector"))
    bearing_to_safety = float(eval_geo.get("bearing_to_safety", 270.0))
    bearing_cardinal = str(eval_geo.get("bearing_cardinal", "W"))
    warning_title = str(eval_geo.get("warning_title", ""))
    warning_message = str(eval_geo.get("warning_message", ""))
    coastguard_number = str(eval_geo.get("coastguard_number", "1554"))

    boundary_risk = "critical" if is_breached else _boundary_risk(dist_to_imbl_km)

    logger.info(
        "[Geofence] %s (%.4f, %.4f) → %s: %.1f km (breached=%s, risk=%s)",
        location_name, lat, lon, boundary_name, dist_to_imbl_km, is_breached, boundary_risk,
    )

    inside_boundary = not is_breached
    warning = None
    if is_breached:
        warning = warning_message or f"CRITICAL: Crossed {boundary_name}! Penetration: {dist_to_imbl_km:.1f} km into foreign waters."
    elif dist_to_imbl_km < 10.0:
        warning = f"CRITICAL: Within {dist_to_imbl_km:.1f} km of {boundary_name}. High risk of boundary crossing."
    elif dist_to_imbl_km < 20.0:
        warning = f"ALERT: Within {dist_to_imbl_km:.1f} km of {boundary_name}. Exercise caution."

    # Dispatch emergency WhatsApp notification if border is breached
    whatsapp_status = None
    if is_breached:
        import config
        recipient_phone = (
            state.get("user_phone")
            or state.get("recipient_phone")
            or getattr(config, "TWILIO_RECIPIENT_PHONE", "")
            or os.environ.get("TWILIO_RECIPIENT_PHONE", "+919236454423")
        )
        if recipient_phone:
            cooldown_s = int(os.environ.get("GEOFENCE_WHATSAPP_COOLDOWN_SECONDS", "30"))
            whatsapp_status = send_geofence_breach_alert_throttled(
                recipient_phone,
                eval_geo,
                cooldown_s=cooldown_s,
            )
            logger.warning(
                "[Geofence Agent] Border breach alert dispatched to %s: result=%s",
                recipient_phone, whatsapp_status,
            )

    data = {
        "query_lat": lat,
        "query_lon": lon,
        "distance_to_boundary_km": round(dist_to_imbl_km, 1),
        "distance_to_imbl_km": round(dist_to_imbl_km, 1),
        "inside_boundary": inside_boundary,
        "is_breached": is_breached,
        "boundary_name": boundary_name,
        "sector": sector,
        "bearing_to_safety": bearing_to_safety,
        "bearing_cardinal": bearing_cardinal,
        "coastguard_number": coastguard_number,
        "warning": warning,
        "warning_title": warning_title,
        "warning_message": warning_message,
        "boundary_risk": boundary_risk,
        "whatsapp_delivery": whatsapp_status,
        "geometry_source": "UNCLOS International Maritime Boundary Geometries & Polygon Sector Engine",
    }

    if is_breached:
        summary = (
            f"🚨 EMERGENCY: Coordinates indicate vessel has CROSSED the {boundary_name} into foreign waters "
            f"({dist_to_imbl_km:.1f} km penetration). Steer {bearing_cardinal} ({int(bearing_to_safety)}°) immediately."
        )
    elif warning:
        summary = (
            f"{location_name} is approximately {dist_to_imbl_km:.0f} km from the {boundary_name}. "
            f"Boundary proximity risk: {boundary_risk.upper()}. {warning}"
        )
    else:
        summary = (
            f"{location_name} is approximately {dist_to_imbl_km:.0f} km from the {boundary_name}. "
            f"Boundary proximity risk: {boundary_risk}."
        )

    source = f"Tarang Geofence Engine ({boundary_name})"

    evidence: list[EvidenceItem] = [
        EvidenceItem(
            claim=f"Distance to {boundary_name} is {dist_to_imbl_km:.0f} km (breached={is_breached})",
            value=round(dist_to_imbl_km, 1),
            unit="km",
            source=source,
            source_time=retrieved_at,
            retrieved_at=retrieved_at,
            location=location_used,
            provenance_tier="official_operational",
            timestamp=retrieved_at,
            data_type="geometric_distance",
        )
    ]
    if warning:
        evidence.append(EvidenceItem(
            claim=f"Maritime boundary advisory: {warning}",
            value=warning,
            unit="",
            source=source,
            source_time=retrieved_at,
            retrieved_at=retrieved_at,
            location=location_used,
            provenance_tier="official_operational",
            timestamp=retrieved_at,
            data_type="geometric_distance",
        ))

    result: AgentResult = {
        "agent_name": "geofence_agent",
        "status": "success",
        "execution_status": "success",
        "data_status": "live",
        "location_used": location_used,
        "observed_at": retrieved_at,
        "data": data,
        "source": source,
        "summary": summary,
        "used_fallback": False,
        "data_quality": "live",
        "timestamp": retrieved_at,
        "error": None,
        "evidence": evidence,
    }

    current_trace = state.get("trace") or []
    current_evidence = state.get("evidence") or []
    return {
        "geofence_result": result,
        "trace": current_trace + [result],
        "evidence": current_evidence + evidence,
    }
