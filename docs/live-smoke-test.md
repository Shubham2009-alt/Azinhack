# Live end-to-end smoke test

Use this checklist after configuring real provider credentials in the backend's local `.env`. Do not paste credentials into a terminal command, chat, issue, or commit.

## 1. Configure providers

In `backend/.env`, set:

- `TINYFISH_API_KEY`: a valid TinyFish API key.
- `LLM_API_KEY`: a valid key for an OpenAI-compatible chat-completions provider.
- `LLM_BASE_URL`: provider base URL, such as `https://api.openai.com/v1`.
- `LLM_MODEL`: a model supported by that provider and its JSON response mode.

Keep `.env` local and untracked. Restart the backend after changing settings.

## 2. Start the app

Terminal A, from the repository root:

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

Open the Vite URL printed by the frontend. Confirm `GET http://127.0.0.1:8000/api/health` returns `{"status":"ok","service":"researchpilot-api"}`.

## 3. Run a bounded, testable research question

In the UI, submit a narrow question such as:

`What methods have been evaluated for detecting phishing websites using URL features, and what limitations do recent studies report?`

Optionally constrain the publication years to a recent interval. Wait for the run to reach a terminal state; provider calls can take time.

## 4. Validate each stage

- The run status moves through source discovery and retrieval; it must eventually stop polling at a terminal state.
- The source list contains source URLs and retrieval statuses. Unavailable pages are disclosed rather than silently treated as read.
- Each extracted claim has an excerpt that exactly occurs in retrieved source text.
- Cross-source relations reference existing claims from different sources.
- Candidate gaps identify their supporting claim IDs and remain labelled as tentative—not verified novelty.
- The report and graph endpoints return the same run's persisted results.
- No full source page text, API key, or provider error details are exposed by the public read endpoints.

You can inspect the read-only endpoints using the run ID displayed/returned by the API:

```text
GET /api/research-runs/{run_id}
GET /api/research-runs/{run_id}/sources
GET /api/research-runs/{run_id}/report
GET /api/research-runs/{run_id}/graph
```

## 5. Failure triage

- `TINYFISH_NOT_CONFIGURED`: check `TINYFISH_API_KEY` in backend `.env`.
- `TINYFISH_SEARCH_FAILED`: check TinyFish key, provider availability and backend logs.
- No retrieved content: inspect per-source retrieval statuses; some paper landing pages block extraction or expose only metadata.
- No claims / LLM warning: check `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, provider quota and JSON-mode compatibility.
- Partial results are valid outcomes. Do not invent missing evidence to make a demo look complete.

## 6. Save a reproducible demo record

Record the question, run ID, timestamp, terminal status, source count, retrieved-source count, and any warnings. Capture the UI only after checking that source URLs and evidence excerpts are visible. Do not include credentials or private provider logs in screenshots.

This runbook is a manual live-provider test procedure; automated CI tests mock provider calls and do not prove external credentials or provider compatibility.
