"""
hazard_client.py
----------------
Milestone 2 stub: IMD / INCOIS advisory retrieval with fallback.

In Milestone 2, implement:
  - fetch_imd_advisory(lat, lon, time_window) → dict | None
    Calls IMD JSON/XML endpoint with ≤5s timeout; returns None on failure.
  - fetch_incois_advisory(lat, lon) → dict | None
    Calls INCOIS Ocean State Forecast endpoint; returns None on failure.

The hazard_agent node will call these functions and fall back to the
pre-cached snapshot in data/fallback_hazards.json if they return None.
"""

from __future__ import annotations


def fetch_imd_advisory(lat: float, lon: float, time_window: str) -> dict | None:
    """
    Milestone 2: implement live IMD advisory retrieval.
    Must complete within 5 seconds or return None.
    """
    raise NotImplementedError("Implement in Milestone 2")


def fetch_incois_advisory(lat: float, lon: float) -> dict | None:
    """
    Milestone 2: implement live INCOIS Ocean State Forecast retrieval.
    Must complete within 5 seconds or return None.
    """
    raise NotImplementedError("Implement in Milestone 2")
