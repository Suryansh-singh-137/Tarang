"""
applicability.py
----------------
Deterministic applicability layer for Tarang capabilities (PRD §4–§9).
Distinguishes between:
- Coastal locations (all marine capabilities applicable)
- Inland locations (weather is applicable; PFZ, Ocean/Tides, Marine Trip Risk are NOT applicable)
- Explicit query override (uses resolved_location, not device_location)
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from location.models import ResolvedLocation


class ApplicabilityResult:
    def __init__(
        self,
        weather: bool = True,
        pfz: bool = True,
        ocean: bool = True,
        geofence: bool = True,
        risk: bool = True,
        reason: Optional[str] = None,
        distance_to_coast_km: Optional[float] = None,
    ):
        self.weather = weather
        self.pfz = pfz
        self.ocean = ocean
        self.geofence = geofence
        self.risk = risk
        self.reason = reason
        self.distance_to_coast_km = distance_to_coast_km

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weather": self.weather,
            "pfz": self.pfz,
            "ocean": self.ocean,
            "geofence": self.geofence,
            "risk": self.risk,
            "reason": self.reason,
            "distance_to_coast_km": self.distance_to_coast_km,
        }


def check_applicability(
    resolved: Optional[ResolvedLocation | dict],
    raw_query: str = "",
    explicit_boundary_query: bool = False,
) -> ApplicabilityResult:
    """
    Deterministically computes capability applicability based on resolved location.
    
    Rules (PRD §5–§9):
    1. If resolved location is coastal:
       All requested marine capabilities are applicable.
    2. If resolved location is inland (coastal == False):
       - Weather remains APPLICABLE (PRD §8)
       - PFZ is NOT APPLICABLE (reason: INLAND_LOCATION)
       - Ocean/Tides is NOT APPLICABLE (reason: INLAND_LOCATION)
       - Geofence is NOT APPLICABLE unless explicitly asked about a maritime boundary
       - Marine trip risk is NOT APPLICABLE for inland location
    """
    if not resolved:
        return ApplicabilityResult(
            weather=False,
            pfz=False,
            ocean=False,
            geofence=False,
            risk=False,
            reason="UNRESOLVED_LOCATION",
        )
    
    is_coastal = resolved.get("coastal", False) if isinstance(resolved, dict) else getattr(resolved, "coastal", False)
    dist_coast = resolved.get("nearest_coast_km") if isinstance(resolved, dict) else getattr(resolved, "nearest_coast_km", None)

    if is_coastal:
        return ApplicabilityResult(
            weather=True,
            pfz=True,
            ocean=True,
            geofence=True,
            risk=True,
            reason=None,
            distance_to_coast_km=dist_coast or 0.0,
        )

    # Inland location handling
    return ApplicabilityResult(
        weather=True,  # Weather always available inland!
        pfz=False,     # Fishing zones not applicable inland
        ocean=False,   # Ocean tides not applicable inland
        geofence=explicit_boundary_query,
        risk=False,    # Marine trip assessment cannot be completed inland
        reason="INLAND_LOCATION",
        distance_to_coast_km=dist_coast,
    )
