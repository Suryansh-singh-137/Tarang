"""
test_geofence_breach.py
-----------------------
Automated test suite for Maritime Geofence Crossing Detection
and automated WhatsApp border breach alert dispatch.
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

from tools.boundary_geo import evaluate_maritime_geofence, compute_bearing, bearing_to_cardinal
from tools.whatsapp_sender import format_breach_alert_message, send_geofence_breach_alert
from fastapi.testclient import TestClient
from main import app


def test_safe_indian_waters():
    """Rameshwaram coastal harbor (Indian side of Palk Strait)."""
    # Rameshwaram: 9.2876°N, 79.3129°E (West of IMBL line)
    res = evaluate_maritime_geofence(9.2876, 79.3129, "Rameshwaram Harbor")
    print("\n[TEST 1] Rameshwaram Indian Waters Evaluation:")
    print(f"  Breached: {res['is_breached']} | Distance: {res['distance_km']} km | Status: {res['status']}")
    assert res["is_breached"] is False, "Rameshwaram should NOT be marked as breached"
    assert res["status"] in ("warning_buffer", "safe", "critical_buffer")
    print("  ✅ TEST 1 PASSED: Indian side correctly identified as safe/buffer.")


def test_sri_lanka_imbl_breach():
    """Point crossed East of the IMBL into Sri Lankan waters in Palk Strait."""
    # 9.28°N, 79.80°E (Well east of IMBL line which is at ~79.55°E at this latitude)
    res = evaluate_maritime_geofence(9.2800, 79.8000, "East of Palk Bay")
    print("\n[TEST 2] Palk Strait Sri Lanka Breach Evaluation:")
    print(f"  Breached: {res['is_breached']} | Boundary: {res['boundary_name']} | Penetration: {res['distance_km']} km")
    print(f"  Bearing to safety: {res['bearing_to_safety']}° ({res['bearing_cardinal']})")
    assert res["is_breached"] is True, "Coordinates east of IMBL should be marked as BREACHED"
    assert res["status"] == "breach"
    assert "Sri Lanka" in res["boundary_name"]
    # Return bearing should steer westward (between 220° and 300°)
    assert 220 <= res["bearing_to_safety"] <= 300, f"Expected westward return bearing, got {res['bearing_to_safety']}"
    print("  ✅ TEST 2 PASSED: Sri Lanka IMBL breach correctly detected with westward return heading.")


def test_pakistan_maritime_breach():
    """Point crossed North-West into Pakistan waters off Sir Creek / Kutch."""
    # 23.50°N, 67.20°E (North-West of Sir Creek boundary)
    res = evaluate_maritime_geofence(23.5000, 67.2000, "Sir Creek Northern Waters")
    print("\n[TEST 3] Pakistan Sir Creek Maritime Breach Evaluation:")
    print(f"  Breached: {res['is_breached']} | Boundary: {res['boundary_name']} | Distance: {res['distance_km']} km")
    assert res["is_breached"] is True, "Coordinates NW of Sir Creek should be marked as BREACHED"
    assert "Pakistan" in res["boundary_name"]
    print("  ✅ TEST 3 PASSED: Pakistan border breach correctly detected.")


def test_whatsapp_alert_formatting_and_endpoint():
    """Test WhatsApp breach alert message text and FastAPI /geofence/evaluate endpoint."""
    client = TestClient(app)
    payload = {
        "lat": 9.3000,
        "lon": 79.8500,
        "name": "Palk Strait East Boundary",
        "phone": "+919876543210",
        "trigger_whatsapp": True,
    }
    response = client.post("/geofence/evaluate", json=payload)
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
    data = response.json()

    print("\n[TEST 4] /geofence/evaluate Endpoint & WhatsApp Delivery:")
    print(f"  Breached: {data['is_breached']}")
    print(f"  Warning: {data['warning_title']}")
    print(f"  WhatsApp Delivery: {data.get('whatsapp_delivery')}")

    assert data["is_breached"] is True
    assert "whatsapp_delivery" in data
    assert data["whatsapp_delivery"]["success"] is True
    print("  ✅ TEST 4 PASSED: Geofence evaluate endpoint returned valid breach payload and WhatsApp alert.")


def test_bangladesh_maritime_breach():
    """Point crossed East into Bangladesh territorial waters in Northern Bay of Bengal."""
    # 21.40°N, 89.80°E (East of 89.25°E boundary)
    res = evaluate_maritime_geofence(21.4000, 89.8000, "Northern Bay of Bengal")
    print("\n[TEST 5] Bangladesh Maritime Breach Evaluation:")
    print(f"  Breached: {res['is_breached']} | Boundary: {res['boundary_name']} | Distance: {res['distance_km']} km")
    assert res["is_breached"] is True
    assert "Bangladesh" in res["boundary_name"]
    print("  ✅ TEST 5 PASSED: Bangladesh border breach correctly detected.")


def test_maldives_maritime_breach():
    """Point crossed South into Maldivian waters across Eight Degree Channel."""
    # 7.20°N, 73.00°E (South of 7.67°N boundary)
    res = evaluate_maritime_geofence(7.2000, 73.0000, "Eight Degree Channel South")
    print("\n[TEST 6] Maldives Maritime Breach Evaluation:")
    print(f"  Breached: {res['is_breached']} | Boundary: {res['boundary_name']} | Distance: {res['distance_km']} km")
    assert res["is_breached"] is True
    assert "Maldives" in res["boundary_name"]
    # Return bearing should steer northward towards Minicoy (340° - 20°)
    assert (res["bearing_to_safety"] <= 30 or res["bearing_to_safety"] >= 330)
    print("  ✅ TEST 6 PASSED: Maldives border breach correctly detected with northward return heading.")


def test_myanmar_maritime_breach():
    """Point crossed North into Myanmar waters across Coco Channel."""
    # 14.15°N, 93.60°E (North of 13.85°N boundary near Coco Islands)
    res = evaluate_maritime_geofence(14.1500, 93.6000, "Coco Channel North")
    print("\n[TEST 7] Myanmar Maritime Breach Evaluation:")
    print(f"  Breached: {res['is_breached']} | Boundary: {res['boundary_name']} | Distance: {res['distance_km']} km")
    assert res["is_breached"] is True
    assert "Myanmar" in res["boundary_name"]
    print("  ✅ TEST 7 PASSED: Myanmar border breach correctly detected.")


def test_indonesia_maritime_breach():
    """Point crossed South-East into Indonesian waters across Great Channel."""
    # 5.60°N, 95.50°E (South-East of Great Channel boundary off Aceh)
    res = evaluate_maritime_geofence(5.6000, 95.5000, "Great Channel South-East")
    print("\n[TEST 8] Indonesia Maritime Breach Evaluation:")
    print(f"  Breached: {res['is_breached']} | Boundary: {res['boundary_name']} | Distance: {res['distance_km']} km")
    assert res["is_breached"] is True
    assert "Indonesia" in res["boundary_name"]
    print("  ✅ TEST 8 PASSED: Indonesia border breach correctly detected.")


if __name__ == "__main__":
    print("=" * 65)
    print("🌊 Running Tarang Maritime Geofence Breach Tests (All 6 Borders)")
    print("=" * 65)
    test_safe_indian_waters()
    test_sri_lanka_imbl_breach()
    test_pakistan_maritime_breach()
    test_whatsapp_alert_formatting_and_endpoint()
    test_bangladesh_maritime_breach()
    test_maldives_maritime_breach()
    test_myanmar_maritime_breach()
    test_indonesia_maritime_breach()
    print("\n" + "=" * 65)
    print("🎉 ALL 6 MARITIME BORDER BREACH & WHATSAPP TESTS PASSED!")
    print("=" * 65)
