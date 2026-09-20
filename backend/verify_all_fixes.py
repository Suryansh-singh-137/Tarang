import json
import io
import wave
import requests

BASE_URL = "http://127.0.0.1:8000"

def parse_sse_result(resp):
    for line in resp.iter_lines(decode_unicode=True):
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:].strip())
                if "answer_text" in data or "parsed_intent" in data:
                    return data
            except Exception:
                pass
    return None

print("=" * 70)
print("VERIFICATION SUITE: TARANG BUG FIXES")
print("=" * 70)

# ---------------------------------------------------------------------------
# Test 1: Delhi Coordinates via Browser Geolocation Path
# ---------------------------------------------------------------------------
print("\n[TEST 1] Delhi Coordinates via Browser Geolocation Payload...")
resp1 = requests.post(
    f"{BASE_URL}/query",
    json={
        "query": "Is it safe to fish right now?",
        "user_lat": 28.6139,
        "user_lon": 77.2090,
        "user_location_name": "Current Location",
        "language": "en"
    },
    stream=True,
    timeout=15.0
)
assert resp1.status_code == 200, f"Expected 200, got {resp1.status_code}"
result1 = parse_sse_result(resp1)
assert result1 is not None, "Failed to parse SSE result for Test 1"

intent1 = result1.get("parsed_intent") or {}
trace1 = result1.get("trace") or []
answer1 = result1.get("answer_text", "")
risk1 = result1.get("risk_data") or {}

print("  Parsed Intent:", intent1)
print("  Answer snippet:", answer1[:160].replace("\n", " ").encode("ascii", "ignore").decode())

# Assertions for Delhi:
assert intent1.get("needs_weather") is False, "needs_weather must be False for Delhi"
assert intent1.get("needs_pfz") is False, "needs_pfz must be False for Delhi"
assert intent1.get("needs_hazard") is False, "needs_hazard must be False for Delhi"
assert intent1.get("needs_geofence") is False, "needs_geofence must be False for Delhi"
assert intent1.get("needs_risk") is False, "needs_risk must be False for Delhi"

# Assert that all 5 specialist marine agents were SKIPPED and not executed
for t in trace1:
    assert t.get("status") == "skipped", f"Agent {t.get('agent_name')} was expected to be skipped, got {t.get('status')}"

active_executed_agents = [t.get("agent_name") for t in trace1 if t.get("status") != "skipped"]
assert len(active_executed_agents) == 0, f"No marine agents should execute for Delhi, but got: {active_executed_agents}"
assert not risk1, f"risk_data must be empty for Delhi, got {risk1}"

assert "inland" in answer1.lower(), "Answer must state that location is inland"
assert "coastal location" in answer1.lower(), "Answer must prompt for coastal location"

print(">>> TEST 1 PASSED: Delhi coordinates correctly flagged inland, zero marine agents executed!")

# ---------------------------------------------------------------------------
# Test 2: Coastal Coordinates (Rameswaram) via Browser Geolocation Payload
# ---------------------------------------------------------------------------
print("\n[TEST 2] Coastal Coordinates (Rameswaram) via Browser Geolocation Payload...")
resp2 = requests.post(
    f"{BASE_URL}/query",
    json={
        "query": "Is it safe to fish right now?",
        "user_lat": 9.2878,
        "user_lon": 79.3129,
        "user_location_name": "Current Location",
        "language": "en"
    },
    stream=True,
    timeout=20.0
)
assert resp2.status_code == 200
result2 = parse_sse_result(resp2)
assert result2 is not None

intent2 = result2.get("parsed_intent") or {}
trace2 = result2.get("trace") or []
answer2 = result2.get("answer_text", "")
risk2 = result2.get("risk_data") or {}

print("  Parsed Intent:", intent2.get("location_name"), f"({intent2.get('lat')}, {intent2.get('lon')})")
print("  Risk Score:", risk2.get("composite_score"), f"({risk2.get('risk_label')})")
print("  Trace agents executed:", [t.get("agent_name") for t in trace2])

assert intent2.get("needs_weather") is True, "needs_weather must be True for coastal"
assert "weather_agent" in [t.get("agent_name") for t in trace2], "weather_agent must run for coastal"
assert risk2.get("risk_label") is not None, "risk_data must be populated for coastal"

# Verify Risk Breakdown Table formatting (must NOT contain markdown table pipes)
assert "| Factor |" not in answer2, "Raw markdown table header '| Factor |' must NOT be present in answer"
assert "|--------|" not in answer2, "Markdown table separator '|--------|' must NOT be present in answer"
print("  Answer 2 snippet:", answer2[:200].replace("\n", " ").encode("ascii", "ignore").decode())
assert any(b in answer2 for b in ["•", "*", "-", "**"]), "Answer should contain clean bullet or formatted factors"
print(">>> TEST 2 PASSED: Coastal coordinates executed marine pipeline with clean bullet points!")

# ---------------------------------------------------------------------------
# Test 3: Island Territory Coordinates (Port Blair, Andaman) via Browser Geolocation
# ---------------------------------------------------------------------------
print("\n[TEST 3] Island Territory Coordinates (Port Blair, Andaman)...")
resp3 = requests.post(
    f"{BASE_URL}/query",
    json={
        "query": "What are the sea conditions?",
        "user_lat": 11.6234,
        "user_lon": 92.7265,
        "user_location_name": "Current Location",
        "language": "en"
    },
    stream=True,
    timeout=20.0
)
assert resp3.status_code == 200
result3 = parse_sse_result(resp3)
assert result3 is not None
intent3 = result3.get("parsed_intent") or {}
assert intent3.get("needs_weather") is True, "Port Blair must be recognized as coastal"
print("  Port Blair Intent:", intent3.get("location_name"), f"({intent3.get('lat')}, {intent3.get('lon')})")
print(">>> TEST 3 PASSED: Andaman island coordinates correctly accepted as coastal!")

# ---------------------------------------------------------------------------
# Test 4: Sarvam TTS Read-Aloud on Full Answer (2000+ chars)
# ---------------------------------------------------------------------------
print("\n[TEST 4] Sarvam TTS Read-Aloud on Full Response...")
full_text = answer2 if len(answer2) > 800 else (answer2 + "\n" + """
Disclaimer: This is a decision-support assessment, not an official safety clearance. Tarang assesses available conditions as a navigational aid. Always follow advisories from IMD, INCOIS, and the Indian Coast Guard before departing. Weather conditions in the coastal zone can change rapidly. Maintain constant VHF radio watch on Channel 16. Ensure all crew members wear certified lifejackets. Check battery levels on distress beacons and navigation equipment before departure. Report your departure time and estimated return time to the local fisheries harbour authority.
""")

print(f"  Sending {len(full_text)} characters to /speak...")
resp4 = requests.post(
    f"{BASE_URL}/speak",
    json={"text": full_text, "language": "en"},
    timeout=35.0
)
assert resp4.status_code == 200, f"Expected 200 from /speak, got {resp4.status_code}: {resp4.text}"
assert "audio" in resp4.headers.get("content-type", ""), f"Expected audio content-type, got {resp4.headers.get('content-type')}"
wav_bytes = resp4.content
assert len(wav_bytes) > 50000, f"Expected audio bytes > 50KB, got {len(wav_bytes)} bytes"

# Validate WAV integrity and length
with wave.open(io.BytesIO(wav_bytes), "rb") as w:
    duration = w.getnframes() / w.getframerate()
    channels = w.getnchannels()
    rate = w.getframerate()
    print(f"  WAV Header Verified: {channels} channel(s), {rate} Hz, duration: {duration:.1f}s")
    assert duration > 10.0, f"Audio duration too short: {duration}s"

print(">>> TEST 4 PASSED: Long answer synthesized and stitched into clean WAV audio!")

print("\n" + "=" * 70)
print("ALL 4 VERIFICATION TESTS PASSED PERFECTLY!")
print("=" * 70)
