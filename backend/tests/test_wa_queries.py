import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from main import _run_graph_direct

queries = [
    "Is it safe to fish tomorrow?",
    "Where is the nearest PFZ?",
    "What is the sea state near Kochi harbour?",
    "Is it safe to fish near Chennai today?",
    "Is there any cyclone or hazard alert near Visakhapatnam?",
    "Check wave conditions and risk near Rameswaram",
    "Where are the nearest potential fishing zones near Chennai?",
    "Are there any active cyclone or storm warnings near Kochi?",
    "What are the wind and wave conditions near Diu today?",
    "kal machli pakadna safe hai kya?",
    "is it safe here?",
]

async def run_all():
    for q in queries:
        try:
            state = await _run_graph_direct(q)
            loc = state.get("resolved_location")
            loc_name = loc.get("name") if loc else None
            ans = (state.get("final_answer_text") or "")[:120]
            safe_ans = ans.encode("ascii", errors="replace").decode("ascii")
            print(f"[QUERY] {q}")
            print(f"   LOC: {loc_name}")
            print(f"   ANS: {safe_ans}\n")
        except Exception as e:
            print(f"[QUERY ERROR] {q}: {e}\n")

if __name__ == "__main__":
    asyncio.run(run_all())
