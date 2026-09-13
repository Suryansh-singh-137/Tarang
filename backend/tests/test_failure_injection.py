"""
test_failure_injection.py
--------------------------
Tarang V2.1 Failure-Injection & Fallback Elimination Verification Suite.

Validates PRD §16, §20:
- Live Weather API failure -> fails with unavailable, NO fallback fabrication.
- Live PFZ / ERDDAP API failure -> fails with unavailable, NO fallback fabrication.
- Live Hazard API failure -> fails with unavailable, NO fallback fabrication.
- Risk Model Fail-Closed: When weather or hazard is unavailable, returns UNKNOWN
  without fabricating default numbers (2.0m waves, 30km/h wind).
- Synthesis under failure: NO DATA -> NO CLAIM.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# Add backend directory to sys.path
_BACKEND_DIR = Path(__file__).parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import unittest
from unittest.mock import patch
from graph.state import ORCAState, ParsedIntent
from graph.nodes.weather_agent import weather_agent
from graph.nodes.pfz_agent import pfz_agent
from graph.nodes.hazard_agent import hazard_agent
from graph.nodes.risk_agent import risk_agent
from graph.nodes.synthesis import synthesis


def _make_mock_state(lat: float = 9.9312, lon: float = 76.2673, loc_name: str = "Kochi") -> ORCAState:
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
        "request_id": "test_fail_req",
        "conversation_id": "test_fail_conv",
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


def test_weather_failure_injection_no_fabrication():
    """PRD §16.1 & §20: When Open-Meteo fails, do NOT fabricate fallback weather data."""
    state = _make_mock_state()

    with patch("graph.nodes.weather_agent.fetch_marine_conditions", return_value=None):
        res = weather_agent(state)
        wr = res.get("weather_result")
        assert wr is not None
        assert wr.get("status") == "error"
        assert wr.get("execution_status") == "failed"
        assert wr.get("data_status") == "unavailable"
        assert wr.get("error") == "LIVE_WEATHER_UNAVAILABLE"
        # Data must be empty — NO fabricated 2.0m waves or 30km/h wind!
        assert wr.get("data") == {}
        assert wr.get("evidence") == []
        assert wr.get("used_fallback") is False


def test_pfz_failure_injection_no_fabrication():
    """PRD §16.2 & §20: When ERDDAP fails, do NOT fabricate fallback PFZ zones."""
    state = _make_mock_state()

    with patch("graph.nodes.pfz_agent.fetch_official_pfz_advisory", return_value=None), \
         patch("graph.nodes.pfz_agent.fetch_pfz_zones", return_value=None):
        res = pfz_agent(state)
        pr = res.get("pfz_result")
        assert pr is not None
        assert pr.get("status") == "error"
        assert pr.get("execution_status") == "failed"
        assert pr.get("data_status") == "unavailable"
        assert pr.get("error") == "LIVE_PFZ_UNAVAILABLE"
        # Data must be empty — NO fabricated zones!
        assert pr.get("data") == {}
        assert pr.get("evidence") == []
        assert pr.get("used_fallback") is False


def test_hazard_failure_injection_no_fabrication():
    """PRD §16.3 & §20: When hazard APIs fail, do NOT fabricate fallback hazards."""
    state = _make_mock_state()

    with patch("graph.nodes.hazard_agent.fetch_imd_warnings", return_value=None), \
         patch("graph.nodes.hazard_agent.fetch_active_cyclones", return_value=None), \
         patch("graph.nodes.hazard_agent.fetch_hazard_advisory", return_value=None):
        res = hazard_agent(state)
        hr = res.get("hazard_result")
        assert hr is not None
        assert hr.get("status") == "error"
        assert hr.get("execution_status") == "failed"
        assert hr.get("data_status") == "unavailable"
        assert hr.get("error") == "LIVE_HAZARDS_UNAVAILABLE"
        assert hr.get("data") == {}
        assert hr.get("evidence") == []
        assert hr.get("used_fallback") is False


def test_risk_model_fail_closed_on_missing_weather():
    """PRD §10 & §20: When weather data is unavailable, risk model MUST fail closed with UNKNOWN."""
    state = _make_mock_state()
    # Inject failed weather
    state["weather_result"] = {
        "agent_name": "weather_agent",
        "status": "error",
        "execution_status": "failed",
        "data_status": "unavailable",
        "location_used": {"lat": 9.9312, "lon": 76.2673},
        "observed_at": None,
        "data": {},
        "source": "Open-Meteo",
        "summary": "Live marine weather data unavailable",
        "used_fallback": False,
        "data_quality": "unavailable",
        "timestamp": "2026-09-14T00:00:00Z",
        "error": "LIVE_WEATHER_UNAVAILABLE",
        "evidence": [],
    }
    # Inject valid hazard
    state["hazard_result"] = {
        "agent_name": "hazard_agent",
        "status": "success",
        "execution_status": "success",
        "data_status": "live",
        "location_used": {"lat": 9.9312, "lon": 76.2673},
        "observed_at": "2026-09-14T00:00:00Z",
        "data": {"overall_hazard_level": "none", "active_warnings": []},
        "source": "Open-Meteo WMO",
        "summary": "No warnings",
        "used_fallback": False,
        "data_quality": "live",
        "timestamp": "2026-09-14T00:00:00Z",
        "error": None,
        "evidence": [],
    }

    res = risk_agent(state)
    rr = res.get("risk_result")
    assert rr is not None
    # Must fail closed:
    assert rr.get("status") == "insufficient_data"
    assert rr.get("execution_status") == "failed"
    assert rr.get("data_status") == "unavailable"
    assert rr.get("error") == "CRITICAL_DATA_UNAVAILABLE"
    assert rr["data"]["composite_score"] is None
    assert rr["data"]["risk_label"] == "UNKNOWN"
    assert res.get("risk_sufficient_data") is False


def test_synthesis_no_data_no_claim():
    """PRD §17 & §20: When critical data is unavailable, synthesis must NOT claim safe conditions."""
    state = _make_mock_state()
    state["weather_result"] = {
        "agent_name": "weather_agent",
        "status": "error",
        "execution_status": "failed",
        "data_status": "unavailable",
        "location_used": {"lat": 9.9312, "lon": 76.2673},
        "observed_at": None,
        "data": {},
        "source": "Open-Meteo",
        "summary": "Live marine weather data unavailable",
        "used_fallback": False,
        "data_quality": "unavailable",
        "timestamp": "",
        "error": "LIVE_WEATHER_UNAVAILABLE",
        "evidence": [],
    }
    state["risk_result"] = {
        "agent_name": "risk_agent",
        "status": "insufficient_data",
        "execution_status": "failed",
        "data_status": "unavailable",
        "location_used": {"lat": 9.9312, "lon": 76.2673},
        "observed_at": None,
        "data": {
            "composite_score": None,
            "risk_label": "UNKNOWN",
            "recommendation": "UNKNOWN: Unable to determine safe conditions due to missing critical marine data.",
        },
        "source": "Tarang Risk Model",
        "summary": "Risk unavailable",
        "used_fallback": False,
        "data_quality": "unavailable",
        "timestamp": "",
        "error": "CRITICAL_DATA_UNAVAILABLE",
        "evidence": [],
    }

    res = synthesis(state)
    ans = res.get("final_answer_text", "")
    ans_lower = ans.lower()
    assert "unknown" in ans_lower or "could not be retrieved" in ans_lower or "unavailable" in ans_lower
    # Assert it never claims low risk or manageable safe conditions when weather failed
    assert "low risk" not in ans_lower
    assert "manageable conditions" not in ans_lower


class TestFailureInjection(unittest.TestCase):
    def test_weather_failure_injection_no_fabrication(self):
        test_weather_failure_injection_no_fabrication()

    def test_pfz_failure_injection_no_fabrication(self):
        test_pfz_failure_injection_no_fabrication()

    def test_hazard_failure_injection_no_fabrication(self):
        test_hazard_failure_injection_no_fabrication()

    def test_risk_model_fail_closed_on_missing_weather(self):
        test_risk_model_fail_closed_on_missing_weather()

    def test_synthesis_no_data_no_claim(self):
        test_synthesis_no_data_no_claim()


if __name__ == "__main__":
    unittest.main(verbosity=2)
