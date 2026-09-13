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

from fastapi import FastAPI, Request, UploadFile, File, Form, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import groq

import config
from tools import sarvam_tts_client
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
    version="3.0.0-milestone5",
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
    # Milestone 5: Multi-turn conversational memory
    # The client passes back what the server returned in the previous turn.
    conversation: list[dict] = []             # [{"role": "user"|"assistant", "content": "..."}]
    last_parsed_intent: dict | None = None    # ParsedIntent from previous turn
    last_results: dict[str, dict] = {}       # {agent_name: AgentResult} from previous turn

class SpeakRequest(BaseModel):
    text: str
    language: str


# ---------------------------------------------------------------------------
# Graph runner
# ---------------------------------------------------------------------------

def _build_initial_state(body: QueryRequest) -> ORCAState:
    return ORCAState(
        raw_query=body.query,
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
        # Milestone 5 fields
        conversation_history=body.conversation[:config.MAX_CONVERSATION_TURNS],
        last_parsed_intent=body.last_parsed_intent,  # type: ignore[arg-type]
        last_results={k: v for k, v in body.last_results.items()},  # type: ignore[arg-type]
        changed_fields=[],
    )


async def _run_graph_streaming(body: QueryRequest) -> AsyncIterator[dict]:
    """
    Run the LangGraph graph and yield SSE-compatible dicts.

    We emit:
      - A "progress" event for each node completion (trace entry)
      - A final "result" event with the full payload
    """
    initial_state = _build_initial_state(body)
    logger.info(f"Starting ORCA pipeline for query: {body.query!r}")

    final_state: ORCAState | None = None

    # astream yields state deltas after each node
    async for chunk in graph.astream(initial_state):
        # Each chunk is {node_name: partial_state_dict}
        for node_name, state_delta in chunk.items():
            logger.info(f"Node completed: {node_name}")
            if not state_delta:
                continue

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

    # --- Build last_results dict for client to echo back in next turn ---
    last_results_for_client: dict = {}
    for agent_key in [
        "weather_result", "pfz_result", "hazard_result", "geofence_result", "risk_result"
    ]:
        ar = final_state.get(agent_key)
        if ar and ar.get("status") == "success":
            agent_name = ar.get("agent_name", agent_key.replace("_result", "_agent"))
            last_results_for_client[agent_name] = {
                "agent_name":   ar.get("agent_name"),
                "status":       ar.get("status"),
                "data":         ar.get("data", {}),
                "source":       ar.get("source", ""),
                "summary":      ar.get("summary", ""),
                "used_fallback": ar.get("used_fallback", False),
                "data_quality": ar.get("data_quality", "live"),
                "timestamp":    ar.get("timestamp", ""),
                "error":        ar.get("error"),
                "evidence":     ar.get("evidence", []),
            }

    # Append assistant reply to conversation history
    answer_text = final_state.get("final_answer_text", "")
    updated_history = list(final_state.get("conversation_history") or [])
    updated_history.append({"role": "assistant", "content": answer_text[:500]})  # cap summary
    updated_history = updated_history[-config.MAX_CONVERSATION_TURNS:]

    result_payload = {
        "answer_text": answer_text,
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
        # Milestone 5: Client must echo these back in the next request
        "conversation_history": updated_history,
        "last_parsed_intent":   final_state.get("parsed_intent"),
        "last_results":         last_results_for_client,
        "changed_fields":       final_state.get("changed_fields") or [],
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
        "version": "3.0.0-milestone5",
        "status": "running",
        "endpoint": "POST /query",
        "milestones": [
            "M1: Mock pipeline",
            "M2: Live data (Open-Meteo + INCOIS)",
            "M3: Trust & disclosure hardening",
            "M4: Explainable risk reasoning",
            "M5: Multi-turn conversational memory",
        ],
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

    Milestone 5: Also accepts:
      - conversation: list of {role, content} from previous turns
      - last_parsed_intent: ParsedIntent dict from previous turn (for location/time inheritance)
      - last_results: {agent_name: AgentResult} from previous turn (for selective re-invocation)

    Final SSE event (type='result') shape:
    {
      "answer_text": "...",
      "language": "hi",
      "map_geojson": { "type": "FeatureCollection", "features": [...] },
      "trace": [
        { "agent_name": "weather_agent", "status": "success", "summary": "...", "source": "..." },
        ...
      ],
      "risk_data": { "composite_score": 35.0, "risk_label": "MODERATE", ... },
      "conversation_history": [...],
      "last_parsed_intent": {...},
      "last_results": { "weather_agent": {...}, ... },
      "changed_fields": [...]
    }
    """

    async def event_generator():
        try:
            async for event in _run_graph_streaming(body):
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

# ---------------------------------------------------------------------------
# Voice Endpoints (Milestone 7)
# ---------------------------------------------------------------------------

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """
    Speech-to-Text via Groq Whisper.
    Returns: {"transcript": "...", "detected_language_whisper": "...", "duration_seconds": float}
    """
    if not config.GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured for transcription.")
        
    try:
        # Read the uploaded audio
        audio_bytes = await audio.read()
        
        # We need a file-like object with a name for the Groq client
        file_tuple = (audio.filename, audio_bytes, audio.content_type)
        
        client = groq.Groq(api_key=config.GROQ_API_KEY, timeout=8.0)
        
        # Whisper auto-detects language if not provided
        transcription = client.audio.transcriptions.create(
            file=file_tuple,
            model="whisper-large-v3-turbo",
            response_format="verbose_json"
        )
        
        # The Groq verbose_json format gives duration and language
        return {
            "transcript": transcription.text,
            "detected_language_whisper": getattr(transcription, "language", "unknown"),
            "duration_seconds": getattr(transcription, "duration", 0.0)
        }
    except Exception as exc:
        logger.error(f"Transcription failed: {exc}")
        raise HTTPException(status_code=500, detail="Transcription failed. Please try again or type your question.")


@app.post("/speak")
def speak(body: SpeakRequest):
    """
    Text-to-Speech via Sarvam AI.
    Returns streaming audio/wav bytes.
    """
    audio_bytes = sarvam_tts_client.synthesize_speech(body.text, body.language)
    
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="Failed to synthesize speech.")
        
    return Response(content=audio_bytes, media_type="audio/wav")