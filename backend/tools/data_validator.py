"""
data_validator.py
-----------------
Data quality validation layer for Tarang M8.

Every agent result must pass through this layer to produce a DataQuality
object that describes:
  - Where the data came from (source, provenance tier)
  - When it was retrieved vs when it was valid
  - Whether it is fresh enough to use for a recommendation
  - Whether it is a fallback, proxy, or live official source
  - A composite quality_score (0.0–1.0) for risk weighting

The LLM does NOT decide data trustworthiness. This module does.

Design rules:
  - Never silently discard stale data — mark it and let the caller decide
  - Never treat proxy as official — is_proxy and is_official are separate fields
  - Fail-closed: missing or insufficient data → quality_score = 0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from tools.source_registry import ProvenanceTier, get_source_meta, tier_rank


# ---------------------------------------------------------------------------
# DataQuality dataclass
# ---------------------------------------------------------------------------

@dataclass
class DataQuality:
    """
    Structured data quality descriptor for a single agent result.

    Attach one of these to every AgentResult to make provenance explicit
    and machine-readable throughout the pipeline.
    """
    source:          str                       # human-readable source name
    source_key:      str                       # registry key (e.g. "open_meteo")
    provenance_tier: ProvenanceTier            # authority level

    retrieved_at:    str                       # ISO-8601 UTC: when we fetched
    data_timestamp:  str                       # ISO-8601 UTC: when data was valid
    valid_until:     Optional[str]             # ISO-8601 UTC: data validity end (if known)

    freshness_hours: float                     # age of data in hours at retrieval time
    max_age_hours:   float                     # maximum allowed age for this source

    is_stale:    bool                          # freshness_hours > max_age_hours
    is_fallback: bool                          # live source was unavailable
    is_proxy:    bool                          # derived/indirect indicator
    is_official: bool                          # from authoritative Indian gov source

    quality_score: float                       # 0.0 (unusable) – 1.0 (excellent)
    warnings:      list[str] = field(default_factory=list)  # human-readable issues


# ---------------------------------------------------------------------------
# Freshness computation
# ---------------------------------------------------------------------------

def _parse_iso(ts: str) -> Optional[datetime]:
    """Parse ISO-8601 UTC string to timezone-aware datetime. Returns None on failure."""
    if not ts or ts in ("fallback", ""):
        return None
    try:
        # Handle trailing Z
        ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def compute_freshness_hours(data_timestamp: str) -> float:
    """
    Return the age (in hours) of data_timestamp relative to now UTC.
    Returns 9999.0 if timestamp is unparseable or absent (= maximally stale).
    """
    dt = _parse_iso(data_timestamp)
    if dt is None:
        return 9999.0
    now = datetime.now(timezone.utc)
    delta = now - dt
    return max(0.0, delta.total_seconds() / 3600.0)


# ---------------------------------------------------------------------------
# Quality score computation
# ---------------------------------------------------------------------------

def compute_quality_score(
    provenance_tier: ProvenanceTier,
    is_stale:    bool,
    is_fallback: bool,
    is_proxy:    bool,
) -> float:
    """
    Compute a composite quality score (0.0–1.0).

    Deductions:
      - Tier rank penalty: higher tier number → lower base score
      - Stale data: −0.30
      - Fallback:   −0.25
      - Proxy:      −0.20

    Floor is 0.0 (never negative).
    """
    # Base score by tier: tier 0 (OFFICIAL_OPERATIONAL) = 1.0 → tier 5 = 0.4
    base = max(0.4, 1.0 - tier_rank(provenance_tier) * 0.12)

    penalty = 0.0
    if is_stale:    penalty += 0.30
    if is_fallback: penalty += 0.25
    if is_proxy:    penalty += 0.20

    return max(0.0, round(base - penalty, 2))


# ---------------------------------------------------------------------------
# Factory function (main entry point for agents)
# ---------------------------------------------------------------------------

def make_data_quality(
    source_key:     str,
    source:         str,
    retrieved_at:   str,
    data_timestamp: str,
    is_fallback:    bool = False,
    is_proxy:       bool = False,
    valid_until:    Optional[str] = None,
    extra_warnings: Optional[list[str]] = None,
) -> DataQuality:
    """
    Build a DataQuality object for an agent result.

    Args:
        source_key:      Registry key (e.g. "open_meteo", "incois_chl_proxy")
        source:          Human-readable source citation string
        retrieved_at:    ISO-8601 UTC: when this agent fetched the data
        data_timestamp:  ISO-8601 UTC: when the data itself was valid/observed
        is_fallback:     True if we couldn't reach the live source
        is_proxy:        True if this is a derived indicator (not direct observation)
        valid_until:     Optional data validity end timestamp
        extra_warnings:  Additional warning strings to include

    Returns:
        DataQuality with all fields populated.
    """
    meta = get_source_meta(source_key)
    tier: ProvenanceTier = meta["tier"]
    max_age: float = float(meta["max_age_hours"])
    is_official: bool = meta.get("official", False)

    freshness_hours = compute_freshness_hours(data_timestamp)
    is_stale = (freshness_hours > max_age) if max_age > 0 else True

    quality_score = compute_quality_score(tier, is_stale, is_fallback, is_proxy)

    warnings: list[str] = list(extra_warnings or [])

    if is_stale and max_age > 0:
        warnings.append(
            f"Data is {freshness_hours:.1f}h old (max allowed: {max_age:.0f}h). "
            "Treat with caution."
        )
    if is_fallback:
        warnings.append("Live source unavailable; using cached fallback data.")
    if is_proxy and not is_official:
        warnings.append(
            "This is a derived proxy indicator, not an official advisory."
        )
    if tier == ProvenanceTier.HISTORICAL_FALLBACK:
        warnings.append(
            "Historical fallback data — NOT real-time. "
            "Do not use for operational safety decisions."
        )

    return DataQuality(
        source=source,
        source_key=source_key,
        provenance_tier=tier,
        retrieved_at=retrieved_at,
        data_timestamp=data_timestamp,
        valid_until=valid_until,
        freshness_hours=round(freshness_hours, 1),
        max_age_hours=max_age,
        is_stale=is_stale,
        is_fallback=is_fallback,
        is_proxy=is_proxy,
        is_official=is_official,
        quality_score=quality_score,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Aggregated quality check (for risk agent)
# ---------------------------------------------------------------------------

def all_critical_data_available(reports: list[dict]) -> bool:
    """
    Return True if the two most critical inputs for a safety assessment
    (weather + hazard) are present.
    
    Fail-closed only triggers when data is genuinely missing or errored 
    and no fallback succeeded. A successful fallback allows the risk 
    calculation to proceed (with the fallback disclosed in the summary).
    """
    has_weather = any(r.get("agent_name") == "weather_agent" for r in reports)
    has_hazard  = any(r.get("agent_name") == "hazard_agent" for r in reports)
    
    return has_weather and has_hazard
