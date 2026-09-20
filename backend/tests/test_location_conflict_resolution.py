"""
test_location_conflict_resolution.py
------------------------------------
Tests resolving location conflicts between active map selections,
physical device GPS, explicit places, and relative keywords ("here", "near me").
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from location.resolver import LocationResolver
from session.session_store import SessionRecord


def test_relative_query_with_active_map_selection():
    """
    When user has actively clicked/selected a pin on the map (e.g. Rameswaram),
    queries with 'here' or 'near me' should resolve to the selected map pin,
    NOT the device's physical GPS location (e.g. Chennai).
    """
    session = SessionRecord(conversation_id="test_conv_1")
    session.selected_location = {
        "name": "Rameswaram Waters",
        "lat": 9.2878,
        "lon": 79.3129,
        "source": "map",
    }

    # Physical device is in Chennai
    device_loc = {
        "lat": 13.0827,
        "lon": 80.2707,
        "accuracy": 10.0,
        "captured_at": "2026-09-20T10:00:00Z",
        "permission_status": "granted",
    }

    # 1. "weather near me"
    mode, q_loc, resolved = LocationResolver.resolve("weather near me", device_loc, session)
    assert resolved is not None, "Expected resolved location"
    assert abs(resolved["lat"] - 9.2878) < 0.01, f"Expected Rameswaram lat, got {resolved['lat']}"
    assert abs(resolved["lon"] - 79.3129) < 0.01, f"Expected Rameswaram lon, got {resolved['lon']}"
    assert "Rameswaram" in resolved["name"]

    # 2. "how are the waves here"
    mode, q_loc, resolved = LocationResolver.resolve("how are the waves here", device_loc, session)
    assert resolved is not None
    assert abs(resolved["lat"] - 9.2878) < 0.01

    # 3. Explicit device request: "check weather at my device location"
    mode, q_loc, resolved = LocationResolver.resolve("check weather at my device location", device_loc, session)
    assert resolved is not None
    assert abs(resolved["lat"] - 13.0827) < 0.01, f"Expected device GPS lat (Chennai), got {resolved['lat']}"


def test_relative_query_without_map_selection():
    """
    When user has NOT selected a map pin (e.g. source is default or none),
    'weather near me' should resolve directly to device GPS.
    """
    session = SessionRecord(conversation_id="test_conv_2")
    session.selected_location = {
        "name": "Default Port",
        "lat": 9.9312,
        "lon": 76.2673,
        "source": "default",
    }

    device_loc = {
        "lat": 13.0827,
        "lon": 80.2707,
        "accuracy": 10.0,
        "captured_at": "2026-09-20T10:00:00Z",
        "permission_status": "granted",
    }

    mode, q_loc, resolved = LocationResolver.resolve("weather near me", device_loc, session)
    assert resolved is not None
    assert abs(resolved["lat"] - 13.0827) < 0.01, f"Expected Chennai device lat, got {resolved['lat']}"
    assert resolved["source"] == "device"


def test_explicit_place_overrides_everything():
    """
    If the user explicitly types a named place (e.g. 'Kochi'),
    it must resolve to that place regardless of active map pin or device GPS.
    """
    session = SessionRecord(conversation_id="test_conv_3")
    session.selected_location = {
        "name": "Rameswaram",
        "lat": 9.2878,
        "lon": 79.3129,
        "source": "map",
    }

    device_loc = {
        "lat": 13.0827,
        "lon": 80.2707,
        "accuracy": 10.0,
        "captured_at": "2026-09-20T10:00:00Z",
        "permission_status": "granted",
    }

    mode, q_loc, resolved = LocationResolver.resolve("What is the weather in Kochi?", device_loc, session)
    assert resolved is not None
    assert "Kochi" in resolved["name"]
    assert abs(resolved["lat"] - 9.9312) < 0.1, f"Expected Kochi lat ~9.93, got {resolved['lat']}"


def test_ambient_query_with_map_pin():
    """
    Query with no location in text ('Is it safe to fish right now?'):
    If map pin is active, uses active map pin.
    """
    session = SessionRecord(conversation_id="test_conv_4")
    session.selected_location = {
        "name": "Palk Bay",
        "lat": 9.35,
        "lon": 79.20,
        "source": "map",
    }

    device_loc = {
        "lat": 13.0827,
        "lon": 80.2707,
        "accuracy": 10.0,
        "captured_at": "2026-09-20T10:00:00Z",
        "permission_status": "granted",
    }

    mode, q_loc, resolved = LocationResolver.resolve("Is it safe to fish right now?", device_loc, session)
    assert resolved is not None
    assert abs(resolved["lat"] - 9.35) < 0.01, f"Expected map pin lat, got {resolved['lat']}"


if __name__ == "__main__":
    print("Running location conflict resolution tests...")
    test_relative_query_with_active_map_selection()
    print("  [PASSED] Relative query with active map selection")
    test_relative_query_without_map_selection()
    print("  [PASSED] Relative query without map selection uses device GPS")
    test_explicit_place_overrides_everything()
    print("  [PASSED] Explicit place overrides map & device")
    test_ambient_query_with_map_pin()
    print("  [PASSED] Ambient query with map pin respects map pin")
    print("ALL TESTS PASSED SUCCESSFULLY!")
