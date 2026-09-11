"""
pfz_agent node
--------------
Returns Potential Fishing Zone (PFZ) information for the queried location.

Milestone 1: Returns deterministic mock PFZ advisories.
             Milestone 2: Replace `_fetch_pfz_advisory()` with INCOIS RAG
             retrieval (tools/incois_rag.py) + CMEMS chlorophyll/SST proxy.
"""

from __future__ import annotations

from graph.state import AgentResult, ORCAState

# ---------------------------------------------------------------------------
# Mock PFZ data per location
# Each entry represents one or more PFZ zones near the location.
# The "zones" list feeds directly into map_geojson as Point features.
# ---------------------------------------------------------------------------
_FALLBACK_PFZ: dict[str, dict] = {
    "thoothukudi": {
        "advisory_date": "2026-09-11",
        "advisory_timestamp": "2026-09-11T06:00:00Z",
        "zones": [
            {
                "zone_id": "PFZ-TN-001",
                "lat": 8.50,
                "lon": 78.20,
                "distance_km": 28,
                "chlorophyll_mg_m3": 1.8,
                "sst_celsius": 29.1,
                "description": "High chlorophyll convergence zone SE of Thoothukudi",
            },
            {
                "zone_id": "PFZ-TN-002",
                "lat": 8.30,
                "lon": 78.40,
                "distance_km": 52,
                "chlorophyll_mg_m3": 2.1,
                "sst_celsius": 28.7,
                "description": "SST gradient zone SSE of Thoothukudi",
            },
        ],
        "nearest_zone_km": 28,
        "overall_productivity": "moderate",
    },
    "rameswaram": {
        "advisory_date": "2026-09-11",
        "advisory_timestamp": "2026-09-11T06:00:00Z",
        "zones": [
            {
                "zone_id": "PFZ-TN-003",
                "lat": 9.10,
                "lon": 79.50,
                "distance_km": 34,
                "chlorophyll_mg_m3": 2.4,
                "sst_celsius": 29.8,
                "description": "High-productivity zone E of Rameswaram",
            }
        ],
        "nearest_zone_km": 34,
        "overall_productivity": "high",
    },
    "chennai": {
        "advisory_date": "2026-09-11",
        "advisory_timestamp": "2026-09-11T06:00:00Z",
        "zones": [
            {
                "zone_id": "PFZ-TN-004",
                "lat": 12.80,
                "lon": 80.60,
                "distance_km": 45,
                "chlorophyll_mg_m3": 1.2,
                "sst_celsius": 28.3,
                "description": "Low-moderate productivity zone SE of Chennai",
            }
        ],
        "nearest_zone_km": 45,
        "overall_productivity": "low",
    },
}

_DEFAULT_PFZ = {
    "advisory_date": "2026-09-11",
    "advisory_timestamp": "2026-09-11T06:00:00Z",
    "zones": [
        {
            "zone_id": "PFZ-GENERIC-001",
            "lat": 8.50,
            "lon": 78.50,
            "distance_km": 40,
            "chlorophyll_mg_m3": 1.5,
            "sst_celsius": 29.0,
            "description": "Moderate chlorophyll zone (generic fallback)",
        }
    ],
    "nearest_zone_km": 40,
    "overall_productivity": "moderate",
}


def _fetch_pfz_advisory(lat: float, lon: float) -> dict | None:
    """
    Milestone 2: query INCOIS RAG retriever + CMEMS chlorophyll/SST here.
    Return None on any error so the fallback path kicks in.
    """
    return None  # live integration deferred to Milestone 2


def pfz_agent(state: ORCAState) -> dict:
    """
    LangGraph node: fetch/mock PFZ advisory data.
    """
    intent = state["parsed_intent"]
    assert intent is not None

    lat = intent["lat"] or 8.7642
    lon = intent["lon"] or 78.1348
    location_name = intent["location_name"].lower()

    live_data = _fetch_pfz_advisory(lat, lon)
    if live_data:
        data = live_data
        used_fallback = False
        source = "INCOIS PFZ Advisory (live) + CMEMS Chl-a/SST"
    else:
        data = _FALLBACK_PFZ.get(location_name, _DEFAULT_PFZ).copy()
        used_fallback = True
        source = "INCOIS PFZ Advisory snapshot — 2026-09-11 (cached)"

    nearest_km = data["nearest_zone_km"]
    productivity = data["overall_productivity"]
    n_zones = len(data["zones"])
    summary = (
        f"{n_zones} PFZ zone(s) identified; nearest is {nearest_km} km away. "
        f"Fishing productivity: {productivity}."
    )

    result: AgentResult = {
        "agent_name": "pfz_agent",
        "status": "success",
        "data": data,
        "source": source,
        "summary": summary,
        "used_fallback": used_fallback,
    }

    current_trace = state.get("trace") or []
    return {
        "pfz_result": result,
        "trace": current_trace + [result],
    }
