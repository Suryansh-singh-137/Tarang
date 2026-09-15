"""
sst_agent node
--------------
Retrieves Sea Surface Temperature (SST) and SST anomaly from the
INCOIS ERDDAP SST dataset (NOAA AVHRR/AMSR high-resolution daily SST).

Invariants:
- Uses latitude, longitude, and latest available date.
- No API key required.
- Returns exact SST value, SST anomaly, observation time, source, and data status.
- Fail-closed: Never uses mock data if the live source is unreachable.
- Never claims that SST guarantees fish presence; always includes the disclaimer.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from graph.state import AgentResult, EvidenceItem, ORCAState
from tools.sst_client import fetch_sst_and_anomaly, SST_DISCLAIMER

logger = logging.getLogger("tarang.agent.sst")


def sst_agent(state: ORCAState) -> dict:
    """
    SST specialist agent node.
    Extracts canonical coordinates and queries INCOIS ERDDAP SST dataset.
    """
    resolved = state.get("resolved_location") or {}
    intent = state.get("parsed_intent") or {}

    loc_name = resolved.get("name") or intent.get("location_name") or "coastal waters"
    lat = resolved.get("lat") if resolved.get("lat") is not None else intent.get("lat")
    lon = resolved.get("lon") if resolved.get("lon") is not None else intent.get("lon")

    now_iso = datetime.now(timezone.utc).isoformat()
    current_trace = list(state.get("trace") or [])
    current_evidence = list(state.get("evidence") or [])

    # If coordinates are missing or location is inland
    is_inland = bool(resolved and not resolved.get("coastal", True))
    if lat is None or lon is None or is_inland:
        reason = "INLAND_LOCATION" if is_inland else "UNRESOLVED_LOCATION"
        skip_res: AgentResult = {
            "agent_name": "sst_agent",
            "status": "skipped",
            "execution_status": "skipped",
            "skip_reason": reason,
            "data_status": "not_applicable" if is_inland else "unavailable",
            "location_used": {"lat": lat or 0.0, "lon": lon or 0.0} if (lat and lon) else None,
            "observed_at": None,
            "data": {
                "sst_celsius": None,
                "sst_anomaly_c": None,
                "observation_time": None,
                "disclaimer": SST_DISCLAIMER,
            },
            "source": "INCOIS ERDDAP",
            "disclaimer": SST_DISCLAIMER,
            "summary": f"SST is not applicable for inland location {loc_name}." if is_inland else "Location not resolved for SST check.",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "",
            "error": None,
            "evidence": [],
        }
        return {
            "sst_result": skip_res,
            "trace": current_trace + [skip_res],
        }

    # Fetch live data from INCOIS ERDDAP
    logger.info("[SSTAgent] Querying INCOIS ERDDAP SST for %s (%.4f, %.4f)", loc_name, lat, lon)
    res = fetch_sst_and_anomaly(lat, lon)

    location_used = {"lat": float(lat), "lon": float(lon)}

    if res.get("success") and res.get("sst_celsius") is not None:
        sst_val = res["sst_celsius"]
        anom_val = res.get("sst_anomaly_c")
        obs_time = res.get("observation_time") or now_iso

        evidence_items: list[EvidenceItem] = [
            {
                "claim": f"Sea surface temperature (SST) at {loc_name} is {sst_val}°C",
                "value": sst_val,
                "unit": "°C",
                "source": res["source"],
                "source_time": obs_time,
                "retrieved_at": now_iso,
                "location": location_used,
                "provenance_tier": "official_operational",
                "data_type": "observation",
                "timestamp": obs_time,
            }
        ]

        if anom_val is not None:
            evidence_items.append({
                "claim": f"SST thermal anomaly at {loc_name} is {anom_val:+.2f}°C relative to baseline",
                "value": anom_val,
                "unit": "°C",
                "source": res["source"],
                "source_time": obs_time,
                "retrieved_at": now_iso,
                "location": location_used,
                "provenance_tier": "official_operational",
                "data_type": "observation",
                "timestamp": obs_time,
            })

        anom_str = f" (anomaly: {anom_val:+.1f}°C)" if anom_val is not None else ""
        summary = (
            f"Sea surface temperature at {loc_name} is {sst_val:.1f}°C{anom_str}. "
            f"{SST_DISCLAIMER}"
        )

        agent_result: AgentResult = {
            "agent_name": "sst_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": res.get("data_status", "live"),
            "location_used": location_used,
            "observed_at": obs_time,
            "data": {
                "sst_celsius": sst_val,
                "sst_anomaly_c": anom_val,
                "observation_time": obs_time,
                "unit": "°C",
                "source": res["source"],
                "disclaimer": SST_DISCLAIMER,
            },
            "source": res["source"],
            "disclaimer": SST_DISCLAIMER,
            "summary": summary,
            "used_fallback": False,
            "data_quality": res.get("data_quality", "live"),
            "timestamp": now_iso,
            "error": None,
            "evidence": evidence_items,
        }

        return {
            "sst_result": agent_result,
            "trace": current_trace + [agent_result],
            "evidence": current_evidence + evidence_items,
        }

    else:
        # Live fetch failed or returned no data — FAIL CLOSED, NO MOCK DATA!
        logger.warning("[SSTAgent] Live SST fetch failed for %s (%.4f, %.4f). Failing closed with unavailable.", loc_name, lat, lon)
        err_msg = res.get("error") or "LIVE_SST_DATA_UNAVAILABLE"

        agent_result: AgentResult = {
            "agent_name": "sst_agent",
            "status": "error",
            "execution_status": "failed",
            "data_status": "unavailable",
            "location_used": location_used,
            "observed_at": None,
            "data": {
                "sst_celsius": None,
                "sst_anomaly_c": None,
                "observation_time": None,
                "unit": "°C",
                "source": res.get("source", "INCOIS ERDDAP (NOAA AVHRR/AMSR SST)"),
                "disclaimer": SST_DISCLAIMER,
            },
            "source": res.get("source", "INCOIS ERDDAP (NOAA AVHRR/AMSR SST)"),
            "disclaimer": SST_DISCLAIMER,
            "summary": f"Live sea surface temperature (SST) data is currently unavailable from INCOIS ERDDAP for {loc_name}. {SST_DISCLAIMER}",
            "used_fallback": False,
            "data_quality": "unavailable",
            "timestamp": now_iso,
            "error": err_msg,
            "evidence": [],
        }

        return {
            "sst_result": agent_result,
            "trace": current_trace + [agent_result],
        }
