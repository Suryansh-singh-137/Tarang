"""
test_sst_agent.py
-----------------
Unit tests for the INCOIS ERDDAP SST Agent, SST Client, and Marine Snapshot integration.

Verifies:
1. Fail-closed contract: No mock data fabricated on ERDDAP network/timeout failures.
2. Mandatory disclaimer: Every SST result contains the scientific disclaimer that SST
   does NOT guarantee fish presence.
3. INCOIS ERDDAP response parsing: Correct extraction of sst, anom, and observation time.
4. SST Agent node adheres to Global Agent Contract v2.1.
5. Inland gating: SST agent skips gracefully for inland locations.
6. Marine Snapshot integration: snapshot['sst'] accurately reflects agent result.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from tools.sst_client import fetch_sst_and_anomaly, SST_DISCLAIMER
from graph.nodes.sst_agent import sst_agent
from graph.nodes.synthesis import _build_marine_snapshot
from graph.state import AgentResult


class TestSSTAgentAndClient(unittest.TestCase):

    def test_sst_disclaimer_invariant(self):
        """Verify the mandatory disclaimer text is present and explicit."""
        self.assertIn("guarantee fish presence", SST_DISCLAIMER.lower())
        self.assertIn("sea surface temperature", SST_DISCLAIMER.lower())

    @patch("httpx.Client")
    def test_client_successful_response(self, mock_client_cls):
        """Verify successful ERDDAP JSON parsing extracts sst and anomaly."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "table": {
                "columnNames": ["time", "latitude", "longitude", "sst", "anom"],
                "rows": [
                    ["2026-09-14T12:00:00Z", 9.93, 76.26, 29.35, 0.45]
                ]
            }
        }
        mock_resp.raise_for_status.return_value = None
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        # Clear cache for isolated testing
        from tools import sst_client
        sst_client._sst_cache.clear()

        res = fetch_sst_and_anomaly(9.93, 76.26)
        self.assertTrue(res["success"])
        self.assertEqual(res["data_status"], "live")
        self.assertEqual(res["sst_celsius"], 29.35)
        self.assertEqual(res["sst_anomaly_c"], 0.45)
        self.assertEqual(res["observation_time"], "2026-09-14T12:00:00Z")
        self.assertIn("INCOIS ERDDAP", res["source"])
        self.assertEqual(res["disclaimer"], SST_DISCLAIMER)

    @patch("httpx.Client")
    def test_client_fail_closed_no_mock_data(self, mock_client_cls):
        """CRITICAL: On ERDDAP network failure, must return unavailable and NEVER fabricate mock numbers."""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.side_effect = Exception("Connection timed out (503)")
        mock_client_cls.return_value = mock_client

        from tools import sst_client
        sst_client._sst_cache.clear()

        res = fetch_sst_and_anomaly(9.93, 76.26)
        self.assertFalse(res["success"])
        self.assertEqual(res["data_status"], "unavailable")
        self.assertIsNone(res["sst_celsius"])
        self.assertIsNone(res["sst_anomaly_c"])
        self.assertIsNone(res["observation_time"])
        self.assertIn("unavailable", res["error"].lower())
        # Disclaimer must still be present
        self.assertEqual(res["disclaimer"], SST_DISCLAIMER)

    def test_agent_inland_location_skip(self):
        """Inland locations must be skipped gracefully with reason INLAND_LOCATION."""
        state = {
            "resolved_location": {
                "name": "Delhi",
                "lat": 28.6139,
                "lon": 77.2090,
                "coastal": False,
                "nearest_coast_km": 1100.0,
            }
        }
        res_state = sst_agent(state)
        self.assertIn("sst_result", res_state)
        sst_res = res_state["sst_result"]
        self.assertEqual(sst_res["execution_status"], "skipped")
        self.assertEqual(sst_res["skip_reason"], "INLAND_LOCATION")
        self.assertEqual(sst_res["data_status"], "not_applicable")
        self.assertIsNone(sst_res["data"]["sst_celsius"])

    @patch("graph.nodes.sst_agent.fetch_sst_and_anomaly")
    def test_agent_contract_compliance(self, mock_fetch):
        """Verify sst_agent returns strict V2.1 AgentResult contract."""
        mock_fetch.return_value = {
            "success": True,
            "sst_celsius": 28.7,
            "sst_anomaly_c": -0.2,
            "observation_time": "2026-09-15T00:00:00Z",
            "source": "INCOIS ERDDAP (NOAA AVHRR/AMSR SST)",
            "data_status": "live",
            "disclaimer": SST_DISCLAIMER,
        }

        state = {
            "resolved_location": {
                "name": "Kochi",
                "lat": 9.9312,
                "lon": 76.2673,
                "coastal": True,
            }
        }
        res_state = sst_agent(state)
        sst_res = res_state["sst_result"]

        # Check required V2.1 fields
        self.assertIn(sst_res["execution_status"], ("ok", "success"))
        self.assertEqual(sst_res["data_status"], "live")
        self.assertIsNotNone(sst_res["location_used"])
        self.assertEqual(sst_res["location_used"]["lat"], 9.9312)
        self.assertEqual(sst_res["observed_at"], "2026-09-15T00:00:00Z")
        self.assertIn("INCOIS ERDDAP", sst_res["source"])
        self.assertIn("guarantee fish presence", sst_res["disclaimer"].lower())
        self.assertEqual(sst_res["data"]["sst_celsius"], 28.7)
        self.assertEqual(sst_res["data"]["sst_anomaly_c"], -0.2)

    def test_marine_snapshot_sst_integration(self):
        """Verify _build_marine_snapshot includes the sst dictionary with all required keys."""
        sst_agent_result: AgentResult = {
            "agent_name": "sst_agent",
            "status": "success",
            "execution_status": "success",
            "data_status": "live",
            "location_used": {"name": "Kochi", "lat": 9.9312, "lon": 76.2673},
            "observed_at": "2026-09-15T00:00:00Z",
            "source": "INCOIS ERDDAP (NOAA AVHRR/AMSR SST)",
            "disclaimer": SST_DISCLAIMER,
            "data": {
                "sst_celsius": 29.1,
                "sst_anomaly_c": 0.3,
                "observation_time": "2026-09-15T00:00:00Z",
                "source": "INCOIS ERDDAP (NOAA AVHRR/AMSR SST)",
                "data_status": "live",
                "disclaimer": SST_DISCLAIMER,
            },
        }

        snapshot = _build_marine_snapshot(
            weather=None,
            ocean=None,
            hazard=None,
            pfz=None,
            geofence=None,
            sst=sst_agent_result,
        )

        self.assertIn("sst", snapshot)
        sst_snap = snapshot["sst"]
        self.assertIsNotNone(sst_snap)
        self.assertEqual(sst_snap["sst_celsius"], 29.1)
        self.assertEqual(sst_snap["sst_anomaly_c"], 0.3)
        self.assertEqual(sst_snap["observation_time"], "2026-09-15T00:00:00Z")
        self.assertIn("INCOIS ERDDAP", sst_snap["source"])
        self.assertEqual(sst_snap["data_status"], "live")
        self.assertIn("guarantee fish presence", sst_snap["disclaimer"].lower())


if __name__ == "__main__":
    unittest.main()
