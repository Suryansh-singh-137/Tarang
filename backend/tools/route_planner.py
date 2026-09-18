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
    avg_risk_score: float = 0.0
    max_risk_score: float = 0.0
    risk_label: str = "UNKNOWN"
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
# Grid construction
# ---------------------------------------------------------------------------

def _build_grid(
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
) -> Tuple[List[List[Optional[GridNode]]], Dict[Tuple[int, int], GridNode]]:
    """
    Build a lat/lon grid covering the bounding box between start and end,
    expanded by GRID_EXPAND_DEG to allow detours.

    Returns:
      - grid: 2D list (row, col) of GridNode or None (if on land)
      - node_map: dict of (row, col) -> GridNode for all passable nodes
    """
    min_lat = min(start_lat, end_lat) - GRID_EXPAND_DEG
    max_lat = max(start_lat, end_lat) + GRID_EXPAND_DEG
    min_lon = min(start_lon, end_lon) - GRID_EXPAND_DEG
    max_lon = max(start_lon, end_lon) + GRID_EXPAND_DEG

    rows = int((max_lat - min_lat) / GRID_SPACING_DEG) + 1
    cols = int((max_lon - min_lon) / GRID_SPACING_DEG) + 1

    logger.info(
        "[RoutePlanner] Grid: %.2f-%.2f lat, %.2f-%.2f lon, %dx%d = %d cells",
        min_lat, max_lat, min_lon, max_lon, rows, cols, rows * cols,
    )

    grid: List[List[Optional[GridNode]]] = []
    node_map: Dict[Tuple[int, int], GridNode] = {}

    for r in range(rows):
        row_nodes: List[Optional[GridNode]] = []
        for c in range(cols):
            lat = min_lat + r * GRID_SPACING_DEG
            lon = min_lon + c * GRID_SPACING_DEG

            # Hard constraint: skip land nodes
            if not is_water(lat, lon):
                row_nodes.append(None)
                continue

            node = GridNode(lat=round(lat, 4), lon=round(lon, 4), row=r, col=c)
            row_nodes.append(node)
            node_map[(r, c)] = node

        grid.append(row_nodes)

    logger.info("[RoutePlanner] %d water nodes out of %d total", len(node_map), rows * cols)
    return grid, node_map


def _snap_to_grid(
    lat: float, lon: float, node_map: Dict[Tuple[int, int], GridNode],
    min_lat: float, min_lon: float,
) -> Optional[Tuple[int, int]]:
    """Find the nearest passable grid node to a given point."""
    # Direct grid cell
    r = round((lat - min_lat) / GRID_SPACING_DEG)
    c = round((lon - min_lon) / GRID_SPACING_DEG)

    if (r, c) in node_map:
        return (r, c)

    # Search expanding rings
    best = None
    best_dist = float("inf")
    for dr in range(-3, 4):
        for dc in range(-3, 4):
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



# ---------------------------------------------------------------------------
# A* pathfinding
# ---------------------------------------------------------------------------

def _heuristic(node: GridNode, goal: GridNode) -> float:
    """Admissible heuristic: straight-line haversine distance."""
    return haversine(node.lat, node.lon, goal.lat, goal.lon)


def _edge_cost(from_node: GridNode, to_node: GridNode) -> float:
    """
    Edge cost combining distance and risk.

    cost = distance_km + RISK_WEIGHT * avg_risk_score - PFZ_BONUS * avg_chl

    PFZ bonus makes nodes near fishing zones slightly cheaper (attractive).
    """
    dist = haversine(from_node.lat, from_node.lon, to_node.lat, to_node.lon)
    avg_risk = (from_node.risk_score + to_node.risk_score) / 2.0
    avg_chl = (from_node.pfz_chl + to_node.pfz_chl) / 2.0

    cost = dist + RISK_WEIGHT * avg_risk - PFZ_BONUS * avg_chl * 10.0
    return max(cost, 0.1)  # ensure non-negative


def _astar(
    node_map: Dict[Tuple[int, int], GridNode],
    start_key: Tuple[int, int],
    end_key: Tuple[int, int],
) -> Optional[List[Tuple[int, int]]]:
    """
    Standard A* search over the grid.
    Returns list of (row, col) keys from start to end, or None if no path.
    """
    start_node = node_map[start_key]
    goal_node = node_map[end_key]

    open_set: List[Tuple[float, int, Tuple[int, int]]] = []
    counter = 0  # tie-breaker for heap

    heapq.heappush(open_set, (0.0, counter, start_key))
    counter += 1

    came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
    g_score: Dict[Tuple[int, int], float] = {start_key: 0.0}
    f_score: Dict[Tuple[int, int], float] = {
        start_key: _heuristic(start_node, goal_node)
    }

    closed: set = set()

    while open_set:
        _, _, current_key = heapq.heappop(open_set)

        if current_key == end_key:
            # Reconstruct path
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

            tentative_g = g_score[current_key] + _edge_cost(current_node, neighbor_node)

            if tentative_g < g_score.get(neighbor_key, float("inf")):
                came_from[neighbor_key] = current_key
                g_score[neighbor_key] = tentative_g
                f = tentative_g + _heuristic(neighbor_node, goal_node)
                f_score[neighbor_key] = f
                heapq.heappush(open_set, (f, counter, neighbor_key))
                counter += 1

    return None  # No path found


# ---------------------------------------------------------------------------
# Route result construction
# ---------------------------------------------------------------------------

def _build_geojson(waypoints: List[Dict], legs: List[Dict], warnings: List[str]) -> Dict:
    """Build a GeoJSON FeatureCollection for the route."""
    features = []

    # Route line segments, colored by risk
    if len(waypoints) >= 2:
        coords = [[wp["lon"], wp["lat"]] for wp in waypoints]
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "type": "route",
                "stroke": "#2563eb",
                "stroke-width": 4,
            },
        })

    # Colored segments per leg
    for i, leg in enumerate(legs):
        color = {"LOW": "#22c55e", "MODERATE": "#f59e0b", "HIGH": "#ef4444", "EXTREME": "#dc2626"}.get(
            leg.get("risk_label", "LOW"), "#2563eb"
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

    # PFZ waypoints (nodes with high chlorophyll)
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
) -> str:
    """Build a human-readable route summary."""
    lines = [
        f"Route from {start_name} to {end_name}",
        f"Total distance: {total_dist:.1f} km | Estimated time: {total_hours:.1f} hours",
        f"Overall risk: {risk_label} (avg score: {avg_risk:.0f}/100)",
    ]

    if pfz_waypoints > 0:
        lines.append(f"🐟 Route passes near {pfz_waypoints} potential fishing zone(s)")

    if warnings:
        lines.append("")
        lines.append("⚠️ Warnings:")
        for w in warnings:
            lines.append(f"  • {w}")

    # Per-leg summary
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


# ---------------------------------------------------------------------------
# Main entry point
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
) -> Dict[str, Any]:
    """
    Compute a safe, optimized marine route between two locations.

    Args:
        start_lat, start_lon: departure coordinates
        end_lat, end_lon: destination coordinates
        start_name, end_name: human-readable location names
        departure_utc: ISO-8601 departure time (defaults to now)
        time_window: fallback time window if departure_utc is not provided
        include_pfz: whether to factor in PFZ zones for route attraction

    Returns:
        Dict with status, route details, GeoJSON, summary, and warnings.
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
        "[RoutePlanner] Planning route: (%.4f, %.4f) -> (%.4f, %.4f), direct=%.1f km, departure=%s",
        start_lat, start_lon, end_lat, end_lon, direct_dist, dep_time.isoformat(),
    )

    # Build grid
    grid, node_map = _build_grid(start_lat, start_lon, end_lat, end_lon)

    if not node_map:
        return RouteResult(
            status="error",
            error="No water nodes found in the routing area. Both points may be on land.",
            summary="Unable to plan route: no navigable water found in the area.",
        ).__dict__

    # Compute bounding box for snapping
    min_lat = min(start_lat, end_lat) - GRID_EXPAND_DEG
    min_lon = min(start_lon, end_lon) - GRID_EXPAND_DEG

    # Snap start/end to grid
    start_key = _snap_to_grid(start_lat, start_lon, node_map, min_lat, min_lon)
    end_key = _snap_to_grid(end_lat, end_lon, node_map, min_lat, min_lon)

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

    # Pre-fetch PFZ zones along corridor if requested
    pfz_zones: List[Dict] = []
    if include_pfz:
        mid_lat = (start_lat + end_lat) / 2.0
        mid_lon = (start_lon + end_lon) / 2.0
        pfz_zones = _prefetch_corridor_pfz(mid_lat, mid_lon)

    # Evaluate safety at all nodes
    logger.info("[RoutePlanner] Evaluating safety at %d water nodes...", len(node_map))

    for key, node in node_map.items():
        _evaluate_node_safety(node, anchors)

        if include_pfz and pfz_zones:
            _evaluate_pfz_at_node(node, pfz_zones)

    # Remove impassable nodes from the map
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

    logger.info("[RoutePlanner] %d passable nodes (of %d evaluated)", len(passable_map), len(node_map))

    # A* search
    path = _astar(passable_map, start_key, end_key)

    if not path:
        return RouteResult(
            status="no_route",
            error="No safe route found between the two locations.",
            summary=(
                f"No safe route found from {start_name} to {end_name}. "
                "All candidate paths are blocked by land, severe weather, hazards, "
                "or international maritime boundaries."
            ),
        ).__dict__

    logger.info("[RoutePlanner] A* found path with %d waypoints", len(path))

    # Build route result
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
        wp: Dict[str, Any] = {
            "lat": node.lat,
            "lon": node.lon,
            "risk_score": node.risk_score,
            "risk_label": node.risk_label,
            "wave_height_m": node.wave_height_m,
            "wind_speed_kmh": node.wind_speed_kmh,
            "boundary_dist_km": node.boundary_dist_km,
            "hazard_level": node.hazard_level,
            "pfz_chl": node.pfz_chl,
        }

        # Name first and last waypoints
        if i == 0:
            wp["name"] = start_name
        elif i == len(path) - 1:
            wp["name"] = end_name

        waypoints.append(wp)
        risk_scores.append(node.risk_score)
        max_risk = max(max_risk, node.risk_score)

        if node.pfz_chl > 0.5:
            pfz_count += 1

        # Build legs
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

            # Generate warnings for concerning legs
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

    # Build GeoJSON
    route_geojson = _build_geojson(waypoints, legs, warnings)

    # Build summary
    summary = _build_summary(
        start_name, end_name, total_dist, total_hours,
        overall_label, avg_risk, warnings, legs, pfz_count,
    )

    result = RouteResult(
        status="success",
        total_distance_km=total_dist,
        total_duration_h=total_hours,
        avg_risk_score=avg_risk,
        max_risk_score=round(max_risk, 1),
        risk_label=overall_label,
        waypoints=waypoints,
        legs=legs,
        route_geojson=route_geojson,
        summary=summary,
        warnings=warnings,
    )

    logger.info(
        "[RoutePlanner] Route found: %.1f km, %.1f hrs, risk=%s (avg=%.0f, max=%.0f), %d legs, %d PFZ nearby",
        total_dist, total_hours, overall_label, avg_risk, max_risk, len(legs), pfz_count,
    )

    return result.__dict__
