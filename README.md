# ResearchPilot AI

ResearchPilot turns a scientific research question into a structured, evidence-backed report with source-linked claims, cross-source comparisons, candidate research gaps and an interactive evidence graph.

It is an evidence-traceability tool for early-stage literature exploration—not a guarantee of scientific correctness or global novelty.

## Current status
- [x] Product requirements, behavior specification and architecture documented.
- [x] FastAPI health, create-research-run, and run-status endpoints added.
- [x] React/Vite/TypeScript question form connected to the create-run API.
- [x] TinyFish Search and Fetch integrated: accessible page content is persisted with a content hash; URL normalization, duplicate suppression and per-source retrieval failures are handled.
- [x] SQLAlchemy models and SQLite table initialization are added for research runs, sources, claims, reports and evidence-graph relationships.
- [x] Configurable OpenAI-compatible LLM extraction stores only claims whose evidence excerpts occur verbatim in retrieved source text.
- [x] Cross-source relation proposals and tentative candidate gaps are validated against persisted claim IDs and saved to the report draft.
- [x] Read-only report, source-list and evidence-graph API endpoints expose persisted results.
- [x] Frontend results workspace displays processing status, source cards, evidence-linked claims, candidate gaps, limitations and an interactive source/claim relationship view.

## MVP pipeline
Research question → TinyFish discovery/retrieval → evidence-validated claims → cross-source comparison and tentative gaps → final cited report and evidence graph.

## Research results API

- `GET /api/research-runs/{run_id}/report` — report draft, claims, sources and validation warnings; partial results are included.
- `GET /api/research-runs/{run_id}/sources` — source metadata, excerpts, retrieval status and linked claims. Full stored page text is not returned.
- `GET /api/research-runs/{run_id}/graph` — source/claim nodes, evidence edges and persisted cross-source relationships.
- Unknown run IDs return `404`. Candidate research gaps remain hypotheses, not proof of novelty.

## Planned stack
- Frontend: React, Vite, TypeScript.
- Backend: Python 3.12, FastAPI, Pydantic, HTTPX.
- Analysis: configurable LLM API with structured output and deterministic validation.
- Research discovery and analysis: TinyFish Search and Fetch plus a configurable OpenAI-compatible chat-completions API for evidence-validated claim extraction.
- Persistence: SQLAlchemy 2.x, SQLite (Alembic migrations remain a follow-up).
- Quality: pytest and Ruff; frontend ESLint and TypeScript build.

## Repository map
- `backend/app/main.py`: FastAPI health, run creation/status, report, source-list and evidence-graph endpoints; new runs start source discovery in a FastAPI background task.
- `backend/app/services/tinyfish_search.py`: TinyFish academic search client and response normalization.\n- `backend/app/services/tinyfish_fetch.py`: TinyFish Fetch API client; Markdown extraction, bounded content storage and normalized errors.
- `backend/app/services/research_discovery.py`: source persistence, full-page retrieval and run-state updates.
- `backend/app/settings.py`: environment-backed settings, including `DATABASE_URL`.
- `backend/app/database.py`: engine, session dependency and table initialization.
- `backend/app/models/`: research records and evidence-graph persistence models.
- `backend/tests/`: API, database, TinyFish adapter and source-discovery tests (authentic provider calls are mocked).
- `frontend/src/App.tsx`: question entry, run-status polling, report/source tabs and selectable evidence-graph nodes.
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

The frontend submits questions, supports optional publication-year bounds, polls run status and displays report, sources and evidence graph views. With `TINYFISH_API_KEY` configured on the backend, a background task searches academic papers and fetches accessible page content. Source retrieval failures are stored per source and do not discard successfully fetched sources. Without a key, the run fails with a safe configuration status. LLM extraction now requires LLM_API_KEY, LLM_BASE_URL and LLM_MODEL on the backend. It stores source-linked claims only when the proposed excerpt is an exact substring of retrieved content. Cross-source comparison and tentative gap analysis are implemented. The report view is a draft synthesis; candidate gaps are not verified novelty claims. The graph view displays selectable source and claim nodes alongside their persisted relationships.

## Environment and security
The backend reads TinyFish and LLM configuration from environment variables. Configure LLM_BASE_URL as an OpenAI-compatible API base URL (for example, https://api.openai.com/v1), plus LLM_API_KEY and LLM_MODEL. Provider compatibility varies; live provider calls have not been verified in this environment. Use real credentials only in a local, ignored `.env` file or the deployment secret manager. Never commit API keys, tokens or real environment files. Additional provider integration will follow verification of each official API contract.

## Evidence integrity
- Preserve original source URLs and excerpts supporting claims.
- Separate source-reported findings from model interpretations.
- Mark weak evidence and inaccessible sources clearly.
- Never claim global novelty based solely on an unsuccessful search.
- Never bypass paywalls or access controls.

## Verification status
The files have been added to the repository, but commands have not been executed in a runtime during this step. Do not interpret the existence of tests or scripts as proof that they pass.
