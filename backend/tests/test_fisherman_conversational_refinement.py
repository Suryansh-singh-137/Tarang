"""
test_fisherman_conversational_refinement.py
-------------------------------------------
PRD §27 Regression Test Suite for Fisherman Conversational Refinement:
1. test_simple_safety_answer: <= 5 sentences, no internal formulas/agent names/contribution points, includes advisory.
2. test_safety_override_severe_hazard: severe lightning / cyclone overrides composite LOW to HIGH/EXTREME (invariant final_level != LOW).
3. test_risk_explanation_no_api_calls: qualitative explanation using previous assessment without refetching external APIs.
4. test_live_recheck: 'is it still safe now?' triggers recheck and re-evaluation.
5. test_multi_intent_cohesive_response: water level + safety blended into a single cohesive response.
6. test_pfz_proxy_wording: proxy wording (Fishing Potential Indicator / satellite chlorophyll proxy), not official PFZ advisory.
7. test_weather_terminology: Current & Forecast Weather / Marine Weather Conditions, not Live Weather Observation.
8. test_ocean_terminology: Tide & Water Level Prediction, not Tide & Water Level Station.
9. test_cached_data_explanation: informs user that dataset is from latest available dataset without claiming live.
10. test_location_regression_preserved: explicit -> inherited -> relative location precedence intact.
"""

import os
import sys
import unittest

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from graph.state import ORCAState, AgentResult, EvidenceItem, AnswerPlan, ParsedIntent
from graph.nodes.risk_agent import risk_agent
from graph.nodes.explain_risk import explain_risk
from graph.nodes.detect_and_parse import detect_and_parse, classify_query_intent
from graph.nodes.synthesis import (
    _render_template,
    _render_weather_response,
    _render_ocean_response,
    _render_pfz_response,
    _render_multi_intent_response,
)
from location.models import DeviceLocation, ResolvedLocation


class TestFishermanConversationalRefinement(unittest.TestCase):

    def setUp(self):
        self.chennai_resolved: ResolvedLocation = {
            "name": "Chennai",
            "lat": 13.0827,
            "lon": 80.2707,
            "coastal": True,
            "state": "Tamil Nadu",
            "country": "India",
            "nearest_coast_km": 0.5,
        }
        self.delhi_device: DeviceLocation = {
            "lat": 28.74,
            "lon": 77.12,
            "accuracy": 10.0,
            "captured_at": "2026-09-14T00:00:00Z",
            "permission_status": "granted",
        }

    # -----------------------------------------------------------------------
    # Scenario 1: Simple safety answer (Layer 1)
    # -----------------------------------------------------------------------
    def test_simple_safety_answer(self):
        """Primary safety response is <= 5 sentences, contains no formulas, no agent names, no contribution points, and includes safety advisory."""
        weather_res: AgentResult = {
            "agent_name": "weather_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {
                "wave_height_m": 0.8,
                "wind_speed_kmh": 12.0,
                "sea_state": "calm",
            },
            "source": "Open-Meteo",
            "summary": "Calm seas",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }
        hazard_res: AgentResult = {
            "agent_name": "hazard_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {
                "overall_hazard_level": "none",
                "active_warnings": [],
            },
            "source": "IMD",
            "summary": "No active warnings",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }
        geofence_res: AgentResult = {
            "agent_name": "geofence_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {"distance_to_imbl_km": 200.0},
            "source": "IMBL",
            "summary": "Far from IMBL",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }

        state: ORCAState = {
            "request_id": "req-1",
            "conversation_id": "conv-1",
            "raw_query": "is it safe to fish in Chennai tomorrow morning?",
            "detected_language": "en",
            "resolved_location": self.chennai_resolved,
            "weather_result": weather_res,
            "hazard_result": hazard_res,
            "geofence_result": geofence_res,
            "pfz_result": None,
            "ocean_result": None,
            "risk_result": None,
            "trace": [],
            "evidence": [],
            "data_quality_reports": [
                {"agent_name": "weather_agent", "source_key": "open_meteo", "source": "Open-Meteo", "provenance_tier": "global_model", "is_official": False, "is_proxy": False, "is_fallback": False, "is_stale": False, "freshness_hours": 1.0, "quality_score": 1.0, "warnings": []},
                {"agent_name": "hazard_agent", "source_key": "imd", "source": "IMD", "provenance_tier": "official_operational", "is_official": True, "is_proxy": False, "is_fallback": False, "is_stale": False, "freshness_hours": 1.0, "quality_score": 1.0, "warnings": []},
            ],
            "execution_status": "success",
            "overall_data_status": "live",
            "final_answer_text": "",
            "map_geojson": {},
            "conversation_history": [],
            "last_parsed_intent": None,
            "last_results": {},
            "changed_fields": [],
            "parse_method": "rule_based_fallback",
            "synthesis_method": "template_fallback",
            "risk_sufficient_data": True,
            "user_location": None,
            "language_override": None,
            "device_location": None,
            "query_location": None,
            "location_mode": "EXPLICIT_PLACE",
            "parsed_intent": None,
        }

        # Run risk agent
        risk_out = risk_agent(state)
        state["risk_result"] = risk_out["risk_result"]

        # Synthesize output (using template synthesis fallback to test deterministic phrasing)
        answer = _render_template(
            lang="en",
            location="Chennai",
            time_window="tomorrow_morning",
            weather=weather_res,
            pfz=None,
            hazard=hazard_res,
            geofence=geofence_res,
            risk=risk_out["risk_result"],
            evidence=[],
        )

        # 1. No departure authorization language
        self.assertNotIn("proceed with standard safety precautions", answer.lower())
        self.assertNotIn("conditions appear manageable", answer.lower())
        self.assertNotIn("safe to go", answer.lower())

        # 2. Includes non-authorizing advisory check
        self.assertIn("check the latest official advisory before leaving shore", answer.lower())

        # 3. No internal weights/formulas/agent names/JSON
        self.assertNotIn("risk_agent", answer)
        self.assertNotIn("component score", answer.lower())
        self.assertNotIn("weight:", answer.lower())
        self.assertNotIn("contribution:", answer.lower())

        # 4. Sentences count <= 5
        sentences = [s.strip() for s in answer.replace("\n", " ").split(".") if s.strip()]
        self.assertLessEqual(len(sentences), 5)

    # -----------------------------------------------------------------------
    # Scenario 2: Deterministic safety override on severe/high active hazard
    # -----------------------------------------------------------------------
    def test_safety_override_severe_hazard(self):
        """Severe lightning or storm warning overrides composite LOW to HIGH/EXTREME, enforcing final_level != LOW."""
        calm_weather: AgentResult = {
            "agent_name": "weather_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {
                "wave_height_m": 0.4,   # wave score 0
                "wind_speed_kmh": 8.0,   # wind score 0
            },
            "source": "Open-Meteo",
            "summary": "Calm",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }
        severe_lightning_hazard: AgentResult = {
            "agent_name": "hazard_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {
                "overall_hazard_level": "high",
                "active_warnings": ["severe_lightning", "squall"],
                "hazards": [{"title": "Severe Lightning", "severity": "high", "detail": "Frequent cloud-to-sea lightning"}],
            },
            "source": "IMD",
            "summary": "Severe lightning warning",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }
        geofence_safe: AgentResult = {
            "agent_name": "geofence_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {"distance_to_imbl_km": 150.0},
            "source": "IMBL",
            "summary": "Safe",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }

        state: ORCAState = {
            "resolved_location": self.chennai_resolved,
            "weather_result": calm_weather,
            "hazard_result": severe_lightning_hazard,
            "geofence_result": geofence_safe,
            "pfz_result": None,
            "ocean_result": None,
            "risk_result": None,
            "trace": [],
            "evidence": [],
            "data_quality_reports": [
                {"agent_name": "weather_agent", "source_key": "open_meteo", "source": "Open-Meteo", "provenance_tier": "global_model", "is_official": False, "is_proxy": False, "is_fallback": False, "is_stale": False, "freshness_hours": 1.0, "quality_score": 1.0, "warnings": []},
                {"agent_name": "hazard_agent", "source_key": "imd", "source": "IMD", "provenance_tier": "official_operational", "is_official": True, "is_proxy": False, "is_fallback": False, "is_stale": False, "freshness_hours": 1.0, "quality_score": 1.0, "warnings": []},
            ],
            "execution_status": "success",
            "overall_data_status": "live",
            "final_answer_text": "",
            "map_geojson": {},
            "conversation_history": [],
            "last_parsed_intent": None,
            "last_results": {},
            "changed_fields": [],
            "parse_method": "rule_based_fallback",
            "synthesis_method": "template_fallback",
            "risk_sufficient_data": True,
            "user_location": None,
            "language_override": None,
            "device_location": None,
            "query_location": None,
            "location_mode": "EXPLICIT_PLACE",
            "parsed_intent": None,
        }

        res = risk_agent(state)
        rdata = res["risk_result"]["data"]
        # Mandatory Invariant: final_level CANNOT be LOW when severe hazard is active
        self.assertNotEqual(rdata["final_level"], "LOW")
        self.assertIn(rdata["final_level"], ("HIGH", "EXTREME"))
        self.assertTrue(rdata["override_active"])
        self.assertTrue(rdata["critical_hazard"])
        self.assertIn("risky right now", rdata["recommendation"].lower())

    # -----------------------------------------------------------------------
    # Scenario 3: Risk explanation without API refetch
    # -----------------------------------------------------------------------
    def test_risk_explanation_no_api_calls(self):
        """Multi-turn 'why is the risk this low?' explains qualitatively using previous assessment without refetching."""
        prev_assessment = {
            "composite_score": 12.0,
            "base_level": "LOW",
            "final_level": "LOW",
            "risk_label": "LOW",
            "override_active": False,
            "components": [
                {"label": "Wave Height", "raw_value": 0.8, "raw_unit": "m", "component_score": 20.0, "weight": 0.3, "contribution": 6.0},
                {"label": "Wind Speed", "raw_value": 14.0, "raw_unit": "km/h", "component_score": 0.0, "weight": 0.2, "contribution": 0.0},
                {"label": "Hazard Level", "raw_value": "none", "raw_unit": "category", "component_score": 0.0, "weight": 0.3, "contribution": 0.0},
                {"label": "Boundary Proximity", "raw_value": 120.0, "raw_unit": "km", "component_score": 0.0, "weight": 0.2, "contribution": 0.0},
            ],
            "recommendation": "Conditions are currently rated low risk by Tarang. Check the latest official advisory before leaving shore.",
        }

        state: ORCAState = {
            "raw_query": "why is the risk this low?",
            "detected_language": "en",
            "previous_marine_assessment": prev_assessment,
            "risk_result": None,
            "weather_result": None,
            "hazard_result": None,
            "geofence_result": None,
            "pfz_result": None,
            "ocean_result": None,
            "trace": [],
            "evidence": [],
            "map_geojson": {},
        }

        out = explain_risk(state)
        text = out["final_answer_text"]

        # Qualitative Layer 1 checks
        self.assertIn("the risk is low because the sea is fairly calm right now", text.lower())
        self.assertIn("the main factor affecting the score is wave height", text.lower())
        self.assertIn("check the latest official advisory before leaving shore", text.lower())

        # Mathematical breakdown must be contained in expandable <details>
        self.assertIn("<details>", text)
        self.assertIn("</details>", text)
        self.assertIn("points contribution", text)

    # -----------------------------------------------------------------------
    # Scenario 4: Live recheck query
    # -----------------------------------------------------------------------
    def test_live_recheck(self):
        """'is it still safe now?' triggers recheck flag and marks 'recheck' in changed_fields."""
        conv_id = "conv-recheck-test"

        # Turn 1: establish location in Chennai
        state_1: ORCAState = {
            "raw_query": "is it safe to fish in Chennai?",
            "conversation_id": conv_id,
            "conversation_history": [],
            "device_location": None,
        }
        out_1 = detect_and_parse(state_1)
        self.assertEqual(out_1["resolved_location"]["name"], "Chennai")

        # Turn 2: recheck query
        state_2: ORCAState = {
            "raw_query": "is it still safe now?",
            "conversation_id": conv_id,
            "conversation_history": [
                {"role": "user", "content": "is it safe to fish in Chennai?"},
                {"role": "assistant", "content": "Conditions are low risk."},
            ],
            "last_parsed_intent": out_1["parsed_intent"],
            "device_location": None,
        }

        out_2 = detect_and_parse(state_2)
        self.assertTrue(out_2.get("is_recheck"))
        self.assertIn("recheck", out_2.get("changed_fields", []))

    # -----------------------------------------------------------------------
    # Scenario 5: Multi-intent cohesive response
    # -----------------------------------------------------------------------
    def test_multi_intent_cohesive_response(self):
        """'What is the sea level in Chennai? Is it safe to fish there?' blends water level and safety seamlessly."""
        ocean_res: AgentResult = {
            "agent_name": "ocean_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {
                "water_level_m": 0.65,
                "current_phase": "Rising (Flood Tide)",
            },
            "source": "INCOIS ERDDAP",
            "summary": "Water level 0.65 m CD",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }
        risk_res: AgentResult = {
            "agent_name": "risk_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {
                "composite_score": 14.0,
                "risk_label": "LOW",
                "recommendation": "Conditions are currently rated low risk by Tarang. Check the latest official advisory before leaving shore.",
            },
            "source": "Tarang Risk Model",
            "summary": "Low risk",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }

        groups = [
            {"intent": "WATER_LEVEL_QUERY", "location": "Chennai"},
            {"intent": "MARINE_SAFETY_QUERY", "location": "Chennai"},
        ]

        text = _render_multi_intent_response(
            lang="en",
            resolved=self.chennai_resolved,
            intent_groups=groups,
            weather=None,
            ocean=ocean_res,
            pfz=None,
            hazard=None,
            risk=risk_res,
        )

        # Both water level and safety are answered in one cohesive text
        self.assertIn("0.65", text)
        self.assertIn("chart datum", text.lower())
        self.assertIn("low risk", text.lower())
        self.assertIn("check the latest official advisory", text.lower())

    # -----------------------------------------------------------------------
    # Scenario 6: PFZ wording (Indicator/Proxy, not Advisory)
    # -----------------------------------------------------------------------
    def test_pfz_proxy_wording(self):
        """PFZ response calls it 'Fishing Potential Indicator' or 'proxy', never 'official PFZ advisory'."""
        pfz_res: AgentResult = {
            "agent_name": "pfz_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {
                "zones": [{"lat": 13.1, "lon": 80.5, "distance_km": 28.0, "chlorophyll_mg_m3": 0.85}],
                "nearest_zone_km": 28.0,
                "overall_productivity": "moderate",
            },
            "source": "INCOIS Oceansat-2",
            "summary": "PFZ proxy zones",
            "used_fallback": False,
            "data_quality": "historical_proxy",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }

        text = _render_pfz_response("en", self.chennai_resolved, pfz_res)
        self.assertIn("Fishing Potential Indicator", text)
        self.assertIn("satellite chlorophyll", text.lower())
        self.assertNotIn("official pfz advisory", text.lower())

    # -----------------------------------------------------------------------
    # Scenario 7: Weather terminology
    # -----------------------------------------------------------------------
    def test_weather_terminology(self):
        """Does not label ERA5-ICON forecast as pure 'Live Weather Observation'."""
        weather_res: AgentResult = {
            "agent_name": "weather_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {
                "temperature_c": 29.5,
                "wind_speed_kmh": 15.0,
                "wave_height_m": 0.9,
            },
            "source": "Open-Meteo Marine + Forecast (ERA5-ICON)",
            "summary": "Weather conditions",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }

        text = _render_weather_response("en", self.chennai_resolved, "next_24h", weather_res)
        self.assertIn("Current & Forecast Weather", text)
        self.assertNotIn("Live Weather Observation", text)

    # -----------------------------------------------------------------------
    # Scenario 8: Ocean terminology
    # -----------------------------------------------------------------------
    def test_ocean_terminology(self):
        """Does not label harmonic prediction as 'Tide & Water Level Station'."""
        ocean_res: AgentResult = {
            "agent_name": "ocean_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {
                "water_level_m": 0.82,
                "current_phase": "High Slack",
            },
            "source": "INCOIS ERDDAP",
            "summary": "Tide prediction",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }

        text = _render_ocean_response("en", self.chennai_resolved, ocean_res)
        self.assertIn("Tide & Water Level Prediction", text)
        self.assertNotIn("Tide & Water Level Station", text)

    # -----------------------------------------------------------------------
    # Scenario 9: Cached data explanation
    # -----------------------------------------------------------------------
    def test_cached_data_explanation(self):
        """Discloses that dataset is from latest available dataset without claiming live."""
        pfz_cached: AgentResult = {
            "agent_name": "pfz_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "cached",
            "data": {
                "zones": [{"lat": 13.1, "lon": 80.5, "distance_km": 30.0}],
                "nearest_zone_km": 30.0,
            },
            "source": "INCOIS Oceansat-2",
            "summary": "Cached proxy",
            "used_fallback": True,
            "data_quality": "historical_proxy",
            "timestamp": "2026-09-10T00:00:00Z",
            "error": None,
            "evidence": [],
        }
        risk_res: AgentResult = {
            "agent_name": "risk_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {
                "composite_score": 10.0,
                "risk_label": "LOW",
                "recommendation": "Conditions are currently rated low risk by Tarang. Check the latest official advisory before leaving shore.",
            },
            "source": "Tarang Risk Model",
            "summary": "Low risk",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }

        text = _render_template(
            lang="en",
            location="Chennai",
            time_window="now",
            weather=None,
            pfz=pfz_cached,
            hazard=None,
            geofence=None,
            risk=risk_res,
            evidence=[],
        )
        self.assertIn("Some fishing-zone data is from the latest available dataset rather than live data", text)

    # -----------------------------------------------------------------------
    # Scenario 10: Location precedence preserved
    # -----------------------------------------------------------------------
    def test_location_regression_preserved(self):
        """Mumbai explicit -> inherited -> 'here' precedence remains intact."""
        # 1. Explicit place Mumbai
        state_1: ORCAState = {
            "raw_query": "is it safe to fish in Mumbai?",
            "conversation_id": "conv-loc-1",
            "conversation_history": [],
            "device_location": self.delhi_device,
        }
        out_1 = detect_and_parse(state_1)
        self.assertEqual(out_1["location_mode"], "EXPLICIT_PLACE")
        self.assertEqual(out_1["resolved_location"]["name"], "Mumbai")

        # 2. Inherited 'there'
        state_2: ORCAState = {
            "raw_query": "is it safe to fish there?",
            "conversation_id": "conv-loc-1",
            "conversation_history": [{"role": "user", "content": "is it safe to fish in Mumbai?"}],
            "last_parsed_intent": out_1["parsed_intent"],
            "device_location": self.delhi_device,
        }
        out_2 = detect_and_parse(state_2)
        self.assertEqual(out_2["location_mode"], "INHERITED")
        self.assertEqual(out_2["resolved_location"]["name"], "Mumbai")

        # 3. Relative 'here' switches to device location
        state_3: ORCAState = {
            "raw_query": "what is the weather here?",
            "conversation_id": "conv-loc-1",
            "conversation_history": [{"role": "user", "content": "is it safe to fish there?"}],
            "last_parsed_intent": out_2["parsed_intent"],
            "device_location": self.delhi_device,
        }
        out_3 = detect_and_parse(state_3)
        self.assertEqual(out_3["location_mode"], "DEVICE")
        self.assertAlmostEqual(out_3["resolved_location"]["lat"], 28.74, places=2)


if __name__ == "__main__":
    unittest.main()
