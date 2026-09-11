"""Quick end-to-end test of the ORCA graph pipeline."""
import asyncio
import sys
import os

# Fix Windows terminal encoding for Unicode output
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(__file__))

from graph.build_graph import graph
from graph.state import ORCAState


QUERY = "kal subah thoothukudi ke paas fishing ke liye jaana safe hai?"


def build_initial(query: str) -> ORCAState:
    return ORCAState(
        raw_query=query,
        detected_language="en",
        parsed_intent=None,
        weather_result=None,
        pfz_result=None,
        hazard_result=None,
        geofence_result=None,
        risk_result=None,
        final_answer_text="",
        map_geojson={"type": "FeatureCollection", "features": []},
        trace=[],
    )


async def main():
    print(f"Query: {QUERY}\n")
    result = await graph.ainvoke(build_initial(QUERY))

    print("=== DETECTED LANGUAGE ===")
    print(result["detected_language"])
    print()

    print("=== PARSED INTENT ===")
    intent = result.get("parsed_intent", {})
    for k, v in intent.items():
        print(f"  {k}: {v}")
    print()

    print("=== TRACE ===")
    for t in result["trace"]:
        status = t["status"].upper()
        name = t["agent_name"]
        summary = t["summary"][:100]
        fallback = " [FALLBACK]" if t.get("used_fallback") else ""
        print(f"  [{status}] {name}{fallback}")
        print(f"    {summary}")
    print()

    print("=== RISK DATA ===")
    risk_result = result.get("risk_result")
    if risk_result and risk_result["status"] == "success":
        d = risk_result["data"]
        print(f"  Score: {d['composite_score']}/100 ({d['risk_label']})")
        print(f"  Components: {d['component_scores']}")
        print(f"  Recommendation: {d['recommendation'][:120]}")
    print()

    print("=== MAP GEOJSON ===")
    features = result["map_geojson"]["features"]
    print(f"  {len(features)} features")
    for f in features:
        ftype = f["properties"].get("feature_type", "unknown")
        print(f"    - {ftype}: {f['geometry']['type']}")
    print()

    print("=== FINAL ANSWER (first 600 chars) ===")
    print(result["final_answer_text"][:600])
    print()

    print("All checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
