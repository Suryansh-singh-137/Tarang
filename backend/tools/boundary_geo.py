"""
boundary_geo.py
---------------
Reusable geospatial helpers extracted from geofence_agent.

Provides:
  - haversine distance (km) between two (lat, lon) points
  - point-to-polyline minimum distance
  - IMBL boundary loader
"""

from __future__ import annotations

import json
import math
from pathlib import Path

_R = 6371.0  # Earth radius km

DATA_DIR = Path(__file__).parent.parent / "data"
_IMBL_FILE = DATA_DIR / "imbl_boundary.geojson"

# Fallback hardcoded IMBL waypoints (UNCLOS reference, public domain)
_IMBL_WAYPOINTS_DEFAULT: list[tuple[float, float]] = [
    (10.00, 80.12),
    (9.50,  80.05),
    (9.00,  79.95),
    (8.50,  79.80),
    (8.00,  79.70),
    (7.50,  79.65),
    (7.00,  79.60),
]


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between two (lat, lon) points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * _R * math.asin(math.sqrt(a))


def distance_to_polyline(
    lat: float, lon: float, waypoints: list[tuple[float, float]]
) -> float:
    """Return the minimum haversine distance (km) from a point to any waypoint."""
    return min(haversine(lat, lon, wlat, wlon) for wlat, wlon in waypoints)


def load_imbl_waypoints() -> list[tuple[float, float]]:
    """Load IMBL boundary waypoints from GeoJSON file, or fall back to hardcoded."""
    if not _IMBL_FILE.exists():
        return _IMBL_WAYPOINTS_DEFAULT

    with open(_IMBL_FILE, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    waypoints: list[tuple[float, float]] = []
    for feature in geojson.get("features", []):
        geom = feature.get("geometry", {})
        gtype = geom.get("type", "")
        coords = geom.get("coordinates", [])

        if gtype == "LineString":
            for lon_c, lat_c in coords:
                waypoints.append((lat_c, lon_c))
        elif gtype == "MultiLineString":
            for line in coords:
                for lon_c, lat_c in line:
                    waypoints.append((lat_c, lon_c))
        elif gtype == "Point":
            lon_c, lat_c = coords[0], coords[1]
            waypoints.append((lat_c, lon_c))

    return waypoints if waypoints else _IMBL_WAYPOINTS_DEFAULT
