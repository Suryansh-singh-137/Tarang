"""
test_graph.py
-------------
Milestone 2 comprehensive end-to-end test for the Tarang LangGraph pipeline.

Usage:
  python test_graph.py                         # run the default Hindi query
  python test_graph.py "your custom query"     # run a single custom query
  python test_graph.py --all                   # run all 6 test cases
"""

import asyncio
import sys
import os

# Fix Windows terminal encoding for Unicode output
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(__file__))

from graph.build_graph import graph
from graph.state import ORCAState


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------
TEST_CASES = [
    {
        "id": 1,
        "description": "Hindi safety query (full pipeline)",
        "query": "kal subah thoothukudi ke paas fishing ke liye jaana safe hai?",
        "expected_language": "hi",
        "expected_query_type": "safety_check",
        "expected_agents": ["weather_agent", "pfz_agent", "hazard_agent", "geofence_agent", "risk_agent"],
    },
    {
        "id": 2,
        "description": "PFZ-only query",
        "query": "Thoothukudi ke paas nearest PFZ kaha hai machli pakdne ke liye?",
        "expected_language": "hi",
        "expected_query_type": "pfz_lookup",
        "expected_agents": ["pfz_agent"],
    },
    {
        "id": 3,
        "description": "English safety query for Chennai",
        "query": "Is it safe to go fishing near Chennai tomorrow morning?",
        "expected_language": "en",
        "expected_query_type": "safety_check",
        "expected_agents": ["weather_agent", "pfz_agent", "hazard_agent", "geofence_agent", "risk_agent"],
    },
    {
        "id": 4,
        "description": "Tamil script query",
        "query": "நாளை காலை தூத்துக்குடி கடலில் மீன்பிடிக்க பாதுகாப்பானதா?",
        "expected_language": "ta",
        "expected_query_type": "safety_check",
        "expected_agents": ["weather_agent", "pfz_agent", "hazard_agent"],
    },
    {
        "id": 5,
        "description": "Hazard-focused English query",
        "query": "Are there any dangerous weather alerts or storm warnings near Thoothukudi?",
        "expected_language": "en",
        "expected_query_type": "hazard_only",
        "expected_agents": ["weather_agent", "hazard_agent"],
    },
    {
        "id": 6,
        "description": "Tomorrow evening query",
        "query": "kal shaam Rameswaram ke paas sea conditions kaisi rahegi?",
        "expected_language": "hi",
        "expected_query_type": "general",
        "expected_agents": ["weather_agent", "hazard_agent"],
    },
]


# ---------------------------------------------------------------------------
# State builder
# ---------------------------------------------------------------------------

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
        evidence=[],
        trace=[],
    )


# ---------------------------------------------------------------------------
# Result printer
# ---------------------------------------------------------------------------

def print_result(result: dict, query: str):
    print(f"\nQuery: {query}")
    print("-" * 60)

    print("=== DETECTED LANGUAGE ===")
    print(result["detected_language"])

    print("\n=== PARSED INTENT ===")
    intent = result.get("parsed_intent", {})
    for k, v in (intent or {}).items():
        print(f"  {k}: {v}")

    print("\n=== TRACE ===")
    all_live = True
    for t in result["trace"]:
        status = t["status"].upper()
        name = t["agent_name"]
        summary = t["summary"][:100]
        ts = t.get("timestamp", "")
        fb = " [FALLBACK]" if t.get("used_fallback") else " [LIVE]"
        if t.get("used_fallback"):
            all_live = False
        print(f"  [{status}] {name}{fb}  ts={ts[:20]}")
        print(f"    {summary}")
        ev_count = len(t.get("evidence", []))
        print(f"    evidence items: {ev_count}")

    print(f"\n  All live (no fallbacks): {'YES ✅' if all_live else 'MIXED ⚠️'}")

    print("\n=== RISK DATA ===")
    risk_result = result.get("risk_result")
    if risk_result and risk_result["status"] == "success":
        d = risk_result["data"]
        print(f"  Score: {d['composite_score']}/100 ({d['risk_label']})")
        print(f"  Components: {d['component_scores']}")
        sources_live = d.get("data_sources_live", {})
        print(f"  Data sources live: {sources_live}")
        print(f"  Recommendation: {d['recommendation'][:120]}")

    print("\n=== EVIDENCE ITEMS ===")
    evidence = result.get("evidence") or []
    print(f"  Total: {len(evidence)}")
    for ev in evidence[:4]:
        print(f"  • [{ev.get('source','?')}] {ev.get('claim','?')[:80]}")

    print("\n=== MAP GEOJSON ===")
    features = result["map_geojson"]["features"]
    print(f"  {len(features)} features")
    for f in features:
        ftype = f["properties"].get("feature_type", "unknown")
        print(f"    - {ftype}: {f['geometry']['type']}")

    print("\n=== FINAL ANSWER (first 800 chars) ===")
    print(result["final_answer_text"][:800])
    print("...")


# ---------------------------------------------------------------------------
# Single test runner
# ---------------------------------------------------------------------------

async def run_test(test_case: dict) -> bool:
    """Run a single test case and return True if it passed."""
    print(f"\n{'='*60}")
    print(f"TEST {test_case['id']}: {test_case['description']}")
    print(f"{'='*60}")

    query = test_case["query"]
    result = await graph.ainvoke(build_initial(query))
    print_result(result, query)

    # --- Assertions ---
    failures = []

    # Language
    expected_lang = test_case.get("expected_language")
    if expected_lang and result.get("detected_language") != expected_lang:
        failures.append(
            f"Language: expected={expected_lang} got={result.get('detected_language')}"
        )

    # All expected agents ran (not errored)
    trace_map = {t["agent_name"]: t["status"] for t in result.get("trace", [])}
    for agent in test_case.get("expected_agents", []):
        if agent not in trace_map:
            failures.append(f"Agent {agent} not in trace")
        elif trace_map[agent] == "error":
            failures.append(f"Agent {agent} returned error")

    # Final answer not empty
    if not result.get("final_answer_text", "").strip():
        failures.append("final_answer_text is empty")

    # Evidence list exists
    evidence = result.get("evidence") or []
    if len(evidence) == 0:
        failures.append("No evidence items in state")

    if failures:
        print(f"\n❌ FAILURES:")
        for f in failures:
            print(f"   • {f}")
        return False
    else:
        print(f"\n✅ TEST {test_case['id']} PASSED")
        return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    args = sys.argv[1:]

    if "--all" in args:
        # Run all test cases
        print("Running all 6 test cases...")
        passed = 0
        for tc in TEST_CASES:
            ok = await run_test(tc)
            if ok:
                passed += 1
        print(f"\n{'='*60}")
        print(f"RESULTS: {passed}/{len(TEST_CASES)} tests passed")
        if passed < len(TEST_CASES):
            sys.exit(1)
    elif args:
        # Single custom query
        query = " ".join(args)
        result = await graph.ainvoke(build_initial(query))
        print_result(result, query)
        if not result.get("final_answer_text", "").strip():
            print("\n❌ FAIL: empty answer")
            sys.exit(1)
        print("\n✅ PASSED: Non-empty answer produced")
    else:
        # Default: first test case
        ok = await run_test(TEST_CASES[0])
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
