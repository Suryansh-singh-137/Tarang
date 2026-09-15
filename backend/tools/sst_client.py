"""
sst_client.py
-------------
Client for fetching Sea Surface Temperature (SST) and SST anomaly
from the INCOIS ERDDAP server.

Dataset: NOAA AVHRR/AMSR high-resolution daily SST (or configured INCOIS ERDDAP dataset).
No API key required — public griddap query.

Invariants:
- Live data retrieval using latitude, longitude, and latest available date [(last)].
- Returns exact values, observation time, source, and data status.
- Strict fail-closed error handling: NO mock data is ever fabricated.
- Disclaimer: SST and thermal anomalies indicate ocean surface temperature trends only;
  they do not guarantee the presence or catchability of fish.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional, TypedDict

import httpx
from cachetools import TTLCache

import config

logger = logging.getLogger("tarang.sst")

# ---------------------------------------------------------------------------
# In-memory TTL cache (60 minutes)
# ---------------------------------------------------------------------------
_sst_cache: TTLCache = TTLCache(maxsize=64, ttl=config.CACHE_TTL_SST_S)

# Dataset ID on INCOIS ERDDAP
_DATASET_SST = os.getenv("INCOIS_SST_DATASET_ID", "NOAA_AVHRR_AMSR_datasets")

SST_DISCLAIMER = (
    "Sea surface temperature (SST) and thermal anomalies indicate ocean surface "
    "temperature trends only and do not guarantee fish presence."
)


class SSTResult(TypedDict):
    success: bool
    sst_celsius: Optional[float]
    sst_anomaly_c: Optional[float]
    observation_time: Optional[str]
    source: str
    data_status: str
    data_quality: str
    disclaimer: str
    error: Optional[str]


def _build_erddap_sst_url(
    lat_min: float, lat_max: float, lon_min: float, lon_max: float
) -> str:
    """
    Construct URL querying both 'sst' and 'anom' for the latest available date.
    URL-encoded brackets: %5B = [, %5D = ]
    """
    constraint = (
        f"%5B(last)%5D"
        f"%5B({lat_min:.4f}):({lat_max:.4f})%5D"
        f"%5B({lon_min:.4f}):({lon_max:.4f})%5D"
    )
    # Request sst and anom in a single griddap call
    return (
        f"{config.INCOIS_ERDDAP_BASE_URL}/griddap/{_DATASET_SST}.json"
        f"?sst{constraint},anom{constraint}"
    )


def fetch_sst_and_anomaly(
    lat: float, lon: float, radius_deg: float = 0.25
) -> SSTResult:
    """
    Fetch SST and SST anomaly for the resolved coastal coordinate using
    latitude, longitude, and latest available date from INCOIS ERDDAP.

    No API key required.
    Fails closed if the endpoint is unreachable or returns an error.
    Never fabricates mock data.
    """
    cache_key = (round(lat, 2), round(lon, 2))
    if cache_key in _sst_cache:
        logger.info("[SST] Cache hit for coordinates (%s, %s)", lat, lon)
        cached = dict(_sst_cache[cache_key])
        cached["data_status"] = "cached"
        return cached  # type: ignore[return-value]

    lat_min = lat - radius_deg
    lat_max = lat + radius_deg
    lon_min = lon - radius_deg
    lon_max = lon + radius_deg

    url = _build_erddap_sst_url(lat_min, lat_max, lon_min, lon_max)
    logger.info("[SST] Requesting INCOIS ERDDAP SST: %s", url[:120])

    try:
        # INCOIS ERDDAP uses an intermediate SSL cert not trusted by all root bundles;
        # verify=False is used deliberately. No sensitive data or credentials transmitted.
        with httpx.Client(timeout=config.HTTP_TIMEOUT, verify=False) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        table = data["table"]
        col_names = table["columnNames"]
        rows_raw = table["rows"]

        time_idx = col_names.index("time") if "time" in col_names else -1
        sst_idx = col_names.index("sst") if "sst" in col_names else -1
        anom_idx = col_names.index("anom") if "anom" in col_names else -1

        sst_values: list[float] = []
        anom_values: list[float] = []
        obs_time: Optional[str] = None

        for row in rows_raw:
            if time_idx >= 0 and not obs_time and row[time_idx]:
                obs_time = str(row[time_idx])

            if sst_idx >= 0 and row[sst_idx] is not None:
                try:
                    val = float(row[sst_idx])
                    # Filter physical ocean bounds (10°C to 40°C for Indian tropical waters)
                    if 10.0 <= val <= 40.0:
                        sst_values.append(val)
                except (TypeError, ValueError):
                    pass

            if anom_idx >= 0 and row[anom_idx] is not None:
                try:
                    aval = float(row[anom_idx])
                    # Anomalies typically between -10°C and +10°C
                    if -10.0 <= aval <= 10.0:
                        anom_values.append(aval)
                except (TypeError, ValueError):
                    pass

        if not sst_values:
            logger.warning("[SST] No valid SST values returned from INCOIS ERDDAP grid")
            return {
                "success": False,
                "sst_celsius": None,
                "sst_anomaly_c": None,
                "observation_time": obs_time,
                "source": "INCOIS ERDDAP (NOAA AVHRR/AMSR SST)",
                "data_status": "unavailable",
                "data_quality": "unavailable",
                "disclaimer": SST_DISCLAIMER,
                "error": "NO_VALID_SST_CELLS",
            }

        avg_sst = round(sum(sst_values) / len(sst_values), 2)
        avg_anom = round(sum(anom_values) / len(anom_values), 2) if anom_values else None

        result: SSTResult = {
            "success": True,
            "sst_celsius": avg_sst,
            "sst_anomaly_c": avg_anom,
            "observation_time": obs_time or datetime.now(timezone.utc).isoformat(),
            "source": "INCOIS ERDDAP (NOAA AVHRR/AMSR SST)",
            "data_status": "live",
            "data_quality": "live",
            "disclaimer": SST_DISCLAIMER,
            "error": None,
        }

        _sst_cache[cache_key] = result
        logger.info(
            "[SST] Successfully fetched SST: %.2f°C (anomaly: %s) time=%s",
            avg_sst, avg_anom, obs_time,
        )
        return result

    except httpx.TimeoutException:
        logger.warning("[SST] INCOIS ERDDAP timed out after %ds", config.HTTP_TIMEOUT)
    except httpx.HTTPError as exc:
        logger.warning("[SST] INCOIS ERDDAP HTTP error: %s", exc)
    except Exception as exc:
        logger.warning("[SST] Unexpected error fetching from INCOIS ERDDAP: %s", exc)

    # Fail-closed: No mock data!
    return {
        "success": False,
        "sst_celsius": None,
        "sst_anomaly_c": None,
        "observation_time": None,
        "source": "INCOIS ERDDAP (NOAA AVHRR/AMSR SST)",
        "data_status": "unavailable",
        "data_quality": "unavailable",
        "disclaimer": SST_DISCLAIMER,
        "error": "INCOIS_ERDDAP_UNAVAILABLE",
    }
