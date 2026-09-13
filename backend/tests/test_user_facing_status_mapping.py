"""
test_user_facing_status_mapping.py
----------------------------------
Verifies that all internal pipeline error codes and technical agent statuses
are cleanly translated into user-facing product language (PRD §10, §11, §13, §57, §58).
"""

import os
import sys
import unittest

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from graph.nodes.synthesis import _render_template, _PHRASES
from graph.state import AgentResult, EvidenceItem


class TestUserFacingStatusMapping(unittest.TestCase):

    def test_no_internal_agent_error_strings_leak(self):
        """PRD §10 & §11: Errors must be translated to 'Live X data is currently unavailable'."""
        failed_weather: AgentResult = {
            "agent_name": "weather_agent",
            "status": "error",
            "execution_status": "failed",
            "data_status": "unavailable",
            "data": {},
            "source": "Open-Meteo",
            "summary": "Network timeout to Open-Meteo API",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "",
            "error": "HTTP_504_GATEWAY_TIMEOUT",
            "evidence": [],
        }

        output = _render_template(
            lang="en",
            location="Kochi",
            time_window="now",
            weather=failed_weather,
            pfz=None,
            hazard=None,
            geofence=None,
            risk=None,
            evidence=[],
        )

        # Forbidden technical leaks
        self.assertNotIn("Weather agent encountered an error", output)
        self.assertNotIn("HTTP_504", output)
        self.assertNotIn("GATEWAY_TIMEOUT", output)
        self.assertNotIn("execution_status", output)

        # Expected calm product message
        self.assertIn("Live marine weather data is currently unavailable", output)

    def test_partial_assessment_when_pfz_unavailable(self):
        """PRD §58: Partial Assessment when PFZ data is unavailable."""
        success_weather: AgentResult = {
            "agent_name": "weather_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "data": {
                "wave_height_m": 1.2,
                "wind_speed_kmh": 14.5,
                "sea_state": "slight",
            },
            "source": "Open-Meteo",
            "summary": "Favorable wave height",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "2026-09-14T00:00:00Z",
            "error": None,
            "evidence": [],
        }

        unavail_pfz: AgentResult = {
            "agent_name": "pfz_agent",
            "status": "insufficient_data",
            "execution_status": "failed",
            "data_status": "unavailable",
            "data": {},
            "source": "INCOIS ERDDAP",
            "summary": "Live PFZ telemetry offline",
            "used_fallback": False,
            "data_quality": "live",
            "timestamp": "",
            "error": "LIVE_PFZ_UNAVAILABLE",
            "evidence": [],
        }

        output = _render_template(
            lang="en",
            location="Kochi",
            time_window="today",
            weather=success_weather,
            pfz=unavail_pfz,
            hazard=None,
            geofence=None,
            risk=None,
            evidence=[],
        )

        self.assertNotIn("LIVE_PFZ_UNAVAILABLE", output)
        self.assertNotIn("PFZ agent encountered an error", output)
        self.assertIn("Live fishing zone (PFZ) data is currently unavailable", output)
        self.assertIn("Fishing-zone suitability could not be assessed because PFZ data is unavailable", output)
        self.assertIn("Partial Assessment", output)


if __name__ == "__main__":
    unittest.main()
