# Tarang Backend — Agentic Marine Safety Intelligence

The Tarang backend is an AI-powered, multi-agent pipeline built with LangGraph. It provides marine safety intelligence by aggregating weather forecasts, remote sensing data (chlorophyll proxies for PFZs), maritime boundary proximity (IMBL), and dynamic hazards.

## Recent Updates (Milestones 3, 4, and 5)

We have recently completed a series of architectural hardenings to improve explainability, safety disclosures, and multi-turn conversational support:

### Milestone 3: Trust & Disclosure
- **Data Quality Labels:** All agents now append a `data_quality` metadata tag (`live`, `fallback`, or `historical_proxy`) to their results.
- **Proxy Disclosures:** The PFZ agent explicitly identifies itself as a `historical_proxy` utilizing chlorophyll-a concentration models, rather than claiming to be a real-time satellite snapshot.
- **Honest Synthesis:** The `synthesis` node dynamically discloses which data sources were live versus fallback, and restricts the LLM from making definitive "it is safe" claims, reframing them as decision-support insights.

### Milestone 4: Explainable Risk
- **Structured Risk Scoring:** The `risk_agent` now generates a comprehensive `composite_score` derived from individualized `RiskComponent` structures.
- **Non-LLM Risk Explanation:** A new `explain_risk` node provides deterministic, templated breakdowns of *why* a particular risk score was assigned (e.g. detailing the exact contribution of wave height or wind speed), completely bypassing LLM hallucination for safety-critical justifications.

### Milestone 5: Conversational Memory (Multi-Turn)
- **Multi-Turn API State:** The `/query` endpoint now accepts and returns a `conversation` array (representing past turns) alongside `last_results` and `last_parsed_intent`.
- **Selective Agent Re-Invocation:** When answering follow-up queries, the pipeline intelligently compares `changed_fields` (e.g. a user only changing the `time_window`). If a dependency field hasn't changed, the pipeline re-uses the cached agent result instead of making redundant API calls (TTL-based cache).

### Milestone 6: Real LLM Integration (Groq)
Tarang uses Groq-hosted LLMs for query understanding and answer synthesis, with deterministic fallback on failure; risk scoring and risk explanation remain fully deterministic by design, to eliminate hallucination risk in safety-critical numeric output.

## Running the API

### Setup
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Environment
Copy `.env.example` to `.env`. The backend uses Open-Meteo for marine data and INCOIS ERDDAP for chlorophyll/PFZ indicators.

### Start the Server
```bash
python main.py
```
The FastAPI application runs by default on `http://localhost:8000`.

### Testing
To run the full end-to-end test suite encompassing multi-turn and disclosure logic:
```bash
python -m pytest test_graph.py
# Or run it directly with custom queries:
python test_graph.py --all
```
