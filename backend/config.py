"""
config.py
---------
Centralised runtime configuration for the Tarang backend.

All values have sensible defaults so the system works out-of-the-box
without a .env file.  Secrets (API keys, passwords) must only come from
environment variables — never from this file.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# ---------------------------------------------------------------------------
# External API base URLs
# ---------------------------------------------------------------------------

# INCOIS ERDDAP — public, no auth required
INCOIS_ERDDAP_BASE_URL: str = os.getenv(
    "INCOIS_ERDDAP_BASE_URL", "https://erddap.incois.gov.in/erddap"
)

# Open-Meteo — free, no auth required
OPEN_METEO_MARINE_URL: str = "https://marine-api.open-meteo.com/v1/marine"
OPEN_METEO_FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"

# Optional CMEMS credentials (Tier-2, not required for M2)
CMEMS_USERNAME: str = os.getenv("CMEMS_USERNAME", "")
CMEMS_PASSWORD: str = os.getenv("CMEMS_PASSWORD", "")

# Optional OpenAI key (used by synthesis LLM upgrade in M3)
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# ---------------------------------------------------------------------------
# HTTP client settings
# ---------------------------------------------------------------------------

# Global connect + read timeout in seconds for all outbound requests
HTTP_TIMEOUT: int = int(os.getenv("HTTP_TIMEOUT", "15"))

# ---------------------------------------------------------------------------
# PFZ configuration
# ---------------------------------------------------------------------------

# Chlorophyll threshold (mg/m³) above which a grid cell is treated as a PFZ
CHL_PFZ_THRESHOLD: float = float(os.getenv("CHL_PFZ_THRESHOLD", "0.5"))

# Default search radius (km) for PFZ zones around the query point
PFZ_SEARCH_RADIUS_KM: float = float(os.getenv("PFZ_SEARCH_RADIUS_KM", "150"))

# ERDDAP bounding-box half-width in degrees (~150 km ≈ 1.5°)
PFZ_BBOX_DEG: float = float(os.getenv("PFZ_BBOX_DEG", "1.5"))

# Maximum PFZ zones to return in a single result
PFZ_MAX_ZONES: int = int(os.getenv("PFZ_MAX_ZONES", "5"))

# ---------------------------------------------------------------------------
# Cache TTLs (seconds)
# ---------------------------------------------------------------------------

CACHE_TTL_MARINE_S: int = int(os.getenv("CACHE_TTL_MARINE_S", "1800"))   # 30 min
CACHE_TTL_HAZARD_S: int = int(os.getenv("CACHE_TTL_HAZARD_S", "1800"))   # 30 min
CACHE_TTL_PFZ_S: int   = int(os.getenv("CACHE_TTL_PFZ_S",    "14400"))   # 4 hours

# ---------------------------------------------------------------------------
# Risk weights (must sum to 1.0)
# Exposed here so they are configurable without editing agent code.
# ---------------------------------------------------------------------------

RISK_WEIGHTS: dict[str, float] = {
    "wave_height":        0.30,
    "wind_speed":         0.20,
    "hazard_level":       0.30,
    "boundary_proximity": 0.20,
}

# ---------------------------------------------------------------------------
# Timezone
# ---------------------------------------------------------------------------

INDIA_TZ: str = "Asia/Kolkata"
