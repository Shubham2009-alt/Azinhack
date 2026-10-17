# ResearchPilot AI

ResearchPilot turns a scientific research question into a structured, evidence-backed report with source-linked claims, cross-source comparisons, candidate research gaps and an interactive evidence graph.

It is an evidence-traceability tool for early-stage literature exploration—not a guarantee of scientific correctness or global novelty.

## Current status
- [x] Product requirements, behavior specification and architecture documented.
- [x] FastAPI health, create-research-run, and run-status endpoints added.
- [x] React/Vite/TypeScript question form connected to the create-run API.
- [x] TinyFish academic-paper search connected to new research runs; full-page fetch and LLM analysis remain pending.
- [x] SQLAlchemy models and SQLite table initialization are added for research runs, sources, claims, reports and evidence-graph relationships.
- [ ] Full orchestration, full-page retrieval, claim extraction, report generation and graph API are not implemented yet.

## MVP pipeline
Research question → query planning → TinyFish discovery/retrieval → structured extraction → evidence validation → claim comparison → candidate-gap analysis → cited report and evidence graph.

## Planned stack
- Frontend: React, Vite, TypeScript.
- Backend: Python 3.12, FastAPI, Pydantic, HTTPX.
- Analysis: configurable LLM API with structured output and deterministic validation.
- Research discovery: TinyFish Search API (`research_paper` domain type); TinyFish Fetch and LLM analysis are follow-up steps.
- Persistence: SQLAlchemy 2.x, SQLite (Alembic migrations remain a follow-up).
- Quality: pytest and Ruff; frontend ESLint and TypeScript build.

## Repository map
- `backend/app/main.py`: FastAPI health, create-run and run-status endpoints; new runs start source discovery in a FastAPI background task.
- `backend/app/services/tinyfish_search.py`: TinyFish academic search client and response normalization.
- `backend/app/services/research_discovery.py`: source persistence and run-state updates.
- `backend/app/settings.py`: environment-backed settings, including `DATABASE_URL`.
- `backend/app/database.py`: engine, session dependency and table initialization.
- `backend/app/models/`: research records and evidence-graph persistence models.
- `backend/tests/`: backend tests.
- `frontend/src/App.tsx`: question-entry interface connected to the API; it displays the queued run ID.
- `frontend/src/styles.css`: responsive workspace styling.
- `docs/prd-researchpilot.md`: product requirements.
- `docs/spec-research-report.md`: behavior, API and data contracts.
- `docs/architecture.md`: system boundaries and data flow.
- `CLAUDE.md`: coding-agent rules.

## Prerequisites
- Python 3.12+
- Node.js 20.19+ or 22.12+ (required by Vite 6)
- npm

## Run locally

### Backend
From the repository root:

```bash
cd backend
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: `http://127.0.0.1:8000/api/health`

Run backend tests in a second terminal:

```bash
cd backend
pytest
ruff check .
```

### Frontend
In a separate terminal from the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`). Check the production bundle and lint rules with:

```bash
npm run build
npm run lint
```

The frontend submits questions to the API and displays the saved run ID. When `TINYFISH_API_KEY` is configured on the backend, a background task searches academic papers and stores source metadata. Without a key, the run fails with a clear configuration status. Full-page source retrieval, claim extraction, LLM analysis, report generation and graph retrieval are not implemented yet.

## Environment and security
The backend reads optional TinyFish and LLM configuration from environment variables. TinyFish is called by the backend source-discovery service; LLM configuration is reserved for a later step. Use real credentials only in a local, ignored `.env` file or the deployment secret manager. Never commit API keys, tokens or real environment files. Additional provider integration will follow verification of each official API contract.

## Evidence integrity
- Preserve original source URLs and excerpts supporting claims.
- Separate source-reported findings from model interpretations.
- Mark weak evidence and inaccessible sources clearly.
- Never claim global novelty based solely on an unsuccessful search.
- Never bypass paywalls or access controls.

## Verification status
The files have been added to the repository, but commands have not been executed in a runtime during this step. Do not interpret the existence of tests or scripts as proof that they pass.
