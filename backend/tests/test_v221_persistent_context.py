"""
test_v221_persistent_context.py
--------------------------------
Regression tests for V2.2.1 — Persistent Conversational Context & Follow-Up Reasoning:
  Turn 1: "what is the sea level in Mumbai?" → Mumbai tide / ocean card
  Turn 2: "is it safe to fish there?" → Mumbai safety assessment (LOW/HIGH/etc.)
  Turn 3: "why is the risk that level?" → explain Turn 2's risk breakdown (zero live APIs)
  Turn 4: "what about the lightning warning?" → explain Turn 2's hazard/warning in Mumbai
  Turn 5: "is it still safe now?" → rerun live data and calculate a fresh risk for Mumbai
  Turn 6: "what is my location?" → Delhi/device location factual coordinates
"""

import json
import unittest
from fastapi.testclient import TestClient
from main import app
from session import get_or_create_session, clear_session


class TestV221PersistentContext(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.conv_id = "test-v221-suite-conv"
        self.delhi_device = {
            "lat": 28.74,
            "lon": 77.12,
            "accuracy": 15.0,
            "captured_at": "2026-09-14T03:00:00Z",
            "permission_status": "granted",
        }
        clear_session(self.conv_id)

    def tearDown(self):
        clear_session(self.conv_id)

    def _query(self, text: str) -> dict:
        """Send streaming query and extract final result event payload."""
        payload = {
            "query": text,
            "conversation_id": self.conv_id,
            "device_location": self.delhi_device,
        }
        with self.client.stream("POST", "/query", json=payload) as resp:
            self.assertEqual(resp.status_code, 200)
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if "answer_text" in data:
                        return data
        self.fail(f"No result event received for query: {text!r}")

    def test_6_turn_conversational_context_pipeline(self):
        # -------------------------------------------------------------------
        # TURN 1: "what is the sea level in Mumbai?"
        # -------------------------------------------------------------------
        r1 = self._query("what is the sea level in Mumbai?")
        parsed_1 = r1.get("parsed_intent") or {}
        self.assertEqual(parsed_1.get("intent"), "WATER_LEVEL_QUERY")
        resolved_1 = (r1.get("location") or {}).get("resolved") or {}
        self.assertEqual(resolved_1.get("name"), "Mumbai")
        # Turn 1 must NOT provide fishing safety advice or composite risk score
        self.assertIsNone(r1.get("risk_data"))
        self.assertIn("Mumbai", r1.get("answer_text", ""))

        # -------------------------------------------------------------------
        # TURN 2: "is it safe to fish there?"
        # "there" inherits Mumbai; runs full marine safety stack
        # -------------------------------------------------------------------
        r2 = self._query("is it safe to fish there?")
        parsed_2 = r2.get("parsed_intent") or {}
        self.assertIn(parsed_2.get("intent"), ("MARINE_SAFETY_QUERY", "TRIP_QUERY"))
        resolved_2 = (r2.get("location") or {}).get("resolved") or {}
        self.assertEqual(resolved_2.get("name"), "Mumbai")
        # Turn 2 MUST have risk_data and safety assessment
        risk_2 = r2.get("risk_data")
        self.assertIsNotNone(risk_2, "Turn 2 should include composite risk_data")
        self.assertIn("composite_score", risk_2)
        self.assertIn("risk_label", risk_2)
        score_2 = risk_2["composite_score"]

        # Check session semantic memory populated
        session = get_or_create_session(self.conv_id)
        self.assertIsNotNone(session.last_marine_assessment)
        self.assertEqual(session.last_marine_assessment["composite_score"], score_2)
        self.assertIn("risk_agent", session.last_results)

        # -------------------------------------------------------------------
        # TURN 3: "why is the risk that level?"
        # Must explain Turn 2's risk breakdown WITHOUT re-fetching or erroring
        # -------------------------------------------------------------------
        r3 = self._query("why is the risk that level?")
        parsed_3 = r3.get("parsed_intent") or {}
        self.assertEqual(parsed_3.get("intent"), "RISK_EXPLANATION")
        t3_text = r3.get("answer_text", "")
        self.assertNotIn("No previous risk assessment is available", t3_text)
        self.assertIn("breakdown", t3_text.lower())
        # Factors must be present
        self.assertTrue(
            any(k in t3_text for k in ("Wave Height", "Wind Speed", "Hazard Level", "Boundary Proximity")),
            f"Explanation should name risk factors: {t3_text}"
        )
        # Session cache must NOT have been cleared by Turn 3!
        session = get_or_create_session(self.conv_id)
        self.assertIn("risk_agent", session.last_results)
        self.assertIn("hazard_agent", session.last_results)

        # -------------------------------------------------------------------
        # TURN 4: "what about the lightning warning?"
        # Must address lightning/hazard status in Mumbai using cached/assessment context
        # -------------------------------------------------------------------
        r4 = self._query("what about the lightning warning?")
        parsed_4 = r4.get("parsed_intent") or {}
        self.assertEqual(parsed_4.get("intent"), "HAZARD_QUERY")
        resolved_4 = (r4.get("location") or {}).get("resolved") or {}
        self.assertEqual(resolved_4.get("name"), "Mumbai")
        t4_text = r4.get("answer_text", "")
        self.assertTrue(
            any(term in t4_text.lower() for term in ("hazard", "lightning", "warning", "precipitation", "rain")),
            f"Hazard response should mention hazard conditions: {t4_text}"
        )

        # -------------------------------------------------------------------
        # TURN 5: "is it still safe now?"
        # Must inherit Mumbai (not Still Coffee!) and re-evaluate live data
        # -------------------------------------------------------------------
        r5 = self._query("is it still safe now?")
        parsed_5 = r5.get("parsed_intent") or {}
        self.assertIn(parsed_5.get("intent"), ("MARINE_SAFETY_QUERY", "TRIP_QUERY"))
        resolved_5 = (r5.get("location") or {}).get("resolved") or {}
        self.assertEqual(resolved_5.get("name"), "Mumbai", "Turn 5 must inherit Mumbai, not geocode 'still'")
        risk_5 = r5.get("risk_data")
        self.assertIsNotNone(risk_5, "Turn 5 must re-evaluate and return risk_data")
        self.assertIn("composite_score", risk_5)
        self.assertIn("risk_label", risk_5)

        # -------------------------------------------------------------------
        # TURN 6: "what is my location?"
        # Hard override to Delhi device location without marine boilerplate
        # -------------------------------------------------------------------
        r6 = self._query("what is my location?")
        parsed_6 = r6.get("parsed_intent") or {}
        self.assertEqual(parsed_6.get("intent"), "LOCATION_QUERY")
        t6_text = r6.get("answer_text", "")
        self.assertIn("28.74", t6_text)
        self.assertIn("77.12", t6_text)
        self.assertNotIn("Here is Tarang's marine safety assessment", t6_text)


if __name__ == "__main__":
    unittest.main()
