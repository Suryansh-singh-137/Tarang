"""
land_mask.py
------------
Lightweight land/water classifier using a static simplified polygon of
the Indian subcontinent (+ Sri Lanka).

Uses shapely's Point.within(Polygon) for O(1)-per-query classification
after the one-time polygon load.

Grid points classified as "land" are hard-excluded from the route graph.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from functools import lru_cache
from typing import List

from shapely.geometry import Point, shape, MultiPolygon
from shapely.prepared import prep

logger = logging.getLogger("tarang.land_mask")

DATA_DIR = Path(__file__).parent.parent / "data"
_LANDMASS_FILE = DATA_DIR / "india_landmass.geojson"

# Buffer in degrees around land polygons.  A grid node within this buffer
# of the coastline is treated as "coastal / too close to shore" for route
# planning.  ~0.02° ≈ 2 km.
_COASTAL_BUFFER_DEG = 0.02


@lru_cache(maxsize=1)
def _load_land_polygons() -> MultiPolygon:
    """Load and merge all land polygons from the static GeoJSON file."""
    if not _LANDMASS_FILE.exists():
        logger.warning(
            "[LandMask] %s not found — land masking disabled (all points treated as water)",
            _LANDMASS_FILE,
        )
        return MultiPolygon()

    try:
        with open(_LANDMASS_FILE, "r", encoding="utf-8") as f:
            geojson = json.load(f)

        polygons = []
        for feature in geojson.get("features", []):
            geom = shape(feature["geometry"])
            if geom.is_valid:
                polygons.append(geom)
            else:
                # Attempt to fix invalid geometry
                fixed = geom.buffer(0)
                if fixed.is_valid:
                    polygons.append(fixed)
                    logger.info("[LandMask] Fixed invalid geometry for %s",
                                feature.get("properties", {}).get("name", "unknown"))

        if not polygons:
            logger.warning("[LandMask] No valid polygons found in %s", _LANDMASS_FILE)
            return MultiPolygon()

        # Merge all polygons, buffered slightly for coastal margin
        merged = polygons[0]
        for p in polygons[1:]:
            merged = merged.union(p)

        # Apply coastal buffer so routes don't hug the coastline
        buffered = merged.buffer(_COASTAL_BUFFER_DEG)

        if not isinstance(buffered, MultiPolygon):
            buffered = MultiPolygon([buffered])

        logger.info(
            "[LandMask] Loaded %d land polygon(s), total area=%.1f sq-deg",
            len(polygons), buffered.area,
        )
        return buffered

    except Exception as exc:
        logger.error("[LandMask] Failed to load landmass GeoJSON: %s", exc)
        return MultiPolygon()


@lru_cache(maxsize=1)
def _prepared_land():
    """Return a prepared geometry for fast repeated containment checks."""
    poly = _load_land_polygons()
    return prep(poly)


def is_land(lat: float, lon: float) -> bool:
    """
    Return True if the point (lat, lon) falls on land (including coastal buffer).

    Uses shapely prepared geometry for O(log n) spatial index lookups.
    """
    prepared = _prepared_land()
    point = Point(lon, lat)  # shapely uses (x=lon, y=lat)
    return prepared.contains(point)


def is_water(lat: float, lon: float) -> bool:
    """Return True if the point is over open water (not land)."""
    return not is_land(lat, lon)


def filter_water_points(
    points: List[tuple[float, float]],
) -> List[tuple[float, float]]:
    """
    Filter a list of (lat, lon) points, keeping only those over water.
    """
    prepared = _prepared_land()
    return [
        (lat, lon) for lat, lon in points
        if not prepared.contains(Point(lon, lat))
    ]
