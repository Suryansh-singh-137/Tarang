"""
location.models
----------------
Data models and TypedDicts for Tarang V2 Location-Aware Architecture.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict

PermissionStatus = Literal["granted", "denied", "unavailable", "not_requested"]
LocationMode = Literal["DEVICE", "EXPLICIT_PLACE", "EXPLICIT_COORDINATES", "INHERITED", "NONE"]
ExecutionStatus = Literal["success", "partial", "failed", "skipped"]
DataStatus = Literal["live", "cached", "mixed", "unavailable"]


class DeviceLocation(TypedDict):
    lat: float
    lon: float
    accuracy: Optional[float]
    captured_at: Optional[str]
    permission_status: PermissionStatus


class QueryLocation(TypedDict):
    name: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    source: Literal["explicit_place", "explicit_coordinates", "relative_device", "inherited", "none"]


class ResolvedLocation(TypedDict):
    lat: float
    lon: float
    name: str
    source: Literal["device", "explicit_text", "coordinates", "previous_query"]
    confidence: float
    coastal: bool
    nearest_coast_km: Optional[float]
    state: Optional[str]
    district: Optional[str]


class MarineContext(TypedDict):
    type: Literal["inland", "coastal", "offshore", "unknown"]
    is_coastal: bool
    nearest_port: Optional[str]
    distance_to_coast_km: Optional[float]
    tide_available: bool
    fishing_data_available: bool


class SelectedLocation(TypedDict):
    name: str
    display_name: str
    lat: float
    lon: float
    country: Optional[str]
    state: Optional[str]
    source: Literal["search", "gps", "map", "conversation"]
    marine_context: MarineContext


class LocationSearchResult(TypedDict):
    name: str
    display_name: str
    lat: float
    lon: float
    state: Optional[str]
    country: Optional[str]

