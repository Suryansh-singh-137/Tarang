"""
incois_client.py
----------------
INCOIS ERDDAP client for Milestone 2.

Data retrieved:
  - Chlorophyll-a (CHL, mg/m³) from INCOIS Oceansat-2 dataset
  - Sea Surface Temperature (SST, °C) from NOAA AVHRR/AMSR dataset

PFZ detection strategy:
  High chlorophyll concentration indicates phytoplankton blooms which
  attract fish.  Grid cells with CHL >= CHL_PFZ_THRESHOLD (default 0.5
  mg/m³) are treated as potential fishing zones.

  This is a scientific proxy for INCOIS PFZ advisories.  The synthesis
  layer explicitly labels results as "INCOIS ERDDAP (chlorophyll-based
  PFZ indicator)" and advises consulting official INCOIS advisories.

ERDDAP query format:
  griddap JSON: /erddap/griddap/<dataset>.json?<var>[(last)][(lat_min):(lat_max)][(lon_min):(lon_max)]

Caching: in-memory TTL cache, 4-hour TTL (satellite passes are infrequent).

Data freshness:
  - source_time:  the timestamp of the latest available satellite pass
  - retrieved_at: when this function was called
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from cachetools import TTLCache

import config

logger = logging.getLogger("tarang.incois")

# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------
_pfz_cache: TTLCache = TTLCache(maxsize=32, ttl=config.CACHE_TTL_PFZ_S)

# ---------------------------------------------------------------------------
# ERDDAP dataset IDs
# ---------------------------------------------------------------------------
_DATASET_CHL = "incois_oceansat2_datasets"
_DATASET_SST = "NOAA_AVHRR_AMSR_datasets"

# ---------------------------------------------------------------------------
# Normalised data types
# ---------------------------------------------------------------------------

@dataclass
class ChlPoint:
    """A single chlorophyll observation from ERDDAP."""
    lat: float
    lon: float
    chl_mg_m3: float
    source_time: str        # ISO-8601 UTC (satellite pass time)


@dataclass
class PFZResult:
    """Normalised PFZ zone data derived from chlorophyll analysis."""
    zones: list[dict]       # list of zone dicts (lat, lon, distance_km, chl, etc.)
    nearest_zone_km: float
    zone_count: int
    avg_chl: float
    source_time: str        # satellite pass time
    retrieved_at: str
    source: str = "INCOIS ERDDAP (Oceansat-2, chlorophyll-based PFZ proxy)"
    used_fallback: bool = False


# ---------------------------------------------------------------------------
# Haversine helper (duplicated here to keep tool self-contained)
# ---------------------------------------------------------------------------
_R = 6371.0

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# ERDDAP fetch helpers
# ---------------------------------------------------------------------------

def _build_erddap_url(
    dataset_id: str, variable: str,
    lat_min: float, lat_max: float,
    lon_min: float, lon_max: float,
) -> str:
    """
    Build an ERDDAP griddap JSON URL for the latest time step.
    ERDDAP constraint format uses URL-encoded brackets.
    """
    # URL-encoded: %5B = [ , %5D = ]
    constraint = (
        f"%5B(last)%5D"
        f"%5B({lat_min:.4f}):({lat_max:.4f})%5D"
        f"%5B({lon_min:.4f}):({lon_max:.4f})%5D"
    )
    return (
        f"{config.INCOIS_ERDDAP_BASE_URL}/griddap/{dataset_id}.json"
        f"?{variable}{constraint}"
    )


def _fetch_erddap_grid(
    dataset_id: str, variable: str,
    lat_min: float, lat_max: float,
    lon_min: float, lon_max: float,
) -> tuple[list[dict], str] | None:
    """
    Fetch a grid variable from ERDDAP.
    Returns (rows_list, source_time_str) or None on failure.
    Each row dict: {"lat": float, "lon": float, "value": float, "time": str}
    """
    url = _build_erddap_url(dataset_id, variable, lat_min, lat_max, lon_min, lon_max)
    logger.info("[INCOIS] Requesting ERDDAP: %s", url[:120])

    try:
        # INCOIS ERDDAP uses an intermediate cert not trusted by all OS stores;
        # verify=False is used deliberately.  No credentials are transmitted.
        with httpx.Client(timeout=config.HTTP_TIMEOUT, verify=False) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.warning("[INCOIS] ERDDAP request timed out after %ds", config.HTTP_TIMEOUT)
        return None
    except httpx.HTTPError as exc:
        logger.warning("[INCOIS] ERDDAP HTTP error: %s", exc)
        return None
    except Exception as exc:
        logger.warning("[INCOIS] Unexpected ERDDAP error: %s", exc)
        return None

    try:
        table = data["table"]
        col_names = table["columnNames"]
        rows_raw = table["rows"]

        time_idx = col_names.index("time")
        lat_idx = col_names.index("latitude")
        lon_idx = col_names.index("longitude")
        val_idx = col_names.index(variable)

        rows: list[dict] = []
        source_time = ""
        for row in rows_raw:
            val = row[val_idx]
            if val is None:
                continue
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            t = row[time_idx] or ""
            if not source_time and t:
                source_time = t  # record first non-null time
            rows.append({
                "lat": float(row[lat_idx]),
                "lon": float(row[lon_idx]),
                "value": val,
                "time": t,
            })

        logger.info("[INCOIS] Retrieved %d valid %s cells", len(rows), variable)
        return rows, source_time

    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("[INCOIS] Failed to parse ERDDAP response: %s", exc)
        return None


# ---------------------------------------------------------------------------
# PFZ detection from chlorophyll grid
# ---------------------------------------------------------------------------

def fetch_pfz_zones(
    query_lat: float, query_lon: float
) -> Optional[PFZResult]:
    """
    Fetch chlorophyll grid from INCOIS ERDDAP, identify high-CHL cells as
    PFZ candidates, filter by search radius, and return ranked zones.

    Returns None if ERDDAP is unreachable or returns no valid data.
    """
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    cache_key = (round(query_lat, 1), round(query_lon, 1))

    if cache_key in _pfz_cache:
        logger.info("[INCOIS] Cache hit for PFZ key=%s", cache_key)
        return _pfz_cache[cache_key]

    # Build bounding box
    half = config.PFZ_BBOX_DEG
    lat_min = round(query_lat - half, 4)
    lat_max = round(query_lat + half, 4)
    lon_min = round(query_lon - half, 4)
    lon_max = round(query_lon + half, 4)

    # Fetch chlorophyll grid
    result = _fetch_erddap_grid(
        _DATASET_CHL, "CHL", lat_min, lat_max, lon_min, lon_max
    )
    if result is None:
        logger.warning("[INCOIS] CHL fetch failed — no PFZ result")
        return None

    chl_rows, source_time = result
    if not chl_rows:
        logger.warning("[INCOIS] No CHL data in bounding box")
        return None

    # Filter: only cells above the PFZ threshold
    threshold = config.CHL_PFZ_THRESHOLD
    pfz_candidates = [r for r in chl_rows if r["value"] >= threshold]
    logger.info(
        "[INCOIS] %d/%d cells above CHL threshold %.2f mg/m³",
        len(pfz_candidates), len(chl_rows), threshold,
    )

    if not pfz_candidates:
        # No cells above threshold — return the highest-CHL cell anyway
        # as the "best" fishing indicator in the area
        pfz_candidates = sorted(chl_rows, key=lambda r: r["value"], reverse=True)[:3]
        logger.info("[INCOIS] No cells above threshold; using top %d CHL cells", len(pfz_candidates))

    # Calculate distances and sort by CHL descending (high CHL = better PFZ)
    for cell in pfz_candidates:
        cell["distance_km"] = round(
            _haversine(query_lat, query_lon, cell["lat"], cell["lon"]), 1
        )

    # Filter to search radius
    within_radius = [c for c in pfz_candidates if c["distance_km"] <= config.PFZ_SEARCH_RADIUS_KM]
    if not within_radius:
        # Extend to closest outside radius
        within_radius = sorted(pfz_candidates, key=lambda c: c["distance_km"])[:1]

    # Sort by CHL desc, take top N
    within_radius.sort(key=lambda c: c["value"], reverse=True)
    top_zones = within_radius[:config.PFZ_MAX_ZONES]

    # Build zone list
    zones = []
    for i, cell in enumerate(top_zones):
        zones.append({
            "zone_id": f"PFZ-CHL-{i+1:03d}",
            "lat": cell["lat"],
            "lon": cell["lon"],
            "distance_km": cell["distance_km"],
            "chlorophyll_mg_m3": round(cell["value"], 3),
            "advisory_date": (source_time or retrieved_at)[:10],
            "source": "INCOIS Oceansat-2 (ERDDAP)",
            "description": (
                f"High chlorophyll zone (CHL={cell['value']:.2f} mg/m³); "
                f"{cell['distance_km']:.0f} km from query point"
            ),
        })

    nearest_km = min(z["distance_km"] for z in zones) if zones else 999.0
    avg_chl = round(sum(z["chlorophyll_mg_m3"] for z in zones) / len(zones), 3)

    logger.info(
        "[INCOIS] PFZ zones found: %d; nearest: %.1f km",
        len(zones), nearest_km,
    )

    pfz_result = PFZResult(
        zones=zones,
        nearest_zone_km=nearest_km,
        zone_count=len(zones),
        avg_chl=avg_chl,
        source_time=source_time or retrieved_at,
        retrieved_at=retrieved_at,
    )
    _pfz_cache[cache_key] = pfz_result
    return pfz_result


# ---------------------------------------------------------------------------
# SST fetch (optional enrichment)
# ---------------------------------------------------------------------------

def fetch_sst(
    lat_min: float, lat_max: float, lon_min: float, lon_max: float
) -> Optional[float]:
    """
    Return the average SST (°C) for the bounding box from NOAA AVHRR/AMSR.
    Returns None on failure.
    """
    result = _fetch_erddap_grid(_DATASET_SST, "sst", lat_min, lat_max, lon_min, lon_max)
    if result is None or not result[0]:
        return None
    values = [r["value"] for r in result[0]]
    return round(sum(values) / len(values), 1)
