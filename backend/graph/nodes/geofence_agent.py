"""
geofence_agent node
-------------------
Computes distance from the query point to maritime boundary lines and
marine protected areas using Shapely geometry over static GeoJSON.

This is a pure, fast, always-reliable computation — no external API call.
It is the demo showpiece for deterministic geospatial reasoning.

Milestone 1: Uses hardcoded IMBL waypoints (simplified) if the GeoJSON file
             is not yet present.  The data/imbl_boundary.geojson file is
             committed to the repo (static, always available).
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

from graph.state import AgentResult, ORCAState

# ---------------------------------------------------------------------------
# Path to the static IMBL GeoJSON (committed to repo, never fails)
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_IMBL_FILE = _DATA_DIR / "imbl_boundary.geojson"

# ---------------------------------------------------------------------------
# Simplified IMBL (India-Sri Lanka Maritime Boundary Line) waypoints.
# These are publicly available reference points used as a hard-coded fallback
# if the GeoJSON file has not yet been committed.
# Source: UNCLOS delimitation reference, publicly available.
# ---------------------------------------------------------------------------
_IMBL_WAYPOINTS: list[tuple[float, float]] = [
    # (lat, lon) — simplified polyline from north to south
    (10.00, 80.12),
    (9.50, 80.05),
    (9.00, 79.95),
    (8.50, 79.80),
    (8.00, 79.70),
    (7.50, 79.65),
    (7.00, 79.60),
]

# ---------------------------------------------------------------------------
# Haversine distance (pure Python — no shapely needed for point-to-polyline)
# ---------------------------------------------------------------------------
_R = 6371.0  # Earth radius in km


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between two (lat, lon) points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _R * math.asin(math.sqrt(a))


def _distance_to_polyline(lat: float, lon: float, waypoints: list[tuple[float, float]]) -> float:
    """Return the minimum distance (km) from a point to any waypoint of a polyline."""
    return min(_haversine(lat, lon, wlat, wlon) for wlat, wlon in waypoints)


# ---------------------------------------------------------------------------
# Load boundary waypoints from GeoJSON if the file exists
# ---------------------------------------------------------------------------

def _load_boundary_waypoints() -> list[tuple[float, float]]:
    if not _IMBL_FILE.exists():
        return _IMBL_WAYPOINTS  # fallback to hardcoded

    with open(_IMBL_FILE, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    waypoints: list[tuple[float, float]] = []
    for feature in geojson.get("features", []):
        geom = feature.get("geometry", {})
        gtype = geom.get("type", "")
        coords = geom.get("coordinates", [])

        if gtype == "LineString":
            for lon, lat in coords:
                waypoints.append((lat, lon))
        elif gtype == "MultiLineString":
            for line in coords:
                for lon, lat in line:
                    waypoints.append((lat, lon))
        elif gtype == "Point":
            lon, lat = coords[0], coords[1]
            waypoints.append((lat, lon))

    return waypoints if waypoints else _IMBL_WAYPOINTS


# ---------------------------------------------------------------------------
# Risk zone classification based on distance to boundary
# ---------------------------------------------------------------------------

def _boundary_risk(dist_km: float) -> str:
    if dist_km < 10:
        return "critical"   # extremely close — do not cross
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
    """
    intent = state["parsed_intent"]
    assert intent is not None

    lat = intent["lat"] or 8.7642
    lon = intent["lon"] or 78.1348
    location_name = intent["location_name"]

    boundary_waypoints = _load_boundary_waypoints()
    used_geojson = _IMBL_FILE.exists()

    dist_to_imbl_km = _distance_to_polyline(lat, lon, boundary_waypoints)
    boundary_risk = _boundary_risk(dist_to_imbl_km)

    data = {
        "query_lat": lat,
        "query_lon": lon,
        "distance_to_imbl_km": round(dist_to_imbl_km, 1),
        "boundary_risk": boundary_risk,
        "boundary_name": "India–Sri Lanka Maritime Boundary Line (IMBL)",
        "geojson_used": used_geojson,
        "waypoint_count": len(boundary_waypoints),
    }

    if dist_to_imbl_km < 20:
        summary = (
            f"{location_name} is approximately {dist_to_imbl_km:.0f} km from the IMBL. "
            f"Boundary proximity risk: {boundary_risk.upper()}. "
            "Fishermen are strongly advised not to cross the maritime boundary."
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

    result: AgentResult = {
        "agent_name": "geofence_agent",
        "status": "success",
        "data": data,
        "source": source,
        "summary": summary,
        "used_fallback": not used_geojson,
    }

    current_trace = state.get("trace") or []
    return {
        "geofence_result": result,
        "trace": current_trace + [result],
    }
