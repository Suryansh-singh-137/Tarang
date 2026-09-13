"""
Automated Test Suite for Tarang V2 Location-Aware Architecture,
State Management, and Multi-Turn Golden Regression Sequence.

Can be run via:
  python tests/test_v2_location_architecture.py
"""

import json
import os
import sys
import httpx

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from location.models import DeviceLocation, LocationMode
from location.resolver import LocationResolver
from session.session_store import SessionRecord, get_or_create_session, save_session


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


# ── UNIT TESTS: LocationResolver ─────────────────────────────────────────────

def test_resolver_unit_suite():
    print("\n--- Running LocationResolver Unit Tests ---")

    # 1. Hard override for relative keywords ("here", "near me")
    session1 = SessionRecord(conversation_id="u1")
    session1.last_query_location = {
        "lat": 18.92, "lon": 72.83, "name": "Mumbai Harbour", "coastal": True, "source": "explicit_text"
    }
    device_kochi: DeviceLocation = {"lat": 9.9312, "lon": 76.2673, "accuracy": None, "captured_at": None, "permission_status": "granted"}

    mode1, q_loc1, resolved1 = LocationResolver.resolve("weather here", device_location=device_kochi, session=session1)
    assert mode1 == "DEVICE", f"Expected mode DEVICE, got {mode1}"
    assert resolved1 is not None, "Expected resolved location for Kochi device"
    assert "kochi" in resolved1["name"].lower() or "kerala" in str(resolved1.get("state", "")).lower()
    assert abs(resolved1["lat"] - 9.9312) < 0.2
    assert abs(resolved1["lon"] - 76.2673) < 0.2
    print("  [PASS] Relative keyword 'here' hard overrides to device_location (Kochi), ignoring Mumbai in session")

    # 2. Relative query without device GPS prompts clarification (NEVER falls back)
    session2 = SessionRecord(conversation_id="u2")
    session2.last_query_location = {
        "lat": 18.92, "lon": 72.83, "name": "Mumbai Harbour", "coastal": True, "source": "explicit_text"
    }
    mode2, q_loc2, resolved2 = LocationResolver.resolve("weather near me", device_location=None, session=session2)
    assert mode2 == "DEVICE", f"Expected mode DEVICE, got {mode2}"
    assert resolved2 is None, f"Expected resolved=None for missing device, got {resolved2}"
    print("  [PASS] 'near me' without device GPS returns resolved=None (controlled clarification, no fallback)")

    # 3. Explicit coastal place
    session3 = SessionRecord(conversation_id="u3")
    mode3, q_loc3, resolved3 = LocationResolver.resolve("is it safe to fish in Mumbai?", device_location=None, session=session3)
    assert mode3 == "EXPLICIT_PLACE", f"Expected EXPLICIT_PLACE, got {mode3}"
    assert resolved3 is not None
    assert "mumbai" in resolved3["name"].lower()
    assert resolved3["coastal"] is True
    print("  [PASS] Explicit coastal place 'Mumbai' resolved correctly")

    # 4. Explicit inland place
    session4 = SessionRecord(conversation_id="u4")
    mode4, q_loc4, resolved4 = LocationResolver.resolve("weather in New Delhi", device_location=None, session=session4)
    assert mode4 == "EXPLICIT_PLACE", f"Expected EXPLICIT_PLACE, got {mode4}"
    assert resolved4 is not None
    assert resolved4["coastal"] is False
    print("  [PASS] Explicit inland place 'New Delhi' resolved with coastal=False")

    # 5. Contextual continuation inherits session's last explicit location
    session5 = SessionRecord(conversation_id="u5")
    session5.last_query_location = {
        "lat": 18.92, "lon": 72.83, "name": "Mumbai Harbour", "coastal": True, "source": "explicit_text", "confidence": 1.0
    }
    mode5, q_loc5, resolved5 = LocationResolver.resolve("what about tomorrow morning?", device_location=device_kochi, session=session5)
    assert mode5 == "INHERITED", f"Expected INHERITED, got {mode5}"
    assert resolved5 is not None
    assert "mumbai" in resolved5["name"].lower()
    print("  [PASS] Contextual continuation 'what about tomorrow morning?' inherits Mumbai from session")


# ── FULL PIPELINE: Multi-Turn Golden Regression Sequence ─────────────────────

def test_golden_sequence_e2e():
    print("\n--- Running Multi-Turn Golden Regression Sequence (E2E) ---")
    base_url = "http://127.0.0.1:8000"
    client = httpx.Client(base_url=base_url, timeout=30.0)

    conv_id = f"test-golden-conv-{os.urandom(4).hex()}"
    device_loc = {
        "lat": 9.9312,
        "lon": 76.2673,
        "permission_status": "granted",
    }

    # ── Turn 1: Device=Kochi, "weather here" ─────────────────────────────────
    print("  Testing Turn 1: Device=Kochi, query='weather here'...")
    req1_id = f"req-1-{os.urandom(3).hex()}"
    resp1 = client.post("/query", json={
        "query": "weather here",
        "conversation_id": conv_id,
        "request_id": req1_id,
        "device_location": device_loc,
    })
    assert resp1.status_code == 200, f"Turn 1 HTTP {resp1.status_code}: {resp1.text}"
    events1 = parse_sse_events(resp1.text)
    result_events1 = [data for evt, data in events1 if evt == "result"]
    assert len(result_events1) == 1, f"Expected exactly 1 result event, got {len(result_events1)}"
    r1 = result_events1[0]

    assert r1["request_id"] == req1_id
    assert r1["conversation_id"] == conv_id
    assert r1["location"]["mode"] == "DEVICE"
    assert r1["location"]["resolved"] is not None
    assert "kochi" in r1["location"]["resolved"]["name"].lower() or "kerala" in str(r1["location"]["resolved"].get("state", "")).lower()
    assert r1["execution_status"] in ["success", "partial"]
    assert r1["overall_data_status"] in ["live", "cached", "mixed"]

    # Triple separation check: Atmospheric pressure vs Tides vs SST
    weather_agent = r1["agents"]["weather"]
    assert weather_agent is not None, "Weather agent must have executed"
    assert "pressure_msl_hpa" in weather_agent["data"], "Atmospheric pressure (MSL) must be in weather agent"

    ocean_agent = r1["agents"]["ocean"]
    assert ocean_agent is not None, "Ocean agent must have executed"
    assert "Chart Datum" in ocean_agent["data"]["datum"], "Tidal water level must be referenced to Chart Datum"
    assert "water_level_m" in ocean_agent["data"]
    print("    [PASS] Turn 1: Resolved to Kochi device, MSL pressure in weather, Chart Datum tides in ocean agent")

    # ── Turn 2: "weather in Mumbai" (Device still Kochi) ─────────────────────
    print("  Testing Turn 2: query='weather in Mumbai' (device still Kochi)...")
    req2_id = f"req-2-{os.urandom(3).hex()}"
    resp2 = client.post("/query", json={
        "query": "weather in Mumbai",
        "conversation_id": conv_id,
        "request_id": req2_id,
        "device_location": device_loc,
    })
    assert resp2.status_code == 200
    events2 = parse_sse_events(resp2.text)
    result_events2 = [data for evt, data in events2 if evt == "result"]
    assert len(result_events2) == 1
    r2 = result_events2[0]

    assert r2["location"]["mode"] == "EXPLICIT_PLACE"
    assert "mumbai" in r2["location"]["resolved"]["name"].lower()
    # Device location must remain unchanged
    assert r2["location"]["device"]["lat"] == 9.9312
    print("    [PASS] Turn 2: Resolved to Mumbai, device_location preserved independently")

    # ── Turn 3: "what about tomorrow?" (Inherits Mumbai) ─────────────────────
    print("  Testing Turn 3: query='what about tomorrow?' (follow-up without place)...")
    req3_id = f"req-3-{os.urandom(3).hex()}"
    resp3 = client.post("/query", json={
        "query": "what about tomorrow?",
        "conversation_id": conv_id,
        "request_id": req3_id,
        "device_location": device_loc,
    })
    assert resp3.status_code == 200
    events3 = parse_sse_events(resp3.text)
    result_events3 = [data for evt, data in events3 if evt == "result"]
    assert len(result_events3) == 1
    r3 = result_events3[0]

    assert r3["location"]["mode"] == "INHERITED"
    assert "mumbai" in r3["location"]["resolved"]["name"].lower(), "Turn 3 must inherit Mumbai from server session"
    print("    [PASS] Turn 3: Inherited Mumbai from server-authoritative session")

    # ── Turn 4: "what about here?" (Hard override to Kochi device) ───────────
    print("  Testing Turn 4: query='what about here?' (relative override breaking inheritance)...")
    req4_id = f"req-4-{os.urandom(3).hex()}"
    resp4 = client.post("/query", json={
        "query": "what about here?",
        "conversation_id": conv_id,
        "request_id": req4_id,
        "device_location": device_loc,
    })
    assert resp4.status_code == 200
    events4 = parse_sse_events(resp4.text)
    result_events4 = [data for evt, data in events4 if evt == "result"]
    assert len(result_events4) == 1
    r4 = result_events4[0]

    assert r4["location"]["mode"] == "DEVICE"
    assert "kochi" in r4["location"]["resolved"]["name"].lower() or "kerala" in str(r4["location"]["resolved"].get("state", "")).lower()
    print("    [PASS] Turn 4: 'here' unconditionally overrode session inheritance back to Kochi device")

    # ── Turn 5: "show PFZ near me" (Hard override to Kochi device + PFZ) ─────
    print("  Testing Turn 5: query='show PFZ near me' (relative override + PFZ)...")
    req5_id = f"req-5-{os.urandom(3).hex()}"
    resp5 = client.post("/query", json={
        "query": "show PFZ near me",
        "conversation_id": conv_id,
        "request_id": req5_id,
        "device_location": device_loc,
    })
    assert resp5.status_code == 200
    events5 = parse_sse_events(resp5.text)
    result_events5 = [data for evt, data in events5 if evt == "result"]
    assert len(result_events5) == 1
    r5 = result_events5[0]

    assert r5["location"]["mode"] == "DEVICE"
    assert "kochi" in r5["location"]["resolved"]["name"].lower() or "kerala" in str(r5["location"]["resolved"].get("state", "")).lower()
    assert r5["parsed_intent"]["needs_pfz"] is True
    assert r5["agents"]["pfz"] is not None
    print("    [PASS] Turn 5: 'near me' resolved to Kochi device with needs_pfz=True")

    # ── Turn 6: Clarification Edge Case (Relative query, NO device GPS) ──────
    print("  Testing Turn 6: query='weather here' with NO device GPS (new session)...")
    new_conv_id = f"test-clarif-{os.urandom(4).hex()}"
    resp6 = client.post("/query", json={
        "query": "weather here",
        "conversation_id": new_conv_id,
        "request_id": f"req-6-{os.urandom(3).hex()}",
        "device_location": None,
    })
    assert resp6.status_code == 200
    events6 = parse_sse_events(resp6.text)
    result_events6 = [data for evt, data in events6 if evt == "result"]
    assert len(result_events6) == 1
    r6 = result_events6[0]

    assert r6["location"]["mode"] == "DEVICE"
    assert r6["location"]["resolved"] is None
    assert "device" in r6["answer_text"].lower() or "location" in r6["answer_text"].lower() or "gps" in r6["answer_text"].lower() or "where" in r6["answer_text"].lower()
    print("    [PASS] Turn 6: Missing device GPS prompts for location/GPS without defaulting to any hardcoded place")


if __name__ == "__main__":
    test_resolver_unit_suite()
    test_golden_sequence_e2e()
    print("\n=======================================================")
    print("ALL TESTS PASSED: Tarang V2 Location Architecture Verified")
    print("=======================================================\n")
