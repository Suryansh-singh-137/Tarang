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
import uuid
from typing import AsyncIterator, Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, Response, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import groq
import os
import config
from tools import sarvam_tts_client
from tools.whatsapp_session import session_store
from tools.whatsapp_formatter import format_for_whatsapp
from twilio.twiml.messaging_response import MessagingResponse
from graph.build_graph import graph
from graph.state import ORCAState
from location.models import DeviceLocation, LocationMode, ExecutionStatus, DataStatus
from session.session_store import get_or_create_session, save_session

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
    version="3.0.0-v2architecture",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten before production; fine for hackathon
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/debug/weather")
def debug_weather(lat: float = 13.0827, lon: float = 80.2707):
    import traceback
    import httpx
    try:
        with httpx.Client(timeout=12.0, headers={"User-Agent": "TarangMarine/1.0"}) as client:
            m = client.get(
                "https://marine-api.open-meteo.com/v1/marine",
                params={"latitude": lat, "longitude": lon, "hourly": "wave_height", "forecast_days": 2}
            )
            f = client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={"latitude": lat, "longitude": lon, "hourly": "wind_speed_10m", "forecast_days": 2}
            )
            return {
                "marine_status": m.status_code,
                "marine_ok": m.status_code == 200,
                "forecast_status": f.status_code,
                "forecast_ok": f.status_code == 200,
                "marine_sample": m.json().get("hourly", {}).get("wave_height", [])[:3] if m.status_code == 200 else m.text,
                "forecast_sample": f.json().get("hourly", {}).get("wind_speed_10m", [])[:3] if f.status_code == 200 else f.text,
            }
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
SUPPORTED_LANGUAGES = ("en", "hi", "ta", "gu", "bn", "te", "ml", "mr", "od", "or")

class QueryRequest(BaseModel):
    query: str
    request_id: str | None = None
    conversation_id: str | None = None
    device_location: dict | None = None
    conversation: list[dict] = []             # [{"role": "user"|"assistant", "content": "..."}]
    last_parsed_intent: dict | None = None    # ParsedIntent from previous turn
    last_results: dict[str, dict] = {}       # {agent_name: AgentResult} from previous turn
    # Legacy Geolocation & Language Override
    user_lat: float | None = None             # Browser geolocation latitude
    user_lon: float | None = None             # Browser geolocation longitude
    user_location_name: str | None = None     # Optional reverse geocoded name
    language: str | None = None               # Manual language override ("en", "hi", "ta", "gu", "bn", "te", "ml", "mr", "od")
    # Universal Dynamic Location System (PRD §11, §20, §21)
    selected_location: dict | None = None
    marine_context: dict | None = None

class SpeakRequest(BaseModel):
    text: str
    language: str

class LocationResolveRequest(BaseModel):
    lat: float
    lon: float
    name: str | None = None
    source: str = "search"

class SessionLocationRequest(BaseModel):
    conversation_id: str | None = None
    location: dict
    marine_context: dict | None = None

class RouteRequest(BaseModel):
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    start_name: str = "Start"
    end_name: str = "Destination"
    departure_utc: str | None = None
    time_window: str = "next_24h"
    include_pfz: bool = True
    mode: str = "all"



# ---------------------------------------------------------------------------
# Graph runner
# ---------------------------------------------------------------------------

def _build_initial_state(body: QueryRequest) -> ORCAState:
    req_id = body.request_id or f"req-{uuid.uuid4().hex[:8]}"
    conv_id = body.conversation_id or f"conv-{uuid.uuid4().hex[:12]}"
    session = get_or_create_session(conv_id)

    # Device location extraction
    device_loc: DeviceLocation | None = None
    if body.device_location and body.device_location.get("lat") is not None and body.device_location.get("lon") is not None:
        device_loc = {
            "lat": float(body.device_location["lat"]),
            "lon": float(body.device_location["lon"]),
            "accuracy": body.device_location.get("accuracy"),
            "captured_at": body.device_location.get("captured_at"),
            "permission_status": body.device_location.get("permission_status", "granted"),
        }
    elif body.user_lat is not None and body.user_lon is not None:
        device_loc = {
            "lat": float(body.user_lat),
            "lon": float(body.user_lon),
            "accuracy": None,
            "captured_at": None,
            "permission_status": "granted",
        }
    elif session.device_location:
        device_loc = session.device_location

    if device_loc:
        session.device_location = device_loc

    # Universal Selected Location sync (PRD §18, §20)
    if body.selected_location and body.selected_location.get("lat") is not None and body.selected_location.get("lon") is not None:
        session.selected_location = body.selected_location
        if body.marine_context:
            session.marine_context = body.marine_context
        else:
            try:
                from location.service import determine_marine_context
                session.marine_context = determine_marine_context(
                    float(body.selected_location["lat"]),
                    float(body.selected_location["lon"]),
                    name=body.selected_location.get("name"),
                )
            except Exception as _e:
                pass

    initial_lang = body.language if body.language in SUPPORTED_LANGUAGES else "en"

    user_loc = None
    if device_loc:
        dev_name = "Your Location"
        if body.user_location_name and (
            not session.selected_location
            or body.user_location_name != session.selected_location.get("name")
        ):
            dev_name = body.user_location_name
        user_loc = {
            "lat": device_loc["lat"],
            "lon": device_loc["lon"],
            "name": dev_name,
        }
    elif session.selected_location:
        user_loc = {
            "lat": session.selected_location["lat"],
            "lon": session.selected_location["lon"],
            "name": session.selected_location.get("name") or "Selected Location",
        }


    return ORCAState(
        request_id=req_id,
        conversation_id=conv_id,
        raw_query=body.query,
        detected_language=initial_lang,
        parsed_intent=None,
        device_location=device_loc,
        query_location=None,
        resolved_location=None,
        location_mode=None,
        weather_result=None,
        pfz_result=None,
        sst_result=None,
        ocean_result=None,
        hazard_result=None,
        geofence_result=None,
        risk_result=None,
        execution_status="success",
        overall_data_status="live",
        final_answer_text="",
        map_geojson={"type": "FeatureCollection", "features": []},
        evidence=[],
        trace=[],
        # Server-authoritative conversation session
        conversation_history=session.conversation_history or body.conversation[:config.MAX_CONVERSATION_TURNS],
        last_parsed_intent=session.last_parsed_intent or body.last_parsed_intent,
        last_results=session.last_results or {k: v for k, v in body.last_results.items()},
        previous_marine_assessment=session.last_marine_assessment,
        previous_relevant_result=session.last_marine_assessment or (session.last_marine_snapshot.get("risk") if session.last_marine_snapshot else None),
        semantic_context=session.semantic_context,
        changed_fields=[],
        parse_method="rule_based_fallback",
        synthesis_method="template_fallback",
        data_quality_reports=[],
        risk_sufficient_data=None,
        user_location=user_loc,
        language_override=body.language if body.language in SUPPORTED_LANGUAGES else None,
    )


async def _run_graph_streaming(body: QueryRequest) -> AsyncIterator[dict]:
    """
    Run the LangGraph graph and yield SSE-compatible dicts.

    We emit:
      - A "progress" event for each node completion (trace entry)
      - A final "result" event with the canonical TarangResponse payload
    """
    initial_state = _build_initial_state(body)
    req_id = initial_state["request_id"]
    conv_id = initial_state["conversation_id"]

    logger.info(
        f"[TRACE][1/2] /query received [req={req_id}, conv={conv_id}]: query={body.query!r}, "
        f"device_location={initial_state.get('device_location')}"
    )

    final_state: ORCAState | None = None

    try:
        # astream yields state deltas after each node (threaded via checkpointer)
        async for chunk in graph.astream(initial_state, config={"configurable": {"thread_id": conv_id}}):
            for node_name, state_delta in chunk.items():
                logger.info(f"[TRACE] Node completed: {node_name}")
                if not state_delta:
                    continue

                # Emit a progress event for each new trace entry
                trace_list = state_delta.get("trace", [])
                if trace_list:
                    latest = trace_list[-1]
                    yield {
                        "event": "progress",
                        "data": json.dumps({
                            "request_id": req_id,
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

                await asyncio.sleep(0)

    except Exception as exc:
        logger.exception("[Query] Top-level unhandled exception: %s", exc)
        yield {
            "event": "result",
            "data": json.dumps({
                "request_id": req_id,
                "conversation_id": conv_id,
                "answer_text": "Something went wrong — please try again.",
                "language": initial_state.get("detected_language", "en"),
                "location": {
                    "mode": "NONE",
                    "resolved": None,
                    "query": None,
                    "device": initial_state.get("device_location"),
                },
                "execution_status": "failed",
                "overall_data_status": "unavailable",
                "agents": {},
                "map_geojson": {"type": "FeatureCollection", "features": []},
                "trace": [],
                "risk_data": {},
                "evidence": [],
            }),
        }
        return

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

    # Persist in Server-Side SessionStore
    session = get_or_create_session(conv_id)

    # --- Build and merge last_results dict for caching (Never wipe out prior agent results on skipped turns) ---
    merged_results = dict(session.last_results or {})
    for agent_key in [
        "weather_result", "pfz_result", "ocean_result", "hazard_result", "geofence_result", "risk_result"
    ]:
        ar = final_state.get(agent_key)
        if ar and ar.get("status") == "success":
            agent_name = ar.get("agent_name", agent_key.replace("_result", "_agent"))
            merged_results[agent_name] = {
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

    # Update last_marine_assessment when risk assessment is performed
    risk_res = final_state.get("risk_result")
    if risk_res and risk_res.get("status") == "success" and isinstance(risk_res.get("data"), dict):
        risk_data = risk_res["data"]
        resolved_loc = final_state.get("resolved_location") or {}
        session.last_marine_assessment = {
            "location": {
                "name": resolved_loc.get("name"),
                "lat": resolved_loc.get("lat"),
                "lon": resolved_loc.get("lon"),
                "coastal": resolved_loc.get("coastal", True),
            },
            "composite_score": risk_data.get("composite_score", 0.0),
            "risk_label": risk_data.get("risk_label", "UNKNOWN"),
            "components": risk_data.get("components", []),
            "inputs": risk_data.get("inputs", {}),
            "recommendation": risk_data.get("recommendation", ""),
            "evidence_coverage": risk_data.get("evidence_coverage", ""),
            "summary": risk_res.get("summary", ""),
            "timestamp": risk_res.get("timestamp", ""),
        }

    # Append assistant reply to conversation history
    answer_text = final_state.get("final_answer_text", "")
    updated_history = list(final_state.get("conversation_history") or [])
    updated_history.append({"role": "assistant", "content": answer_text[:500]})
    updated_history = updated_history[-config.MAX_CONVERSATION_TURNS:]

    session.conversation_history = updated_history
    session.last_parsed_intent = final_state.get("parsed_intent")
    session.last_results = merged_results
    if final_state.get("resolved_location"):
        session.last_query_location = final_state.get("resolved_location")
    if not session.semantic_context:
        session.semantic_context = {}
    parsed_intent = final_state.get("parsed_intent") or {}
    session.semantic_context["last_intent"] = parsed_intent.get("intent") or "UNKNOWN"
    if session.last_marine_assessment:
        session.semantic_context["last_risk_label"] = session.last_marine_assessment.get("risk_label")
        session.semantic_context["last_risk_score"] = session.last_marine_assessment.get("composite_score")
        session.semantic_context["last_active_warnings"] = session.last_marine_assessment.get("inputs", {}).get("active_warnings", [])
    if final_state.get("marine_snapshot"):
        session.last_marine_snapshot = final_state.get("marine_snapshot")
    save_session(session)

    # Debug Logging (PRD Section 46)
    raw_query = final_state.get("raw_query", "")
    parsed_intent = final_state.get("parsed_intent") or {}
    intent_name = parsed_intent.get("intent", "UNKNOWN")
    resp_mode = parsed_intent.get("response_mode", "UNKNOWN")
    resolved = final_state.get("resolved_location")
    resolved_name = resolved.get("name") if resolved else "None"
    is_coastal = resolved.get("coastal", False) if resolved else False
    answer_plan = final_state.get("answer_plan") or parsed_intent.get("answer_plan") or {}
    trace_items = final_state.get("trace") or []
    executed_caps = [r.get("agent_name") for r in trace_items if r.get("status") == "success"]

    logger.info(
        f"\n=======================================================\n"
        f"[REQUEST DEBUG]\n"
        f"  REQUEST: {req_id}\n"
        f"  QUERY: {raw_query!r}\n"
        f"  INTENT: {intent_name}\n"
        f"  RESPONSE_MODE: {resp_mode}\n"
        f"  LOCATION: {resolved_name} (coastal={is_coastal})\n"
        f"  REQUIRED_CAPABILITIES: {answer_plan.get('required_capabilities', [])}\n"
        f"  EXECUTED_CAPABILITIES: {executed_caps}\n"
        f"  ANSWER_PLAN: {answer_plan.get('answer_type', 'None')}\n"
        f"  SYNTHESIS: {final_state.get('synthesis_method', 'unknown')}\n"
        f"======================================================="
    )

    _RESPONSE_MODE_MAP = {
        "DIRECT_FACT": "factual_direct",
        "factual_direct": "factual_direct",
        "DATA_SUMMARY": "specialist_card",
        "specialist_card": "specialist_card",
        "APPLICABILITY_EXPLANATION": "applicability_explanation",
        "applicability_explanation": "applicability_explanation",
        "DECISION_ASSESSMENT": "safety_assessment",
        "safety_assessment": "safety_assessment",
        "CLARIFICATION": "clarification",
        "clarification": "clarification",
    }
    _PRESENTATION_HINT_MAP = {
        "LocationCard": "location_card",
        "location_card": "location_card",
        "WeatherCard": "weather_card",
        "weather_card": "weather_card",
        "OceanCard": "ocean_card",
        "ocean_card": "ocean_card",
        "PFZCard": "pfz_card",
        "pfz_card": "pfz_card",
        "HazardCard": "hazard_card",
        "hazard_card": "hazard_card",
        "SafetyCard": "safety_card",
        "safety_card": "safety_card",
        "ApplicabilityCard": "applicability_card",
        "applicability_card": "applicability_card",
        "ClarificationCard": "clarification_card",
        "clarification_card": "clarification_card",
    }
    norm_resp_mode = _RESPONSE_MODE_MAP.get(resp_mode, resp_mode)

    if answer_plan:
        card_type = answer_plan.get("answer_type", "SafetyCard")
        answer_plan["presentation_hint"] = answer_plan.get("presentation_hint") or _PRESENTATION_HINT_MAP.get(card_type, "safety_card")
        answer_plan["intent_name"] = answer_plan.get("intent_name") or answer_plan.get("intent") or intent_name
        answer_plan["response_mode"] = answer_plan.get("response_mode") or norm_resp_mode

    if parsed_intent:
        parsed_intent["intent_name"] = parsed_intent.get("intent_name") or parsed_intent.get("intent") or intent_name
        parsed_intent["response_mode"] = norm_resp_mode

    # Canonical TarangResponse Payload
    result_payload = {
        "request_id": req_id,
        "conversation_id": conv_id,
        "answer_text": answer_text,
        "language": final_state.get("detected_language", "en"),
        "location": {
            "mode": final_state.get("location_mode", "NONE"),
            "resolved": final_state.get("resolved_location"),
            "query": final_state.get("query_location"),
            "device": final_state.get("device_location"),
        },
        "execution_status": final_state.get("execution_status", "success"),
        "overall_data_status": final_state.get("overall_data_status", "live"),
        "agents": {
            "weather": final_state.get("weather_result"),
            "pfz": final_state.get("pfz_result"),
            "sst": final_state.get("sst_result"),
            "ocean": final_state.get("ocean_result"),
            "hazard": final_state.get("hazard_result"),
            "geofence": final_state.get("geofence_result"),
            "risk": final_state.get("risk_result"),
        },
        "map_geojson": final_state.get("map_geojson", {"type": "FeatureCollection", "features": []}),
        "trace": trace_for_response,
        "risk_data": (
            final_state.get("risk_result", {}).get("data", {})
            if final_state.get("risk_result")
            and final_state.get("risk_result", {}).get("status") in ("success", "insufficient_data")
            and intent_name in ("MARINE_SAFETY_QUERY", "TRIP_QUERY", "RISK_EXPLANATION")
            else None
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
        "answer_plan": answer_plan,
        "response_mode": norm_resp_mode,
        "query_signature": final_state.get("query_signature"),
        "conversation_history": updated_history,
        "last_parsed_intent":   final_state.get("parsed_intent"),
        "last_results":         merged_results,
        "changed_fields":       final_state.get("changed_fields") or [],
        "marine_snapshot":      final_state.get("marine_snapshot"),
        "change_summary":       final_state.get("change_summary"),
        "selected_location":    session.selected_location,
        "marine_context":       session.marine_context,
    }

    yield {
        "event": "result",
        "data": json.dumps(result_payload),
    }

    logger.info("ORCA pipeline complete [req=%s, conv=%s].", req_id, conv_id)



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
            logger.exception(f"Unhandled pipeline error in /query: {exc}")
            yield {
                "event": "error",
                "data": json.dumps({"error": "Something went wrong — please try again"}),
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
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio payload received.")
        
        filename = audio.filename or "recording.webm"
        content_type = audio.content_type or "audio/webm"
        file_tuple = (filename, audio_bytes, content_type)
        
        client = groq.Groq(api_key=config.GROQ_API_KEY, timeout=12.0)
        
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
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Transcription failed: {exc}")
        raise HTTPException(status_code=500, detail="Transcription failed. Please try again or type your question.")


@app.post("/speak")
def speak(body: SpeakRequest):
    """
    Text-to-Speech via Sarvam AI.
    Returns streaming audio/wav bytes.
    """
    if not config.SARVAM_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="SARVAM_API_KEY is not configured in backend/.env. Please configure your Sarvam AI API key.",
        )

    audio_bytes = sarvam_tts_client.synthesize_speech(body.text, body.language)
    
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="Failed to synthesize speech via Sarvam AI API.")
        
    return Response(content=audio_bytes, media_type="audio/wav")


# ---------------------------------------------------------------------------
# Dynamic Location & Marine Context Endpoints (PRD §8, §9, §11, §21)
# ---------------------------------------------------------------------------

@app.get("/location/search")
def location_search(q: str, limit: int = 6):
    """
    3-tier location search:
    Gazetteer -> OpenWeather Geocoding API -> Nominatim OSM fallback.
    """
    from location.service import search_locations
    results = search_locations(q, limit=limit)
    return {"results": results}


@app.get("/location/reverse")
def location_reverse(lat: float, lon: float):
    """
    Reverse geocode coordinates into a standardized place name.
    Supports offshore marine coordinates (PRD §10).
    """
    from location.service import reverse_geocode
    loc = reverse_geocode(lat, lon)
    return {"location": loc}


@app.post("/location/resolve")
def location_resolve(body: LocationResolveRequest):
    """
    Resolve coordinates to canonical SelectedLocation + MarineContext (PRD §11 & §12).
    """
    from location.service import resolve_canonical_location
    resolved = resolve_canonical_location(body.lat, body.lon, name=body.name, source=body.source)
    return resolved


@app.post("/session/location")
def session_location_set(body: SessionLocationRequest):
    """
    Set canonical selected location and marine context for conversation session (PRD §20).
    """
    from location.service import determine_marine_context
    conv_id = body.conversation_id or "default"
    session = get_or_create_session(conv_id)
    session.selected_location = body.location
    if body.marine_context:
        session.marine_context = body.marine_context
    elif "lat" in body.location and "lon" in body.location:
        session.marine_context = determine_marine_context(
            float(body.location["lat"]), float(body.location["lon"]), name=body.location.get("name")
        )
    save_session(session)
    return {
        "status": "ok",
        "conversation_id": conv_id,
        "selected_location": session.selected_location,
        "marine_context": session.marine_context,
    }


@app.get("/session/location")
def session_location_get(conversation_id: str | None = None):
    """
    Get current selected location and marine context for conversation session.
    """
    conv_id = conversation_id or "default"
    session = get_or_create_session(conv_id)
    return {
        "conversation_id": conv_id,
        "selected_location": session.selected_location,
        "marine_context": session.marine_context,
    }


@app.get("/location/pfz")
def location_pfz(lat: float, lon: float, name: Optional[str] = None):
    """
    Retrieve Potential Fishing Zones (PFZ) and GeoJSON feature layer for any location.
    If the location is inland, returns is_coastal=False with an informational notice.
    """
    from location.service import determine_marine_context
    ctx = determine_marine_context(lat, lon, name=name)
    if ctx.get("type") == "inland" or ctx.get("fishing_data_available") is False:
        return {
            "status": "inland",
            "is_coastal": False,
            "location": {"name": name or "Inland Location", "lat": lat, "lon": lon, "coastal": False},
            "zones": [],
            "features": [],
            "summary": "Potential fishing zones (PFZ) are not applicable to inland non-marine locations.",
        }

    from graph.nodes.pfz_agent import pfz_agent, _build_pfz_geojson_features
    loc_name = name or "Coastal Harbour"
    mock_state = {
        "resolved_location": {"name": loc_name, "lat": lat, "lon": lon, "coastal": True},
        "raw_query": f"fishing zones near {loc_name}",
        "trace": [],
        "evidence": [],
        "data_quality_reports": [],
    }
    result_dict = pfz_agent(mock_state)
    pfz_res = result_dict.get("pfz_result", {})
    data = pfz_res.get("data", {})
    zones = data.get("zones", [])
    features = _build_pfz_geojson_features(zones, pfz_res.get("source", "INCOIS Oceansat-2"))

    return {
        "status": "success",
        "is_coastal": True,
        "location": {"name": loc_name, "lat": lat, "lon": lon, "coastal": True},
        "zones": zones,
        "nearest_zone_km": data.get("nearest_zone_km"),
        "zone_count": len(zones),
        "avg_chl": data.get("avg_chl"),
        "source": pfz_res.get("source", "INCOIS Oceansat-2 (Chlorophyll Satellite Climatology)"),
        "data_quality": pfz_res.get("data_quality", "historical_proxy"),
        "used_fallback": pfz_res.get("used_fallback", False),
        "summary": pfz_res.get("summary", ""),
        "features": features,
    }


# ---------------------------------------------------------------------------
# WhatsApp Integration (Twilio)
# ---------------------------------------------------------------------------

def _extract_last_results(final_state: dict) -> dict[str, dict]:
    """Extract success specialist agent results for client/session reuse."""
    last_results: dict[str, dict] = {}
    for agent_key in [
        "weather_result", "pfz_result", "sst_result", "hazard_result", "geofence_result", "risk_result"
    ]:
        ar = final_state.get(agent_key)
        if ar and ar.get("status") == "success":
            agent_name = ar.get("agent_name", agent_key.replace("_result", "_agent"))
            last_results[agent_name] = {
                "agent_name": ar.get("agent_name"),
                "status": ar.get("status"),
                "data": ar.get("data", {}),
                "source": ar.get("source", ""),
                "summary": ar.get("summary", ""),
                "used_fallback": ar.get("used_fallback", False),
                "data_quality": ar.get("data_quality", "live"),
                "timestamp": ar.get("timestamp", ""),
                "error": ar.get("error"),
                "evidence": ar.get("evidence", []),
            }
    return last_results


async def _run_graph_direct(
    query: str,
    conversation: list[dict] | None = None,
    last_parsed_intent: dict | None = None,
    last_results: dict[str, dict] | None = None,
    wa_session_id: str | None = None,
) -> ORCAState:
    """
    Run the LangGraph pipeline end-to-end and return the final ORCAState directly.

    For WhatsApp turns, pass `wa_session_id` (the phone number string) so that:
      1. A *stable* conv_id is derived from it (same session across turns).
      2. The server-side SessionRecord is pre-seeded with the last known location
         from `last_parsed_intent`, enabling LocationResolver Priority-5C inheritance
         for location-less follow-up queries (e.g. "Is it safe to fish tomorrow?").
    """
    req_id = str(uuid.uuid4())

    # Use a stable conv_id per WhatsApp phone so the SessionRecord persists across turns.
    # Without this, every call creates a brand-new empty SessionRecord and the resolver
    # always returns NONE mode, skipping all agents.
    if wa_session_id:
        # Derive a deterministic ID from the phone number (safe for dict keys)
        stable_key = wa_session_id.replace("whatsapp:", "").replace("+", "").replace(" ", "")
        conv_id = f"conv-wa-{stable_key}"
    else:
        conv_id = f"conv-wa-{req_id[:8]}"

    # Pre-seed the server-side SessionRecord with last known location so that
    # LocationResolver can inherit it (Priority 5C) for location-less follow-up queries.
    if last_parsed_intent:
        from session.session_store import get_or_create_session as _get_session, save_session as _save_session
        _wa_session = _get_session(conv_id)
        loc_name = last_parsed_intent.get("location_name")
        loc_lat = last_parsed_intent.get("lat")
        loc_lon = last_parsed_intent.get("lon")
        if loc_name and loc_lat is not None and loc_lon is not None:
            if not _wa_session.last_query_location:
                _wa_session.last_query_location = {
                    "lat": float(loc_lat),
                    "lon": float(loc_lon),
                    "name": loc_name,
                    "source": "previous_query",
                    "confidence": 0.85,
                    "coastal": True,
                }
            if not _wa_session.selected_location:
                _wa_session.selected_location = {
                    "lat": float(loc_lat),
                    "lon": float(loc_lon),
                    "name": loc_name,
                    "source": "conversation",
                }
            _save_session(_wa_session)
            logger.info(
                "[WhatsApp] Pre-seeded SessionRecord '%s' with last location: %s (%.4f, %.4f)",
                conv_id, loc_name, float(loc_lat), float(loc_lon),
            )

    user_loc = None
    if last_parsed_intent and last_parsed_intent.get("location_name"):
        user_loc = {
            "lat": last_parsed_intent.get("lat"),
            "lon": last_parsed_intent.get("lon"),
            "name": last_parsed_intent.get("location_name"),
        }
    initial_state = ORCAState(
        request_id=req_id,
        conversation_id=conv_id,
        raw_query=query,
        detected_language="en",
        parsed_intent=None,
        device_location=None,
        query_location=None,
        resolved_location=None,
        location_mode=None,
        weather_result=None,
        pfz_result=None,
        sst_result=None,
        ocean_result=None,
        hazard_result=None,
        geofence_result=None,
        risk_result=None,
        execution_status="success",
        overall_data_status="live",
        final_answer_text="",
        map_geojson={"type": "FeatureCollection", "features": []},
        evidence=[],
        trace=[],
        conversation_history=(conversation or [])[-config.MAX_CONVERSATION_TURNS:],
        last_parsed_intent=last_parsed_intent,  # type: ignore[arg-type]
        last_results=last_results or {},  # type: ignore[arg-type]
        previous_marine_assessment=None,
        previous_relevant_result=None,
        semantic_context={},
        changed_fields=[],
        parse_method="rule_based_fallback",
        synthesis_method="template_fallback",
        data_quality_reports=[],
        risk_sufficient_data=None,
        user_location=user_loc,
        language_override=None,
    )
    final_state = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": conv_id}})
    return final_state


@app.post("/whatsapp")
@app.post("/webhook")
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Twilio WhatsApp Webhook Endpoint.

    Strategy: Return an immediate empty TwiML response to Twilio (within 1-2s)
    to avoid the 15-second webhook timeout. The actual query is processed in a
    background asyncio task, and the answer is sent back via Twilio REST API.
    """
    from_number = ""
    body_text = ""

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
            from_number = data.get("From") or data.get("from") or "whatsapp:+1000000000"
            body_text = data.get("Body") or data.get("query") or data.get("text") or ""
        except Exception:
            pass
    else:
        try:
            form_data = await request.form()
            from_number = form_data.get("From", "")
            body_text = form_data.get("Body", "")
        except Exception:
            pass

    from_number = str(from_number).strip()
    body_text = str(body_text).strip()

    twiml = MessagingResponse()

    if not body_text:
        twiml.message(
            "🌊 *Tarang Marine Safety Advisor*\n\n"
            "Please send a coastal query. For example:\n"
            "• _kal subah thoothukudi safe hai?_\n"
            "• _Is it safe to fish near Chennai tomorrow morning?_\n"
            "• _Where is the nearest PFZ near Kochi?_"
        )
        return Response(content=str(twiml), media_type="application/xml")

    session_id = from_number or "default_whatsapp_user"

    logger.info(f"Received WhatsApp query from {session_id}: {body_text!r}")

    # Launch background processing task — do NOT await it
    asyncio.create_task(
        _process_whatsapp_query_background(session_id, body_text)
    )

    # Return empty TwiML immediately so Twilio doesn't time out
    # The actual reply will be sent via Twilio REST API from the background task
    return Response(content=str(twiml), media_type="application/xml")


async def _process_whatsapp_query_background(session_id: str, body_text: str):
    """
    Background task: runs the full ORCA pipeline and sends the result
    back to the user via Twilio REST API (not TwiML).
    """
    from tools.whatsapp_sender import send_whatsapp_message

    try:
        session = session_store.get_session(session_id)

        final_state = await _run_graph_direct(
            query=body_text,
            conversation=session.get("conversation", []),
            last_parsed_intent=session.get("last_parsed_intent"),
            last_results=session.get("last_results", {}),
            wa_session_id=session_id,
        )

        answer_text = final_state.get("final_answer_text", "")
        risk_data = (
            final_state.get("risk_result", {}).get("data", {})
            if final_state.get("risk_result")
            else {}
        )

        formatted_reply = format_for_whatsapp(answer_text, risk_data)

        logger.info(f"[WhatsApp] answer_text length={len(answer_text)}, formatted_reply length={len(formatted_reply)}")
        logger.info(f"[WhatsApp] formatted_reply preview: {formatted_reply[:300]!r}")

        # Update session memory
        updated_history = list(session.get("conversation", []))
        updated_history.append({"role": "user", "content": body_text})
        updated_history.append({"role": "assistant", "content": answer_text[:500]})

        last_results = _extract_last_results(final_state)
        curr_intent = final_state.get("parsed_intent")
        if (not curr_intent or not curr_intent.get("location_name")) and session.get("last_parsed_intent"):
            curr_intent = session.get("last_parsed_intent")

        # Enrich curr_intent with resolved lat/lon so the next WhatsApp turn can
        # pre-seed the SessionRecord for location inheritance (LocationResolver Priority 5C).
        # The LLM parsed_intent only carries location_name, not coordinates.
        resolved_loc = final_state.get("resolved_location")
        if curr_intent and resolved_loc:
            if not curr_intent.get("lat") and resolved_loc.get("lat") is not None:
                curr_intent = dict(curr_intent)  # don't mutate original
                curr_intent["lat"] = resolved_loc["lat"]
                curr_intent["lon"] = resolved_loc["lon"]
                if not curr_intent.get("location_name") and resolved_loc.get("name"):
                    curr_intent["location_name"] = resolved_loc["name"]

        session_store.update_session(
            phone=session_id,
            conversation=updated_history,
            last_parsed_intent=curr_intent,
            last_results=last_results,
        )

        # Send reply via Twilio REST API (works regardless of webhook timeout)
        send_result = send_whatsapp_message(session_id, formatted_reply)
        if send_result.get("success"):
            logger.info(f"[WhatsApp] Reply sent successfully to {session_id} via REST API (SID={send_result.get('sid', 'simulated')})")
        else:
            logger.error(f"[WhatsApp] Failed to send reply to {session_id}: {send_result.get('error')}")

    except Exception as exc:
        logger.exception(f"[WhatsApp] Background processing error for {session_id}: {exc}")
        # Try to send error notification
        try:
            from tools.whatsapp_sender import send_whatsapp_message as _send
            _send(
                session_id,
                "⚠️ *Tarang Service Notice*\n\n"
                "An error occurred while processing your request. "
                "Please verify the location and try again in a few moments."
            )
        except Exception:
            logger.exception("[WhatsApp] Could not send error notification")


# ---------------------------------------------------------------------------
# Geofence Boundary Breach & Alert Endpoint
# ---------------------------------------------------------------------------

class RouteRequest(BaseModel):
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    start_name: str | None = None
    end_name: str | None = None
    departure_utc: str | None = None   # ISO-8601 departure time
    time_window: str = "next_24h"
    include_pfz: bool = True
    mode: str = "all"


class GeofenceEvaluateRequest(BaseModel):
    lat: float
    lon: float
    phone: Optional[str] = None
    name: Optional[str] = None
    trigger_whatsapp: Optional[bool] = True
    trigger_sms: Optional[bool] = True


# Server-side rate limiter for geofence WhatsApp/SMS alerts
_geofence_whatsapp_last_sent: dict[str, float] = {}  # phone -> last_sent_timestamp
_geofence_sms_last_sent: dict[str, float] = {}  # phone -> last_sent_timestamp
def _get_geofence_cooldown_s() -> int:
    return int(os.environ.get("GEOFENCE_WHATSAPP_COOLDOWN_SECONDS", "30"))


# ---------------------------------------------------------------------------
# Route Planning Endpoint
# ---------------------------------------------------------------------------

@app.post("/route")
async def route_endpoint(body: RouteRequest):
    """
    Compute safe, optimized marine routes between two locations.

    Supports multi-objective profiles:
      - 'safest': minimizes risk, rough swell, and IMBL boundary proximity
      - 'direct': minimizes nautical distance and transit time
      - 'pfz_maximizer': detours through high-chlorophyll potential fishing zones
      - 'all': computes and returns all 3 candidate profiles
    """
    from tools.route_planner import plan_safe_route

    try:
        result = plan_safe_route(
            start_lat=body.start_lat,
            start_lon=body.start_lon,
            end_lat=body.end_lat,
            end_lon=body.end_lon,
            start_name=body.start_name or "Start",
            end_name=body.end_name or "Destination",
            departure_utc=body.departure_utc,
            time_window=body.time_window,
            include_pfz=body.include_pfz,
            mode=body.mode,
        )
        return result
    except Exception as exc:
        logger.exception("[Route] Unhandled error in /route: %s", exc)
        raise HTTPException(status_code=500, detail=f"Route planning failed: {exc}")


# ---------------------------------------------------------------------------
# Geofence Evaluation Endpoint
# ---------------------------------------------------------------------------

@app.post("/geofence/evaluate")
def geofence_evaluate_endpoint(body: GeofenceEvaluateRequest):
    """
    Evaluate user coordinates against International Maritime Boundary Lines (IMBL).
    Detects if coordinates cross into foreign waters (e.g. Sri Lanka or Pakistan),
    computes return bearing to Indian safety, and dispatches critical WhatsApp + SMS alerts if breached.

    Alerts are rate-limited to one per GEOFENCE_WHATSAPP_COOLDOWN_SECONDS (default 300s = 5 min).
    If no phone is provided, falls back to TWILIO_RECIPIENT_PHONE from environment.
    """
    import time
    from tools.boundary_geo import evaluate_maritime_geofence
    from tools.whatsapp_sender import send_geofence_breach_alert
    from tools.sms_sender import send_geofence_breach_sms

    eval_result = evaluate_maritime_geofence(body.lat, body.lon, location_name=body.name or "")

    # Determine recipient phone: request body > config/env default
    recipient_phone = (
        (body.phone or "").strip()
        or getattr(config, "TWILIO_RECIPIENT_PHONE", "").strip()
        or os.environ.get("TWILIO_RECIPIENT_PHONE", "+919236454423").strip()
    )

    whatsapp_status = None
    whatsapp_rate_limited = False
    sms_status = None
    sms_rate_limited = False

    if eval_result.get("is_breached") and recipient_phone:
        now = time.time()
        cooldown_s = _get_geofence_cooldown_s()

        # --- WhatsApp dispatch ---
        if body.trigger_whatsapp:
            last_sent = _geofence_whatsapp_last_sent.get(recipient_phone, 0.0)
            elapsed = now - last_sent

            if elapsed >= cooldown_s:
                whatsapp_status = send_geofence_breach_alert(recipient_phone, eval_result)
                _geofence_whatsapp_last_sent[recipient_phone] = now
                logger.warning(
                    "[Geofence] WhatsApp breach alert dispatched to %s for location %s (dist=%.1f km)",
                    recipient_phone, body.name or f"({body.lat}, {body.lon})", eval_result.get("distance_km", 0.0)
                )
            else:
                remaining = int(cooldown_s - elapsed)
                whatsapp_rate_limited = True
                whatsapp_status = {
                    "success": False,
                    "rate_limited": True,
                    "cooldown_seconds": cooldown_s,
                    "next_allowed_in_seconds": remaining,
                    "note": f"WhatsApp alert rate-limited. Next alert allowed in {remaining}s.",
                }
                logger.info(
                    "[Geofence] WhatsApp alert rate-limited for %s (next in %ds)",
                    recipient_phone, remaining,
                )

        # --- SMS dispatch ---
        if body.trigger_sms:
            last_sent_sms = _geofence_sms_last_sent.get(recipient_phone, 0.0)
            elapsed_sms = now - last_sent_sms

            if elapsed_sms >= cooldown_s:
                sms_status = send_geofence_breach_sms(recipient_phone, eval_result)
                _geofence_sms_last_sent[recipient_phone] = now
                logger.warning(
                    "[Geofence] SMS breach alert dispatched to %s for location %s (dist=%.1f km)",
                    recipient_phone, body.name or f"({body.lat}, {body.lon})", eval_result.get("distance_km", 0.0)
                )
            else:
                remaining_sms = int(cooldown_s - elapsed_sms)
                sms_rate_limited = True
                sms_status = {
                    "success": False,
                    "rate_limited": True,
                    "cooldown_seconds": cooldown_s,
                    "next_allowed_in_seconds": remaining_sms,
                    "note": f"SMS alert rate-limited. Next alert allowed in {remaining_sms}s.",
                }
                logger.info(
                    "[Geofence] SMS alert rate-limited for %s (next in %ds)",
                    recipient_phone, remaining_sms,
                )

    return {
        **eval_result,
        "whatsapp_delivery": whatsapp_status,
        "whatsapp_result": whatsapp_status,
        "whatsapp_sent": bool(whatsapp_status and whatsapp_status.get("success") and not whatsapp_rate_limited),
        "sms_delivery": sms_status,
        "sms_result": sms_status,
        "sms_sent": bool(sms_status and sms_status.get("success") and not sms_rate_limited),
        "recipient_phone": recipient_phone if eval_result.get("is_breached") else None,
    }


# ---------------------------------------------------------------------------
# Incoming SMS Webhook (Twilio)
# ---------------------------------------------------------------------------

@app.post("/sms")
@app.post("/webhook/sms")
async def sms_webhook(request: Request):
    """
    Twilio SMS Webhook Endpoint.

    Accepts:
      - Standard Twilio form POST data (From, Body)
      - Or JSON data {"From": "...", "Body": "..."} for developer/API testing

    Returns:
      - TwiML XML (<Response><Message>...</Message></Response>)
    """
    from_number = ""
    body_text = ""

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
            from_number = data.get("From") or data.get("from") or "+1000000000"
            body_text = data.get("Body") or data.get("query") or data.get("text") or ""
        except Exception:
            pass
    else:
        try:
            form_data = await request.form()
            from_number = form_data.get("From", "")
            body_text = form_data.get("Body", "")
        except Exception:
            pass

    from_number = str(from_number).strip()
    body_text = str(body_text).strip()

    twiml = MessagingResponse()

    if not body_text:
        twiml.message(
            "TARANG Marine Safety Advisor\n"
            "Send a coastal query, e.g.:\n"
            "- Is it safe to fish near Chennai tomorrow?\n"
            "- Where is the nearest PFZ near Kochi?"
        )
        return Response(content=str(twiml), media_type="application/xml")

    # Use plain phone for SMS sessions (no whatsapp: prefix)
    session_id = f"sms:{from_number}" if from_number else "default_sms_user"
    session = session_store.get_session(session_id)

    logger.info(f"Received SMS query from {session_id}: {body_text!r}")

    try:
        final_state = await _run_graph_direct(
            query=body_text,
            conversation=session.get("conversation", []),
            last_parsed_intent=session.get("last_parsed_intent"),
            last_results=session.get("last_results", {}),
        )

        answer_text = final_state.get("final_answer_text", "")

        # For SMS, strip markdown formatting and keep concise
        import re
        sms_reply = re.sub(r'\*([^*]+)\*', r'\1', answer_text)  # remove *bold*
        sms_reply = re.sub(r'_([^_]+)_', r'\1', sms_reply)  # remove _italic_
        # Truncate to SMS-friendly length (max ~1500 chars for multi-part SMS)
        if len(sms_reply) > 1500:
            sms_reply = sms_reply[:1497] + "..."

        # Update session memory
        updated_history = list(session.get("conversation", []))
        updated_history.append({"role": "user", "content": body_text})
        updated_history.append({"role": "assistant", "content": answer_text[:500]})

        last_results = _extract_last_results(final_state)
        curr_intent = final_state.get("parsed_intent")
        if (not curr_intent or not curr_intent.get("location_name")) and session.get("last_parsed_intent"):
            curr_intent = session.get("last_parsed_intent")

        session_store.update_session(
            phone=session_id,
            conversation=updated_history,
            last_parsed_intent=curr_intent,
            last_results=last_results,
        )

        twiml.message(sms_reply)
        return Response(content=str(twiml), media_type="application/xml")

    except Exception as exc:
        logger.exception(f"Error processing SMS query: {exc}")
        twiml.message(
            "TARANG Service Notice:\n"
            "An error occurred processing your request. "
            "Please verify the location and try again."
        )
        return Response(content=str(twiml), media_type="application/xml")


# ---------------------------------------------------------------------------
# Ecosystem Productivity & Researcher Suite Endpoints
# ---------------------------------------------------------------------------

@app.get("/analytics/regions")
async def get_ecosystem_regions():
    from tools.ecosystem_analytics import get_available_regions
    return {"regions": get_available_regions()}

@app.get("/analytics/productivity")
async def get_ecosystem_productivity(
    region: str = Query("malabar", description="Coastal region ID"),
    start_year: int = Query(2018, description="Start year"),
    end_year: int = Query(2024, description="End year"),
):
    from tools.ecosystem_analytics import get_regional_ecosystem_data
    try:
        data = get_regional_ecosystem_data(region, start_year=start_year, end_year=end_year)
        return data
    except Exception as exc:
        logger.exception(f"Error fetching productivity analytics for {region}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

class DiagnoseProductivityRequest(BaseModel):
    region: str = "malabar"
    start_year: int = 2018
    end_year: int = 2024

@app.post("/analytics/productivity/diagnose")
async def diagnose_productivity_endpoint(body: DiagnoseProductivityRequest):
    from tools.ecosystem_analytics import diagnose_productivity_decline
    try:
        diag = diagnose_productivity_decline(body.region, start_year=body.start_year, end_year=body.end_year)
        return diag
    except Exception as exc:
        logger.exception(f"Error diagnosing productivity decline for {body.region}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

class ResearcherChatRequest(BaseModel):
    region: str = "malabar"
    message: str
    history: Optional[List[Dict[str, str]]] = None

@app.post("/analytics/chat")
async def researcher_chat_endpoint(body: ResearcherChatRequest):
    from tools.ecosystem_analytics import chat_researcher_ecosystem
    try:
        reply = chat_researcher_ecosystem(
            region_id=body.region,
            message=body.message,
            history=body.history,
        )
        return {"region": body.region, "reply": reply}
    except Exception as exc:
        logger.exception(f"Error in researcher chat for {body.region}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))