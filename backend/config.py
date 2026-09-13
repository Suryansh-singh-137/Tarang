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

# Groq configuration (Milestone 6)
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL_FAST: str = "llama-3.1-8b-instant"
GROQ_MODEL_QUALITY: str = "llama-3.3-70b-versatile"

# Sarvam TTS configuration (Milestone 7)
SARVAM_API_KEY: str = os.getenv("SARVAM_API_KEY", "")

# ---------------------------------------------------------------------------
# HTTP client settings
# ---------------------------------------------------------------------------

# Global connect + read timeout in seconds for all outbound requests
HTTP_TIMEOUT: int = int(os.getenv("HTTP_TIMEOUT", "10"))  # M8: reduced from 15 → 10 (fail fast)

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

CACHE_TTL_MARINE_S: int = int(os.getenv("CACHE_TTL_MARINE_S", "600"))    # M8: 10 min (was 30 min)
CACHE_TTL_HAZARD_S: int = int(os.getenv("CACHE_TTL_HAZARD_S", "600"))    # M8: 10 min (was 30 min)
CACHE_TTL_PFZ_S: int   = int(os.getenv("CACHE_TTL_PFZ_S",    "3600"))    # M8: 60 min (was 4 h)
CACHE_TTL_GDACS_S: int = int(os.getenv("CACHE_TTL_GDACS_S",  "600"))     # M8: 10 min

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
# Milestone 8: Data freshness max-age (hours) per domain
# Used by data_validator.py to determine staleness
# ---------------------------------------------------------------------------

WEATHER_MAX_AGE_HOURS: float = float(os.getenv("WEATHER_MAX_AGE_HOURS", "12"))
HAZARD_MAX_AGE_HOURS: float  = float(os.getenv("HAZARD_MAX_AGE_HOURS",  "6"))
PFZ_MAX_AGE_HOURS: float     = float(os.getenv("PFZ_MAX_AGE_HOURS",     "168"))  # 7 days (satellite)
SST_MAX_AGE_HOURS: float     = float(os.getenv("SST_MAX_AGE_HOURS",     "72"))

# ---------------------------------------------------------------------------
# Milestone 8: GDACS cyclone configuration
# ---------------------------------------------------------------------------

# Base URL for GDACS event search API (confirmed working, returns GeoJSON)
GDACS_BASE_URL: str = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"

# Distance threshold (km): only cyclones within this radius are treated as
# spatially relevant to the query location
GDACS_SEARCH_RADIUS_KM: float = float(os.getenv("GDACS_SEARCH_RADIUS_KM", "500"))

# Alert levels to include in cyclone queries (Orange/Red = significant)
# Green cyclones are also fetched for situational awareness if within radius/4
GDACS_ALERT_LEVELS: str = os.getenv("GDACS_ALERT_LEVELS", "Orange,Red")

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
