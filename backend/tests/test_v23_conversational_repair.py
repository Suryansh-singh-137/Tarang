"""
tests.test_v23_conversational_repair
------------------------------------
Test suite for Tarang V2.3 Conversational Intelligence Repair:
1. Meaningless/Ambiguous input ('.', '...', 'ok') -> CONVERSATIONAL_GUIDANCE, no marine agents, no risk result.
2. Questioning previous verdict -> WHAT_DOES_THIS_LEVEL_MEAN sub-intent.
3. Why this risk -> WHY_THIS_RISK sub-intent with plain explanation.
4. Change since last check -> COMPARE_WITH_PREVIOUS sub-intent.
5. Canonical MarineSnapshot structure & data-truth guarantees.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
_BACKEND_DIR = Path(__file__).parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from graph.state import ORCAState, ParsedIntent
from graph.nodes.detect_and_parse import (
    classify_message_quality,
    classify_risk_sub_intent,
    detect_and_parse,
)
from graph.nodes.synthesis import _build_marine_snapshot, synthesis
from graph.nodes.explain_risk import explain_risk


class TestV23ConversationalRepair(unittest.TestCase):

    def test_message_quality_classifier(self):
        """PRD §5.1: Non-substantive messages must be classified correctly."""
        self.assertEqual(classify_message_quality("."), "AMBIGUOUS")
        self.assertEqual(classify_message_quality("..."), "AMBIGUOUS")
        self.assertEqual(classify_message_quality("???"), "AMBIGUOUS")
        self.assertEqual(classify_message_quality(""), "EMPTY")
        self.assertEqual(classify_message_quality("   "), "EMPTY")
        self.assertEqual(classify_message_quality("ok"), "ACKNOWLEDGEMENT")
        self.assertEqual(classify_message_quality("okay"), "ACKNOWLEDGEMENT")
        self.assertEqual(classify_message_quality("hmm"), "ACKNOWLEDGEMENT")
        self.assertEqual(classify_message_quality("theek hai"), "ACKNOWLEDGEMENT")
        self.assertEqual(classify_message_quality("is it safe to fish in Mumbai?"), "MEANINGFUL")

    def test_risk_sub_intent_classifier(self):
        """PRD §6: Fine-grained risk explanation sub-intents must be recognized."""
        self.assertEqual(
            classify_risk_sub_intent("what do you mean high risk? i didn't ask anything like that?"),
            "WHAT_DOES_THIS_LEVEL_MEAN"
        )
        self.assertEqual(
            classify_risk_sub_intent("what does caution mean?"),
            "WHAT_DOES_THIS_LEVEL_MEAN"
        )
        self.assertEqual(
            classify_risk_sub_intent("what changed since last check?"),
            "COMPARE_WITH_PREVIOUS"
        )
        self.assertEqual(
            classify_risk_sub_intent("is it different from earlier?"),
            "COMPARE_WITH_PREVIOUS"
        )
        self.assertEqual(
            classify_risk_sub_intent("how does the cyclone warning affect the risk?"),
            "HAZARD_IMPACT"
        )
        self.assertEqual(
            classify_risk_sub_intent("what caused this risk?"),
            "WHAT_CAUSED_THIS_RISK"
        )
        self.assertEqual(
            classify_risk_sub_intent("why is it high risk?"),
            "WHY_THIS_RISK"
        )

    def test_meaningless_query_blocks_marine_agents_and_prevents_stale_risk(self):
        """PRD §5.1: Meaningless query MUST NOT run marine agents or return HIGH RISK."""
        state: ORCAState = {
            "request_id": "test-v23-1",
            "conversation_id": "conv-v23-1",
            "raw_query": "...",
            "detected_language": "en",
            "parsed_intent": None,
            "device_location": None,
            "query_location": None,
            "resolved_location": {"name": "Mumbai", "lat": 18.9388, "lon": 72.8354, "coastal": True},
            "location_mode": "INHERITED",
            "weather_result": None,
            "pfz_result": None,
            "ocean_result": None,
            "hazard_result": None,
            "geofence_result": None,
            "risk_result": {"status": "success", "data": {"risk_label": "HIGH", "composite_score": 75.0}},
            "execution_status": "success",
            "overall_data_status": "live",
            "final_answer_text": "",
            "map_geojson": {},
            "evidence": [],
            "trace": [],
            "conversation_history": [],
            "last_parsed_intent": {"intent": "MARINE_SAFETY_QUERY", "location_name": "Mumbai"},
            "last_results": {},
            "previous_marine_assessment": None,
            "semantic_context": {},
            "changed_fields": [],
            "parse_method": "rule_based_fallback",
            "synthesis_method": "template_fallback",
            "data_quality_reports": [],
            "risk_sufficient_data": None,
            "user_location": None,
            "language_override": None,
        }

        output = detect_and_parse(state)
        parsed = output.get("parsed_intent") or {}
        
        self.assertEqual(parsed.get("intent"), "CONVERSATIONAL_GUIDANCE")
        self.assertFalse(parsed.get("needs_weather"))
        self.assertFalse(parsed.get("needs_pfz"))
        self.assertFalse(parsed.get("needs_ocean"))
        self.assertFalse(parsed.get("needs_hazard"))
        self.assertFalse(parsed.get("needs_risk"))
        # Must reset risk_result to None so stale high risk is NEVER returned
        self.assertIsNone(output.get("risk_result"))
        self.assertIn("What would you like to know?", output.get("final_answer_text", ""))

    def test_what_do_you_mean_routes_to_risk_explanation_not_new_safety(self):
        """PRD §5.2: 'what do you mean high risk? i didn't ask anything like that?' questions context."""
        state: ORCAState = {
            "request_id": "test-v23-2",
            "conversation_id": "conv-v23-2",
            "raw_query": "what do you mean high risk? i didn't ask anything like that?",
            "detected_language": "en",
            "parsed_intent": None,
            "device_location": None,
            "query_location": None,
            "resolved_location": {"name": "Mumbai", "lat": 18.9388, "lon": 72.8354, "coastal": True},
            "location_mode": "INHERITED",
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
            "conversation_history": [
                {"role": "user", "content": "is it safe to fish in Mumbai?"},
                {"role": "assistant", "content": "🔴 High risk right now."}
            ],
            "last_parsed_intent": {"intent": "MARINE_SAFETY_QUERY", "location_name": "Mumbai"},
            "last_results": {
                "risk_agent": {
                    "status": "success",
                    "data": {"risk_label": "HIGH", "composite_score": 70.0, "components": []}
                }
            },
            "previous_marine_assessment": {"risk_label": "HIGH", "composite_score": 70.0},
            "semantic_context": {},
            "changed_fields": [],
            "parse_method": "rule_based_fallback",
            "synthesis_method": "template_fallback",
            "data_quality_reports": [],
            "risk_sufficient_data": None,
            "user_location": None,
            "language_override": None,
        }

        output = detect_and_parse(state)
        parsed = output.get("parsed_intent") or {}
        
        self.assertEqual(parsed.get("intent"), "RISK_EXPLANATION")
        self.assertEqual(output.get("intent_subtype"), "WHAT_DOES_THIS_LEVEL_MEAN")
        # Must NOT request a brand new marine safety re-run
        self.assertFalse(parsed.get("needs_weather"))
        self.assertFalse(parsed.get("needs_risk"))

        # Test synthesis output for this sub-intent
        state.update(output)
        syn_out = synthesis(state)
        ans = syn_out.get("final_answer_text", "")
        self.assertIn("Mumbai", ans)
        self.assertIn("not because you asked for departure clearance", ans)

    def test_canonical_marine_snapshot_structure(self):
        """PRD §17: MarineSnapshot must have canonical keys and truthful sources."""
        snapshot = _build_marine_snapshot(
            resolved={"name": "Kochi", "lat": 9.9312, "lon": 76.2673, "coastal": True, "state": "Kerala", "district": "Ernakulam"},
            location_name="Kochi",
            lat=9.9312,
            lon=76.2673,
            is_coastal=True,
            weather={
                "status": "success",
                "data": {"wave_height_m": 1.2, "wind_speed_kmh": 18.0, "temperature_c": 29.0},
                "source": "Open-Meteo Marine",
                "timestamp": "2026-09-14T10:00:00Z"
            },
            ocean={
                "status": "success",
                "data": {"water_level_m": 0.55, "current_phase": "Rising"},
                "source": "INCOIS Tides",
                "timestamp": "2026-09-14T10:00:00Z"
            },
            pfz={
                "status": "success",
                "data": {"nearest_zone_km": 42.0, "overall_productivity": "moderate", "is_proxy": True},
                "source": "INCOIS Oceansat-2",
                "timestamp": "2026-09-14T10:00:00Z"
            },
            hazard={
                "status": "success",
                "data": {"active_warnings": ["rough_sea"], "overall_hazard_level": "moderate"},
                "source": "Open-Meteo & GDACS",
                "timestamp": "2026-09-14T10:00:00Z"
            },
            geofence={
                "status": "success",
                "data": {"distance_to_boundary_km": 140.0, "zone_status": "safe"},
                "source": "Tarang Geofence Engine",
                "timestamp": "2026-09-14T10:00:00Z"
            },
            risk={
                "status": "success",
                "data": {"composite_score": 38.0, "risk_label": "MODERATE", "components": []},
                "source": "Tarang Deterministic Risk Engine",
                "timestamp": "2026-09-14T10:00:00Z"
            },
            evidence=[],
            overall_data_status="live",
            change_summary={"has_changes": True, "changes": []}
        )

        self.assertEqual(snapshot["location"]["name"], "Kochi")
        self.assertEqual(snapshot["location"]["lat"], 9.9312)
        self.assertEqual(snapshot["weather"]["wave_height_m"], 1.2)
        self.assertEqual(snapshot["ocean"]["water_level_m"], 0.55)
        self.assertEqual(snapshot["pfz"]["nearest_zone_km"], 42.0)
        self.assertTrue(snapshot["pfz"]["is_proxy"])
        self.assertEqual(snapshot["risk"]["final_level"], "MODERATE")
        self.assertIsNotNone(snapshot["generated_at"])
        self.assertIn("change_summary", snapshot)


if __name__ == "__main__":
    unittest.main(verbosity=2)
