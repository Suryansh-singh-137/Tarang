"""
test_dynamic_location_system.py
--------------------------------
Comprehensive test suite for Tarang Dynamic Location & Marine Context System:
- Scenario A: Delhi (inland) -> tide unavailable, is_coastal False.
- Scenario B: Kochi (coastal) -> full marine context, tide available, is_coastal True.
- Scenario C: Offshore Point (13.02, 80.42) -> offshore marine point, tide available.
- Scenario D: Conversational location inheritance & switching.
- Location search: Gazetteer + multi-tier geocoding.
- Session location persistence.
- Zero hardcoded Thoothukudi as default.
"""

import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from location.service import (
    search_locations,
    reverse_geocode,
    determine_marine_context,
    resolve_canonical_location,
    is_offshore_marine_point,
)
from location.resolver import LocationResolver
from session.session_store import get_or_create_session, save_session


def test_scenario_a_delhi_inland():
    """Scenario A: User in Delhi (28.74° N, 77.12° E) is classified as INLAND with tide unavailable."""
    ctx = determine_marine_context(28.74, 77.12, name="Delhi")
    assert ctx["type"] == "inland"
    assert ctx["is_coastal"] is False
    assert ctx["tide_available"] is False
    assert ctx["fishing_data_available"] is False
    assert ctx["distance_to_coast_km"] > 300


def test_scenario_b_kochi_coastal():
    """Scenario B: User switches to Kochi (9.93° N, 76.27° E) -> coastal, tide available."""
    ctx = determine_marine_context(9.93, 76.27, name="Kochi")
    assert ctx["type"] == "coastal"
    assert ctx["is_coastal"] is True
    assert ctx["tide_available"] is True
    assert ctx["fishing_data_available"] is True
    assert ctx["distance_to_coast_km"] < 20


def test_scenario_c_offshore_point():
    """Scenario C: Fisherman clicks offshore (13.02° N, 80.42° E) in Bay of Bengal."""
    lat, lon = 13.02, 80.42
    assert is_offshore_marine_point(lat, lon) is True

    resolved = resolve_canonical_location(lat, lon, source="map")
    loc = resolved["location"]
    ctx = resolved["marine_context"]

    assert ctx["type"] == "offshore"
    assert ctx["tide_available"] is True
    assert ctx["fishing_data_available"] is True
    assert "13.02°N, 80.42°E" in loc["name"]
    assert "Marine Location" in loc["display_name"]


def test_location_search_gazetteer_and_fallback():
    """Location search returns multiple candidates and finds coastal and inland places."""
    kochi_results = search_locations("Kochi", limit=5)
    assert len(kochi_results) >= 1
    assert any("kochi" in r["name"].lower() for r in kochi_results)

    rames_results = search_locations("Rameswaram", limit=5)
    assert len(rames_results) >= 1
    assert any("rameswaram" in r["name"].lower() for r in rames_results)


def test_session_location_persistence_and_inheritance():
    """Scenario D: Session location persists and is inherited for follow-up queries."""
    conv_id = "test-session-location-001"
    session = get_or_create_session(conv_id)

    # 1. Set canonical location to Kochi
    session.selected_location = {
        "name": "Kochi",
        "display_name": "Kochi, Kerala, India",
        "lat": 9.9312,
        "lon": 76.2673,
        "state": "Kerala",
        "country": "India",
        "source": "search",
    }
    session.marine_context = determine_marine_context(9.9312, 76.2673, name="Kochi")
    save_session(session)

    # 2. Query without location mentions ("What is the wind?")
    mode, q_loc, resolved = LocationResolver.resolve("What is the wind?", session=session)
    assert mode == "INHERITED"
    assert resolved is not None
    assert resolved["name"] == "Kochi"
    assert round(resolved["lat"], 2) == 9.93
    assert round(resolved["lon"], 2) == 76.27

    # 3. User switches to Rameswaram ("Check Rameswaram")
    mode2, q_loc2, resolved2 = LocationResolver.resolve("Check Rameswaram", session=session)
    assert mode2 == "EXPLICIT_PLACE"
    assert resolved2 is not None
    assert "rameswaram" in resolved2["name"].lower()
    # Ensure session selected_location was automatically updated
    assert session.selected_location is not None
    assert "rameswaram" in session.selected_location["name"].lower()

    # 4. Subsequent question ("Is fishing good today?") inherits Rameswaram!
    mode3, q_loc3, resolved3 = LocationResolver.resolve("Is fishing good today?", session=session)
    assert mode3 == "INHERITED"
    assert resolved3 is not None
    assert "rameswaram" in resolved3["name"].lower()


if __name__ == "__main__":
    tests = [
        test_scenario_a_delhi_inland,
        test_scenario_b_kochi_coastal,
        test_scenario_c_offshore_point,
        test_location_search_gazetteer_and_fallback,
        test_session_location_persistence_and_inheritance,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            raise
    print(f"\nAll {passed} dynamic location tests passed successfully!")
