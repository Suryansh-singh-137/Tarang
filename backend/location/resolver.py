"""
location.resolver
-----------------
V2 Location Resolver for Tarang Marine Intelligence Platform.

Enforces strict resolution hierarchy:
1. Explicit Coordinates: Numeric lat/lon pairs in the query string.
2. Explicit Place: Coastal gazetteer hit or Nominatim geocoder match.
3. Explicit Device Override: Explicit keywords ("my gps", "phone location", "where i am physically").
4. Relative Keywords ("here", "near me", "mere yaha", "enga", etc.):
   - If user actively selected a pin on the map or searched for a place (source in "map", "search"),
     resolves to the active map selection (matching spatial UI context).
   - Otherwise, resolves strictly to device_location (GPS). If device_location is missing, returns
     unresolved prompt state; NEVER falls back to prior query location.
5. Implicit / Ambient Queries (e.g. "Is it safe to fish right now?"):
   - Checks active map selection if user chose one (source in "map", "search").
   - Else checks device_location (browser GPS).
   - Else inherits previous query location.
   - Else prompts for coastal clarification.
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

# Explicit physical device keywords
_DEVICE_EXPLICIT_RE = re.compile(
    r"\b(my\s+gps|phone\s+location|device\s+location|current\s+gps|actual\s+position|where\s+i\s+am\s+physically|physical\s+location)\b",
    re.IGNORECASE,
)

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
    def is_device_explicit_query(query: str) -> bool:
        """Check if user explicitly asks for their physical device/GPS position."""
        return bool(_DEVICE_EXPLICIT_RE.search(query))

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
        has_device_explicit = cls.is_device_explicit_query(raw_query)

        # ----------------------------------------------------------------------
        # Priority 1: Explicit Coordinates in Query
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
        # Priority 2: Explicit Physical Device Query ("my gps", "phone location")
        # ----------------------------------------------------------------------
        if has_device_explicit:
            logger.info("[Resolver] Detected explicit device keyword in '%s'", raw_query)
            return cls._resolve_device_location(device_location, session, raw_query)

        # ----------------------------------------------------------------------
        # Priority 3: Relative "here" / "near me" Query
        # ----------------------------------------------------------------------
        if has_relative:
            logger.info("[Resolver] Detected relative keyword in '%s'", raw_query)
            # If user has an actively chosen map pin or searched place, "here" means that map pin!
            if session and session.selected_location and session.selected_location.get("source") in ("map", "search"):
                s_loc = session.selected_location
                if s_loc.get("lat") is not None and s_loc.get("lon") is not None:
                    s_lat = float(s_loc["lat"])
                    s_lon = float(s_loc["lon"])
                    s_coast, s_name, s_meta = location_is_coastal(s_lat, s_lon, name=s_loc.get("name"))
                    s_dist = s_meta.get("distance_to_coast_km") if s_meta else distance_to_nearest_coast_km(s_lat, s_lon)
                    resolved_selected: ResolvedLocation = {
                        "lat": s_lat,
                        "lon": s_lon,
                        "name": s_name or s_loc.get("name") or f"{s_lat:.2f}°N, {s_lon:.2f}°E",
                        "source": f"map_pin_{s_loc.get('source', 'map')}",
                        "confidence": 0.95,
                        "coastal": bool(s_coast),
                        "nearest_coast_km": s_dist,
                        "state": s_meta.get("state") if s_meta else s_loc.get("state"),
                        "district": s_meta.get("district") if s_meta else None,
                    }
                    session.last_query_location = resolved_selected
                    logger.info(
                        "[Resolver] Relative query in map context resolved to active map selection: %s",
                        resolved_selected["name"],
                    )
                    return (
                        "INHERITED",
                        {"name": resolved_selected["name"], "lat": s_lat, "lon": s_lon, "source": "map_selected"},
                        resolved_selected,
                    )

            # Otherwise, relative query resolves to device location
            return cls._resolve_device_location(device_location, session, raw_query)

        # ----------------------------------------------------------------------
        # Priority 4: Explicit Named Place (Gazetteer or Geocoder)
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
        # Priority 5: Ambient / Implicit Queries (No text location, e.g. "Is it safe to fish right now?")
        # ----------------------------------------------------------------------
        # 5A: User actively picked a point on map or searched a location
        if session and session.selected_location and session.selected_location.get("source") in ("map", "search"):
            s_loc = session.selected_location
            if s_loc.get("lat") is not None and s_loc.get("lon") is not None:
                s_lat = float(s_loc["lat"])
                s_lon = float(s_loc["lon"])
                m_ctx = session.marine_context or {}
                is_coast = m_ctx.get("is_coastal", True)
                dist_km = m_ctx.get("distance_to_coast_km")
                resolved_map: ResolvedLocation = {
                    "lat": s_lat,
                    "lon": s_lon,
                    "name": s_loc.get("name") or f"{s_lat:.2f}°N, {s_lon:.2f}°E",
                    "source": f"map_pin_{s_loc.get('source', 'map')}",
                    "confidence": 0.9,
                    "coastal": bool(is_coast),
                    "nearest_coast_km": dist_km,
                    "state": s_loc.get("state"),
                    "district": None,
                }
                session.last_query_location = resolved_map
                return (
                    "INHERITED",
                    {"name": s_loc.get("name"), "lat": s_lat, "lon": s_lon, "source": "map_selected"},
                    resolved_map,
                )

        # 5B: Device coordinates provided via browser geolocation payload
        if device_location and device_location.get("lat") is not None and device_location.get("lon") is not None:
            d_lat = float(device_location["lat"])
            d_lon = float(device_location["lon"])
            is_coast, place_name, metadata = location_is_coastal(d_lat, d_lon)
            dist_km = metadata.get("distance_to_coast_km") if metadata else distance_to_nearest_coast_km(d_lat, d_lon)

            resolved_device: ResolvedLocation = {
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
            if session:
                session.last_query_location = resolved_device
            q_loc = {
                "name": resolved_device["name"],
                "lat": d_lat,
                "lon": d_lon,
                "source": "device",
            }
            logger.info(
                "[Resolver] Implicit query resolved to device location: %s (coastal=%s)",
                resolved_device["name"],
                resolved_device["coastal"],
            )
            return "DEVICE", q_loc, resolved_device

        # 5C: Inherit from previous session query
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
        # Priority 6: Controlled Clarification (No Location)
        # ----------------------------------------------------------------------
        logger.info("[Resolver] No location resolvable; returning NONE mode.")
        q_loc = {
            "name": None,
            "lat": None,
            "lon": None,
            "source": "none",
        }
        return "NONE", q_loc, None

    @classmethod
    def _resolve_device_location(
        cls,
        device_location: Optional[DeviceLocation],
        session: Optional[SessionRecord],
        raw_query: str,
    ) -> Tuple[LocationMode, QueryLocation, Optional[ResolvedLocation]]:
        """Helper to resolve strictly to device location with inland fallback check."""
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

            # If device is inland, check if user has an active coastal map selection as fallback
            if not is_coast and session and session.selected_location:
                s_loc = session.selected_location
                if s_loc.get("lat") is not None and s_loc.get("lon") is not None:
                    s_lat = float(s_loc["lat"])
                    s_lon = float(s_loc["lon"])
                    s_coast, s_name, s_meta = location_is_coastal(s_lat, s_lon, name=s_loc.get("name"))
                    if s_coast:
                        logger.info(
                            "[Resolver] Device location is inland (%s), falling back to user's active coastal selection: %s",
                            place_name,
                            s_name or s_loc.get("name"),
                        )
                        s_dist = s_meta.get("distance_to_coast_km") if s_meta else distance_to_nearest_coast_km(s_lat, s_lon)
                        resolved_selected: ResolvedLocation = {
                            "lat": s_lat,
                            "lon": s_lon,
                            "name": s_name or s_loc.get("name") or f"{s_lat:.2f}°N, {s_lon:.2f}°E",
                            "source": "selected_location_fallback",
                            "confidence": 0.9,
                            "coastal": True,
                            "nearest_coast_km": s_dist,
                            "state": s_meta.get("state") if s_meta else s_loc.get("state"),
                            "district": s_meta.get("district") if s_meta else None,
                        }
                        session.last_query_location = resolved_selected
                        return (
                            "INHERITED",
                            {"name": resolved_selected["name"], "lat": s_lat, "lon": s_lon, "source": "selected_fallback"},
                            resolved_selected,
                        )

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
            logger.warning("[Resolver] Relative query requested but device_location unavailable.")
            return "DEVICE", q_loc, None
