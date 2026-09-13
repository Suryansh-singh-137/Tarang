"""
imd_client.py
-------------
India Meteorological Department (IMD) warnings client — architecture stub.

M8 Status: STUB — IMD API access requires registration with IMD.

Role in the hazard hierarchy:
  TIER 1 (most authoritative for India)

  IMD official warnings   [TIER 1 — authoritative for India, cyclone/severe weather]
         ↓  (if unavailable)
  GDACS cyclone events    [TIER 2]
         ↓  (if unavailable)
  Open-Meteo WMO codes    [TIER 3]

Activation instructions (for future integration):
  1. Register at: https://mausam.imd.gov.in/imd_latest/contents/api.php
  2. Obtain API key
  3. Set environment variable: IMD_API_KEY=<your_key>
  4. Replace fetch_imd_warnings() stub with live implementation

The architecture below is ready for live activation.

Endpoint structure (when credentials available):
  Base: https://mausam.imd.gov.in/api/
  Endpoints of interest:
    - /warnings       — cyclone + severe weather warnings
    - /bulletins      — district-level bulletins
    - /observations   — surface observations

This module MUST NOT be bypassed. When activated, IMD warnings must
dominate the hazard result over GDACS and Open-Meteo.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("tarang.imd")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

IMD_API_KEY: str = os.getenv("IMD_API_KEY", "")
IMD_BASE_URL: str = "https://mausam.imd.gov.in/api"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class IMDWarning:
    """A single IMD official warning advisory."""
    warning_type:    str          # "CYCLONE_WARNING" | "GALE_WARNING" | "HEAVY_RAIN" | etc.
    severity:        str          # "none" | "low" | "moderate" | "high" | "extreme"
    headline:        str
    detail:          str
    issued_at:       str          # ISO-8601 UTC
    valid_from:      str          # ISO-8601 UTC
    valid_until:     str          # ISO-8601 UTC
    area_description: str
    lat_min:         Optional[float]
    lat_max:         Optional[float]
    lon_min:         Optional[float]
    lon_max:         Optional[float]
    source:          str = "India Meteorological Department (IMD)"
    is_official:     bool = True


@dataclass
class IMDAdvisoryResult:
    """Container for all active IMD warnings for a location."""
    warnings:       list[IMDWarning]
    overall_level:  str           # "none" | "low" | "moderate" | "high" | "extreme"
    retrieved_at:   str
    source:         str = "India Meteorological Department (IMD)"
    available:      bool = False  # False when API credentials not configured


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def fetch_imd_warnings(
    lat: float, lon: float, time_window: str = "next_24h"
) -> Optional[IMDAdvisoryResult]:
    """
    Fetch official IMD weather and marine warnings for a location.

    STUB STATUS: Returns None because IMD API requires registration.

    When activated (IMD_API_KEY is set):
    - Query IMD API for warnings relevant to (lat, lon)
    - Filter temporally by time_window
    - Return IMDAdvisoryResult with full warning detail

    Args:
        lat:         Query latitude
        lon:         Query longitude
        time_window: Requested time window (e.g. "next_24h", "tomorrow")

    Returns:
        None — always (stub implementation).
        Future: IMDAdvisoryResult when API credentials are configured.
    """
    if not IMD_API_KEY:
        logger.info(
            "[IMD] API key not configured (set IMD_API_KEY env var). "
            "IMD Tier-1 warnings unavailable. Falling through to GDACS/Open-Meteo."
        )
        return None

    # ── Future live implementation ────────────────────────────────────────
    # When IMD_API_KEY is set, implement:
    #   1. GET {IMD_BASE_URL}/warnings?lat={lat}&lon={lon}&apikey={IMD_API_KEY}
    #   2. Parse response for relevant warnings
    #   3. Filter by time_window
    #   4. Return IMDAdvisoryResult(warnings=[...], overall_level="...", ...)
    #
    # Until then:
    logger.info("[IMD] Stub: IMD API integration ready but not yet activated.")
    return None
