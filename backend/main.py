"""
ORCA Backend — FastAPI Application
-----------------------------------
Single endpoint: POST /query

Runs the full LangGraph pipeline and returns a Server-Sent Events (SSE)
stream. The final event contains answer_text, language, map_geojson, and trace.

Run with:
  uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from graph.build_graph import graph
from graph.state import ORCAState

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orca")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Tarang — Marine Ecosystem Reasoning with Collaborative Agents",
    description=(
        "Multi-agent marine safety advisor for Indian coastal fishermen. "
        "Powered by LangGraph + real INCOIS/Open-Meteo data."
    ),
    version="2.0.0-milestone2",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten before production; fine for hackathon
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str


# ---------------------------------------------------------------------------
# Graph runner
# ---------------------------------------------------------------------------

def _build_initial_state(query: str) -> ORCAState:
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


async def _run_graph_streaming(query: str) -> AsyncIterator[dict]:
    """
    Run the LangGraph graph and yield SSE-compatible dicts.

    We emit:
      - A "progress" event for each node completion (trace entry)
      - A final "result" event with the full payload
    """
    initial_state = _build_initial_state(query)
    logger.info(f"Starting ORCA pipeline for query: {query!r}")

    final_state: ORCAState | None = None

    # astream yields state deltas after each node
    async for chunk in graph.astream(initial_state):
        # Each chunk is {node_name: partial_state_dict}
        for node_name, state_delta in chunk.items():
            logger.info(f"Node completed: {node_name}")

            # Emit a progress event for each new trace entry
            trace_list = state_delta.get("trace", [])
            if trace_list:
                latest = trace_list[-1]
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "node": node_name,
                        "agent_name": latest.get("agent_name", node_name),
                        "status": latest.get("status", "unknown"),
                        "summary": latest.get("summary", ""),
                        "source": latest.get("source", ""),
                    }),
                }

            # Track the last delta to build final state
            if final_state is None:
                final_state = dict(initial_state)  # type: ignore[arg-type]
            final_state.update(state_delta)  # type: ignore[arg-type]

            # Small yield to let the event loop breathe
            await asyncio.sleep(0)

    if final_state is None:
        final_state = initial_state  # type: ignore[assignment]

    # --- Final result event ---
    trace_for_response = [
        {
            "agent_name": r.get("agent_name", "unknown"),
            "status": r.get("status", "unknown"),
            "summary": r.get("summary", ""),
            "source": r.get("source", ""),
            "used_fallback": r.get("used_fallback", False),
        }
        for r in (final_state.get("trace") or [])
    ]

    result_payload = {
        "answer_text": final_state.get("final_answer_text", ""),
        "language": final_state.get("detected_language", "en"),
        "map_geojson": final_state.get("map_geojson", {"type": "FeatureCollection", "features": []}),
        "trace": trace_for_response,
        "risk_data": (
            final_state.get("risk_result", {}).get("data", {})
            if final_state.get("risk_result")
            else {}
        ),
        "evidence": [
            {
                "claim":        ev.get("claim", ""),
                "value":        ev.get("value"),
                "unit":         ev.get("unit", ""),
                "source":       ev.get("source", ""),
                "source_time":  ev.get("source_time", ""),
                "retrieved_at": ev.get("retrieved_at", ""),
            }
            for ev in (final_state.get("evidence") or [])
        ],
        "parsed_intent": final_state.get("parsed_intent"),
    }

    yield {
        "event": "result",
        "data": json.dumps(result_payload),
    }

    logger.info("ORCA pipeline complete.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "service": "Tarang Marine Safety Advisor",
        "version": "2.0.0-milestone2",
        "status": "running",
        "endpoint": "POST /query",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query")
async def query_endpoint(body: QueryRequest, request: Request):
    """
    Main ORCA query endpoint.

    Accepts a natural-language query in English, Hindi, or Tamil.
    Returns a Server-Sent Events stream.

    Final SSE event (type='result') shape:
    {
      "answer_text": "...",
      "language": "hi",
      "map_geojson": { "type": "FeatureCollection", "features": [...] },
      "trace": [
        { "agent_name": "weather_agent", "status": "success", "summary": "...", "source": "..." },
        ...
      ],
      "risk_data": { "composite_score": 35.0, "risk_label": "MODERATE", ... }
    }
    """

    async def event_generator():
        try:
            async for event in _run_graph_streaming(body.query):
                # Respect client disconnect
                if await request.is_disconnected():
                    logger.info("Client disconnected; stopping stream.")
                    break
                yield event
        except Exception as exc:
            logger.exception(f"Pipeline error: {exc}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(exc)}),
            }

    return EventSourceResponse(event_generator())