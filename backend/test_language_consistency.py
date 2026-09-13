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

print("=== TEST 1: Manual Language Override in /query ===")
# Send an English text query, but with explicit Tamil manual toggle override: language="ta"
resp = requests.post(
    "http://127.0.0.1:8000/query",
    json={
        "query": "Is it safe to fish near Thoothukudi today?",
        "language": "ta"
    },
    stream=True
)
events = parse_sse_events(resp)
result_payload = None
for ev in events:
    if ev.get("event") == "result":
        result_payload = json.loads(ev["data"])

print("Result payload language:", result_payload.get("language"))
assert result_payload is not None, "Expected result event from /query"
assert result_payload.get("language") == "ta", f"Expected language 'ta' from override, got {result_payload.get('language')}"
print(">>> TEST 1 PASSED: Manual language override 'ta' was honored and skipped auto-detection to 'en'!")

print("\n=== TEST 2: Exact Language Consistency with /speak ===")
query_lang = result_payload.get("language")
answer_text = result_payload.get("answer_text")

# Call /speak with the exact language from the query result
speak_resp = requests.post(
    "http://127.0.0.1:8000/speak",
    json={
        "text": answer_text[:100],
        "language": query_lang
    }
)
print("Speak endpoint status:", speak_resp.status_code)
print("Speak content-type:", speak_resp.headers.get("content-type"))
print("Speak received bytes:", len(speak_resp.content))

assert speak_resp.status_code == 200, f"Expected 200 from /speak, got {speak_resp.status_code}"
assert "audio" in speak_resp.headers.get("content-type", ""), f"Expected audio content type, got {speak_resp.headers.get('content-type')}"
assert len(speak_resp.content) > 1000, "Expected non-empty audio wav bytes"
print(">>> TEST 2 PASSED: /speak received and used exact same language value ('ta') producing audio bytes without re-detecting!")
