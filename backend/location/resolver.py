"""
location.resolver
-----------------
V2 Location Resolver for Tarang Marine Intelligence Platform.

Enforces strict resolution hierarchy:
1. Hard Override: Relative keywords ("here", "near me", "mere yaha", "enga", etc.)
   strictly resolve to device_location. If device_location is missing, returns
   unresolved prompt state; NEVER falls back to prior query location.
2. Explicit Coordinates: Numeric lat/lon pairs in the query string.
3. Explicit Place: Coastal gazetteer hit or Nominatim geocoder match.
4. Contextual Continuation: Inherits session.last_query_location only when query
   is a continuation without a new location or relative override.
5. Controlled Clarification: If unresolved, returns clean prompt state without
   defaulting silently to any hardcoded town.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple, TYPE_CHECKING

from location.models import (
    DeviceLocation,
    QueryLocation,
    ResolvedLocation,
    LocationMode,
)

if TYPE_CHECKING:
    from session.session_store import SessionRecord
from tools.location_resolver import (
    resolve_location as tool_resolve_location,
    location_is_coastal,
    distance_to_nearest_coast_km,
    GAZETTEER,
)

logger = logging.getLogger("tarang.location.resolver")

# Relative device keywords across English, Hindi, and Tamil
_RELATIVE_KEYWORDS_RE = re.compile(
    r"\b(here|near\s+me|my\s+location|current\s+location|around\s+me|"
    r"mere\s+yaha[an]?|mere\s+paas|yaha[an]|idhar|apne\s+yaha[an]|hama?are\s+yaha[an]|"
    r"inga|ingey|enga|engalukku|ingu|inge|namma\s+idathula)\b",
    re.IGNORECASE,
)

# Coordinate pattern: e.g., "9.93, 76.26" or "lat: 9.93, lon: 76.26"
_COORDINATE_RE = re.compile(
    r"(?:(?:lat|latitude)[:\s]*)?([+-]?\d{1,2}\.\d+)[,\s]+(?:(?:lon|long|longitude)[:\s]*)?([+-]?\d{1,3}\.\d+)",
    re.IGNORECASE,
)


class LocationResolver:
    """Unified location resolver enforcing single-source-of-truth semantics."""

    @staticmethod
    def is_relative_query(query: str) -> bool:
        """Check if user explicitly refers to their physical / current position."""
        return bool(_RELATIVE_KEYWORDS_RE.search(query))

    @staticmethod
    def extract_coordinates(query: str) -> Optional[Tuple[float, float]]:
        """Extract numeric lat/lon from query if present."""
        match = _COORDINATE_RE.search(query)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                # Sanity range for India / surrounding waters
                if 0.0 <= lat <= 38.0 and 60.0 <= lon <= 100.0:
                    return lat, lon
            except (ValueError, TypeError):
                pass
        return None

    @classmethod
    def resolve(
        cls,
        query: str,
        device_location: Optional[DeviceLocation] = None,
        session: Optional[SessionRecord] = None,
    ) -> Tuple[LocationMode, QueryLocation, Optional[ResolvedLocation]]:
        """
        Resolve location for the current turn.

        Returns:
            (location_mode, query_location, resolved_location)
        """
        raw_query = (query or "").strip()
        has_relative = cls.is_relative_query(raw_query)

        # ----------------------------------------------------------------------
        # Priority 1: Relative "here" / "near me" Hard Override
        # ----------------------------------------------------------------------
        if has_relative:
            logger.info("[Resolver] Detected relative keyword in '%s'", raw_query)
            q_loc: QueryLocation = {
                "name": "Current Location",
                "lat": device_location["lat"] if device_location else None,
                "lon": device_location["lon"] if device_location else None,
                "source": "relative_device",
            }

            if device_location and device_location.get("lat") is not None and device_location.get("lon") is not None:
                d_lat = float(device_location["lat"])
                d_lon = float(device_location["lon"])
                is_coast, place_name, metadata = location_is_coastal(d_lat, d_lon)
                dist_km = metadata.get("distance_to_coast_km") if metadata else distance_to_nearest_coast_km(d_lat, d_lon)

                resolved: ResolvedLocation = {
                    "lat": d_lat,
                    "lon": d_lon,
                    "name": place_name or f"Device ({d_lat:.2f}°N, {d_lon:.2f}°E)",
                    "source": "device",
                    "confidence": 0.95,
                    "coastal": bool(is_coast),
                    "nearest_coast_km": dist_km,
                    "state": metadata.get("state") if metadata else None,
                    "district": metadata.get("district") if metadata else None,
                }
                logger.info("[Resolver] Resolved to device location: %s (coastal=%s)", resolved["name"], resolved["coastal"])
                if session:
                    session.last_query_location = resolved
                return "DEVICE", q_loc, resolved
            else:
                # Relative query without device coordinates: MUST NOT inherit previous place!
                logger.warning("[Resolver] Relative query requested but device_location unavailable.")
                return "DEVICE", q_loc, None

        # ----------------------------------------------------------------------
        # Priority 2: Explicit Coordinates in Query
        # ----------------------------------------------------------------------
        coords = cls.extract_coordinates(raw_query)
        if coords:
            lat, lon = coords
            logger.info("[Resolver] Detected explicit coordinates: (%.4f, %.4f)", lat, lon)
            is_coast, place_name, metadata = location_is_coastal(lat, lon)
            dist_km = metadata.get("distance_to_coast_km") if metadata else distance_to_nearest_coast_km(lat, lon)

            q_loc = {
                "name": f"{lat:.2f}°N, {lon:.2f}°E",
                "lat": lat,
                "lon": lon,
                "source": "explicit_coordinates",
            }
            resolved = {
                "lat": lat,
                "lon": lon,
                "name": place_name or f"{lat:.2f}°N, {lon:.2f}°E",
                "source": "coordinates",
                "confidence": 0.9,
                "coastal": bool(is_coast),
                "nearest_coast_km": dist_km,
                "state": metadata.get("state") if metadata else None,
                "district": metadata.get("district") if metadata else None,
            }
            if session:
                session.last_query_location = resolved
                session.last_explicit_location = resolved
                try:
                    from location.service import determine_marine_context
                    m_ctx = determine_marine_context(lat, lon, name=resolved["name"])
                    session.selected_location = {
                        "name": resolved["name"],
                        "display_name": f"{resolved['name']}, India",
                        "lat": lat,
                        "lon": lon,
                        "state": resolved.get("state"),
                        "country": "India",
                        "source": "conversation",
                    }
                    session.marine_context = m_ctx
                except Exception as e:
                    logger.warning("[Resolver] Could not update session selected_location: %s", e)
            return "EXPLICIT_COORDINATES", q_loc, resolved

        # ----------------------------------------------------------------------
        # Priority 3: Explicit Named Place (Gazetteer or Geocoder)
        # ----------------------------------------------------------------------
        tool_res = tool_resolve_location(raw_query)
        if tool_res.get("status") in ("success", "inland") and tool_res.get("latitude") is not None:
            lat = float(tool_res["latitude"])
            lon = float(tool_res["longitude"])
            name = tool_res.get("location_name") or raw_query.title()
            is_coast, verified_name, metadata = location_is_coastal(lat, lon, name=name)
            dist_km = metadata.get("distance_to_coast_km") if metadata else distance_to_nearest_coast_km(lat, lon)

            q_loc = {
                "name": name,
                "lat": lat,
                "lon": lon,
                "source": "explicit_place",
            }
            resolved = {
                "lat": lat,
                "lon": lon,
                "name": name,
                "source": "explicit_text",
                "confidence": 0.95 if tool_res.get("source") == "gazetteer" else 0.8,
                "coastal": bool(is_coast),
                "nearest_coast_km": dist_km,
                "state": metadata.get("state") if metadata else None,
                "district": metadata.get("district") if metadata else None,
            }
            logger.info("[Resolver] Resolved explicit place: %s (coastal=%s)", resolved["name"], resolved["coastal"])
            if session:
                session.last_query_location = resolved
                session.last_explicit_location = resolved
                try:
                    from location.service import determine_marine_context
                    m_ctx = determine_marine_context(lat, lon, name=resolved["name"])
                    session.selected_location = {
                        "name": resolved["name"],
                        "display_name": f"{resolved['name']}, India",
                        "lat": lat,
                        "lon": lon,
                        "state": resolved.get("state"),
                        "country": "India",
                        "source": "conversation",
                    }
                    session.marine_context = m_ctx
                except Exception as e:
                    logger.warning("[Resolver] Could not update session selected_location: %s", e)
            return "EXPLICIT_PLACE", q_loc, resolved

        # ----------------------------------------------------------------------
        # Priority 4: Contextual Continuation / Inheritance from Session
        # ----------------------------------------------------------------------
        # Check session.selected_location first (canonical source of truth), then last_query_location
        if session and (session.selected_location or session.last_query_location):
            if session.selected_location:
                s_loc = session.selected_location
                logger.info("[Resolver] Inheriting canonical selected location from session: %s", s_loc.get("name"))
                m_ctx = session.marine_context or {}
                is_coast = m_ctx.get("is_coastal", True)
                dist_km = m_ctx.get("distance_to_coast_km")
                q_loc = {
                    "name": s_loc.get("name"),
                    "lat": s_loc.get("lat"),
                    "lon": s_loc.get("lon"),
                    "source": "inherited",
                }
                resolved = {
                    "lat": float(s_loc["lat"]),
                    "lon": float(s_loc["lon"]),
                    "name": s_loc.get("name") or f"{s_loc['lat']:.2f}°N, {s_loc['lon']:.2f}°E",
                    "source": "previous_query",
                    "confidence": 0.85,
                    "coastal": bool(is_coast),
                    "nearest_coast_km": dist_km,
                    "state": s_loc.get("state"),
                    "district": None,
                }
                session.last_query_location = resolved
                return "INHERITED", q_loc, resolved
            elif session.last_query_location:
                inherited = session.last_query_location
                logger.info("[Resolver] Inheriting previous query location from session: %s", inherited["name"])
                q_loc = {
                    "name": inherited["name"],
                    "lat": inherited["lat"],
                    "lon": inherited["lon"],
                    "source": "inherited",
                }
                resolved = {
                    "lat": inherited["lat"],
                    "lon": inherited["lon"],
                    "name": inherited["name"],
                    "source": "previous_query",
                    "confidence": inherited.get("confidence", 0.7),
                    "coastal": inherited.get("coastal", True),
                    "nearest_coast_km": inherited.get("nearest_coast_km"),
                    "state": inherited.get("state"),
                    "district": inherited.get("district"),
                }
                return "INHERITED", q_loc, resolved


        # ----------------------------------------------------------------------
        # Priority 5: Controlled Clarification (No Location)
        # ----------------------------------------------------------------------
        logger.info("[Resolver] No location resolvable; returning NONE mode.")
        q_loc = {
            "name": None,
            "lat": None,
            "lon": None,
            "source": "none",
        }
        return "NONE", q_loc, None
