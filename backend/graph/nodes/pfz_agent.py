"""
pfz_agent node
--------------
Returns Potential Fishing Zone (PFZ) information for the queried location.

Milestone 2: Calls tools/incois_client.py (INCOIS ERDDAP Oceansat-2 CHL data)
             with fallback to data/fallback_pfz.json.
Milestone 3: Emits data_quality = "historical_proxy" always — INCOIS Oceansat-2
             data is real satellite data but historical, not a live real-time advisory.

Milestone 8 (M8):
  Source priority:
    1. Official INCOIS PFZ advisory (fetch_official_pfz_advisory) — Tier 1
       Currently returns None (no stable machine-readable endpoint found).
    2. INCOIS ERDDAP Oceansat-2 CHL proxy — Tier 4 (PROXY)
    3. Fallback static JSON — Tier 5

  SAFETY RULE: Historical CHL data → NEVER "PFZ found today".
  is_official_pfz is always False unless Tier 1 succeeds.
  is_proxy is always True for CHL data.

GeoJSON coordinate order: [longitude, latitude] (RFC 7946).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from graph.state import AgentResult, DataQualityReport, EvidenceItem, ORCAState
from tools.data_validator import make_data_quality
from tools.incois_client import PFZResult, fetch_official_pfz_advisory, fetch_pfz_zones

logger = logging.getLogger("tarang.pfz")

# ---------------------------------------------------------------------------
# Fallback data
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_FALLBACK_FILE = _DATA_DIR / "fallback_pfz.json"

_DEFAULT_FALLBACK = {
    "advisory_date": "2026-09-11",
    "source_time": "2020-05-01T00:00:00Z",
    "zones": [
        {
            "zone_id": "PFZ-FALLBACK-001",
            "lat": 8.50,
            "lon": 78.20,
            "distance_km": 28,
            "chlorophyll_mg_m3": 0.85,
            "advisory_date": "2026-09-11",
            "source": "fallback_pfz.json",
            "description": "Moderate chlorophyll zone SE of Thoothukudi (fallback)",
        },
    ],
    "nearest_zone_km": 28,
    "zone_count": 1,
    "avg_chl": 0.85,
    "overall_productivity": "moderate",
}


def _load_fallback(location_name: str) -> dict:
    """Load PFZ fallback for a location."""
    try:
        if _FALLBACK_FILE.exists():
            raw = json.loads(_FALLBACK_FILE.read_text(encoding="utf-8"))
            locations = raw.get("locations", {})
            entry = locations.get(location_name.lower())
            if entry:
                return entry
            return raw.get("default", _DEFAULT_FALLBACK)
    except Exception as exc:
        logger.warning("[PFZ] Failed to load fallback file: %s", exc)
    return _DEFAULT_FALLBACK.copy()


# ---------------------------------------------------------------------------
# Evidence builder
# ---------------------------------------------------------------------------

def _build_evidence(
    zones: list[dict], source: str, source_time: str, retrieved_at: str,
    query_lat: float, query_lon: float,
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    if not zones:
        return evidence

    nearest_km = min(z["distance_km"] for z in zones)
    evidence.append(EvidenceItem(
        claim=f"Nearest PFZ indicator zone is approximately {nearest_km:.0f} km from query point",
        value=nearest_km,
        unit="km",
        source=source,
        source_time=source_time,
        retrieved_at=retrieved_at,
        location={"lat": query_lat, "lon": query_lon},
    ))

    for z in zones[:2]:  # top 2 zones as individual evidence items
        evidence.append(EvidenceItem(
            claim=(
                f"PFZ zone at ({z['lat']:.2f}°N, {z['lon']:.2f}°E): "
                f"chlorophyll={z.get('chlorophyll_mg_m3', '?')} mg/m³, "
                f"distance={z['distance_km']:.0f} km"
            ),
            value=z.get("chlorophyll_mg_m3"),
            unit="mg/m³",
            source=source,
            source_time=source_time,
            retrieved_at=retrieved_at,
            location={"lat": z["lat"], "lon": z["lon"]},
        ))

    return evidence


# ---------------------------------------------------------------------------
# GeoJSON feature builder (coordinate order: [lon, lat] per RFC 7946)
# ---------------------------------------------------------------------------

def _build_pfz_geojson_features(zones: list[dict], source: str) -> list[dict]:
    features = []
    for zone in zones:
        # Explicit [longitude, latitude] — GeoJSON spec
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [zone["lon"], zone["lat"]],   # [lon, lat]
            },
            "properties": {
                "feature_type": "pfz_zone",
                "zone_id": zone.get("zone_id", "PFZ"),
                "description": zone.get("description", ""),
                "distance_km": zone["distance_km"],
                "chlorophyll_mg_m3": zone.get("chlorophyll_mg_m3"),
                "advisory_date": zone.get("advisory_date", ""),
                "source": source,
            },
        })
    return features


# ---------------------------------------------------------------------------
# Public node function
# ---------------------------------------------------------------------------

def pfz_agent(state: ORCAState) -> dict:
    """
    LangGraph node: fetch PFZ data via INCOIS ERDDAP chlorophyll proxy.

    Priority:
      1. INCOIS ERDDAP Oceansat-2 CHL (via incois_client)
      2. fallback_pfz.json (clearly disclosed)
    """
    intent = state["parsed_intent"]
    assert intent is not None

    lat = intent["lat"] or 8.7642
    lon = intent["lon"] or 78.1348
    location_name = intent["location_name"]

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    logger.info("[PFZ] Fetching zones for %s (%.4f, %.4f)", location_name, lat, lon)

    # ---- Tier 1: Official INCOIS PFZ advisory probe ----
    official: Optional[PFZResult] = None
    try:
        official = fetch_official_pfz_advisory(lat, lon)
    except Exception as exc:
        logger.warning("[PFZ] Official advisory probe raised exception: %s", exc)

    # ---- Tier 2: ERDDAP CHL proxy ----
    live: Optional[PFZResult] = None
    if official is None:
        try:
            live = fetch_pfz_zones(lat, lon)
        except Exception as exc:
            logger.warning("[PFZ] Live ERDDAP fetch raised exception: %s", exc)

    # Determine which result to use
    if official is not None and official.zones:
        active = official
        is_official_pfz = True
        is_proxy = False
        source_key = "incois_pfz_official"
        source_type = "official_operational"
        data_quality_label = "live"
    elif live is not None and live.zones:
        active = live
        is_official_pfz = False
        is_proxy = True
        source_key = "incois_chl_proxy"
        source_type = "ocean_color_proxy"
        data_quality_label = "historical_proxy"
    else:
        active = None
        is_official_pfz = False
        is_proxy = True
        source_key = "fallback_static"
        source_type = "historical_fallback"
        data_quality_label = "fallback"

    if active is not None and active.zones:
        data = {
            "zones": active.zones,
            "nearest_zone_km": active.nearest_zone_km,
            "zone_count": active.zone_count,
            "avg_chl": active.avg_chl,
            "source_time": active.source_time,
            "retrieved_at": active.retrieved_at,
            "advisory_date": active.source_time[:10] if active.source_time else "",
            "overall_productivity": (
                "high" if active.avg_chl >= 0.9
                else "moderate" if active.avg_chl >= 0.5
                else "low"
            ),
            "pfz_method": "official_advisory" if is_official_pfz else "chlorophyll_proxy",
            # M8 provenance fields
            "is_official_pfz": is_official_pfz,
            "is_proxy": is_proxy,
            "source_type": source_type,
        }
        used_fallback = False
        source = active.source
        source_time = active.source_time
        logger.info(
            "[PFZ] %s: %d zones, nearest=%.1fkm (official=%s proxy=%s)",
            source_type, active.zone_count, active.nearest_zone_km,
            is_official_pfz, is_proxy,
        )
        data = {
            "zones": live.zones,
            "nearest_zone_km": live.nearest_zone_km,
            "zone_count": live.zone_count,
            "avg_chl": live.avg_chl,
            "source_time": live.source_time,
            "retrieved_at": live.retrieved_at,
            "advisory_date": live.source_time[:10] if live.source_time else "",
            "overall_productivity": (
                "high" if live.avg_chl >= 0.9
                else "moderate" if live.avg_chl >= 0.5
                else "low"
            ),
            "pfz_method": "chlorophyll_proxy",
        }
        used_fallback = False
        source = live.source
        source_time = live.source_time
        logger.info(
            "[PFZ] Live: %d zones, nearest=%.1fkm, avg_chl=%.3f mg/m³",
            live.zone_count, live.nearest_zone_km, live.avg_chl,
        )
    else:
        data = _load_fallback(location_name)
        data["pfz_method"] = "fallback"
        data["is_official_pfz"] = False
        data["is_proxy"] = True
        data["source_type"] = "historical_fallback"
        used_fallback = True
        source = "fallback_pfz.json (live INCOIS ERDDAP unavailable)"
        source_time = data.get("source_time", "fallback")
        logger.warning("[PFZ] Falling back to cached dataset for %s", location_name)

    nearest_km = data.get("nearest_zone_km", 40)
    n_zones = len(data.get("zones", []))
    productivity = data.get("overall_productivity", "unknown")

    # M8: Build summary with correct provenance disclosure
    is_official_pfz_flag = data.get("is_official_pfz", False)
    is_proxy_flag = data.get("is_proxy", True)
    summary = (
        f"{n_zones} PFZ indicator zone(s) identified; "
        f"nearest is {nearest_km:.0f} km away. "
        f"Fishing productivity indicator: {productivity}."
    )
    if is_official_pfz_flag:
        summary += " [Source: INCOIS official PFZ advisory]"
    elif is_proxy_flag and not used_fallback:
        summary += " [⚠️ Scientific proxy (INCOIS Oceansat-2 CHL) — NOT an official PFZ advisory. Historical data.]"
    if used_fallback:
        summary += " [⚠️ Using cached fallback — live INCOIS ERDDAP unavailable]"

    evidence = _build_evidence(
        data.get("zones", []), source, source_time, retrieved_at, lat, lon
    )

    # M8: Build DataQualityReport
    dq = make_data_quality(
        source_key=source_key,
        source=source,
        retrieved_at=retrieved_at,
        data_timestamp=source_time,
        is_fallback=used_fallback,
        is_proxy=is_proxy_flag,
    )
    dq_report: DataQualityReport = {
        "agent_name":      "pfz_agent",
        "source_key":      dq.source_key,
        "source":          dq.source,
        "provenance_tier": dq.provenance_tier.value,
        "is_official":     dq.is_official,
        "is_proxy":        dq.is_proxy,
        "is_fallback":     dq.is_fallback,
        "is_stale":        dq.is_stale,
        "freshness_hours": dq.freshness_hours,
        "quality_score":   dq.quality_score,
        "warnings":        dq.warnings,
    }

    result: AgentResult = {
        "agent_name": "pfz_agent",
        "status": "success",
        "data": data,
        "source": source,
        "summary": summary,
        "used_fallback": used_fallback,
        # Always historical_proxy unless official Tier 1 succeeded
        "data_quality": "live" if is_official_pfz_flag else ("fallback" if used_fallback else "historical_proxy"),
        "timestamp": retrieved_at,
        "error": None,
        "evidence": evidence,
    }

    current_trace = state.get("trace") or []
    current_evidence = state.get("evidence") or []
    current_dq_reports = state.get("data_quality_reports") or []
    return {
        "pfz_result": result,
        "trace": current_trace + [result],
        "evidence": current_evidence + evidence,
        "data_quality_reports": current_dq_reports + [dq_report],
    }
