"""
test_conversational_response_regression.py
-----------------------------------------
Automated regression test suite verifying the Conversational Response Architecture:
1. Intent interpretation & capability matrix routing
2. AnswerPlan generation
3. Turn-by-turn conversational sequence (Delhi -> Delhi Weather -> Delhi Sea Level -> Mumbai Sea Level -> Mumbai Fishing -> Delhi Location)
4. Exact repeat query isolation
5. Response quality & Grounding constraints (no fake data, no marine assessment for simple queries)
"""

import json
import os
import sys
import unittest

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from starlette.testclient import TestClient
from main import app
from graph.build_graph import graph
from graph.nodes.detect_and_parse import classify_query_intent
from location.models import DeviceLocation


def parse_sse_events(response_text: str):
    """Helper to parse SSE text into list of (event, dict_or_str) tuples."""
    events = []
    current_event = "message"
    current_data = []

    for line in response_text.splitlines():
        if line.startswith("event:"):
            current_event = line.replace("event:", "").strip()
        elif line.startswith("data:"):
            current_data.append(line.replace("data:", "").strip())
        elif line == "":
            if current_data:
                data_str = "\n".join(current_data)
                try:
                    events.append((current_event, json.loads(data_str)))
                except Exception:
                    events.append((current_event, data_str))
                current_data = []
                current_event = "message"

    if current_data:
        data_str = "\n".join(current_data)
        try:
            events.append((current_event, json.loads(data_str)))
        except Exception:
            events.append((current_event, data_str))

    return events


class TestConversationalResponseRegression(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.delhi_device: DeviceLocation = {
            "lat": 28.74,
            "lon": 77.12,
            "accuracy": 10.0,
            "captured_at": "2026-09-14T00:00:00Z",
            "permission_status": "granted",
        }

    def test_01_intent_classification_unit_rules(self):
        """Verify regex classification for all core intent categories."""
        self.assertEqual(classify_query_intent("what is my location?")[0], "LOCATION_QUERY")
        self.assertEqual(classify_query_intent("where am I right now?")[0], "LOCATION_QUERY")
        self.assertEqual(classify_query_intent("tell me my coordinates")[0], "LOCATION_QUERY")
        self.assertEqual(classify_query_intent("current location")[0], "LOCATION_QUERY")

        self.assertEqual(classify_query_intent("what is the weather here?")[0], "WEATHER_QUERY")
        self.assertEqual(classify_query_intent("how is the wind speed and temperature?")[0], "WEATHER_QUERY")

        self.assertEqual(classify_query_intent("what is the sea level here?")[0], "WATER_LEVEL_QUERY")
        self.assertEqual(classify_query_intent("what is the sea level in Mumbai?")[0], "WATER_LEVEL_QUERY")
        self.assertEqual(classify_query_intent("when is high tide?")[0], "TIDE_QUERY")

        self.assertEqual(classify_query_intent("what is the atmospheric pressure?")[0], "SEA_LEVEL_PRESSURE_QUERY")
        self.assertEqual(classify_query_intent("barometric pressure at sea level")[0], "SEA_LEVEL_PRESSURE_QUERY")

        self.assertEqual(classify_query_intent("where are the fish?")[0], "PFZ_QUERY")
        self.assertEqual(classify_query_intent("show potential fishing zones near me")[0], "PFZ_QUERY")

        self.assertEqual(classify_query_intent("are there any cyclone alerts?")[0], "HAZARD_QUERY")
        self.assertEqual(classify_query_intent("high wave warning")[0], "HAZARD_QUERY")

        self.assertEqual(classify_query_intent("is it safe to fish?")[0], "MARINE_SAFETY_QUERY")
        self.assertEqual(classify_query_intent("can I go out to sea today?")[0], "MARINE_SAFETY_QUERY")

        # Contextual inheritance for relative/follow-up
        self.assertEqual(classify_query_intent("what about tomorrow?", last_intent="WEATHER_QUERY")[0], "WEATHER_QUERY")
        self.assertEqual(classify_query_intent("what about tomorrow?", last_intent="MARINE_SAFETY_QUERY")[0], "MARINE_SAFETY_QUERY")

    def test_02_graph_turn1_location_query(self):
        """Turn 1: 'What is my location?' must return direct location answer, NOT marine safety."""
        init_state = {
            "raw_query": "what is my location?",
            "conversation_id": "test-conv-loc-1",
            "device_location": self.delhi_device,
            "conversation_history": [],
        }
        output = graph.invoke(init_state)

        intent = output.get("parsed_intent", {})
        self.assertEqual(intent.get("intent_name"), "LOCATION_QUERY")
        self.assertEqual(intent.get("query_type"), "location_only")
        self.assertFalse(intent.get("needs_weather"))
        self.assertFalse(intent.get("needs_ocean"))
        self.assertFalse(intent.get("needs_pfz"))
        self.assertFalse(intent.get("needs_hazard"))
        self.assertFalse(intent.get("needs_risk"))

        plan = intent.get("answer_plan", {})
        self.assertEqual(plan.get("response_mode"), "factual_direct")
        self.assertEqual(plan.get("presentation_hint"), "location_card")

        ans = output.get("final_answer_text", "")
        self.assertIn("28.74", ans)
        self.assertIn("77.12", ans)
        # Quality rule: Must NOT include marine assessment boilerplate
        self.assertNotIn("marine safety assessment", ans.lower())
        self.assertNotIn("fishing assessment", ans.lower())
        self.assertNotIn("not applicable for fishing", ans.lower())

    def test_03_graph_turn2_weather_query_inland(self):
        """Turn 2: 'What is the weather here?' runs weather agent only, no ocean/pfz/risk."""
        init_state = {
            "raw_query": "what is the weather here?",
            "conversation_id": "test-conv-weather-2",
            "device_location": self.delhi_device,
            "conversation_history": [],
        }
        output = graph.invoke(init_state)

        intent = output.get("parsed_intent", {})
        self.assertEqual(intent.get("intent_name"), "WEATHER_QUERY")
        self.assertTrue(intent.get("needs_weather"))
        self.assertFalse(intent.get("needs_ocean"))
        self.assertFalse(intent.get("needs_pfz"))
        self.assertFalse(intent.get("needs_risk"))

        plan = intent.get("answer_plan", {})
        self.assertEqual(plan.get("response_mode"), "specialist_card")
        self.assertEqual(plan.get("presentation_hint"), "weather_card")

        ans = output.get("final_answer_text", "")
        # Weather data present
        self.assertTrue(any(term in ans.lower() for term in ["temperature", "wind", "weather", "celsius", "km/h", "°c"]))
        # Ocean/PFZ/Risk must NOT be in text
        self.assertNotIn("chart datum", ans.lower())
        self.assertNotIn("potential fishing zone", ans.lower())
        self.assertNotIn("composite risk", ans.lower())

    def test_04_graph_turn3_sea_level_inland(self):
        """Turn 3: 'What is the sea level here?' at Delhi gives scientific applicability notice."""
        init_state = {
            "raw_query": "what is the sea level here?",
            "conversation_id": "test-conv-sealevel-inland-3",
            "device_location": self.delhi_device,
            "conversation_history": [],
        }
        output = graph.invoke(init_state)

        intent = output.get("parsed_intent", {})
        self.assertEqual(intent.get("intent_name"), "WATER_LEVEL_QUERY")
        self.assertFalse(intent.get("needs_ocean"))

        plan = intent.get("answer_plan", {})
        self.assertEqual(plan.get("response_mode"), "applicability_explanation")
        self.assertEqual(plan.get("presentation_hint"), "applicability_card")

        ans = output.get("final_answer_text", "")
        self.assertIn("inland", ans.lower())
        self.assertTrue("tide gauge" in ans.lower() or "datum" in ans.lower() or "tidal" in ans.lower() or "coastal" in ans.lower())
        # Must suggest coastal ports
        self.assertTrue(any(port in ans.lower() for port in ["mumbai", "kochi", "chennai", "thoothukudi"]))
        # Must NOT claim sea level does not exist
        self.assertNotIn("sea level does not exist", ans.lower())

    def test_05_graph_turn4_sea_level_mumbai(self):
        """Turn 4: 'What is the sea level in Mumbai?' runs ocean agent for Mumbai."""
        init_state = {
            "raw_query": "what is the sea level in Mumbai?",
            "conversation_id": "test-conv-sealevel-mumbai-4",
            "device_location": self.delhi_device,
            "conversation_history": [],
        }
        output = graph.invoke(init_state)

        resolved = output.get("resolved_location", {})
        self.assertEqual(resolved.get("name"), "Mumbai")
        self.assertTrue(resolved.get("coastal"))

        intent = output.get("parsed_intent", {})
        self.assertEqual(intent.get("intent_name"), "WATER_LEVEL_QUERY")
        self.assertTrue(intent.get("needs_ocean"))

        plan = intent.get("answer_plan", {})
        self.assertEqual(plan.get("response_mode"), "specialist_card")
        self.assertEqual(plan.get("presentation_hint"), "ocean_card")

        ans = output.get("final_answer_text", "")
        self.assertIn("mumbai", ans.lower())
        self.assertTrue(any(term in ans.lower() for term in ["tide", "water level", "chart datum", "m"]))

    def test_06_e2e_full_conversation_and_repeat_query(self):
        """End-to-end multi-turn sequence via HTTP POST /query SSE."""
        conv_id = f"test-e2e-conv-{os.urandom(4).hex()}"

        # ── Turn 1: "what is my location?"
        resp1 = self.client.post("/query", json={
            "query": "what is my location?",
            "conversation_id": conv_id,
            "request_id": "req-1",
            "device_location": self.delhi_device,
        })
        self.assertEqual(resp1.status_code, 200)
        events1 = parse_sse_events(resp1.text)
        result1 = [d for e, d in events1 if e == "result"][0]

        self.assertEqual(result1["response_mode"], "factual_direct")
        self.assertEqual(result1["answer_plan"]["presentation_hint"], "location_card")
        self.assertIn("28.74", result1["answer_text"])
        self.assertIsNone(result1.get("risk_data"))  # Risk data gated out

        # ── Exact repeat query: "what is my location?"
        resp1_repeat = self.client.post("/query", json={
            "query": "what is my location?",
            "conversation_id": conv_id,
            "request_id": "req-1-rep",
            "device_location": self.delhi_device,
        })
        self.assertEqual(resp1_repeat.status_code, 200)
        events1_rep = parse_sse_events(resp1_repeat.text)
        result1_rep = [d for e, d in events1_rep if e == "result"][0]
        self.assertEqual(result1_rep["response_mode"], "factual_direct")
        self.assertIn("28.74", result1_rep["answer_text"])

        # ── Turn 2: "what is the weather here?"
        resp2 = self.client.post("/query", json={
            "query": "what is the weather here?",
            "conversation_id": conv_id,
            "request_id": "req-2",
            "device_location": self.delhi_device,
        })
        self.assertEqual(resp2.status_code, 200)
        events2 = parse_sse_events(resp2.text)
        result2 = [d for e, d in events2 if e == "result"][0]
        self.assertEqual(result2["response_mode"], "specialist_card")
        self.assertEqual(result2["answer_plan"]["presentation_hint"], "weather_card")
        self.assertIsNone(result2.get("risk_data"))

        # ── Turn 3: "what is the sea level here?"
        resp3 = self.client.post("/query", json={
            "query": "what is the sea level here?",
            "conversation_id": conv_id,
            "request_id": "req-3",
            "device_location": self.delhi_device,
        })
        self.assertEqual(resp3.status_code, 200)
        events3 = parse_sse_events(resp3.text)
        result3 = [d for e, d in events3 if e == "result"][0]
        self.assertEqual(result3["response_mode"], "applicability_explanation")
        self.assertEqual(result3["answer_plan"]["presentation_hint"], "applicability_card")
        self.assertIn("inland", result3["answer_text"].lower())

        # ── Turn 4: "what is the sea level in Mumbai?"
        resp4 = self.client.post("/query", json={
            "query": "what is the sea level in Mumbai?",
            "conversation_id": conv_id,
            "request_id": "req-4",
            "device_location": self.delhi_device,
        })
        self.assertEqual(resp4.status_code, 200)
        events4 = parse_sse_events(resp4.text)
        result4 = [d for e, d in events4 if e == "result"][0]
        self.assertEqual(result4["response_mode"], "specialist_card")
        self.assertEqual(result4["answer_plan"]["presentation_hint"], "ocean_card")
        self.assertEqual(result4["location"]["resolved"]["name"], "Mumbai")

        # ── Turn 5: "is it safe to fish there?"
        resp5 = self.client.post("/query", json={
            "query": "is it safe to fish there?",
            "conversation_id": conv_id,
            "request_id": "req-5",
            "device_location": self.delhi_device,
        })
        self.assertEqual(resp5.status_code, 200)
        events5 = parse_sse_events(resp5.text)
        result5 = [d for e, d in events5 if e == "result"][0]
        self.assertEqual(result5["response_mode"], "safety_assessment")
        self.assertEqual(result5["answer_plan"]["presentation_hint"], "safety_card")
        self.assertEqual(result5["location"]["resolved"]["name"], "Mumbai")
        self.assertIsNotNone(result5.get("risk_data"))
        self.assertIn(result5["risk_data"]["risk_label"], ["LOW", "MODERATE", "HIGH", "EXTREME", "UNKNOWN"])

        # ── Turn 6: Switch back to "what is my location?"
        resp6 = self.client.post("/query", json={
            "query": "what is my location?",
            "conversation_id": conv_id,
            "request_id": "req-6",
            "device_location": self.delhi_device,
        })
        self.assertEqual(resp6.status_code, 200)
        events6 = parse_sse_events(resp6.text)
        result6 = [d for e, d in events6 if e == "result"][0]
        self.assertEqual(result6["response_mode"], "factual_direct")
        self.assertEqual(result6["answer_plan"]["presentation_hint"], "location_card")
        self.assertIn("28.74", result6["answer_text"])
        self.assertIsNone(result6.get("risk_data"))


if __name__ == "__main__":
    unittest.main()
