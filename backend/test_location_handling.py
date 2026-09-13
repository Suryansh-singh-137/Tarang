import requests
import json

def parse_sse_events(response):
    events = []
    current_event = {}
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            if current_event:
                events.append(current_event)
                current_event = {}
            continue
        if line.startswith("event: "):
            current_event["event"] = line[7:].strip()
        elif line.startswith("data: "):
            current_event["data"] = line[6:].strip()
    if current_event:
        events.append(current_event)
    return events

# -------------------------------------------------------------
# Test A: Ambiguous query without location or coords
# Query: "Is it safe to fish right now?" (No location given, no user_lat/lon)
# Expected: Location clarification requested, NOT defaulting to Thoothukudi!
# -------------------------------------------------------------
print("--- RUNNING TEST A: Ambiguous location without coords ---")
resp_a = requests.post(
    "http://127.0.0.1:8000/query",
    json={"query": "Is it safe to fish right now?"},
    stream=True
)
events_a = parse_sse_events(resp_a)
result_a = None
for ev in events_a:
    if ev.get("event") == "result":
        result_a = json.loads(ev["data"])

print("Result A Parsed Intent:", result_a.get("parsed_intent"))
print("Result A Answer snippet:", result_a.get("answer_text")[:150] if result_a else "No result")

# Assert that it did NOT default to Thoothukudi
assert result_a is not None, "Expected result event"
loc_name_a = (result_a.get("parsed_intent") or {}).get("location_name")
assert loc_name_a is None or loc_name_a == "Unknown", f"Expected location_name to be None, got {loc_name_a}"
assert "could not determine your coastal location" in result_a.get("answer_text", "").lower() or "clarify" in result_a.get("answer_text", "").lower() or "specify which harbour" in result_a.get("answer_text", "").lower(), "Expected clarification prompt"
print(">>> TEST A PASSED: No silent default to Thoothukudi, clarification asked!")

# -------------------------------------------------------------
# Test B: Query without location in text, BUT with browser coords
# Query: "Is it safe to fish right now?" with coords (9.28, 79.31) [Rameswaram waters]
# Expected: Uses the passed browser coords!
# -------------------------------------------------------------
print("\n--- RUNNING TEST B: Ambiguous query WITH browser coords ---")
resp_b = requests.post(
    "http://127.0.0.1:8000/query",
    json={
        "query": "Is it safe to fish right now?",
        "user_lat": 9.2878,
        "user_lon": 79.3129,
        "user_location_name": "Rameswaram Waters"
    },
    stream=True
)
events_b = parse_sse_events(resp_b)
result_b = None
for ev in events_b:
    if ev.get("event") == "result":
        result_b = json.loads(ev["data"])

print("Result B Parsed Intent:", result_b.get("parsed_intent"))
print("Result B Risk Label:", (result_b.get("risk_data") or {}).get("risk_label"))
snippet = result_b.get("answer_text", "")[:150].encode("ascii", "ignore").decode()
print("Result B Answer snippet:", snippet)

assert result_b is not None, "Expected result event"
intent_b = result_b.get("parsed_intent") or {}
assert abs(intent_b.get("lat") - 9.2878) < 0.01, f"Expected lat ~9.2878, got {intent_b.get('lat')}"
assert abs(intent_b.get("lon") - 79.3129) < 0.01, f"Expected lon ~79.3129, got {intent_b.get('lon')}"
print(">>> TEST B PASSED: Browser coordinates used for analysis!")
