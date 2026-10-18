# Live end-to-end smoke test

This is the guided checklist for a real provider-backed demo. It is meant to help you verify the app in a realistic run without exposing secrets or making unsupported claims.

> Keep credentials in the backend’s local `.env` file only. Never paste them into a terminal command, chat, issue, commit, or screenshot.

## 1) Prepare the database

For local development, the app applies Alembic migrations automatically. For staging/production, set `DATABASE_URL` to PostgreSQL and run `cd backend && alembic upgrade head` once as a release step before starting API replicas. Do not use the SQLite default in production.

## 2) Configure the providers

Set these values in `backend/.env`:

- `TINYFISH_API_KEY` — valid TinyFish API key
- `LLM_API_KEY` — valid key for an OpenAI-compatible provider
- `LLM_BASE_URL` — provider base URL such as `https://api.openai.com/v1`
- `LLM_MODEL` — a model that supports the provider’s JSON output mode

Keep the file local and untracked. Restart the backend after any setting changes.

## 3) Start the app

Open two terminals from the repo root.

Terminal A:

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal B:

```bash
cd frontend
npm install
npm run dev
```

Open the frontend local URL shown by Vite. Confirm this endpoint responds successfully:

```text
http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"status":"ok","service":"researchpilot-api"}
```

## 4) Run a focused research question

In the UI, submit a narrow question such as:

```text
What methods have been evaluated for detecting phishing websites using URL features, and what limitations do recent studies report?
```

Optionally set a recent publication-year range to keep the search focused. Wait for the run to reach a terminal state; live provider calls can take time.

## 5) Validate the stages

Check that the run behaves like this:

- It moves through source discovery and retrieval
- It eventually reaches a terminal state instead of continuing forever
- The source list includes real URLs and retrieval statuses
- Unavailable pages are disclosed clearly instead of being silently treated as retrieved
- Each extracted claim contains an excerpt that appears exactly in the source text
- Cross-source relations reference valid existing claims from different sources
- Candidate gaps identify supporting claim IDs and are explicitly labeled as tentative
- The report and graph endpoints return the same persisted results for that run
- The public read endpoints do not expose full page text, provider keys, or raw provider error payloads

You can inspect these read-only endpoints using the run ID returned by the API:

```text
GET /api/research-runs/{run_id}
GET /api/research-runs/{run_id}/sources
GET /api/research-runs/{run_id}/report
GET /api/research-runs/{run_id}/graph
```

## 6) If something fails

Common issues and what to check:

- `TINYFISH_NOT_CONFIGURED` — check the TinyFish key in `backend/.env`
- `TINYFISH_SEARCH_FAILED` — verify TinyFish availability and backend logs
- No retrieved content — inspect per-source retrieval statuses; some pages block extraction or expose only metadata
- No claims / LLM warning — check the LLM key, base URL, model, provider quota, and JSON mode compatibility
- Partial results — these are valid outcomes; do not fill gaps with invented evidence

## 7) Record a reproducible demo outcome

Keep a short record of:

- the exact question you asked
- the run ID
- the timestamp
- the terminal status
- the source count and retrieved-source count
- any warnings shown in the UI

Capture the UI only after checking that URLs and evidence excerpts are visible. Do not include credentials or private provider logs in screenshots or notes.

This runbook is for live-provider validation. The automated CI tests mock provider calls and do not prove that external credentials or provider compatibility are valid.
