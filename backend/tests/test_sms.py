"""
test_sms.py
-----------
Automated test suite for Tarang Twilio SMS integration.

Tests:
  1. SMS breach message formatting (concise, GSM-safe, key details present)
  2. SMS sender — live delivery to verified number
  3. SMS phone normalization (unit test with env override)
  4. Dual dispatch on /geofence/evaluate endpoint (both WhatsApp and SMS results present)
  5. /sms webhook endpoint — empty message handling
  6. /geofence/evaluate with trigger_sms=False

Usage:
  python tests/test_sms.py
  (or: pytest tests/test_sms.py -v)
"""

import sys
import os
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from tools.sms_sender import format_breach_sms_message, send_sms_message, send_geofence_breach_sms
from fastapi.testclient import TestClient
from main import app
import xml.etree.ElementTree as ET

# Use the verified recipient phone from env for live tests
VERIFIED_PHONE = os.environ.get("TWILIO_RECIPIENT_PHONE", "+919236454423")


def parse_twiml_message(xml_text: str) -> str:
    """Extract message body from TwiML XML string."""
    try:
        root = ET.fromstring(xml_text)
        message_el = root.find("Message")
        return message_el.text if message_el is not None and message_el.text else ""
    except Exception as e:
        return f"[XML Parse Error: {e}]"


def test_sms_breach_message_formatting():
    """Test that breach SMS text is concise and contains critical details."""
    breach_data = {
        "boundary_name": "India-Sri Lanka IMBL (Palk Strait)",
        "sector": "Palk Strait",
        "coordinates": {"lat": 9.3000, "lon": 79.8500},
        "distance_km": 12.5,
        "bearing_to_safety": 265,
        "bearing_cardinal": "W",
        "coastguard_number": "1554",
    }
    msg = format_breach_sms_message(breach_data)
    print("\n[TEST 1] SMS Breach Message Formatting:")
    print(f"  Message ({len(msg)} chars):")
    print(f"  ---\n{msg}\n  ---")

    assert len(msg) < 500, f"SMS message too long: {len(msg)} chars (should be < 500)"
    assert "TARANG" in msg.upper(), "Expected TARANG in SMS alert"
    assert "9.3000" in msg, "Expected latitude in SMS"
    assert "79.8500" in msg, "Expected longitude in SMS"
    assert "12.5" in msg, "Expected penetration distance in SMS"
    assert "W" in msg, "Expected cardinal direction in SMS"
    assert "1554" in msg, "Expected coastguard number in SMS"
    # No markdown formatting in SMS
    assert "*" not in msg, "SMS should not contain markdown asterisks"
    print("  ✅ TEST 1 PASSED: SMS message is concise and contains all critical details.")


def test_sms_live_delivery():
    """Test SMS delivery to the verified recipient phone number."""
    result = send_sms_message(VERIFIED_PHONE, "Tarang SMS Test: Integration test message.")
    print("\n[TEST 2] SMS Live Delivery:")
    print(f"  To: {VERIFIED_PHONE}")
    print(f"  Result: {result}")

    assert result["success"] is True, f"Expected success=True, got: {result}"
    assert VERIFIED_PHONE.replace("whatsapp:", "") in result["to"], "Expected recipient phone in result"
    if result.get("simulated"):
        print("  ✅ TEST 2 PASSED: SMS simulated (no TWILIO_PHONE_NUMBER configured).")
    else:
        print(f"  ✅ TEST 2 PASSED: SMS dispatched live! SID={result.get('sid')}")


def test_sms_phone_normalization():
    """Test phone number normalization logic (format only, no actual send)."""
    from tools.sms_sender import send_sms_message as _send

    # Temporarily unset SMS number to force simulation (avoids hitting Twilio API)
    original = os.environ.get("TWILIO_PHONE_NUMBER", "")
    os.environ["TWILIO_PHONE_NUMBER"] = ""

    try:
        # 10-digit number
        result = _send("9876543210", "Test")
        assert result["to"] == "+919876543210", f"Expected +919876543210, got {result['to']}"

        # whatsapp: prefix
        result = _send("whatsapp:+919876543210", "Test")
        assert result["to"] == "+919876543210", f"Expected +919876543210, got {result['to']}"

        # Already with +
        result = _send("+919876543210", "Test")
        assert result["to"] == "+919876543210", f"Expected +919876543210, got {result['to']}"
    finally:
        os.environ["TWILIO_PHONE_NUMBER"] = original

    print("\n[TEST 3] SMS Phone Normalization:")
    print("  ✅ TEST 3 PASSED: Phone numbers normalized correctly (10-digit, whatsapp:, +91).")


def test_geofence_dual_dispatch():
    """Test that /geofence/evaluate returns both WhatsApp and SMS results."""
    client = TestClient(app)
    payload = {
        "lat": 9.3000,
        "lon": 79.8500,
        "name": "Palk Strait East Boundary",
        "phone": VERIFIED_PHONE,
        "trigger_whatsapp": True,
        "trigger_sms": True,
    }
    response = client.post("/geofence/evaluate", json=payload)
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
    data = response.json()

    print("\n[TEST 4] /geofence/evaluate Dual Dispatch (WhatsApp + SMS):")
    print(f"  Breached: {data['is_breached']}")
    print(f"  WhatsApp Result: {data.get('whatsapp_result')}")
    print(f"  SMS Result: {data.get('sms_result')}")

    assert data["is_breached"] is True, "Expected breach to be True"

    # WhatsApp result present and successful
    assert "whatsapp_result" in data, "Expected whatsapp_result in response"
    assert data["whatsapp_result"]["success"] is True, "Expected WhatsApp success"

    # SMS result present and successful
    assert "sms_result" in data, "Expected sms_result in response"
    assert data["sms_result"]["success"] is True, "Expected SMS success"

    # Both sent flags
    assert "whatsapp_sent" in data, "Expected whatsapp_sent flag"
    assert "sms_sent" in data, "Expected sms_sent flag"

    print("  ✅ TEST 4 PASSED: Geofence endpoint returns both WhatsApp and SMS results.")


def test_sms_webhook_empty_message():
    """Test /sms webhook with empty body returns welcome message."""
    client = TestClient(app)
    res = client.post(
        "/sms",
        data={"From": "+919876543210", "Body": ""},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert "xml" in res.headers.get("content-type", ""), "Expected XML content type"
    msg = parse_twiml_message(res.text)
    print("\n[TEST 5] /sms Webhook Empty Message:")
    print(f"  Response: {msg[:100]}...")
    assert "TARANG" in msg.upper(), "Expected welcome message mentioning TARANG"
    print("  ✅ TEST 5 PASSED: Empty SMS handled gracefully.")


def test_sms_no_trigger():
    """Test that /geofence/evaluate with trigger_sms=false doesn't send SMS."""
    client = TestClient(app)
    payload = {
        "lat": 9.3000,
        "lon": 79.8500,
        "name": "Palk Strait No SMS Test",
        "phone": "+919999999999",
        "trigger_whatsapp": False,
        "trigger_sms": False,
    }
    response = client.post("/geofence/evaluate", json=payload)
    data = response.json()

    print("\n[TEST 6] /geofence/evaluate with trigger_sms=False:")
    print(f"  SMS Result: {data.get('sms_result')}")
    print(f"  SMS Sent: {data.get('sms_sent')}")

    assert data.get("sms_result") is None, "Expected sms_result to be None when trigger_sms=False"
    assert data.get("sms_sent") is False, "Expected sms_sent to be False"
    assert data.get("whatsapp_result") is None, "Expected whatsapp_result to be None when trigger_whatsapp=False"
    print("  ✅ TEST 6 PASSED: No alerts dispatched when both triggers are False.")


def run_all_tests():
    print("=" * 65)
    print("🌊 Running Tarang SMS (Twilio) Integration Tests")
    print("=" * 65)

    test_sms_breach_message_formatting()
    test_sms_live_delivery()
    test_sms_phone_normalization()
    test_geofence_dual_dispatch()
    test_sms_webhook_empty_message()
    test_sms_no_trigger()

    print("\n" + "=" * 65)
    print("✅ All SMS integration tests PASSED!")
    print("=" * 65)


if __name__ == "__main__":
    run_all_tests()
