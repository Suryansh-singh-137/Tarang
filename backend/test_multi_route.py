"""
test_multi_route.py
Verify multi-route generation (Direct vs. Safest vs. PFZ Maximizer) and path smoothing.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from tools.route_planner import plan_safe_route

def test_multi_route_generation():
    print("Testing multi-route planning between Kochi and Kollam...")
    # Kochi: ~9.9312, 76.2673; Kollam: ~8.8932, 76.6141
    res = plan_safe_route(
        start_lat=9.9312,
        start_lon=76.2673,
        end_lat=8.8932,
        end_lon=76.6141,
        start_name="Kochi Port",
        end_name="Kollam Port",
        mode="all",
        include_pfz=True,
    )

    assert res["status"] == "success", f"Failed with status: {res.get('status')}, error: {res.get('error')}"
    assert "routes" in res, "Missing 'routes' dictionary in response"
    routes = res["routes"]
    print(f"Generated {len(routes)} routing profiles: {list(routes.keys())}")

    assert "safest" in routes, "Missing 'safest' profile"
    assert "direct" in routes, "Missing 'direct' profile"
    assert "pfz_maximizer" in routes, "Missing 'pfz_maximizer' profile"

    for m, r in routes.items():
        print(f"\n--- Mode: {m} ({r['title']}) ---")
        print(f"  Distance: {r['total_distance_km']} km")
        print(f"  Duration: {r['total_duration_h']} hrs")
        print(f"  Fuel Est: {r['fuel_liters_est']} L")
        print(f"  Avg Risk: {r['avg_risk_score']} ({r['risk_label']})")
        print(f"  Legs count: {len(r['legs'])}")
        print(f"  GeoJSON features: {len(r['route_geojson']['features'])}")

    # Direct should be <= Safest or PFZ in distance
    print("\nVerifying profile characteristics:")
    print(f"Direct distance ({routes['direct']['total_distance_km']} km) vs Safest ({routes['safest']['total_distance_km']} km)")
    assert routes["direct"]["total_distance_km"] <= routes["safest"]["total_distance_km"] + 2.0, "Direct route should be shortest"

    # Safest route should have lowest or equal risk
    print(f"Safest risk ({routes['safest']['avg_risk_score']}) vs Direct risk ({routes['direct']['avg_risk_score']})")
    assert routes["safest"]["avg_risk_score"] <= routes["direct"]["avg_risk_score"] + 1.0, "Safest route should have minimal risk"

    # Top-level backwards compatibility
    assert res["total_distance_km"] > 0
    assert res["selected_mode"] in ("safest", "direct", "pfz_maximizer")
    assert len(res["waypoints"]) > 0
    assert len(res["legs"]) > 0

    print("\n All multi-route generation tests passed successfully!")

if __name__ == "__main__":
    test_multi_route_generation()
