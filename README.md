# ResearchPilot AI

ResearchPilot helps turn a research question into a structured, evidence-linked draft that is easier to inspect, compare, and discuss.

Instead of treating a single search result as a final answer, it gathers sources, validates the evidence, and surfaces only the claims that can actually be tied back to retrieved text. It is built for early-stage literature exploration, not for claiming scientific certainty or global novelty.

## What this project does

- Accepts a research question from the user
- Finds candidate papers and fetches accessible source content
- Stores source metadata and retrieval status
- Extracts evidence-backed claims only when the extracted excerpt matches retrieved text
- Compares claims across sources and suggests tentative research gaps
- Shows a report, source list, and evidence graph for human review

## Current status

- [x] Product requirements and architecture docs are in place
- [x] Backend APIs for health checks, research-run creation, and status retrieval are working
- [x] Frontend flow for submitting a question and viewing results is implemented
- [x] TinyFish search and fetch are integrated with normalization and failure handling
- [x] SQLite persistence for runs, sources, claims, and relationships is in place
- [x] LLM extraction is limited to claims that match retrieved source excerpts exactly
- [x] Cross-source comparisons and candidate research gaps are saved as draft output
- [x] Read-only report, source, and graph endpoints are exposed
- [x] Frontend results workspace shows progress, source cards, evidence, and graph relationships

## How the pipeline works

Research question → source discovery → source retrieval → evidence validation → cross-source comparison → draft report and graph

## Main API endpoints

- `GET /api/health` — liveness check; confirms the API process is responding
- `GET /api/health/ready` — readiness check; returns `200` only when the configured database can execute a simple query, otherwise `503`
- `GET /api/research-runs/{run_id}/report` — report draft, source-linked claims, and warnings
- `GET /api/research-runs/{run_id}/sources` — discovered sources, retrieval status, and linked claims
- `GET /api/research-runs/{run_id}/graph` — nodes and relationships for the evidence graph
- Unknown run IDs return a `404`
- Candidate research gaps remain hypotheses, not proof of novelty

## Tech stack

- Frontend: React, Vite, TypeScript
- Backend: Python 3.12+, FastAPI, Pydantic, HTTPX
- Data layer: SQLAlchemy 2.x, SQLite
- Search/retrieval: TinyFish Search and Fetch
- Analysis: OpenAI-compatible LLM API with structured validation
- Quality checks: pytest, Ruff, ESLint, TypeScript build

## Repository layout

- `backend/app/main.py` — API routes, health checks, validation, and error handling
- `backend/app/services/tinyfish_search.py` — TinyFish search client and URL normalization
- `backend/app/services/tinyfish_fetch.py` — TinyFish fetch client and bounded content extraction
- `backend/app/services/research_discovery.py` — source discovery and retrieval flow
- `backend/app/settings.py` — environment-backed configuration
- `backend/app/database.py` — database connection and startup setup
- `backend/app/models/` — persisted research data models
- `backend/tests/` — API, database, and provider-mock tests
- `frontend/src/App.tsx` — main UI and polling logic
- `frontend/src/styles.css` — interface styling
- `docs/` — product, spec, and runbook documents
- `CLAUDE.md` — repo-specific instructions for the coding agent

## Prerequisites

- Python 3.12+
- Node.js 20.19+ or 22.12+
- npm

## Run locally

### 1) Backend

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

Check liveness at `http://127.0.0.1:8000/api/health` and database readiness at `http://127.0.0.1:8000/api/health/ready`.

The liveness endpoint does not depend on database availability. Use the readiness endpoint for deployment checks that should route traffic only when the database is reachable.

Run the backend tests in a second terminal:

```bash
cd backend
pytest
ruff check .
```

### 2) Frontend and Supabase Auth

Create a Supabase project and enable Email authentication. In the Supabase dashboard, configure the allowed site URL and redirect URLs for your frontend deployment. Copy `frontend/.env.example` to `frontend/.env.local`, then set `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` using the project's URL and publishable key. The publishable key is intended for browser use; never put a Supabase secret or service-role key in a `VITE_` variable.

In a separate terminal from the repo root:

```bash
cd frontend
npm install
npm run dev
```

Open the local Vite URL, usually `http://localhost:5173`. The frontend keeps the session in `sessionStorage` and attaches the access token to API requests. **Backend token verification and per-run ownership enforcement are a separate follow-up PR; do not treat this frontend foundation alone as protecting API data.**

For build and lint checks:

```bash
npm run build
npm run lint
```

## Security and environment notes

The backend reads provider settings from environment variables. Keep real credentials in a local `.env` file or your deployment secret manager, and never commit them.

Recommended values:

- `TINYFISH_API_KEY`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`

A few good defaults to keep in mind:

- Do not expose provider keys to the browser
- Keep secret material on the backend only
- Never store real credentials in a commit, issue, screenshot, or shared log
- Treat all external provider responses as untrusted input and validate before displaying or persisting them

For production deployment limits and the current no-authentication boundary, see [docs/deployment-security.md](docs/deployment-security.md).

## Evidence integrity

This project is designed to be honest about what it knows and what it does not know.

- Preserve original source URLs and excerpts
- Keep source evidence separate from model interpretation
- Label uncertain or inferred content clearly
- Do not claim global novelty from a weak or incomplete search
- Do not bypass paywalls or access restrictions

## Verification and live testing

The project has automated checks for the backend and frontend. Those checks mock external providers and verify the app logic, but they do not replace a real live provider run.

For the live runbook, see [docs/live-smoke-test.md](docs/live-smoke-test.md).

---

A quick reminder: ResearchPilot produces a draft, source-linked report and tentative research-gap suggestions. It does not guarantee scientific correctness or establish novelty by itself.
