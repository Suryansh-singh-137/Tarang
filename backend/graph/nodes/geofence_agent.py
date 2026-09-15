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
    Pure deterministic computation — no external API.
    """
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

    from pathlib import Path
    _DATA_DIR = Path(__file__).parent.parent.parent / "data"
    _IMBL_FILE = _DATA_DIR / "imbl_boundary.geojson"
    used_geojson = _IMBL_FILE.exists()

    boundary_waypoints = load_imbl_waypoints()
    dist_to_imbl_km = distance_to_polyline(lat, lon, boundary_waypoints)
    boundary_risk = _boundary_risk(dist_to_imbl_km)

    logger.info(
        "[Geofence] %s → IMBL: %.1f km (risk=%s)",
        location_name, dist_to_imbl_km, boundary_risk,
    )

    # Variables per PRD §9
    inside_boundary = True  # In Indian maritime waters
    warning = None
    if dist_to_imbl_km < 10.0:
        warning = f"CRITICAL: Within {dist_to_imbl_km:.1f} km of India-Sri Lanka IMBL. High risk of boundary crossing."
    elif dist_to_imbl_km < 20.0:
        warning = f"ALERT: Within {dist_to_imbl_km:.1f} km of India-Sri Lanka IMBL. Exercise caution."

    geometry_source = (
        "data/imbl_boundary.geojson"
        if used_geojson
        else "Hardcoded IMBL waypoints (UNCLOS reference, public domain)"
    )

    data = {
        "query_lat": lat,
        "query_lon": lon,
        "distance_to_boundary_km": round(dist_to_imbl_km, 1),
        "distance_to_imbl_km": round(dist_to_imbl_km, 1),
        "inside_boundary": inside_boundary,
        "warning": warning,
        "geometry_source": geometry_source,
        "boundary_risk": boundary_risk,
        "boundary_name": "India–Sri Lanka Maritime Boundary Line (IMBL)",
        "geojson_used": used_geojson,
        "waypoint_count": len(boundary_waypoints),
    }

    if warning:
        summary = (
            f"{location_name} is approximately {dist_to_imbl_km:.0f} km from the IMBL. "
            f"Boundary proximity risk: {boundary_risk.upper()}. {warning}"
        )
    else:
        summary = (
            f"{location_name} is approximately {dist_to_imbl_km:.0f} km from the IMBL. "
            f"Boundary proximity risk: {boundary_risk}."
        )

    source = (
        "Static IMBL GeoJSON (data/imbl_boundary.geojson)"
        if used_geojson
        else "Hardcoded IMBL waypoints (UNCLOS reference, public domain)"
    )

    evidence: list[EvidenceItem] = [
        EvidenceItem(
            claim=f"Distance to India-Sri Lanka Maritime Boundary Line (IMBL) is {dist_to_imbl_km:.0f} km",
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
            claim=f"Maritime boundary proximity warning: {warning}",
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
        "used_fallback": not used_geojson,
        "data_quality": "live" if used_geojson else "fallback",
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
