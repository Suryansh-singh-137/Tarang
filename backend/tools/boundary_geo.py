"""
boundary_geo.py
---------------
Reusable geospatial helpers for maritime boundary calculation, geofencing,
and international border breach detection.

Provides:
  - haversine distance (km) between two (lat, lon) points
  - compute_bearing & bearing_to_cardinal
  - closest point on polyline segment
  - IMBL & maritime boundary definitions (India-Sri Lanka, India-Pakistan)
  - evaluate_maritime_geofence: detects if a vessel has crossed into foreign waters
"""

from __future__ import annotations
import os

import json
import math
from pathlib import Path
from typing import TypedDict, Optional

_R = 6371.0  # Earth radius km

DATA_DIR = Path(__file__).parent.parent / "data"
_IMBL_FILE = DATA_DIR / "imbl_boundary.geojson"

# Fallback hardcoded IMBL waypoints (UNCLOS reference, Palk Strait / Gulf of Mannar)
# Ordered North to South
_IMBL_SRI_LANKA_DEFAULT: list[tuple[float, float]] = [
    (10.08, 80.05),
    (9.90,  79.98),
    (9.65,  79.90),
    (9.40,  79.82),
    (9.20,  79.62),
    (9.00,  79.52),
    (8.85,  79.35),
    (8.60,  79.15),
    (8.25,  78.85),
    (7.80,  78.50),
]

# India-Pakistan Maritime Boundary Line (Arabian Sea / Sir Creek sector)
# Ordered North-East (inland creek) to South-West (open sea)
_IMBL_PAKISTAN_DEFAULT: list[tuple[float, float]] = [
    (23.65, 68.18),
    (23.50, 68.00),
    (23.30, 67.80),
    (23.00, 67.45),
    (22.60, 67.00),
    (22.10, 66.40),
    (21.50, 65.70),
]

# India-Bangladesh Maritime Boundary (Bay of Bengal / PCA 2014 delimitation award)
# Ordered North (Sundarbans / Haribhanga mouth) to South (deep Bay of Bengal)
_IMBL_BANGLADESH_DEFAULT: list[tuple[float, float]] = [
    (21.65, 89.15),
    (21.40, 89.25),
    (20.80, 89.45),
    (19.80, 89.70),
    (18.50, 89.95),
    (17.00, 90.20),
]

# India-Maldives Maritime Boundary (1976 Agreement / Eight Degree Channel)
# Ordered West to East between Minicoy Island (India) and Ihavandhippolhu Atoll (Maldives)
_IMBL_MALDIVES_DEFAULT: list[tuple[float, float]] = [
    (7.68, 71.00),
    (7.68, 72.00),
    (7.67, 73.00),
    (7.70, 74.00),
    (7.72, 75.50),
]

# India-Myanmar Maritime Boundary (1986 Agreement / Coco Channel)
# Ordered West to East between North Andaman (Landfall Island) and Coco Islands
_IMBL_MYANMAR_DEFAULT: list[tuple[float, float]] = [
    (13.95, 92.00),
    (13.90, 93.00),
    (13.85, 93.80),
    (13.80, 94.60),
    (13.75, 95.50),
]

# India-Indonesia Maritime Boundary (1974 & 1977 Agreements / Great Channel)
# Ordered North-West to South-East between Indira Point (Great Nicobar) and Rondo Island (Aceh/Sumatra)
_IMBL_INDONESIA_DEFAULT: list[tuple[float, float]] = [
    (6.65, 93.40),
    (6.35, 94.10),
    (6.00, 94.80),
    (5.70, 95.40),
    (5.45, 96.00),
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


def compute_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return initial compass bearing from (lat1, lon1) to (lat2, lon2) in degrees (0-360).
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    initial_bearing = math.atan2(y, x)
    return (math.degrees(initial_bearing) + 360) % 360


def bearing_to_cardinal(degrees: float) -> str:
    """Convert compass heading in degrees to a 16-point cardinal string."""
    cardinals = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
    ]
    idx = int((degrees + 11.25) / 22.5) % 16
    return cardinals[idx]


def closest_point_on_segment(
    plat: float, plon: float,
    alat: float, alon: float,
    blat: float, blon: float
) -> tuple[float, float, float]:
    """
    Project point P onto line segment AB.
    Returns (closest_lat, closest_lon, distance_km).
    """
    dx = blon - alon
    dy = blat - alat
    if dx == 0 and dy == 0:
        return alat, alon, haversine(plat, plon, alat, alon)

    # Parametric t for projection
    t = ((plon - alon) * dx + (plat - alat) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))

    closest_lat = alat + t * dy
    closest_lon = alon + t * dx
    return closest_lat, closest_lon, haversine(plat, plon, closest_lat, closest_lon)


def distance_to_polyline(
    lat: float, lon: float, waypoints: list[tuple[float, float]]
) -> float:
    """Return the minimum haversine distance (km) from a point to a polyline."""
    if not waypoints:
        return 9999.0
    min_dist = float("inf")
    for i in range(len(waypoints) - 1):
        _, _, d = closest_point_on_segment(
            lat, lon,
            waypoints[i][0], waypoints[i][1],
            waypoints[i + 1][0], waypoints[i + 1][1],
        )
        if d < min_dist:
            min_dist = d
    return min_dist


def load_imbl_waypoints() -> list[tuple[float, float]]:
    """Load IMBL boundary waypoints from GeoJSON file, or fall back to hardcoded."""
    if not _IMBL_FILE.exists():
        return _IMBL_SRI_LANKA_DEFAULT

    try:
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

        return waypoints if len(waypoints) >= 2 else _IMBL_SRI_LANKA_DEFAULT
    except Exception:
        return _IMBL_SRI_LANKA_DEFAULT


class GeofenceEvaluation(TypedDict):
    is_breached: bool
    boundary_name: str
    distance_km: float
    status: str  # "breach", "critical_buffer", "warning_buffer", "safe"
    bearing_to_safety: float
    bearing_cardinal: str
    warning_title: str
    warning_message: str
    sector: str
    coordinates: dict[str, float]
    coastguard_number: str


def evaluate_maritime_geofence(lat: float, lon: float, location_name: str = "") -> GeofenceEvaluation:
    """
    Evaluates whether the vessel/coordinates have crossed the International Maritime
    Boundary Line into foreign territorial waters (Sri Lanka or Pakistan),
    or are in immediate buffer risk.
    """
    # 1. Evaluate Sri Lanka IMBL (Palk Strait & Gulf of Mannar)
    # The Sri Lanka IMBL runs roughly N to S between 7.5°N - 10.5°N, 78.5°E - 80.5°E.
    # Indian waters are to the WEST (lower longitude); Sri Lankan waters are to the EAST.
    sl_waypoints = load_imbl_waypoints()
    sl_min_dist = float("inf")
    sl_closest_pt = sl_waypoints[0]
    sl_breached = False

    # Check proximity and which side of each segment
    for i in range(len(sl_waypoints) - 1):
        a_lat, a_lon = sl_waypoints[i]
        b_lat, b_lon = sl_waypoints[i + 1]
        c_lat, c_lon, dist = closest_point_on_segment(lat, lon, a_lat, a_lon, b_lat, b_lon)
        if dist < sl_min_dist:
            sl_min_dist = dist
            sl_closest_pt = (c_lat, c_lon)

    # Determine if east of the IMBL line
    if 5.5 <= lat <= 11.0 and 76.5 <= lon <= 83.0:
        # Interpolate boundary longitude at this latitude
        matched = False
        for i in range(len(sl_waypoints) - 1):
            a_lat, a_lon = sl_waypoints[i]
            b_lat, b_lon = sl_waypoints[i + 1]
            min_l, max_l = min(a_lat, b_lat), max(a_lat, b_lat)
            if min_l <= lat <= max_l:
                fraction = (lat - a_lat) / (b_lat - a_lat) if (b_lat != a_lat) else 0.0
                boundary_lon_at_lat = a_lon + fraction * (b_lon - a_lon)
                if lon > boundary_lon_at_lat:
                    sl_breached = True
                matched = True
                break

        # Extrapolate if point is beyond waypoint range
        if not matched:
            # South of southernmost waypoint — extrapolate from last segment
            if lat < min(p[0] for p in sl_waypoints):
                a_lat, a_lon = sl_waypoints[-2]
                b_lat, b_lon = sl_waypoints[-1]
                if b_lat != a_lat:
                    fraction = (lat - a_lat) / (b_lat - a_lat)
                    boundary_lon_at_lat = a_lon + fraction * (b_lon - a_lon)
                    if lon > boundary_lon_at_lat:
                        sl_breached = True
            # North of northernmost waypoint — extrapolate from first segment
            elif lat > max(p[0] for p in sl_waypoints):
                a_lat, a_lon = sl_waypoints[0]
                b_lat, b_lon = sl_waypoints[1]
                if b_lat != a_lat:
                    fraction = (lat - a_lat) / (b_lat - a_lat)
                    boundary_lon_at_lat = a_lon + fraction * (b_lon - a_lon)
                    if lon > boundary_lon_at_lat:
                        sl_breached = True

    # 2. Evaluate Pakistan Maritime Boundary (Sir Creek / Arabian Sea off Gujarat)
    # Boundary runs NE to SW between 21.0°N - 24.0°N, 65.0°E - 68.5°E.
    # Indian waters are to the SOUTH-EAST; Pakistani waters are to the NORTH-WEST.
    pak_waypoints = _IMBL_PAKISTAN_DEFAULT
    pak_min_dist = float("inf")
    pak_closest_pt = pak_waypoints[0]
    pak_closest_seg_idx = 0
    pak_breached = False

    for i in range(len(pak_waypoints) - 1):
        a_lat, a_lon = pak_waypoints[i]
        b_lat, b_lon = pak_waypoints[i + 1]
        c_lat, c_lon, dist = closest_point_on_segment(lat, lon, a_lat, a_lon, b_lat, b_lon)
        if dist < pak_min_dist:
            pak_min_dist = dist
            pak_closest_pt = (c_lat, c_lon)
            pak_closest_seg_idx = i

    if 20.0 <= lat <= 25.0 and 64.0 <= lon <= 70.5:
        a_lat, a_lon = pak_waypoints[pak_closest_seg_idx]
        b_lat, b_lon = pak_waypoints[pak_closest_seg_idx + 1]
        # Vector cross product: A -> B and A -> P
        # Line runs NE to SW (dx < 0, dy < 0). Right side (NW, Pakistan) produces cross < 0.
        cross = (b_lon - a_lon) * (lat - a_lat) - (b_lat - a_lat) * (lon - a_lon)
        if cross < 0:
            pak_breached = True

    # 3. Evaluate Bangladesh Maritime Boundary (Bay of Bengal / Sundarbans)
    # Boundary runs from Sundarbans south-southeast into Bay of Bengal between 17.0°N - 22.0°N, 89.0°E - 90.5°E.
    # Indian waters are to the WEST; Bangladesh waters are to the EAST.
    bd_waypoints = _IMBL_BANGLADESH_DEFAULT
    bd_min_dist = float("inf")
    bd_closest_pt = bd_waypoints[0]
    bd_breached = False

    for i in range(len(bd_waypoints) - 1):
        a_lat, a_lon = bd_waypoints[i]
        b_lat, b_lon = bd_waypoints[i + 1]
        c_lat, c_lon, dist = closest_point_on_segment(lat, lon, a_lat, a_lon, b_lat, b_lon)
        if dist < bd_min_dist:
            bd_min_dist = dist
            bd_closest_pt = (c_lat, c_lon)

    if 16.0 <= lat <= 22.5 and 88.0 <= lon <= 93.0:
        for i in range(len(bd_waypoints) - 1):
            a_lat, a_lon = bd_waypoints[i]
            b_lat, b_lon = bd_waypoints[i + 1]
            min_l, max_l = min(a_lat, b_lat), max(a_lat, b_lat)
            if min_l <= lat <= max_l:
                frac = (lat - a_lat) / (b_lat - a_lat) if (b_lat != a_lat) else 0.0
                bd_lon = a_lon + frac * (b_lon - a_lon)
                if lon > bd_lon:
                    bd_breached = True
                break

    # 4. Evaluate Maldives Maritime Boundary (Eight Degree Channel)
    # Boundary runs east-west at approx Lat 7.68°N between 71.0°E - 75.5°E.
    # Indian waters (Minicoy) are to the NORTH; Maldives waters are to the SOUTH.
    mv_waypoints = _IMBL_MALDIVES_DEFAULT
    mv_min_dist = float("inf")
    mv_closest_pt = mv_waypoints[0]
    mv_breached = False

    for i in range(len(mv_waypoints) - 1):
        a_lat, a_lon = mv_waypoints[i]
        b_lat, b_lon = mv_waypoints[i + 1]
        c_lat, c_lon, dist = closest_point_on_segment(lat, lon, a_lat, a_lon, b_lat, b_lon)
        if dist < mv_min_dist:
            mv_min_dist = dist
            mv_closest_pt = (c_lat, c_lon)

    if 4.0 <= lat <= 8.2 and 70.0 <= lon <= 76.5:
        if lat < 7.68:
            mv_breached = True

    # 5. Evaluate Myanmar Maritime Boundary (Coco Channel / North Andaman)
    # Boundary runs east-west across Coco Channel at approx Lat 13.85°N between 92.0°E - 95.5°E.
    # Indian waters (North Andaman) are to the SOUTH; Myanmar waters are to the NORTH.
    mm_waypoints = _IMBL_MYANMAR_DEFAULT
    mm_min_dist = float("inf")
    mm_closest_pt = mm_waypoints[0]
    mm_breached = False

    for i in range(len(mm_waypoints) - 1):
        a_lat, a_lon = mm_waypoints[i]
        b_lat, b_lon = mm_waypoints[i + 1]
        c_lat, c_lon, dist = closest_point_on_segment(lat, lon, a_lat, a_lon, b_lat, b_lon)
        if dist < mm_min_dist:
            mm_min_dist = dist
            mm_closest_pt = (c_lat, c_lon)

    if 13.5 <= lat <= 16.5 and 91.5 <= lon <= 96.0:
        if lat > 13.85:
            mm_breached = True

    # 6. Evaluate Indonesia Maritime Boundary (Great Channel / Great Nicobar)
    # Boundary runs NW to SE from 6.65°N, 93.40°E to 5.45°N, 96.00°E.
    # Indian waters (Great Nicobar) are to the NORTH-WEST; Indonesia waters (Aceh) are to the SOUTH-EAST.
    id_waypoints = _IMBL_INDONESIA_DEFAULT
    id_min_dist = float("inf")
    id_closest_pt = id_waypoints[0]
    id_breached = False

    for i in range(len(id_waypoints) - 1):
        a_lat, a_lon = id_waypoints[i]
        b_lat, b_lon = id_waypoints[i + 1]
        c_lat, c_lon, dist = closest_point_on_segment(lat, lon, a_lat, a_lon, b_lat, b_lon)
        if dist < id_min_dist:
            id_min_dist = dist
            id_closest_pt = (c_lat, c_lon)

    if 4.5 <= lat <= 7.2 and 93.0 <= lon <= 96.8:
        # Check if point is south-east of the Great Channel line
        cross = (id_waypoints[-1][1] - id_waypoints[0][1]) * (lat - id_waypoints[0][0]) - (id_waypoints[-1][0] - id_waypoints[0][0]) * (lon - id_waypoints[0][1])
        if cross < 0:
            id_breached = True

    # Multi-boundary Candidate Selection
    candidates = [
        {
            "name": "India–Sri Lanka IMBL",
            "sector": "Palk Strait / Gulf of Mannar Sector",
            "breached": sl_breached,
            "dist": sl_min_dist,
            "safe_pt": (sl_closest_pt[0], sl_closest_pt[1] - 0.08),  # Steer West into Indian waters
        },
        {
            "name": "India–Pakistan Maritime Boundary",
            "sector": "Sir Creek / Kutch Arabian Sea Sector",
            "breached": pak_breached,
            "dist": pak_min_dist,
            "safe_pt": (pak_closest_pt[0] - 0.05, pak_closest_pt[1] + 0.06),  # Steer SE into Gujarat waters
        },
        {
            "name": "India–Bangladesh Maritime Boundary",
            "sector": "Sundarbans / Northern Bay of Bengal Sector",
            "breached": bd_breached,
            "dist": bd_min_dist,
            "safe_pt": (bd_closest_pt[0], bd_closest_pt[1] - 0.08),  # Steer West into Bengal waters
        },
        {
            "name": "India–Maldives Maritime Boundary",
            "sector": "Eight Degree Channel / Minicoy Sector",
            "breached": mv_breached,
            "dist": mv_min_dist,
            "safe_pt": (mv_closest_pt[0] + 0.08, mv_closest_pt[1]),  # Steer North towards Minicoy
        },
        {
            "name": "India–Myanmar Maritime Boundary",
            "sector": "Coco Channel / North Andaman Sector",
            "breached": mm_breached,
            "dist": mm_min_dist,
            "safe_pt": (mm_closest_pt[0] - 0.08, mm_closest_pt[1]),  # Steer South towards Andaman
        },
        {
            "name": "India–Indonesia Maritime Boundary",
            "sector": "Great Channel / Indira Point Sector",
            "breached": id_breached,
            "dist": id_min_dist,
            "safe_pt": (id_closest_pt[0] + 0.06, id_closest_pt[1] - 0.06),  # Steer NW towards Nicobar
        },
    ]

    # Prioritize any breached boundary; otherwise choose closest within 150 km
    breached_candidates = [c for c in candidates if c["breached"]]
    if breached_candidates:
        active = min(breached_candidates, key=lambda c: c["dist"])
        is_breached = True
        active_name = active["name"]
        sector = active["sector"]
        distance_km = round(active["dist"], 1)
        safe_lat, safe_lon = active["safe_pt"]
        bearing = round(compute_bearing(lat, lon, safe_lat, safe_lon), 0)
    else:
        closest = min(candidates, key=lambda c: c["dist"])
        if closest["dist"] < 150.0:
            active_name = closest["name"]
            sector = closest["sector"]
            is_breached = False
            distance_km = round(closest["dist"], 1)
            safe_lat, safe_lon = closest["safe_pt"]
            bearing = round(compute_bearing(lat, lon, safe_lat, safe_lon), 0)
        else:
            # Far out or deep interior (e.g. Goa, Mumbai, Andhra coast)
            active_name = "National Maritime EEZ Boundary"
            sector = "Indian Territorial Waters"
            is_breached = False
            distance_km = round(closest["dist"], 1)
            bearing = 270.0

    cardinal = bearing_to_cardinal(bearing)

    # Classify status
    if is_breached:
        status = "breach"
        warning_title = f"CRITICAL: {active_name} Crossed!"
        warning_message = (
            f"Vessel has crossed {distance_km:.1f} km beyond Indian waters into foreign territory ({sector}). "
            f"Halt fishing gear immediately and steer compass heading {int(bearing)}° {cardinal} "
            f"back into Indian waters to avoid detention."
        )
    elif distance_km < 5.0:
        status = "critical_buffer"
        warning_title = f"EMERGENCY WARNING: Approaching {active_name}"
        warning_message = (
            f"Vessel is within {distance_km:.1f} km of the maritime border. "
            f"Do not drift or set nets eastwards. Turn heading {int(bearing)}° {cardinal}."
        )
    elif distance_km < 15.0:
        status = "warning_buffer"
        warning_title = f"CAUTION: Border Proximity Alert"
        warning_message = (
            f"Vessel is {distance_km:.1f} km from {active_name}. "
            f"Maintain safe buffer margin inside Indian waters."
        )
    else:
        status = "safe"
        warning_title = "Within Safe Indian Waters"
        warning_message = (
            f"Operating {distance_km:.1f} km clear of the nearest international maritime boundary."
        )

    return {
        "is_breached": is_breached,
        "boundary_name": active_name,
        "distance_km": distance_km,
        "status": status,
        "bearing_to_safety": bearing,
        "bearing_cardinal": cardinal,
        "warning_title": warning_title,
        "warning_message": warning_message,
        "sector": sector,
        "coordinates": {"lat": round(lat, 4), "lon": round(lon, 4)},
        "coastguard_number": "1554",
    }
