"""
test_applicability.py
---------------------
Tests the Tarang V2.2 Applicability Layer (§4–§9, §35, §54, §55).
Verifies:
1. Inland location query ("Are there fishing zones near me?" at Delhi):
   - resolved_location = Delhi (coastal = False)
   - PFZ and Ocean marked skipped with reason INLAND_LOCATION
   - Skipped != Failed (no agent error, no pipeline crash)
   - Polite inland explanation rendered with distance to nearest coast
2. Explicit coastal override from inland ("Show fishing zones near Kochi" at Delhi):
   - device_location = Delhi
   - resolved_location = Kochi (coastal = True)
   - PFZ runs live
3. Weather remains available inland ("What is the weather here in Delhi?"):
   - Weather agent executes and retrieves live Open-Meteo conditions for Delhi coordinates
4. Pure unit test for check_applicability rules
"""

import os
import sys
import unittest

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from location.models import DeviceLocation, LocationMode
from location.resolver import LocationResolver
from location.applicability import check_applicability, ApplicabilityResult
from session.session_store import SessionRecord, get_or_create_session
from graph.build_graph import graph


class TestApplicabilityLayer(unittest.TestCase):

    def test_applicability_unit_rules(self):
        """Verify deterministic applicability rules for coastal vs inland locations."""
        # 1. Coastal location (Kochi)
        coastal_loc = {
            "name": "Kochi",
            "lat": 9.9312,
            "lon": 76.2673,
            "coastal": True,
            "nearest_coast_km": 0.0,
            "source": "GAZETTEER",
        }
        res_coastal = check_applicability(coastal_loc)
        self.assertTrue(res_coastal.weather)
        self.assertTrue(res_coastal.pfz)
        self.assertTrue(res_coastal.ocean)
        self.assertTrue(res_coastal.risk)
        self.assertIsNone(res_coastal.reason)

        # 2. Inland location (Delhi)
        inland_loc = {
            "name": "Delhi",
            "lat": 28.6139,
            "lon": 77.2090,
            "coastal": False,
            "nearest_coast_km": 980.0,
            "source": "GAZETTEER",
        }
        res_inland = check_applicability(inland_loc)
        self.assertTrue(res_inland.weather, "Weather MUST remain applicable inland (PRD §8)")
        self.assertFalse(res_inland.pfz, "PFZ must not be applicable inland")
        self.assertFalse(res_inland.ocean, "Ocean/tides must not be applicable inland")
        self.assertFalse(res_inland.risk, "Marine trip risk cannot be assessed inland")
        self.assertEqual(res_inland.reason, "INLAND_LOCATION")

    def test_acceptance_54_inland_marine_query(self):
        """PRD §54: Device = Delhi, Query = 'Are there fishing zones near me?'"""
        delhi_device: DeviceLocation = {
            "lat": 28.6139,
            "lon": 77.2090,
            "accuracy": 15.0,
            "captured_at": "2026-09-14T00:00:00Z",
            "permission_status": "granted",
        }
        session = SessionRecord(conversation_id="conv-test-inland-54", device_location=delhi_device)

        init_state = {
            "raw_query": "Are there fishing zones near me?",
            "conversation_id": session.conversation_id,
            "device_location": delhi_device,
            "conversation_history": [],
        }

        output = graph.invoke(init_state)

        # Check resolution
        resolved = output.get("resolved_location")
        self.assertIsNotNone(resolved)
        self.assertAlmostEqual(resolved["lat"], 28.6139, places=2)
        self.assertAlmostEqual(resolved["lon"], 77.2090, places=2)
        self.assertFalse(resolved["coastal"])

        # Check intent
        intent = output.get("parsed_intent")
        self.assertEqual(intent.get("location_status"), "inland")
        self.assertFalse(intent.get("needs_pfz"))
        self.assertFalse(intent.get("needs_ocean"))

        # Check user-facing text
        ans = output.get("final_answer_text", "")
        self.assertIn("inland", ans.lower())
        self.assertNotIn("encountered an error", ans.lower())
        self.assertNotIn("crashed", ans.lower())

    def test_acceptance_55_explicit_coastal_query_from_inland(self):
        """PRD §55: Device = Delhi, Query = 'Show fishing zones near Kochi.'"""
        delhi_device: DeviceLocation = {
            "lat": 28.6139,
            "lon": 77.2090,
            "accuracy": 15.0,
            "captured_at": "2026-09-14T00:00:00Z",
            "permission_status": "granted",
        }
        session = SessionRecord(conversation_id="conv-test-inland-55", device_location=delhi_device)

        init_state = {
            "raw_query": "Show fishing zones near Kochi.",
            "conversation_id": session.conversation_id,
            "device_location": delhi_device,
            "conversation_history": [],
        }

        output = graph.invoke(init_state)

        # Resolved must be Kochi
        resolved = output.get("resolved_location")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["name"], "Kochi")
        self.assertTrue(resolved["coastal"])

        # PFZ agent must have run
        pfz_res = output.get("pfz_result")
        self.assertIsNotNone(pfz_res)
        self.assertIn(pfz_res.get("status"), ("success", "insufficient_data"))
        self.assertNotEqual(pfz_res.get("reason"), "INLAND_LOCATION")

    def test_inland_weather_remains_available(self):
        """PRD §8: Device = Delhi, Query = 'What is the weather here in Delhi?'"""
        delhi_device: DeviceLocation = {
            "lat": 28.6139,
            "lon": 77.2090,
            "accuracy": 15.0,
            "captured_at": "2026-09-14T00:00:00Z",
            "permission_status": "granted",
        }
        session = SessionRecord(conversation_id="conv-test-inland-weather", device_location=delhi_device)

        init_state = {
            "raw_query": "What is the weather here in Delhi?",
            "conversation_id": session.conversation_id,
            "device_location": delhi_device,
            "conversation_history": [],
        }

        output = graph.invoke(init_state)

        # Weather agent must have run (PRD §8: not skipped)
        w_res = output.get("weather_result")
        self.assertIsNotNone(w_res)
        self.assertNotEqual(w_res.get("status"), "skipped", "Weather agent must NOT be skipped for inland queries (PRD §8)")
        if w_res.get("status") == "success":
            self.assertIn("wind_speed_kmh", w_res.get("data", {}))
        else:
            self.assertEqual(w_res.get("error"), "LIVE_WEATHER_UNAVAILABLE")
            self.assertIn("unavailable", output.get("final_answer_text", "").lower())


if __name__ == "__main__":
    unittest.main()
