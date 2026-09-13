"""
source_registry.py
------------------
Centralised data-source provenance registry for Tarang M8.

Every external data source that Tarang uses is registered here with:
  - provenance_tier: authority level (OFFICIAL_OPERATIONAL → HISTORICAL_FALLBACK)
  - domain:          the marine intelligence domain it covers
  - official:        whether this is an authoritative Indian government source
  - max_age_hours:   how stale this source's data is allowed to be before it is
                     flagged — domain-aware (PFZ can tolerate more than weather)
  - description:     plain-language description for transparency in synthesis

This prevents provenance logic being duplicated across agents and ensures
the LLM never has to decide what is "authoritative" — Python code does.
"""

from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# Provenance Tier
# ---------------------------------------------------------------------------

class ProvenanceTier(str, Enum):
    """
    Ordered authority tiers for marine data sources.

    OFFICIAL_OPERATIONAL  — Indian government operational advisory service
                            (INCOIS PFZ, IMD cyclone warnings)
    OFFICIAL_NRT          — Official near-real-time scientific dataset
                            (INCOIS ERDDAP oceanographic grids)
    SCIENTIFIC_MODEL      — High-quality global scientific model
                            (CMEMS, Copernicus Marine)
    GLOBAL_MODEL          — Operational global NWP / marine forecast model
                            (Open-Meteo ERA5 + ICON)
    PROXY                 — Derived or indirect indicator
                            (CHL as PFZ proxy, WMO codes as hazard proxy)
    HISTORICAL_FALLBACK   — Pre-cached static data used only when live fails
    """
    OFFICIAL_OPERATIONAL = "official_operational"
    OFFICIAL_NRT         = "official_nrt"
    SCIENTIFIC_MODEL     = "scientific_model"
    GLOBAL_MODEL         = "global_model"
    PROXY                = "proxy"
    HISTORICAL_FALLBACK  = "historical_fallback"


# ---------------------------------------------------------------------------
# Source Registry
# ---------------------------------------------------------------------------

SOURCE_REGISTRY: dict[str, dict] = {

    # ── Tier 1: Official Indian operational sources ─────────────────────────

    "incois_pfz_official": {
        "tier":         ProvenanceTier.OFFICIAL_OPERATIONAL,
        "domain":       "fisheries",
        "official":     True,
        "max_age_hours": 24,
        "description":  (
            "INCOIS official Potential Fishing Zone (PFZ) advisory. "
            "Operationally generated for Indian coastal sectors. "
            "Provides coordinates, depth, distance and direction."
        ),
    },

    "imd": {
        "tier":         ProvenanceTier.OFFICIAL_OPERATIONAL,
        "domain":       "hazard",
        "official":     True,
        "max_age_hours": 6,
        "description":  (
            "India Meteorological Department (IMD). "
            "Authoritative source for cyclone warnings, severe weather "
            "warnings, and official meteorological advisories for India."
        ),
    },

    # ── Tier 2: Official near-real-time scientific sources ──────────────────

    "incois_erddap": {
        "tier":         ProvenanceTier.OFFICIAL_NRT,
        "domain":       "ocean",
        "official":     True,
        "max_age_hours": 72,
        "description":  (
            "INCOIS ERDDAP — machine-readable access to INCOIS "
            "scientific datasets including Oceansat-2 chlorophyll, "
            "SST, and other oceanographic products."
        ),
    },

    "gdacs": {
        "tier":         ProvenanceTier.SCIENTIFIC_MODEL,
        "domain":       "hazard",
        "official":     False,
        "max_age_hours": 6,
        "description":  (
            "Global Disaster Alert and Coordination System (GDACS). "
            "UN-backed real-time global hazard alerts. "
            "Used for cyclone situational awareness only; "
            "does NOT override IMD warnings for India."
        ),
    },

    # ── Tier 3: Global forecast models ─────────────────────────────────────

    "open_meteo": {
        "tier":         ProvenanceTier.GLOBAL_MODEL,
        "domain":       "weather",
        "official":     False,
        "max_age_hours": 12,
        "description":  (
            "Open-Meteo — ERA5 reanalysis + ICON NWP marine and "
            "atmospheric forecast. Free, globally available. "
            "NOT an official Indian advisory."
        ),
    },

    "cmems": {
        "tier":         ProvenanceTier.SCIENTIFIC_MODEL,
        "domain":       "ocean",
        "official":     False,
        "max_age_hours": 24,
        "description":  (
            "Copernicus Marine Environment Monitoring Service (CMEMS). "
            "European operational ocean service providing wave, "
            "current, and SST forecasts. Optional secondary validation."
        ),
    },

    # ── Tier 4: Proxy / derived indicators ─────────────────────────────────

    "incois_chl_proxy": {
        "tier":         ProvenanceTier.PROXY,
        "domain":       "fisheries",
        "official":     False,
        "max_age_hours": 168,  # 7 days — satellite revisit cycle
        "description":  (
            "INCOIS Oceansat-2 chlorophyll-a grid (ERDDAP). "
            "High-CHL areas used as PFZ indicator. "
            "This is a scientific proxy — NOT an official PFZ advisory. "
            "Coverage ended ~2020; data is historical satellite product."
        ),
    },

    "open_meteo_wmo": {
        "tier":         ProvenanceTier.PROXY,
        "domain":       "hazard",
        "official":     False,
        "max_age_hours": 12,
        "description":  (
            "Open-Meteo WMO weather-code interpretation. "
            "Used as hazard proxy when official IMD advisory unavailable. "
            "NOT equivalent to official warning status."
        ),
    },

    # ── Tier 5: Historical fallback ─────────────────────────────────────────

    "fallback_static": {
        "tier":         ProvenanceTier.HISTORICAL_FALLBACK,
        "domain":       "all",
        "official":     False,
        "max_age_hours": 0,  # always considered stale
        "description":  (
            "Pre-cached static fallback data embedded in the application. "
            "Used only when all live sources fail. "
            "NOT real-time data."
        ),
    },
}


def get_source_meta(source_key: str) -> dict:
    """
    Return registry metadata for a source key.

    Falls back to a safe 'unknown' entry if the key is not registered,
    so callers never crash on missing registry entries.
    """
    return SOURCE_REGISTRY.get(source_key, {
        "tier":         ProvenanceTier.HISTORICAL_FALLBACK,
        "domain":       "unknown",
        "official":     False,
        "max_age_hours": 0,
        "description":  "Unknown source — treat as lowest provenance.",
    })


def tier_rank(tier: ProvenanceTier) -> int:
    """Return an integer rank for a tier (lower = more authoritative)."""
    _ORDER = [
        ProvenanceTier.OFFICIAL_OPERATIONAL,
        ProvenanceTier.OFFICIAL_NRT,
        ProvenanceTier.SCIENTIFIC_MODEL,
        ProvenanceTier.GLOBAL_MODEL,
        ProvenanceTier.PROXY,
        ProvenanceTier.HISTORICAL_FALLBACK,
    ]
    try:
        return _ORDER.index(tier)
    except ValueError:
        return len(_ORDER)
