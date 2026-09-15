"""
test_whatsapp.py
----------------
Automated test suite for Tarang Twilio WhatsApp integration.

Tests:
  1. Empty message response (welcome / instructions)
  2. Single-turn safety query via Form POST (Twilio standard)
  3. Multi-turn context inheritance (follow-up query retains location)
  4. JSON payload support (for developer testing / API compatibility)

Usage:
  python test_whatsapp.py
"""

import sys
import os
import xml.etree.ElementTree as ET

# Fix Windows terminal encoding for Unicode output
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from main import app
from tools.whatsapp_session import session_store


def parse_twiml_message(xml_text: str) -> str:
    """Extract message body from TwiML XML string."""
    try:
        root = ET.fromstring(xml_text)
        message_el = root.find("Message")
        return message_el.text if message_el is not None and message_el.text else ""
    except Exception as e:
        return f"[XML Parse Error: {e}]"


def run_tests():
    print("=" * 65)
    print("🌊 Running Tarang WhatsApp (Twilio) Integration Tests")
    print("=" * 65)

    client = TestClient(app)
    test_phone = "whatsapp:+919876543210"
    session_store.clear_session(test_phone)

    # -----------------------------------------------------------------------
    # TEST 1: Empty Query
    # -----------------------------------------------------------------------
    print("\n[TEST 1] Empty Query handling")
    res1 = client.post(
        "/whatsapp",
        data={"From": test_phone, "Body": ""},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res1.status_code == 200, f"Expected 200, got {res1.status_code}"
    assert "xml" in res1.headers.get("content-type", ""), "Expected XML content type"
    msg1 = parse_twiml_message(res1.text)
    print(f"  Response status: {res1.status_code}")
    print(f"  TwiML message: {msg1[:100]}...")
    assert "Tarang" in msg1, "Expected welcome message mentioning Tarang"
    print("  ✅ TEST 1 PASSED: Empty message handled gracefully.")

    # -----------------------------------------------------------------------
    # TEST 2: Single-turn safety query (Form POST)
    # -----------------------------------------------------------------------
    print("\n[TEST 2] Single-turn query via standard Twilio Form POST")
    query_text = "kal subah thoothukudi ke paas fishing ke liye jaana safe hai?"
    print(f"  Query: {query_text}")
    res2 = client.post(
        "/whatsapp",
        data={"From": test_phone, "Body": query_text},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res2.status_code == 200, f"Expected 200, got {res2.status_code}"
    msg2 = parse_twiml_message(res2.text)
    print(f"  Response status: {res2.status_code}")
    print(f"  Formatted WhatsApp reply (preview):\n{'-'*40}\n{msg2[:300]}\n{'-'*40}")
    assert len(msg2) > 50, "Expected non-trivial answer text"
    
    # Check session was created
    session = session_store.get_session(test_phone)
    assert len(session["conversation"]) == 2, f"Expected 2 conversation entries, got {len(session['conversation'])}"
    assert session["last_parsed_intent"] is not None, "Expected parsed_intent in session"
    print("  ✅ TEST 2 PASSED: Pipeline generated response & saved session state.")

    # -----------------------------------------------------------------------
    # TEST 3: Multi-turn Follow-up (Context Inheritance)
    # -----------------------------------------------------------------------
    print("\n[TEST 3] Multi-turn follow-up query (inheriting location)")
    followup_text = "aur kal shaam kya hoga?"
    print(f"  Follow-up Query: {followup_text}")
    res3 = client.post(
        "/whatsapp",
        data={"From": test_phone, "Body": followup_text},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res3.status_code == 200, f"Expected 200, got {res3.status_code}"
    msg3 = parse_twiml_message(res3.text)
    print(f"  Response status: {res3.status_code}")
    print(f"  Follow-up reply (preview):\n{'-'*40}\n{msg3[:300]}\n{'-'*40}")
    
    session_after = session_store.get_session(test_phone)
    assert len(session_after["conversation"]) == 4, f"Expected 4 conversation entries, got {len(session_after['conversation'])}"
    # Inherited location should still be Thoothukudi
    last_intent = session_after.get("last_parsed_intent") or {}
    inherited_loc = last_intent.get("location_name")
    print(f"  Inherited location in session: {inherited_loc}")
    assert "thoothukudi" in str(inherited_loc).lower(), f"Expected Thoothukudi location inherited, got {inherited_loc}"
    print("  ✅ TEST 3 PASSED: Multi-turn context and location inherited successfully.")

    # -----------------------------------------------------------------------
    # TEST 4: JSON format support via /webhook
    # -----------------------------------------------------------------------
    print("\n[TEST 4] JSON payload format via /webhook")
    json_phone = "whatsapp:+919876543299"
    res4 = client.post(
        "/webhook",
        json={"From": json_phone, "Body": "Is it safe to fish near Kochi tomorrow?"},
    )
    assert res4.status_code == 200, f"Expected 200, got {res4.status_code}"
    msg4 = parse_twiml_message(res4.text)
    print(f"  Response status: {res4.status_code}")
    print(f"  JSON endpoint response (preview):\n{'-'*40}\n{msg4[:300]}\n{'-'*40}")
    assert len(msg4) > 50, "Expected non-trivial answer text"
    print("  ✅ TEST 4 PASSED: JSON request parsed and processed successfully.")

    print("\n" + "=" * 65)
    print("🎉 ALL WHATSAPP INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
