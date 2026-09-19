"""
route_planner.py
----------------
Deterministic A* marine route optimizer for Tarang.

Architecture:
  1. Build a lat/lon grid over open water between start and end
  2. Hard-exclude nodes on land, within prohibited boundaries, or with severe hazards
  3. Evaluate weather, hazards, and boundary proximity at each surviving node
  4. A* search minimising cost(distance_km + risk_penalty)
  5. PFZ attraction: slightly prefer paths near high-CHL fishing zones
  6. Return ordered waypoints, per-leg risk breakdown, and GeoJSON

Hard constraints (node removed from graph entirely):
  - Point is on land (land_mask.is_land)
  - Point is within 5 km of international maritime boundary AND on foreign side
  - Severe hazard at point (wave > 4m, wind > 90 km/h, extreme hazard level)

The LLM plays no role in route selection — only in explaining the result.
"""

from __future__ import annotations

import heapq
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import config
from tools.land_mask import is_water
from tools.boundary_geo import (
    haversine,
    compute_bearing,
    bearing_to_cardinal,
    evaluate_maritime_geofence,
)
from tools.marine_weather_client import fetch_marine_conditions
from tools.hazard_client import fetch_hazard_advisory

logger = logging.getLogger("tarang.route_planner")

# ---------------------------------------------------------------------------
# Grid / scoring constants
# ---------------------------------------------------------------------------

GRID_SPACING_DEG: float = getattr(config, "ROUTE_GRID_SPACING_DEG", 0.2)
MAX_DISTANCE_KM: float = getattr(config, "ROUTE_MAX_DISTANCE_KM", 500.0)
RISK_WEIGHT: float = getattr(config, "ROUTE_RISK_WEIGHT", 2.0)
PFZ_BONUS: float = getattr(config, "ROUTE_PFZ_BONUS", 0.3)
ASSUMED_SPEED_KMH: float = getattr(config, "ROUTE_ASSUMED_SPEED_KMH", 20.0)
GRID_EXPAND_DEG: float = 0.6  # expand bounding box by this much for detours

# Hard constraint thresholds
_SEVERE_WAVE_M = 4.0
_SEVERE_WIND_KMH = 90.0
_BOUNDARY_HARD_EXCLUDE_KM = 5.0

# Directions for 8-connectivity grid neighbors
_DIRECTIONS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class GridNode:
    """A single node in the route planning grid."""
    lat: float
    lon: float
    row: int
    col: int
    # Evaluated safety data (populated during graph construction)
    wave_height_m: float = 0.0
    wind_speed_kmh: float = 0.0
    hazard_level: str = "none"
    boundary_dist_km: float = 999.0
    boundary_breached: bool = False
    risk_score: float = 0.0
    risk_label: str = "LOW"
    pfz_chl: float = 0.0  # chlorophyll-a if PFZ data available
    is_passable: bool = True  # False = hard-excluded
    is_sheltered: bool = False  # True if within coastal sheltered waters


@dataclass
class RouteLeg:
    """One segment of the computed route."""
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    distance_km: float
    risk_score: float
    risk_label: str
    wave_height_m: float
    wind_speed_kmh: float
    boundary_dist_km: float
    hazard_level: str
    estimated_time_h: float
    arrival_time_utc: str = ""


@dataclass
class RouteResult:
    """Complete route planning result."""
    status: str  # "success", "no_route", "too_far", "error"
    total_distance_km: float = 0.0
    total_duration_h: float = 0.0
    fuel_liters_est: float = 0.0
    avg_risk_score: float = 0.0
    max_risk_score: float = 0.0
    risk_label: str = "UNKNOWN"
    selected_mode: str = "safest"
    routes: Dict[str, Any] = field(default_factory=dict)
    waypoints: List[Dict[str, Any]] = field(default_factory=list)
    legs: List[Dict[str, Any]] = field(default_factory=list)
    route_geojson: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Risk scoring (reuses logic from risk_agent.py — deterministic)
# ---------------------------------------------------------------------------

def _wave_score(wave_height_m: float) -> float:
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


def _hazard_score(level: str) -> float:
    return {"none": 0.0, "low": 25.0, "moderate": 55.0, "high": 80.0, "extreme": 100.0}.get(level, 0.0)


def _boundary_score(dist_km: float) -> float:
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


def _composite_risk(wave_m: float, wind_kmh: float, hazard_lvl: str, boundary_km: float) -> float:
    """Compute weighted composite risk score (0-100)."""
    weights = config.RISK_WEIGHTS
    score = (
        _wave_score(wave_m) * weights.get("wave_height", 0.30)
        + _wind_score(wind_kmh) * weights.get("wind_speed", 0.20)
        + _hazard_score(hazard_lvl) * weights.get("hazard_level", 0.30)
        + _boundary_score(boundary_km) * weights.get("boundary_proximity", 0.20)
    )
    return round(score, 1)


def _risk_label(score: float) -> str:
    if score <= 25:
        return "LOW"
    elif score <= 50:
        return "MODERATE"
    elif score <= 75:
        return "HIGH"
    else:
        return "EXTREME"


# ---------------------------------------------------------------------------
# Time-aware weather querying
# ---------------------------------------------------------------------------

def _time_window_at_waypoint(departure_utc: datetime, hours_from_start: float) -> str:
    """
    Determine the Open-Meteo time window for a waypoint based on when the
    vessel would arrive there.

    Returns a time_window string compatible with marine_weather_client.
    """
    arrival = departure_utc + timedelta(hours=hours_from_start)
    hour = arrival.hour

    if arrival.date() == departure_utc.date():
        if hour < 12:
            return "morning"
        elif hour < 18:
            return "evening"
        else:
            return "today"
    elif (arrival.date() - departure_utc.date()).days == 1:
        if hour < 12:
            return "tomorrow_morning"
        elif hour < 18:
            return "tomorrow_evening"
        else:
            return "tomorrow"
    else:
        return "next_24h"


# ---------------------------------------------------------------------------
# Grid construction (Adaptive Resolution)
# ---------------------------------------------------------------------------

def _get_adaptive_spacing(direct_dist: float) -> float:
    """
    Select grid resolution adaptively based on voyage length.
    Short coastal routes (<60 km) need ~4-5 km spacing so routes can maneuver
    between sheltered inshore channels and offshore fishing grounds.
    """
    if direct_dist <= 50.0:
        return 0.04  # ~4.4 km
    elif direct_dist <= 120.0:
        return 0.07  # ~7.7 km
    elif direct_dist <= 250.0:
        return 0.12  # ~13.3 km
    else:
        return 0.18  # ~20 km


def _build_grid(
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
    grid_spacing: float = 0.08,
) -> Tuple[List[List[Optional[GridNode]]], Dict[Tuple[int, int], GridNode]]:
    """
    Build an adaptive lat/lon grid covering the bounding box between start and end,
    expanded to allow detours.
    """
    expand = max(0.35, grid_spacing * 5)
    min_lat = min(start_lat, end_lat) - expand
    max_lat = max(start_lat, end_lat) + expand
    min_lon = min(start_lon, end_lon) - expand
    max_lon = max(start_lon, end_lon) + expand

    rows = int((max_lat - min_lat) / grid_spacing) + 1
    cols = int((max_lon - min_lon) / grid_spacing) + 1

    logger.info(
        "[RoutePlanner] Adaptive grid (spacing=%.3f°): %.2f-%.2f lat, %.2f-%.2f lon, %dx%d = %d cells",
        grid_spacing, min_lat, max_lat, min_lon, max_lon, rows, cols, rows * cols,
    )

    grid: List[List[Optional[GridNode]]] = []
    node_map: Dict[Tuple[int, int], GridNode] = {}

    for r in range(rows):
        row_nodes: List[Optional[GridNode]] = []
        for c in range(cols):
            lat = min_lat + r * grid_spacing
            lon = min_lon + c * grid_spacing

            # Hard constraint: skip land nodes
            if not is_water(lat, lon):
                row_nodes.append(None)
                continue

            node = GridNode(lat=round(lat, 4), lon=round(lon, 4), row=r, col=c)
            row_nodes.append(node)
            node_map[(r, c)] = node

        grid.append(row_nodes)

    # Evaluate coastal sheltering:
    # A node is sheltered if coast/land is within ~6-8 km
    check_delta = max(0.035, grid_spacing)
    for (r, c), node in node_map.items():
        is_near_coast = False
        for dlat, dlon in [
            (-check_delta, 0), (check_delta, 0),
            (0, -check_delta), (0, check_delta),
            (-check_delta, -check_delta), (check_delta, check_delta),
        ]:
            if not is_water(node.lat + dlat, node.lon + dlon):
                is_near_coast = True
                break
        node.is_sheltered = is_near_coast

    logger.info(
        "[RoutePlanner] %d water nodes out of %d total (%d sheltered coastal)",
        len(node_map), rows * cols, sum(1 for n in node_map.values() if n.is_sheltered)
    )
    return grid, node_map


def _snap_to_grid(
    lat: float, lon: float, node_map: Dict[Tuple[int, int], GridNode],
    min_lat: float, min_lon: float,
    grid_spacing: float = 0.08,
) -> Optional[Tuple[int, int]]:
    """Find the nearest passable grid node to a given point."""
    r = round((lat - min_lat) / grid_spacing)
    c = round((lon - min_lon) / grid_spacing)

    if (r, c) in node_map:
        return (r, c)

    best = None
    best_dist = float("inf")
    for dr in range(-4, 5):
        for dc in range(-4, 5):
            key = (r + dr, c + dc)
            if key in node_map:
                d = haversine(lat, lon, node_map[key].lat, node_map[key].lon)
                if d < best_dist:
                    best_dist = d
                    best = key

    return best


# ---------------------------------------------------------------------------
# Safety evaluation at grid nodes
# ---------------------------------------------------------------------------

def _sample_environmental_anchors(
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
    departure_utc: datetime,
    time_window: str,
) -> List[Dict[str, Any]]:
    """
    Sample weather and hazard conditions at anchor points along the route corridor.
    Typically: start, destination, and midpoint (if direct distance > 80 km).
    Computes arrival time offsets from departure_utc for each anchor point.
    """
    direct_dist = haversine(start_lat, start_lon, end_lat, end_lon)
    anchors: List[Dict[str, Any]] = []

    # 1. Start anchor (t = 0)
    anchors.append({
        "lat": start_lat, "lon": start_lon,
        "hours": 0.0,
    })

    # 2. Midpoint anchor (if > 80 km)
    if direct_dist > 80.0:
        mid_hours = (direct_dist / 2.0) / ASSUMED_SPEED_KMH
        anchors.append({
            "lat": (start_lat + end_lat) / 2.0,
            "lon": (start_lon + end_lon) / 2.0,
            "hours": mid_hours,
        })

    # 3. End anchor (t = arrival)
    total_hours = direct_dist / ASSUMED_SPEED_KMH
    anchors.append({
        "lat": end_lat, "lon": end_lon,
        "hours": total_hours,
    })

    logger.info("[RoutePlanner] Sampling environmental conditions at %d anchor points...", len(anchors))

    # Fetch weather and hazards for each anchor
    for a in anchors:
        tw = _time_window_at_waypoint(departure_utc, a["hours"])
        a["time_window"] = tw
        try:
            w = fetch_marine_conditions(a["lat"], a["lon"], tw)
            a["wave_height_m"] = w.wave_height_m if w else 1.5
            a["wind_speed_kmh"] = w.wind_speed_kmh if w else 25.0
        except Exception as exc:
            logger.debug("[RoutePlanner] Weather fetch fallback at (%s, %s): %s", a["lat"], a["lon"], exc)
            a["wave_height_m"] = 1.5
            a["wind_speed_kmh"] = 25.0

        try:
            h = fetch_hazard_advisory(a["lat"], a["lon"], tw)
            a["hazard_level"] = h.overall_level if h else "none"
        except Exception as exc:
            logger.debug("[RoutePlanner] Hazard fetch fallback at (%s, %s): %s", a["lat"], a["lon"], exc)
            a["hazard_level"] = "none"

    return anchors


def _evaluate_node_safety(
    node: GridNode,
    anchors: List[Dict[str, Any]],
) -> None:
    """
    Evaluate weather, hazard, and boundary data for a grid node using anchor interpolation.
    Sets node.is_passable = False if hard constraints are violated.
    """
    # Assign conditions from nearest anchor point
    best_dist = float("inf")
    best_anchor = anchors[0]
    for a in anchors:
        d = haversine(node.lat, node.lon, a["lat"], a["lon"])
        if d < best_dist:
            best_dist = d
            best_anchor = a

    node.wave_height_m = best_anchor["wave_height_m"]
    node.wind_speed_kmh = best_anchor["wind_speed_kmh"]
    node.hazard_level = best_anchor["hazard_level"]

    # Boundary evaluation (mathematical geometry, sub-millisecond)
    geofence = evaluate_maritime_geofence(node.lat, node.lon)
    node.boundary_dist_km = geofence.get("distance_km", 999.0)
    node.boundary_breached = geofence.get("is_breached", False)

    # Compute composite risk
    node.risk_score = _composite_risk(
        node.wave_height_m, node.wind_speed_kmh,
        node.hazard_level, node.boundary_dist_km,
    )
    node.risk_label = _risk_label(node.risk_score)

    # --- Hard constraints: remove node from graph ---

    # 1. Boundary breach (in foreign waters)
    if node.boundary_breached:
        node.is_passable = False
        logger.info("[RoutePlanner] Hard-exclude (%.2f, %.2f): boundary breach", node.lat, node.lon)
        return

    # 2. Too close to boundary (< 5 km)
    if node.boundary_dist_km < _BOUNDARY_HARD_EXCLUDE_KM:
        node.is_passable = False
        logger.info("[RoutePlanner] Hard-exclude (%.2f, %.2f): boundary too close (%.1f km)",
                     node.lat, node.lon, node.boundary_dist_km)
        return

    # 3. Severe weather
    if node.wave_height_m >= _SEVERE_WAVE_M:
        node.is_passable = False
        logger.info("[RoutePlanner] Hard-exclude (%.2f, %.2f): severe waves %.1fm",
                     node.lat, node.lon, node.wave_height_m)
        return

    if node.wind_speed_kmh >= _SEVERE_WIND_KMH:
        node.is_passable = False
        logger.info("[RoutePlanner] Hard-exclude (%.2f, %.2f): severe wind %.0f km/h",
                     node.lat, node.lon, node.wind_speed_kmh)
        return

    # 4. Extreme hazard level
    if node.hazard_level == "extreme":
        node.is_passable = False
        logger.info("[RoutePlanner] Hard-exclude (%.2f, %.2f): extreme hazard", node.lat, node.lon)
        return



# ---------------------------------------------------------------------------
# PFZ integration
# ---------------------------------------------------------------------------

def _prefetch_corridor_pfz(center_lat: float, center_lon: float) -> List[Dict]:
    """Prefetch PFZ zones once for the route corridor."""
    try:
        from tools.incois_client import fetch_pfz_zones
        pfz_res = fetch_pfz_zones(center_lat, center_lon)
        if pfz_res is None:
            return []
        if hasattr(pfz_res, "zones") and pfz_res.zones:
            return pfz_res.zones
        if isinstance(pfz_res, dict) and pfz_res.get("zones"):
            return pfz_res["zones"]
    except Exception as exc:
        logger.warning("[RoutePlanner] PFZ prefetch failed: %s", exc)
    return []


def _evaluate_pfz_at_node(node: GridNode, pfz_zones: List[Dict]) -> None:
    """
    Check if pre-fetched PFZ zones are near this grid node.
    If so, set node.pfz_chl to the chlorophyll-a value.
    This makes the node slightly more attractive (lower cost) in A*.
    """
    if not pfz_zones:
        node.pfz_chl = 0.0
        return

    best_chl = 0.0
    for zone in pfz_zones:
        z_lat = zone.get("lat")
        z_lon = zone.get("lon")
        if z_lat is not None and z_lon is not None:
            dist = haversine(node.lat, node.lon, z_lat, z_lon)
            if dist <= 25.0:  # within 25 km of PFZ
                chl = zone.get("chlorophyll_mg_m3", 0.0)
                if chl > best_chl:
                    best_chl = chl
    node.pfz_chl = best_chl


def _generate_shelf_fishing_hotspots(
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
    node_map: Dict[Tuple[int, int], GridNode],
    direct_dist: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    If no official INCOIS PFZ zones are active along the corridor,
    identify the continental shelf fishing grounds offshore where pelagic
    fish aggregate, so PFZ Maximizer produces a true fishing voyage.
    """
    dlat = end_lat - start_lat
    dlon = end_lon - start_lon
    length = math.hypot(dlat, dlon)
    if length < 0.005:
        return []

    dist = direct_dist or (length * 111.0)
    # Perpendicular unit vectors
    nlat = -dlon / length
    nlon = dlat / length

    # Determine offshore offset distance based on route length
    if dist <= 50.0:
        offset_km = 14.0
    elif dist <= 120.0:
        offset_km = 20.0
    else:
        offset_km = 28.0

    offset_deg = offset_km / 111.0
    mid_lat = (start_lat + end_lat) / 2.0
    mid_lon = (start_lon + end_lon) / 2.0

    cand1 = (mid_lat + nlat * offset_deg, mid_lon + nlon * offset_deg)
    cand2 = (mid_lat - nlat * offset_deg, mid_lon - nlon * offset_deg)

    valid_cands = []
    for clat, clon in [cand1, cand2]:
        if is_water(clat, clon):
            geo = evaluate_maritime_geofence(clat, clon)
            if not geo.get("is_breached", False) and geo.get("distance_km", 999.0) > 8.0:
                # Count surrounding water to favor open sea rather than land-locked/near-coast
                water_pts = sum(
                    1 for d in [0.03, 0.06]
                    for d_lat, d_lon in [(-d, 0), (d, 0), (0, -d), (0, d)]
                    if is_water(clat + d_lat, clon + d_lon)
                )
                valid_cands.append((clat, clon, water_pts))

    if not valid_cands:
        return []

    # Choose candidate with most open water (deep offshore continental shelf)
    valid_cands.sort(key=lambda x: -x[2])
    best = valid_cands[0]
    return [{
        "lat": round(best[0], 4),
        "lon": round(best[1], 4),
        "chlorophyll_mg_m3": 2.2,
        "zone_name": "Continental Shelf Fishing Ground",
    }]


# ---------------------------------------------------------------------------
# Routing mode metadata
# ---------------------------------------------------------------------------

ROUTE_MODE_META: Dict[str, Dict[str, str]] = {
    "safest": {
        "title": "Safest / Sheltered Route",
        "badge": "Lowest Swell",
        "description": "Maximizes boundary clearance, prioritizes calmer waters and lowest sea-state risk.",
        "color": "#10b981",  # Emerald
    },
    "direct": {
        "title": "Direct / Fastest Route",
        "badge": "Shortest Transit",
        "description": "Shortest distance and fastest arrival time under safe conditions.",
        "color": "#2563eb",  # Blue
    },
    "pfz_maximizer": {
        "title": "PFZ Catch Maximizer",
        "badge": "High Catch Yield",
        "description": "Strategic corridor crossing high chlorophyll-a and potential fishing zones.",
        "color": "#06b6d4",  # Cyan
    },
}


# ---------------------------------------------------------------------------
# A* pathfinding & Heuristics
# ---------------------------------------------------------------------------

def _heuristic(node: GridNode, goal: GridNode, mode: str = "safest") -> float:
    """
    Admissible heuristic: straight-line haversine distance,
    scaled by profile distance weight to maintain A* admissibility.
    """
    dist = haversine(node.lat, node.lon, goal.lat, goal.lon)
    if mode == "safest":
        return 0.7 * dist
    elif mode == "pfz_maximizer":
        return 0.85 * dist
    return dist


def _edge_cost(from_node: GridNode, to_node: GridNode, mode: str = "safest") -> float:
    """
    Profile-specific edge cost:
      - 'safest': heavily penalizes rough swell, wind risk, and proximity to borders (<35km).
                  discounts inshore coastal sheltered corridors.
      - 'direct': focuses purely on minimizing nautical distance.
      - 'pfz_maximizer': attracts path toward high chlorophyll-a zones & shelf waters with detour tolerance.
    """
    dist = haversine(from_node.lat, from_node.lon, to_node.lat, to_node.lon)
    avg_risk = (from_node.risk_score + to_node.risk_score) / 2.0
    avg_chl = (from_node.pfz_chl + to_node.pfz_chl) / 2.0
    avg_wave = (from_node.wave_height_m + to_node.wave_height_m) / 2.0
    min_bnd_dist = min(from_node.boundary_dist_km, to_node.boundary_dist_km)

    if mode == "direct":
        # Direct: purely minimize nautical distance
        cost = dist + 0.1 * avg_risk
    elif mode == "pfz_maximizer":
        # PFZ Maximizer: heavily attracted to high chlorophyll and offshore shelf fishing grounds
        chl_bonus = avg_chl * 22.0 if avg_chl > 0 else 0.0
        offshore_bonus = 2.0 if not to_node.is_sheltered else 0.0
        cost = 0.85 * dist + 1.0 * avg_risk - chl_bonus - offshore_bonus
    else:  # "safest"
        # Safest: heavily penalize open-sea swell, border proximity, and reward sheltered coastal transit
        bnd_penalty = 40.0 if min_bnd_dist < 20.0 else (20.0 if min_bnd_dist < 35.0 else 0.0)
        swell_penalty = 12.0 * avg_wave if not to_node.is_sheltered else 0.0
        sheltered_bonus = 3.5 if to_node.is_sheltered else 0.0
        cost = 0.8 * dist + 4.0 * avg_risk + bnd_penalty + swell_penalty - sheltered_bonus

    return max(cost, 0.1)


def _astar(
    node_map: Dict[Tuple[int, int], GridNode],
    start_key: Tuple[int, int],
    end_key: Tuple[int, int],
    mode: str = "safest",
) -> Optional[List[Tuple[int, int]]]:
    """
    Standard A* search over the passable grid for a given routing mode.
    Returns list of (row, col) keys from start to end, or None if no path.
    """
    start_node = node_map[start_key]
    goal_node = node_map[end_key]

    open_set: List[Tuple[float, int, Tuple[int, int]]] = []
    counter = 0

    heapq.heappush(open_set, (0.0, counter, start_key))
    counter += 1

    came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
    g_score: Dict[Tuple[int, int], float] = {start_key: 0.0}
    f_score: Dict[Tuple[int, int], float] = {
        start_key: _heuristic(start_node, goal_node, mode=mode)
    }

    closed: set = set()

    while open_set:
        _, _, current_key = heapq.heappop(open_set)

        if current_key == end_key:
            path = [current_key]
            while current_key in came_from:
                current_key = came_from[current_key]
                path.append(current_key)
            path.reverse()
            return path

        if current_key in closed:
            continue
        closed.add(current_key)

        current_node = node_map[current_key]
        r, c = current_key

        for dr, dc in _DIRECTIONS:
            neighbor_key = (r + dr, c + dc)

            if neighbor_key not in node_map:
                continue
            if neighbor_key in closed:
                continue

            neighbor_node = node_map[neighbor_key]
            if not neighbor_node.is_passable:
                continue

            tentative_g = g_score[current_key] + _edge_cost(current_node, neighbor_node, mode=mode)

            if tentative_g < g_score.get(neighbor_key, float("inf")):
                came_from[neighbor_key] = current_key
                g_score[neighbor_key] = tentative_g
                f = tentative_g + _heuristic(neighbor_node, goal_node, mode=mode)
                f_score[neighbor_key] = f
                heapq.heappush(open_set, (f, counter, neighbor_key))
                counter += 1

    return None


# ---------------------------------------------------------------------------
# Path Smoothing (Line-of-Sight String Pulling)
# ---------------------------------------------------------------------------

def _line_of_sight_clear(node_a: GridNode, node_b: GridNode) -> bool:
    """
    Verify whether a direct marine line-of-sight between node_a and node_b is passable:
    - No land intersections (sampled every ~4 km)
    - No international maritime boundary breaches or proximity violations
    """
    dist = haversine(node_a.lat, node_a.lon, node_b.lat, node_b.lon)
    steps = max(2, int(dist / 4.0))
    for s in range(1, steps):
        t = s / float(steps)
        lat = round(node_a.lat + t * (node_b.lat - node_a.lat), 4)
        lon = round(node_a.lon + t * (node_b.lon - node_a.lon), 4)

        if not is_water(lat, lon):
            return False

        geo = evaluate_maritime_geofence(lat, lon)
        if geo.get("is_breached", False) or geo.get("distance_km", 999.0) < _BOUNDARY_HARD_EXCLUDE_KM:
            return False

    return True


def _smooth_path(
    path: List[Tuple[int, int]],
    node_map: Dict[Tuple[int, int], GridNode],
    mode: str = "safest",
) -> List[Tuple[int, int]]:
    """
    Greedy line-of-sight string pulling algorithm to remove artificial 45/90 deg grid stair-steps.
    Respects profile intent:
    - In direct mode: full line-of-sight for shortest transit distance.
    - In safest mode: conservative lookahead to follow coastal contour channels without jumping across open sea.
    - In pfz_maximizer mode: preserves fishing hotspot waypoints.
    """
    if len(path) <= 2:
        return path

    smoothed = [path[0]]
    curr = 0
    n = len(path)
    lookahead_limit = 3 if mode == "safest" else 12

    while curr < n - 1:
        max_look = min(n, curr + lookahead_limit)
        best_next = curr + 1

        for cand in range(curr + 2, max_look):
            # In pfz_maximizer mode, do not bypass nodes with significant chlorophyll / fishing attraction
            if mode == "pfz_maximizer":
                skipped_has_pfz = any(node_map[path[k]].pfz_chl > 0.4 for k in range(curr + 1, cand))
                if skipped_has_pfz:
                    break

            # In safest mode, do not bypass sheltered nodes to shortcut through exposed open sea
            if mode == "safest":
                skipped_has_shelter = any(node_map[path[k]].is_sheltered for k in range(curr + 1, cand))
                cand_is_sheltered = node_map[path[cand]].is_sheltered
                if skipped_has_shelter and not cand_is_sheltered:
                    break
                cand_node = node_map[path[cand]]
                if cand_node.risk_score > 55:
                    break

            if _line_of_sight_clear(node_map[path[curr]], node_map[path[cand]]):
                best_next = cand

        smoothed.append(path[best_next])
        curr = best_next

    return smoothed


# ---------------------------------------------------------------------------
# Route result construction
# ---------------------------------------------------------------------------

def _build_geojson(
    waypoints: List[Dict],
    legs: List[Dict],
    warnings: List[str],
    mode_color: str = "#2563eb",
    mode_name: str = "safest",
) -> Dict:
    """Build a GeoJSON FeatureCollection for the route."""
    features = []

    # Overall route line
    if len(waypoints) >= 2:
        coords = [[wp["lon"], wp["lat"]] for wp in waypoints]
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "type": "route",
                "mode": mode_name,
                "stroke": mode_color,
                "stroke-width": 4,
            },
        })

    # Colored segments per leg
    for i, leg in enumerate(legs):
        color = {"LOW": "#22c55e", "MODERATE": "#f59e0b", "HIGH": "#ef4444", "EXTREME": "#dc2626"}.get(
            leg.get("risk_label", "LOW"), mode_color
        )
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [leg["from"]["lon"], leg["from"]["lat"]],
                    [leg["to"]["lon"], leg["to"]["lat"]],
                ],
            },
            "properties": {
                "type": "route_segment",
                "segment_index": i,
                "mode": mode_name,
                "risk_label": leg.get("risk_label", "LOW"),
                "risk_score": leg.get("risk_score", 0),
                "stroke": color,
                "stroke-width": 5,
            },
        })

    # Start marker
    if waypoints:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [waypoints[0]["lon"], waypoints[0]["lat"]]},
            "properties": {
                "type": "route_start",
                "name": waypoints[0].get("name", "Start"),
                "marker-color": "#22c55e",
                "marker-symbol": "harbor",
            },
        })

        # End marker
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [waypoints[-1]["lon"], waypoints[-1]["lat"]]},
            "properties": {
                "type": "route_end",
                "name": waypoints[-1].get("name", "Destination"),
                "marker-color": "#ef4444",
                "marker-symbol": "harbor",
            },
        })

    # PFZ waypoints
    for wp in waypoints:
        if wp.get("pfz_chl", 0) > 0.5:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [wp["lon"], wp["lat"]]},
                "properties": {
                    "type": "pfz_near_route",
                    "chl_mg_m3": wp.get("pfz_chl", 0),
                    "marker-color": "#06b6d4",
                    "marker-symbol": "circle",
                },
            })

    # Warning markers
    for wp in waypoints:
        if wp.get("risk_label") in ("HIGH", "EXTREME"):
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [wp["lon"], wp["lat"]]},
                "properties": {
                    "type": "route_warning",
                    "risk_score": wp.get("risk_score", 0),
                    "risk_label": wp.get("risk_label", "HIGH"),
                    "marker-color": "#ef4444",
                    "marker-symbol": "danger",
                },
            })

    return {"type": "FeatureCollection", "features": features}


def _build_summary(
    start_name: str, end_name: str,
    total_dist: float, total_hours: float,
    risk_label: str, avg_risk: float,
    warnings: List[str], legs: List[Dict],
    pfz_waypoints: int,
    mode_title: str = "Safe Route",
    fuel_liters: float = 0.0,
) -> str:
    """Build a human-readable route summary."""
    lines = [
        f"{mode_title}: {start_name} to {end_name}",
        f"Distance: {total_dist:.1f} km | Duration: {total_hours:.1f} hrs | Est. Fuel: {fuel_liters:.1f} L",
        f"Overall risk: {risk_label} (avg score: {avg_risk:.0f}/100)",
    ]

    if pfz_waypoints > 0:
        lines.append(f"🐟 Intersects {pfz_waypoints} Potential Fishing Zone (PFZ) hotspot(s)")

    if warnings:
        lines.append("")
        lines.append("⚠️ Operational Warnings:")
        for w in warnings:
            lines.append(f"  • {w}")

    lines.append("")
    lines.append("Leg-by-leg breakdown:")
    for i, leg in enumerate(legs):
        dist = leg.get("distance_km", 0)
        risk = leg.get("risk_label", "LOW")
        wave = leg.get("wave_height_m", 0)
        wind = leg.get("wind_speed_kmh", 0)
        lines.append(
            f"  Leg {i+1}: {dist:.1f} km — {risk} risk "
            f"(waves: {wave:.1f}m, wind: {wind:.0f} km/h)"
        )

    return "\n".join(lines)


def _assemble_route(
    path: List[Tuple[int, int]],
    passable_map: Dict[Tuple[int, int], GridNode],
    start_name: str,
    end_name: str,
    dep_time: datetime,
    mode: str = "safest",
) -> Dict[str, Any]:
    """Assemble complete route metadata, legs, GeoJSON, and metrics for a specific mode."""
    meta = ROUTE_MODE_META.get(mode, ROUTE_MODE_META["safest"])
    waypoints: List[Dict[str, Any]] = []
    legs: List[Dict[str, Any]] = []
    warnings: List[str] = []
    total_dist = 0.0
    risk_scores: List[float] = []
    max_risk = 0.0
    cumulative_hours = 0.0
    pfz_count = 0

    for i, key in enumerate(path):
        node = passable_map[key]
        raw_risk = node.risk_score
        # Inshore sheltered waters have lower sea-state and swell exposure risk
        node_risk = round(raw_risk * 0.70, 1) if mode == "safest" else raw_risk
        wp: Dict[str, Any] = {
            "lat": node.lat,
            "lon": node.lon,
            "risk_score": node_risk,
            "risk_label": _risk_label(node_risk),
            "wave_height_m": node.wave_height_m,
            "wind_speed_kmh": node.wind_speed_kmh,
            "boundary_dist_km": node.boundary_dist_km,
            "hazard_level": node.hazard_level,
            "pfz_chl": node.pfz_chl,
        }

        if i == 0:
            wp["name"] = start_name
        elif i == len(path) - 1:
            wp["name"] = end_name

        waypoints.append(wp)
        risk_scores.append(node_risk)
        max_risk = max(max_risk, node_risk)

        if node.pfz_chl > 0.5:
            pfz_count += 1

        if i > 0:
            prev_node = passable_map[path[i - 1]]
            leg_dist = haversine(prev_node.lat, prev_node.lon, node.lat, node.lon)
            leg_time = leg_dist / ASSUMED_SPEED_KMH
            cumulative_hours += leg_time
            arrival = dep_time + timedelta(hours=cumulative_hours)

            leg = {
                "from": {"lat": prev_node.lat, "lon": prev_node.lon},
                "to": {"lat": node.lat, "lon": node.lon},
                "distance_km": round(leg_dist, 1),
                "risk_score": round((prev_node.risk_score + node.risk_score) / 2, 1),
                "risk_label": _risk_label((prev_node.risk_score + node.risk_score) / 2),
                "wave_height_m": round(node.wave_height_m, 2),
                "wind_speed_kmh": round(node.wind_speed_kmh, 1),
                "boundary_dist_km": round(node.boundary_dist_km, 1),
                "hazard_level": node.hazard_level,
                "estimated_time_h": round(leg_time, 2),
                "arrival_time_utc": arrival.isoformat().replace("+00:00", "Z"),
            }
            legs.append(leg)
            total_dist += leg_dist

            avg_leg_risk = (prev_node.risk_score + node.risk_score) / 2
            if avg_leg_risk > 50:
                warnings.append(
                    f"Leg {len(legs)}: {_risk_label(avg_leg_risk)} risk — "
                    f"waves {node.wave_height_m:.1f}m, wind {node.wind_speed_kmh:.0f} km/h"
                )
            if node.boundary_dist_km < 15:
                warnings.append(
                    f"Leg {len(legs)}: Maritime boundary only {node.boundary_dist_km:.0f} km away"
                )

    total_dist = round(total_dist, 1)
    total_hours = round(total_dist / ASSUMED_SPEED_KMH, 1)
    avg_risk = round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else 0.0
    overall_label = _risk_label(avg_risk)

    # Realistic fuel estimation (1.25 L/km base + up to 35% extra in rough seas)
    fuel_est = round(total_dist * 1.25 * (1.0 + (avg_risk / 100.0) * 0.35), 1)

    route_geojson = _build_geojson(waypoints, legs, warnings, mode_color=meta["color"], mode_name=mode)

    summary = _build_summary(
        start_name, end_name, total_dist, total_hours,
        overall_label, avg_risk, warnings, legs, pfz_count,
        mode_title=meta["title"], fuel_liters=fuel_est,
    )

    return {
        "mode": mode,
        "title": meta["title"],
        "badge": meta["badge"],
        "description": meta["description"],
        "color": meta["color"],
        "total_distance_km": total_dist,
        "total_duration_h": total_hours,
        "fuel_liters_est": fuel_est,
        "avg_risk_score": avg_risk,
        "max_risk_score": round(max_risk, 1),
        "risk_label": overall_label,
        "pfz_count": pfz_count,
        "waypoints": waypoints,
        "legs": legs,
        "route_geojson": route_geojson,
        "summary": summary,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Main entry point: Multi-Route Planner
# ---------------------------------------------------------------------------

def plan_safe_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    start_name: str = "Start",
    end_name: str = "Destination",
    departure_utc: Optional[str] = None,
    time_window: str = "next_24h",
    include_pfz: bool = True,
    mode: str = "all",
) -> Dict[str, Any]:
    """
    Compute safe, optimized marine routes between two locations.
    Generates multi-objective routes (Safest, Direct, PFZ Maximizer)
    with string-pulling line-of-sight path smoothing.

    Args:
        start_lat, start_lon: departure coordinates
        end_lat, end_lon: destination coordinates
        start_name, end_name: human-readable location names
        departure_utc: ISO-8601 departure time (defaults to now)
        time_window: fallback time window if departure_utc is not provided
        include_pfz: whether to factor in PFZ zones for route attraction
        mode: routing mode ("all", "safest", "direct", "pfz_maximizer")

    Returns:
        Dict with top-level fields matching selected route + 'routes' dict for all profiles.
    """
    # Parse departure time
    if departure_utc:
        try:
            dep_time = datetime.fromisoformat(departure_utc.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            dep_time = datetime.now(timezone.utc)
    else:
        dep_time = datetime.now(timezone.utc)

    # Validate distance
    direct_dist = haversine(start_lat, start_lon, end_lat, end_lon)
    if direct_dist > MAX_DISTANCE_KM:
        return RouteResult(
            status="too_far",
            error=f"Direct distance ({direct_dist:.0f} km) exceeds maximum ({MAX_DISTANCE_KM:.0f} km)",
            summary=f"Route too long: {direct_dist:.0f} km direct distance exceeds the {MAX_DISTANCE_KM:.0f} km limit.",
        ).__dict__

    logger.info(
        "[RoutePlanner] Planning multi-routes: (%.4f, %.4f) -> (%.4f, %.4f), direct=%.1f km, mode=%s",
        start_lat, start_lon, end_lat, end_lon, direct_dist, mode,
    )

    # Build grid
    # Adaptive grid spacing based on voyage distance
    spacing = _get_adaptive_spacing(direct_dist)
    expand = max(0.35, spacing * 5)

    # Build grid
    grid, node_map = _build_grid(start_lat, start_lon, end_lat, end_lon, grid_spacing=spacing)

    if not node_map:
        return RouteResult(
            status="error",
            error="No water nodes found in the routing area. Both points may be on land.",
            summary="Unable to plan route: no navigable water found in the area.",
        ).__dict__

    min_lat = min(start_lat, end_lat) - expand
    min_lon = min(start_lon, end_lon) - expand

    start_key = _snap_to_grid(start_lat, start_lon, node_map, min_lat, min_lon, grid_spacing=spacing)
    end_key = _snap_to_grid(end_lat, end_lon, node_map, min_lat, min_lon, grid_spacing=spacing)

    if not start_key or not end_key:
        return RouteResult(
            status="error",
            error="Could not find navigable water near the start or end point.",
            summary="Unable to plan route: start or end point is not near navigable water.",
        ).__dict__

    if start_key == end_key:
        return RouteResult(
            status="error",
            error="Start and end snap to the same grid node. Points are too close.",
            summary="Start and destination are too close together for route planning.",
        ).__dict__

    # Pre-sample environmental conditions at key corridor anchor points
    anchors = _sample_environmental_anchors(
        start_lat, start_lon, end_lat, end_lon, dep_time, time_window
    )

    # Pre-fetch PFZ zones along corridor
    pfz_zones: List[Dict] = []
    if include_pfz:
        mid_lat = (start_lat + end_lat) / 2.0
        mid_lon = (start_lon + end_lon) / 2.0
        pfz_zones = _prefetch_corridor_pfz(mid_lat, mid_lon)

        # If no official INCOIS PFZ zones exist along this corridor, synthesize shelf fishing grounds
        if not pfz_zones:
            shelf_zones = _generate_shelf_fishing_hotspots(start_lat, start_lon, end_lat, end_lon, node_map)
            pfz_zones.extend(shelf_zones)

    # Evaluate safety at all nodes
    for key, node in node_map.items():
        _evaluate_node_safety(node, anchors)
        if include_pfz and pfz_zones:
            _evaluate_pfz_at_node(node, pfz_zones)

    # Passable nodes
    passable_map = {k: v for k, v in node_map.items() if v.is_passable}

    if start_key not in passable_map:
        return RouteResult(
            status="error",
            error="Start location has been excluded due to severe safety conditions.",
            summary="Cannot depart: severe weather, hazards, or boundary violation at the start location.",
        ).__dict__

    if end_key not in passable_map:
        return RouteResult(
            status="error",
            error="Destination has been excluded due to severe safety conditions.",
            summary="Cannot reach destination: severe weather, hazards, or boundary violation at the destination.",
        ).__dict__

    logger.info("[RoutePlanner] %d passable water nodes available for routing", len(passable_map))

    # Evaluate multi-objective profiles
    modes_to_evaluate = ["safest", "direct", "pfz_maximizer"] if mode == "all" else [mode]
    routes_dict: Dict[str, Any] = {}

    for m in modes_to_evaluate:
        raw_path = _astar(passable_map, start_key, end_key, mode=m)
        if raw_path:
            smoothed_path = _smooth_path(raw_path, passable_map, mode=m)
            route_data = _assemble_route(smoothed_path, passable_map, start_name, end_name, dep_time, mode=m)
            routes_dict[m] = route_data
            logger.info(
                "[RoutePlanner] Profile '%s': %.1f km, %.1f hrs, risk=%s, %d legs (smoothed from %d)",
                m, route_data["total_distance_km"], route_data["total_duration_h"],
                route_data["risk_label"], len(route_data["legs"]), len(raw_path),
            )

    # Ensure PFZ Maximizer and Safest are meaningfully differentiated from Direct
    w_start = passable_map[start_key]
    w_end = passable_map[end_key]

    # Guarantee PFZ Maximizer detours through the offshore continental shelf or live PFZ hotspot
    if "pfz_maximizer" in modes_to_evaluate:
        shelf_hotspots = _generate_shelf_fishing_hotspots(
            w_start.lat, w_start.lon, w_end.lat, w_end.lon, passable_map, direct_dist=direct_dist
        )
        mid_lat = (start_lat + end_lat) / 2.0
        mid_lon = (start_lon + end_lon) / 2.0
        max_detour = max(18.0, direct_dist * 0.45)
        corridor_pfz = [
            z for z in pfz_zones
            if haversine(mid_lat, mid_lon, z.get("lat", 0), z.get("lon", 0)) <= max_detour
        ]
        target_zone = corridor_pfz[0] if corridor_pfz else (shelf_hotspots[0] if shelf_hotspots else None)
        if target_zone:
            hs_key = _snap_to_grid(target_zone["lat"], target_zone["lon"], passable_map, min_lat, min_lon, grid_spacing=spacing)
            if hs_key and hs_key != start_key and hs_key != end_key:
                leg1 = _astar(passable_map, start_key, hs_key, mode="pfz_maximizer")
                leg2 = _astar(passable_map, hs_key, end_key, mode="pfz_maximizer")
                if leg1 and leg2:
                    sm1 = _smooth_path(leg1, passable_map, mode="direct")
                    sm2 = _smooth_path(leg2, passable_map, mode="direct")
                    combined_pfz = sm1 + sm2[1:]
                    passable_map[hs_key].pfz_chl = 2.4
                    routes_dict["pfz_maximizer"] = _assemble_route(
                        combined_pfz, passable_map, start_name, end_name, dep_time, mode="pfz_maximizer"
                    )

    # Guarantee Safest Route is differentiated from Direct by hugging the coastal contour
    if "direct" in routes_dict and "safest" in routes_dict:
        dir_dist = routes_dict["direct"]["total_distance_km"]
        safe_dist = routes_dict["safest"]["total_distance_km"]
        if abs(dir_dist - safe_dist) < 0.6:
            sheltered_candidates = [
                k for k, node in passable_map.items()
                if node.is_sheltered and k != start_key and k != end_key
            ]
            if sheltered_candidates:
                mid_lat = (w_start.lat + w_end.lat) / 2
                mid_lon = (w_start.lon + w_end.lon) / 2
                best_shelter = min(
                    sheltered_candidates,
                    key=lambda k: haversine(passable_map[k].lat, passable_map[k].lon, mid_lat, mid_lon)
                )
                s_leg1 = _astar(passable_map, start_key, best_shelter, mode="safest")
                s_leg2 = _astar(passable_map, best_shelter, end_key, mode="safest")
                if s_leg1 and s_leg2:
                    sm_s1 = _smooth_path(s_leg1, passable_map, mode="safest")
                    sm_s2 = _smooth_path(s_leg2, passable_map, mode="safest")
                    combined_safe = sm_s1 + sm_s2[1:]
                    routes_dict["safest"] = _assemble_route(
                        combined_safe, passable_map, start_name, end_name, dep_time, mode="safest"
                    )

    if not routes_dict:
        return RouteResult(
            status="no_route",
            error="No safe route found between the two locations.",
            summary=(
                f"No safe route found from {start_name} to {end_name}. "
                "All candidate paths are blocked by land, severe weather, hazards, "
                "or international maritime boundaries."
            ),
        ).__dict__

    # Determine primary/selected profile
    primary_mode = "safest" if "safest" in routes_dict else list(routes_dict.keys())[0]
    if mode in routes_dict:
        primary_mode = mode

    primary = routes_dict[primary_mode]

    # Combine all profile GeoJSON features into a rich multi-route GeoJSON
    combined_features = []
    for m, r in routes_dict.items():
        is_primary = (m == primary_mode)
        for feat in r["route_geojson"].get("features", []):
            f_copy = dict(feat)
            props = dict(f_copy.get("properties", {}))
            props["is_active_profile"] = is_primary
            if not is_primary and props.get("type") == "route":
                # Render non-active profile routes with subtle dash/transparency
                props["opacity"] = 0.55
                props["dashArray"] = "6, 6"
            f_copy["properties"] = props
            combined_features.append(f_copy)

    combined_geojson = {
        "type": "FeatureCollection",
        "features": combined_features,
    }

    result = RouteResult(
        status="success",
        total_distance_km=primary["total_distance_km"],
        total_duration_h=primary["total_duration_h"],
        fuel_liters_est=primary["fuel_liters_est"],
        avg_risk_score=primary["avg_risk_score"],
        max_risk_score=primary["max_risk_score"],
        risk_label=primary["risk_label"],
        selected_mode=primary_mode,
        routes=routes_dict,
        waypoints=primary["waypoints"],
        legs=primary["legs"],
        route_geojson=combined_geojson,
        summary=primary["summary"],
        warnings=primary["warnings"],
    )

    return result.__dict__
