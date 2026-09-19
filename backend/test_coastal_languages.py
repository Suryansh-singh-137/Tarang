import requests
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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

print("=== TESTING COASTAL LANGUAGES (GU, BN, TE, ML, MR, OD) ===")

test_cases = [
    {
        "name": "Gujarati Manual Override",
        "query": "Is it safe to fish near Veraval tomorrow?",
        "lang": "gu",
        "expected_lang": "gu",
    },
    {
        "name": "Bengali Manual Override",
        "query": "Is it safe to fish near Digha tomorrow?",
        "lang": "bn",
        "expected_lang": "bn",
    },
    {
        "name": "Malayalam Manual Override",
        "query": "Is it safe to fish near Kochi tomorrow?",
        "lang": "ml",
        "expected_lang": "ml",
    },
    {
        "name": "Gujarati Script Auto-Detection",
        "query": "શું આવતીકાલે વેરાવળ પાસે માછીમારી કરવા જવું સલામત છે?",
        "lang": None,
        "expected_lang": "gu",
    },
    {
        "name": "Bengali Script Auto-Detection",
        "query": "দীঘার কাছে মাছ ধরা কি কাল নিরাপদ?",
        "lang": None,
        "expected_lang": "bn",
    },
    {
        "name": "Telugu Manual Override",
        "query": "Is it safe to fish near Visakhapatnam tomorrow?",
        "lang": "te",
        "expected_lang": "te",
    },
    {
        "name": "Marathi Manual Override",
        "query": "Is it safe to fish near Ratnagiri tomorrow?",
        "lang": "mr",
        "expected_lang": "mr",
    },
    {
        "name": "Odia Manual Override",
        "query": "Is it safe to fish near Paradip tomorrow?",
        "lang": "od",
        "expected_lang": "od",
    },
]

all_passed = True
for tc in test_cases:
    payload = {"query": tc["query"]}
    if tc["lang"]:
        payload["language"] = tc["lang"]

    try:
        resp = requests.post("http://127.0.0.1:8000/query", json=payload, stream=True, timeout=25)
        events = parse_sse_events(resp)
        res_payload = None
        for ev in events:
            if ev.get("event") == "result":
                res_payload = json.loads(ev["data"])

        if not res_payload:
            print(f"FAILED {tc['name']}: No result event received")
            all_passed = False
            continue

        actual_lang = res_payload.get("language")
        answer_preview = res_payload.get("answer_text", "")[:80].replace("\n", " ")
        print(f"[{tc['name']}] Detected/Result Language: {actual_lang} | Expected: {tc['expected_lang']}")
        print(f"  Sample answer: {answer_preview}...")

        if actual_lang != tc["expected_lang"]:
            print(f"  FAIL Language mismatch: expected {tc['expected_lang']}, got {actual_lang}")
            all_passed = False
        else:
            print("  PASS")
    except Exception as e:
        print(f"FAILED {tc['name']} with exception: {e}")
        all_passed = False

print("\n=== TESTING TTS /speak WITH GUJARATI & BENGALI ===")
for lang, test_txt in [("gu", "વેરાવળ પાસે દરિયાઈ સ્થિતિ હાલ સામાન્ય છે."), ("bn", "দীঘার কাছে সমুদ্রের পরিস্থিতি স্বাভাবিক রয়েছে।")]:
    try:
        sp_resp = requests.post(
            "http://127.0.0.1:8000/speak",
            json={"text": test_txt, "language": lang},
            timeout=15,
        )
        print(f"Speak ({lang}) status: {sp_resp.status_code}, content-type: {sp_resp.headers.get('content-type')}")
        if sp_resp.status_code == 200:
            print(f"  PASS Audio generated ({len(sp_resp.content)} bytes)")
        else:
            print(f"  WARN Non-200 response: {sp_resp.text}")
    except Exception as e:
        print(f"Speak ({lang}) test skipped/failed: {e}")

if all_passed:
    print("\nALL COASTAL LANGUAGE BACKEND TESTS PASSED!")
    sys.exit(0)
else:
    print("\nSOME TESTS FAILED")
    sys.exit(1)
