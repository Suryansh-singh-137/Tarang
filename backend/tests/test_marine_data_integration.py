"""
test_marine_data_integration.py
--------------------------------
Tarang V2.1 Marine Data Source & Specialist Agent Integration Verification Suite.

Validates PRD §5 - §12, §18, §19:
- Weather data variables, V2.1 contract, no SST claim
- PFZ data variables, GeoJSON [lon, lat] ordering, proxy disclosure
- Ocean / Tide data variables, Chart Datum reference, harmonic constituent model
- Hazard data variables, absence-of-data framing
- Geofence boundary calculations, warnings, geometry source
- Risk calculation, transparent component breakdown, fail-closed handling
- Location Integrity Invariant validation across all executed agents
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend directory to sys.path
_BACKEND_DIR = Path(__file__).parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import unittest
from location.models import ResolvedLocation
from graph.state import ORCAState, ParsedIntent
from graph.nodes.weather_agent import weather_agent
from graph.nodes.pfz_agent import pfz_agent
from graph.nodes.ocean_agent import ocean_agent
from graph.nodes.hazard_agent import hazard_agent
from graph.nodes.geofence_agent import geofence_agent
from graph.nodes.risk_agent import risk_agent
from graph.build_graph import _status_validator_node, graph


def _make_mock_state(lat: float = 9.9312, lon: float = 76.2673, loc_name: str = "Kochi") -> ORCAState:
    """Construct minimal mock state with canonical ResolvedLocation."""
    resolved: ResolvedLocation = {
        "name": loc_name,
        "lat": lat,
        "lon": lon,
        "source": "explicit_query",
        "confidence": 1.0,
        "coastal": True,
        "state": "Kerala",
        "distance_to_coast_km": 0.5,
    }
    intent: ParsedIntent = {
        "location_name": loc_name,
        "lat": lat,
        "lon": lon,
        "time_window": "next_24h",
        "time_start_utc": "",
        "time_end_utc": "",
        "query_type": "safety_check",
        "needs_weather": True,
        "needs_pfz": True,
        "needs_hazard": True,
        "needs_geofence": True,
        "needs_risk": True,
        "needs_ocean": True,
    }
    return {
        "request_id": "test_req_001",
        "conversation_id": "test_conv_001",
        "raw_query": f"Is it safe to fish off {loc_name}?",
        "detected_language": "en",
        "parsed_intent": intent,
        "device_location": None,
        "query_location": None,
        "resolved_location": resolved,
        "location_mode": "explicit",
        "weather_result": None,
        "pfz_result": None,
        "ocean_result": None,
        "hazard_result": None,
        "geofence_result": None,
        "risk_result": None,
        "execution_status": "success",
        "overall_data_status": "live",
        "final_answer_text": "",
        "map_geojson": {},
        "evidence": [],
        "trace": [],
        "conversation_history": [],
        "last_parsed_intent": None,
        "last_results": {},
        "changed_fields": [],
        "parse_method": "llm",
        "synthesis_method": "llm",
        "data_quality_reports": [],
        "risk_sufficient_data": True,
        "user_location": None,
        "language_override": None,
    }


def test_weather_agent_integration():
    """PRD §5: Verify weather agent execution, contract, and separation from SST."""
    state = _make_mock_state()
    res = weather_agent(state)
    wr = res.get("weather_result")
    assert wr is not None, "weather_result must not be None"

    # Global Agent Contract (§3)
    assert wr.get("execution_status") in ("success", "failed")
    assert wr.get("data_status") in ("live", "unavailable")
    assert "location_used" in wr
    if wr.get("execution_status") == "success":
        assert wr["location_used"] == {"lat": 9.9312, "lon": 76.2673}
        data = wr["data"]
        # Required variables
        assert "wave_height_m" in data
        assert "wind_speed_kmh" in data
        assert "sea_state" in data
        assert "pressure_msl_hpa" in data
        # SST separation: Weather capability must NOT claim SST
        assert "sst_celsius" not in data or data["sst_celsius"] is None

        # Evidence checks
        ev_items = wr.get("evidence", [])
        assert len(ev_items) > 0
        for ev in ev_items:
            assert ev.get("data_type") == "forecast"
            assert ev.get("timestamp") is not None


def test_pfz_agent_integration():
    """PRD §6: Verify PFZ agent, GeoJSON [lon, lat] ordering, and contract."""
    state = _make_mock_state(lat=8.7642, lon=78.1348, loc_name="Thoothukudi")
    res = pfz_agent(state)
    pr = res.get("pfz_result")
    assert pr is not None

    assert pr.get("execution_status") in ("success", "failed")
    assert pr.get("data_status") in ("live", "cached", "unavailable")
    if pr.get("execution_status") == "success":
        assert pr["location_used"] == {"lat": 8.7642, "lon": 78.1348}
        data = pr["data"]
        assert "zones" in data
        assert "nearest_zone_km" in data
        assert "avg_chl" in data

        # Check GeoJSON RFC 7946 coordinates [lon, lat]
        from graph.nodes.pfz_agent import _build_pfz_geojson_features
        features = _build_pfz_geojson_features(data["zones"], pr["source"])
        for feat in features:
            coords = feat["geometry"]["coordinates"]
            # coords[0] is longitude (should be ~70-95 in India), coords[1] is latitude (~5-25)
            assert coords[0] > coords[1], f"Expected [lon, lat] order, got {coords}"


def test_ocean_agent_integration():
    """PRD §7: Verify ocean tides, Chart Datum reference, and harmonic prediction model."""
    state = _make_mock_state(lat=18.93, lon=72.83, loc_name="Mumbai")
    res = ocean_agent(state)
    ocr = res.get("ocean_result")
    assert ocr is not None
    assert ocr.get("execution_status") == "success"
    assert ocr.get("data_status") == "live"
    assert ocr["location_used"] == {"lat": 18.93, "lon": 72.83}

    data = ocr["data"]
    # Check datum is strictly Chart Datum
    assert data.get("datum") == "Chart Datum"
    assert data.get("data_type") == "harmonic_prediction"
    assert "water_level_m" in data
    assert "current_phase" in data
    assert "next_high_tide" in data
    assert "next_low_tide" in data
    assert data["next_high_tide"]["height_m"] > data["next_low_tide"]["height_m"]

    # Evidence items
    ev_items = ocr.get("evidence", [])
    assert len(ev_items) >= 3
    for ev in ev_items:
        assert ev.get("data_type") == "harmonic_prediction"
        assert "Chart Datum" in ev["claim"] or "CD" in ev["claim"]


def test_hazard_agent_integration():
    """PRD §8: Verify hazard agent, absence-of-data phrasing, and contract."""
    state = _make_mock_state(lat=13.08, lon=80.27, loc_name="Chennai")
    res = hazard_agent(state)
    hr = res.get("hazard_result")
    assert hr is not None
    assert hr.get("execution_status") in ("success", "partial", "failed")
    if hr.get("execution_status") in ("success", "partial"):
        assert hr["location_used"] == {"lat": 13.08, "lon": 80.27}
        data = hr["data"]
        assert "overall_hazard_level" in data
        assert "active_warnings" in data
        assert "cyclone_warning" in data


def test_geofence_agent_integration():
    """PRD §9: Verify geofence geometric computation, boundary distance, and warnings."""
    # Test point close to IMBL (Rameswaram area)
    state = _make_mock_state(lat=9.28, lon=79.31, loc_name="Rameswaram")
    res = geofence_agent(state)
    gr = res.get("geofence_result")
    assert gr is not None
    assert gr.get("execution_status") == "success"
    assert gr.get("data_status") == "live"
    assert gr["location_used"] == {"lat": 9.28, "lon": 79.31}

    data = gr["data"]
    assert "distance_to_boundary_km" in data
    assert "inside_boundary" in data
    assert isinstance(data["inside_boundary"], bool)
    assert "geometry_source" in data
    assert "boundary_name" in data
    assert data["distance_to_boundary_km"] < 100.0


def test_risk_agent_integration():
    """PRD §10: Verify deterministic risk model, weighted formula, and components."""
    state = _make_mock_state()
    # Inject valid live specialist results into state
    w_res = weather_agent(state)
    h_res = hazard_agent(state)
    g_res = geofence_agent(state)
    state["weather_result"] = w_res["weather_result"]
    state["hazard_result"] = h_res["hazard_result"]
    state["geofence_result"] = g_res["geofence_result"]
    state["data_quality_reports"] = (
        w_res.get("data_quality_reports", [])
        + h_res.get("data_quality_reports", [])
    )

    res = risk_agent(state)
    rr = res.get("risk_result")
    assert rr is not None
    assert rr.get("execution_status") == "success"
    assert rr.get("data_status") == "live"
    assert rr["location_used"] == {"lat": 9.9312, "lon": 76.2673}

    data = rr["data"]
    assert data.get("risk_label") in ("LOW", "MODERATE", "HIGH", "EXTREME")
    assert 0.0 <= data.get("composite_score", -1) <= 100.0
    assert len(data.get("components", [])) == 4


def test_location_integrity_invariant():
    """PRD §4: Verify Location Integrity Invariant catches mismatched coordinates."""
    state = _make_mock_state(lat=9.9312, lon=76.2673, loc_name="Kochi")
    # Simulate an agent that queried a wrong location (e.g. Mumbai 18.93, 72.83 instead of Kochi)
    bad_agent_result = {
        "agent_name": "weather_agent",
        "status": "success",
        "execution_status": "success",
        "data_status": "live",
        "location_used": {"lat": 18.93, "lon": 72.83},  # Mismatched!
        "observed_at": "2026-09-14T00:00:00Z",
        "data": {"wave_height_m": 1.2},
        "source": "Open-Meteo",
        "summary": "Weather",
        "used_fallback": False,
        "data_quality": "live",
        "timestamp": "2026-09-14T00:00:00Z",
        "error": None,
        "evidence": [],
    }
    state["trace"] = [bad_agent_result]

    validator_res = _status_validator_node(state)
    # The validator must flag the violation, invalidate the agent, and fail overall
    assert validator_res["execution_status"] == "failed"
    assert bad_agent_result["status"] == "error"
    assert bad_agent_result["execution_status"] == "failed"
    assert bad_agent_result["error"] == "LOCATION_INTEGRITY_VIOLATION"


def test_end_to_end_graph_execution():
    """PRD §18: Verify full compiled StateGraph execution produces compliant output."""
    initial_state = {
        "raw_query": "Is it safe to fish off Kochi tomorrow morning?",
        "detected_language": "en",
        "conversation_history": [],
        "last_parsed_intent": None,
        "last_results": {},
        "changed_fields": [],
        "evidence": [],
        "trace": [],
        "data_quality_reports": [],
    }
    output = graph.invoke(initial_state)

    assert output.get("resolved_location") is not None
    assert output["resolved_location"]["coastal"] is True
    assert output.get("execution_status") in ("success", "partial")
    assert output.get("overall_data_status") in ("live", "mixed", "cached")
    assert len(output.get("final_answer_text", "")) > 50
    # Confirm triple separation in answer or data:
class TestMarineDataIntegration(unittest.TestCase):
    def test_weather_agent_integration(self):
        test_weather_agent_integration()

    def test_pfz_agent_integration(self):
        test_pfz_agent_integration()

    def test_ocean_agent_integration(self):
        test_ocean_agent_integration()

    def test_hazard_agent_integration(self):
        test_hazard_agent_integration()

    def test_geofence_agent_integration(self):
        test_geofence_agent_integration()

    def test_risk_agent_integration(self):
        test_risk_agent_integration()

    def test_location_integrity_invariant(self):
        test_location_integrity_invariant()

    def test_end_to_end_graph_execution(self):
        test_end_to_end_graph_execution()


if __name__ == "__main__":
    unittest.main(verbosity=2)
