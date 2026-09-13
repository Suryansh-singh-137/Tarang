import requests
import json

resp = requests.post(
    "http://127.0.0.1:8000/query",
    json={
        "query": "Is it safe to fish right now?",
        "user_lat": 28.6139,
        "user_lon": 77.2090,
        "user_location_name": "New Delhi"
    },
    stream=True
)

for line in resp.iter_lines(decode_unicode=True):
    if line.startswith("data: "):
        data = line[6:].strip()
        try:
            parsed = json.loads(data)
            if "risk_data" in parsed or "parsed_intent" in parsed:
                print("Result event:")
                print("Parsed intent:", parsed.get("parsed_intent"))
                print("Risk data:", parsed.get("risk_data"))
                print("Answer text:", parsed.get("answer_text")[:200])
        except Exception:
            pass
