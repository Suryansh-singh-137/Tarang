# Tarang (तरंग) — Marine Intelligence & Decision Support Platform

**Tarang** is an AI-powered Marine Safety and Fisheries Intelligence Decision-Support Engine for artisanal and small-scale fishermen along India's 7,516 km coastline.

## Problem We Solve

Artisanal fishermen face three critical challenges:

1. **Hazardous Sea Conditions**: Dense technical bulletins from INCOIS and IMD are incomprehensible to non-English speakers
2. **Maritime Border Enforcement**: Vessels inadvertently cross the IMBL (International Maritime Boundary Line) into foreign waters, leading to arrests and seizures
3. **Inefficient Fishing Routes**: No spatial guidance for Potential Fishing Zones (PFZ), resulting in wasted fuel and time

Tarang solves this by ingesting live satellite, meteorological, and geospatial data, reasoning deterministically over safety risks, and delivering actionable, plain-language answers in **English, Hindi, and Tamil** via:
- **Web Application** (Next.js 14)
- **WhatsApp Bot** (Twilio integration)
- **Voice Interface** (Groq Whisper + Sarvam AI)

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker (optional)

### Installation

**Backend Setup:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file with required API keys
cp .env.example .env
```

**Frontend Setup:**
```bash
cd frontend
npm install
```

### Running Locally

**Terminal 1 — Backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
# Open http://localhost:3000
```

### Testing a Sample Request

**Via cURL:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Is it safe to go out from Kochi tomorrow morning?",
    "conversation_id": "test-conv-1",
    "language": "en",
    "selected_location": {"name": "Kochi", "lat": 9.9312, "lon": 76.2673}
  }' \
  --raw
```

**Via Web UI:**
1. Navigate to `http://localhost:3000`
2. Select a location (e.g., "Thoothukudi")
3. Type a marine safety question
4. Watch the agent pipeline execute in real-time

---

## Project Structure

```
tarang/
├── DATA_SOURCES.md                    # Comprehensive API inventory
├── backend/
│   ├── main.py                        # FastAPI entry point
│   ├── config.py                      # Centralized configuration (env vars, TTLs)
│   ├── requirements.txt               # Python dependencies
│   ├── graph/
│   │   ├── state.py                   # TypedDict: ORCAState, AgentResult, EvidenceItem
│   │   ├── build_graph.py             # LangGraph StateGraph compiler & routing logic
│   │   └── nodes/                     # Specialist agent implementations
│   │       ├── detect_and_parse.py    # NLP intent parsing & location resolution
│   │       ├── weather_agent.py       # Open-Meteo Marine API (waves, wind)
│   │       ├── pfz_agent.py           # INCOIS satellite chlorophyll zones
│   │       ├── ocean_agent.py         # Harmonic tidal predictions (Chart Datum)
│   │       ├── hazard_agent.py        # GDACS cyclones + IMD coastal alerts
│   │       ├── geofence_agent.py      # IMBL boundary proximity monitoring
│   │       ├── risk_agent.py          # Deterministic risk scoring + safety overrides
│   │       ├── explain_risk.py        # Factor contribution breakdown
│   │       └── synthesis.py           # Layer 1 + Layer 2 response generation
│   ├── location/
│   │   ├── models.py                  # Pydantic schemas (LocationSlot, HarbourDetail)
│   │   ├── service.py                 # Marine boundary checks, harbour catalog
│   │   ├── resolver.py                # Three-tier location resolver
│   │   └── applicability.py           # Coastal vs inland routing rules
│   ├── session/
│   │   └── session_store.py           # In-memory session persistence (TTL cleanup)
│   ├── tools/                         # Reusable API clients & formatters
│   │   ├── boundary_geo.py            # Great-circle distance & bearing math
│   │   ├── incois_client.py           # ERDDAP REST client (chlorophyll)
│   │   ├── marine_weather_client.py   # Open-Meteo wrapper
│   │   ├── hazard_client.py           # GDACS + IMD aggregator
│   │   ├── whatsapp_formatter.py      # Markdown to WhatsApp styling
│   │   ├── whatsapp_sender.py         # Twilio REST API wrapper
│   │   └── source_registry.py         # Provenance tier hierarchy
│   ├── data/
│   │   ├── coastal_places.json        # 35+ Indian fishing harbours
│   │   ├── imbl_boundary.geojson      # UNCLOS treaty boundary polylines
│   │   ├── fallback_weather.json      # Offline test payloads
│   │   ├── fallback_hazards.json      # Pre-computed cyclone data
│   │   └── fallback_pfz.json          # Satellite PFZ zones
│   └── tests/                         # Pytest suite & regression tests
│       ├── test_dynamic_location_system.py
│       ├── test_geofence_breach.py
│       └── test_failure_injection.py
└── frontend/
    ├── src/
    │   ├── app/                       # App Router pages (/, /app)
    │   ├── components/
    │   │   ├── chat/                  # Message bubbles, evidence drawer
    │   │   ├── location/              # Location selector modal
    │   │   ├── map/                   # Leaflet map (IMBL lines, PFZ zones)
    │   │   ├── alerts/                # Hazard bulletins
    │   │   └── trace/                 # Agent execution transparency
    │   └── lib/
    │       ├── api.ts                 # SSE streaming & REST client
    │       ├── locationContext.tsx    # React Context for 3-tier locations
    │       └── types.ts               # TypeScript interfaces
    └── tailwind.config.ts             # "Coastal Dawn" design system
```

---

## System Architecture

### High-Level Data Flow

```
[USER QUERY]  (WhatsApp / Web UI / Voice)
    │
    ▼
[FastAPI /query Endpoint]
    │
    ▼
[detect_and_parse] ──► Intent classification, temporal resolution, location mapping
    │
    ├─► [weather_agent]      ──► Open-Meteo (waves, wind, pressure)
    ├─► [pfz_agent]          ──► INCOIS ERDDAP (chlorophyll zones)
    ├─► [ocean_agent]        ──► Harmonic tidal prediction
    ├─► [hazard_agent]       ──► GDACS + IMD (cyclones, alerts)
    ├─► [geofence_agent]     ──► IMBL boundary proximity
    │
    ▼
[risk_agent] ──► Deterministic weighted scoring + safety overrides
    │
    ▼
[synthesis] ──► Layer 1 (Conversational) + Layer 2 (Evidence Cards)
    │
    ▼
[OUTPUT] ──► SSE (Web) / TwiML (WhatsApp) / Audio (Voice)
```

### LangGraph Orchestration

Tarang uses a **compiled LangGraph StateGraph** with deterministic sequential routing:

```
detect_and_parse → weather → pfz → ocean → hazard → geofence → risk → explain_risk → status_validator → synthesis → END
```

**Node-Level Routing (Wrapper Gating):**
- Each agent wrapper node inspects boolean flags (needs_weather, needs_pfz, needs_hazard, etc.)
- If an agent is not needed or location is inland: wrapper calls `_skip()`, recording explicit "skipped" status in trace
- If needed: evaluates cache validity via `_can_reuse_cached()`, re-injects cached result if TTL valid, otherwise executes live specialist agent
- **Result**: 100% complete execution trace, always audit-ready

**Fail-Closed Architecture:**
- If weather or hazard data is unreachable: risk_agent refuses to compute partial score
- Outputs `final_level = "UNKNOWN"` and disables all "Safe" badges
- Presents explicit safety warning

---

## Agent Specializations

| Agent | File | Purpose | Input | Output | When Executed |
|-------|------|---------|-------|--------|---------------|
| **detect_and_parse** | `detect_and_parse.py` | NLP intent parsing, temporal resolution, location mapping | raw_query, conversation_history | ParsedIntent (intent flags, canonical coords, AnswerPlan) | Always (first node) |
| **weather_agent** | `weather_agent.py` | Marine atmospheric & ocean-surface variables | lat, lon, time_start_utc, time_end_utc | Wave height (Hs), wind speed, pressure, sea state | `needs_weather == True` |
| **pfz_agent** | `pfz_agent.py` | Potential Fishing Zones via satellite chlorophyll | Departure harbour lat, lon, search_radius | GeoJSON zones, distances, bearings from harbour | `needs_pfz == True` |
| **ocean_agent** | `ocean_agent.py` | Tidal predictions & water level (Chart Datum) | Coastal lat, lon | next_high_tide, next_low_tide, water_level_m, tidal_phase | `needs_ocean == True` |
| **hazard_agent** | `hazard_agent.py` | Active cyclones, coastal alerts, weather warnings | lat, lon, search_radius (500 km) | overall_hazard_level, active_warnings, cyclone parameters | `needs_hazard == True` |
| **geofence_agent** | `geofence_agent.py` | IMBL boundary proximity monitoring | lat, lon | distance_to_boundary_km, boundary_risk, safe_bearing_deg | `needs_geofence == True` |
| **risk_agent** | `risk_agent.py` | Deterministic multi-factor safety scoring | Outputs from weather, hazard, geofence agents | composite_score (0-100), final_level, components breakdown | `needs_risk == True` |
| **synthesis** | `synthesis.py` | Two-layer response generation | All agent outputs + AnswerPlan | Layer 1 (conversational text) + Layer 2 (evidence cards) | Always (last node) |

---

## API Endpoints

### POST /query

**Description:** Core question-answering endpoint with Server-Sent Events (SSE) streaming.

**Request:**
```json
{
  "query": "Is it safe to fish near Kochi tomorrow?",
  "conversation_id": "conv-4a8b2c",
  "language": "en",
  "selected_location": {
    "name": "Kochi",
    "lat": 9.9312,
    "lon": 76.2673
  },
  "conversation": [
    { "role": "user", "content": "..." }
  ]
}
```

**Streamed Events:**
- `event: status` → `{"agent": "weather_agent", "status": "running"}` (UI agent indicator)
- `event: result` → Final payload with answer_text, risk_data, evidence, map_geojson, trace

**Response Example:**
```json
{
  "answer_text": "Sea conditions near Kochi are generally calm with wave heights around 1.2m and moderate winds...",
  "risk_data": {
    "composite_score": 18.0,
    "risk_label": "LOW",
    "components": [
      { "factor": "wave_height", "score": 20.0, "weight": 0.30 },
      { "factor": "wind_speed", "score": 25.0, "weight": 0.20 }
    ]
  },
  "evidence": [
    {
      "type": "wave_height",
      "value": 1.2,
      "unit": "m",
      "timestamp": "2026-09-15T10:30Z",
      "source_tier": "live"
    }
  ],
  "map_geojson": {
    "type": "FeatureCollection",
    "features": [
      { "type": "Feature", "geometry": {...}, "properties": {"type": "pfz_zone"} }
    ]
  },
  "trace": [...]
}
```

---

### GET /location/marine-access

**Description:** Computes topological marine context and returns nearest fishing harbours.

**Query Params:**
- `lat` (float): Latitude
- `lon` (float): Longitude

**Response:**
```json
{
  "marine_context": "COASTAL",
  "distance_to_coast_km": 0.8,
  "nearest_harbours": [
    {
      "name": "V.O. Chidambaranar Port, Thoothukudi",
      "lat": 8.7642,
      "lon": 78.1348,
      "distance_km": 0.8,
      "bearing_deg": 45.2
    }
  ]
}
```

---

### POST /transcribe

**Description:** Converts audio (WhatsApp/Voice) to text.

**Request:** multipart/form-data with audio blob

**Response:**
```json
{
  "transcript": "Is it safe to go out tomorrow?",
  "detected_language_whisper": "en"
}
```

---

### POST /speak

**Description:** Converts text to speech (Indian languages).

**Request:**
```json
{
  "text": "समुद्र की स्थिति कल सुबह सामान्य होगी।",
  "language": "hi"
}
```

**Response:** Binary audio/wav stream

---

### POST /whatsapp

**Description:** Twilio webhook for inbound WhatsApp messages.

**Request:** Form-encoded from Twilio

**Response:** TwiML reply with message text

---

### POST /geofence/evaluate

**Description:** Real-time GPS geofencing against IMBL boundaries.

**Request:**
```json
{
  "lat": 8.15,
  "lon": 78.25,
  "phone": "+919876543210"
}
```

**Response:**
```json
{
  "inside_boundary": true,
  "distance_to_boundary_km": 72.4,
  "boundary_risk": "low"
}
```

If `distance_to_boundary_km < 10 km`, triggers WhatsApp alert (rate-limited to 1 per 5 minutes).

---

## Data Sources & External APIs

| API | Purpose | Auth | Rate Limits | Freshness |
|-----|---------|------|-------------|-----------|
| **Open-Meteo Marine** | Wave height, wave period, sea state | Public/Free | Unlimited | 10 min cache |
| **Open-Meteo Forecast** | Wind speed, gusts, pressure, visibility | Public/Free | Unlimited | 10 min cache |
| **INCOIS ERDDAP** | Satellite chlorophyll (Oceansat-2) | Public/Free | Unlimited | 60 min cache |
| **GDACS** | Global Disaster Alert; tropical cyclones | Public/Free | Unlimited | 10 min cache |
| **Groq Cloud** | Fast LLM inference (parsing, synthesis) | API Key | 10 req/min | Real-time |
| **Sarvam AI** | Text-to-Speech (Hindi, Tamil, English) | API Key | Quota-based | Real-time |
| **OpenWeather Geocoding** | Place name → coordinate resolution | API Key | 1000/day | Cached |
| **OSM Nominatim** | Reverse geocoding, place search | Public | 1 req/sec | Cached |
| **Twilio WhatsApp** | Inbound/outbound messaging | API Key | Quota-based | Real-time |

### Fallback Behavior

If an API is unreachable:
1. **Weather**: Falls back to `data/fallback_weather.json`
2. **PFZ**: Falls back to `data/fallback_pfz.json` (pre-extracted regional zones)
3. **Hazard**: Cached historical feed or `data/fallback_hazards.json`
4. **Risk Scoring**: Fails-closed with `final_level = "UNKNOWN"`, disables all "Safe" badges

---

## Configuration

All parameters are externalized in `.env`:

```bash
# LLM & Voice Providers
GROQ_API_KEY=gsk_...
GROQ_MODEL_FAST=openai/gpt-oss-20b      # For fast parsing
GROQ_MODEL_QUALITY=openai/gpt-oss-120b  # For synthesis
SARVAM_API_KEY=...
OPENWEATHER_API_KEY=...

# Twilio WhatsApp Integration
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
TWILIO_RECIPIENT_PHONE=+919236454423

# Operational Thresholds
HTTP_TIMEOUT=10                          # seconds
CACHE_TTL_MARINE_S=600                   # 10 minutes (weather, hazard)
CACHE_TTL_PFZ_S=3600                     # 60 minutes (satellite chlorophyll)
FOLLOWUP_CACHE_TTL_SECONDS=300           # Multi-turn conversation caching
MAX_CONVERSATION_TURNS=6
GEOFENCE_WHATSAPP_COOLDOWN_SECONDS=300   # Rate-limit breach alerts

# Location & Marine Access
MARINE_COASTAL_THRESHOLD_KM=15
INLAND_THRESHOLD_KM=60

# Risk Weights (must sum to 1.0)
RISK_WEIGHT_WAVE=0.30
RISK_WEIGHT_WIND=0.20
RISK_WEIGHT_HAZARD=0.30
RISK_WEIGHT_BOUNDARY=0.20

# LangGraph Checkpointer
LANGGRAPH_CHECKPOINTER=memory  # or "postgres" for production
```

---

## Database & Storage

### Session Store (In-Memory)

**Schema:**
```python
SessionRecord:
  - conversation_id: str                     # Unique identifier
  - reference_location: Optional[LocationSlot]    # Where user is now
  - departure_location: Optional[HarbourDetail]   # Where boat leaves from
  - operating_area: Optional[LocationSlot]       # Where boat operates
  - device_location: Optional[DeviceLocation]    # GPS coordinates
  - conversation: List[ConversationTurn]    # Max 6 turns (pruned)
  - last_parsed_intent: Optional[ParsedIntent]   # Cache for follow-ups
  - last_results: Dict[str, AgentResult]   # Agent outputs (reused if TTL valid)
  - updated_at: float                      # Epoch timestamp (TTL cleanup)
```

**TTL Cleanup:**
- Sessions inactive for > 10 minutes (`WHATSAPP_SESSION_TTL_SECONDS = 600`) are evicted from memory

### LangGraph Checkpoint Memory

- Managed by `langgraph.checkpoint.memory.MemorySaver`
- Allows resuming interrupted graph executions
- Inspects step-by-step state diffs for debugging

### Static Geospatial Assets

- **imbl_boundary.geojson**: UNCLOS treaty coordinates for India-Sri Lanka, India-Pakistan, India-Bangladesh boundaries
- **coastal_places.json**: 100+ fishing harbours and coastal villages with exact coordinates

---

## Deployment

### Docker Setup (Production)

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build & Run:**
```bash
docker build -t tarang-backend .
docker run -p 8000:8000 --env-file .env tarang-backend
```

### Environment Setup

1. Create `.env` file with all required API keys
2. Ensure `.env` is **not** committed to Git (add to `.gitignore`)
3. Deploy secrets via CI/CD (GitHub Secrets, GitLab CI, etc.)

### Monitoring & Logging

- **Application Logs**: Streamed to stdout (pick up with Docker logs)
- **Execution Traces**: Complete step-by-step logs in `/trace` event
- **Performance Metrics**: Agent execution latency in SSE status events

---

## Troubleshooting

### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| **API Key Missing** | 401 Unauthorized from Groq/Twilio | Verify `.env` file has correct keys; check console for which service failed |
| **Location Not Found** | "No matching location" error | Check `coastal_places.json` gazetteer; fall back to OSM Nominatim |
| **Weather Data Stale** | Evidence shows old timestamp | Check cache TTL (`CACHE_TTL_MARINE_S`); API may be down (check fallback) |
| **Risk = UNKNOWN** | Safety warning instead of risk score | Weather or hazard data unreachable; check API connectivity and fallback files |
| **WhatsApp Messages Not Sending** | Twilio errors in logs | Verify `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, phone numbers correct |
| **Graph Execution Hangs** | Response takes > 30 seconds | Check individual agent timeouts; increase `HTTP_TIMEOUT` if needed |

### Debug Mode

Enable debug logging in config:
```python
# config.py
DEBUG = True
LOG_LEVEL = "DEBUG"
```

View detailed trace in SSE events:
```bash
curl -N http://localhost:8000/query ... | grep "event: status"
```

---

## Contributing

### Adding a New Agent

1. Create `backend/graph/nodes/new_agent.py`:
```python
from langgraph.graph import StateGraph
from backend.graph.state import ORCAState

async def new_agent(state: ORCAState) -> dict:
    """Your agent logic."""
    return {
        "new_agent_result": AgentResult(
            agent="new_agent",
            status="success",
            data_quality="live",
            data={...}
        )
    }
```

2. Register in `build_graph.py`:
```python
graph.add_node("new_agent", new_agent)
graph.add_edge("previous_node", "new_agent")
```

3. Add parsing logic in `detect_and_parse.py`:
```python
parsed_intent.needs_new_agent = "new_agent" in user_query.lower()
```

4. Add tests in `backend/tests/test_new_agent.py`

5. Update `config.py` with cache TTL and risk weights (if applicable)

### Code Style

- Follow **PEP 8** (Python)
- Use **type hints** throughout
- Write docstrings for all functions
- Test locally before pushing

### PR Review Process

1. Create branch: `git checkout -b feature/agent-name`
2. Implement & test locally
3. Ensure all tests pass: `pytest backend/tests/`
4. Submit PR with description of changes
5. Address review comments

---

## Performance Baselines

| Operation | Typical Latency | Notes |
|-----------|-----------------|-------|
| **Intent Parsing** | 200–350ms | Groq fast model (gpt-oss-20b) |
| **Single Agent** | 300–800ms | Weather: ~400ms, Hazard: ~600ms |
| **Complete Query** | 2.5–3.5s | All agents in parallel (sequential graph) |
| **Follow-up (Cached)** | 400–600ms | Re-uses agent results if TTL valid |
| **SSE Start-to-First Event** | 100–200ms | Network + FastAPI overhead |

### Optimization Tips

- **Caching**: Validate `CACHE_TTL_*` settings for your use case
- **Parallel Agents**: Current graph is sequential; agents could be parallelized (not yet implemented)
- **LLM Selection**: `GROQ_MODEL_FAST` is optimized for latency; switch to `GROQ_MODEL_QUALITY` for accuracy if needed
- **Database**: Production deployments should replace in-memory `SessionStore` with PostgreSQL

---

## Key Architectural Decisions

### 1. Deterministic Risk Scoring (No LLM)

- Risk agent uses **mathematical weighted formula**, not LLM inference
- Ensures **reproducibility**, **auditability**, and **transparency**
- Safety overrides (cyclones) always trigger regardless of other factors

### 2. Three-Tier Location Model

- **Reference Location** (where user is now) ≠ **Departure Harbour** (where boat leaves) ≠ **Operating Area** (where boat fishes)
- Prevents accidental erasure of location context in multi-turn conversations

### 3. Fail-Closed Architecture

- Missing critical data → `risk_level = "UNKNOWN"`
- Never delivers false "Safe" reassurance
- Errs on the side of caution

### 4. Strict Attribution Contract (Layer 1 + Layer 2)

- **Layer 1**: Plain-language conversational response (no jargon, no agent names)
- **Layer 2**: Structured evidence cards with timestamps, sources, and data provenance tiers
- LLM synthesis forbidden from inventing metrics

---

## Resources

- **DATA_SOURCES.md**: Comprehensive inventory of all APIs, variables, TTLs, and rate limits
- **backend/graph/state.py**: All TypedDict definitions (read here first!)
- **backend/graph/nodes/*.py**: Individual agent implementations with docstrings
- **frontend/src/components/trace/TraceDrawer.tsx**: Real-time agent execution visualization

---

## License

© 2026 Tarang Project. All rights reserved.

---

## Team Contacts

- **Backend Lead**: [Your Name]
- **Frontend Lead**: [Your Name]
- **Data & Geospatial**: [Your Name]

For questions or issues, open a GitHub issue or reach out to the team Slack channel.
