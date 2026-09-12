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

# Optional OpenAI key (reserved for future LLM-synthesis upgrades)
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# ---------------------------------------------------------------------------
# HTTP client settings
# ---------------------------------------------------------------------------

# Global connect + read timeout in seconds for all outbound requests
HTTP_TIMEOUT: int = int(os.getenv("HTTP_TIMEOUT", "15"))

# ---------------------------------------------------------------------------
# PFZ configuration
# ---------------------------------------------------------------------------

# Chlorophyll threshold (mg/m³) above which a grid cell is treated as a PFZ indicator
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
# Milestone 5: Conversational memory settings
# ---------------------------------------------------------------------------

# How long (seconds) an agent result remains reusable in a follow-up query
# without re-fetching from the external source.
FOLLOWUP_CACHE_TTL_SECONDS: int = int(os.getenv("FOLLOWUP_CACHE_TTL_SECONDS", "300"))

# Maximum number of turns to keep in conversation_history.
MAX_CONVERSATION_TURNS: int = int(os.getenv("MAX_CONVERSATION_TURNS", "6"))

# Which ParsedIntent fields each agent depends on.
# If none of these fields appear in changed_fields, the cached result can be reused.
AGENT_DEPENDS_ON: dict[str, list[str]] = {
    "weather_agent":  ["lat", "lon", "time_window", "time_start_utc", "time_end_utc"],
    "pfz_agent":      ["lat", "lon"],
    "hazard_agent":   ["lat", "lon", "time_window", "time_start_utc", "time_end_utc"],
    "geofence_agent": ["lat", "lon"],
    # risk_agent always recomputes deterministically — no cache bypass for it
    "risk_agent":     [],
}

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
