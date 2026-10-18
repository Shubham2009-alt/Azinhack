# Deployment security boundary

## Authentication and ownership
ResearchPilot uses Supabase Auth to authenticate API requests. The backend validates bearer tokens and stores the authenticated user ID on each new research run. Every run-specific endpoint checks ownership; unknown and non-owned IDs return the same 404. Older runs without an owner are intentionally inaccessible.

Keep provider credentials in environment variables or a secret manager. Use HTTPS at the public edge, restrict CORS to exact frontend origins, and review retention/deletion before collecting real user research data.

## Production database and migrations
Production must use PostgreSQL; SQLite is local-development/test-only. Apply versioned Alembic migrations once in the release pipeline with `cd backend && alembic upgrade head` before starting or scaling API replicas. Do not let multiple production replicas race to mutate the schema at startup. Back up the database and test the initial compatibility baseline against a staging copy before first deployment. See [`backend/MIGRATIONS.md`](../backend/MIGRATIONS.md).

## Production configuration
Set `APP_ENV=production`. Startup validation requires `TINYFISH_API_KEY`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `REDIS_URL`. Frontend and Supabase URLs must be HTTPS; LLM base URL must use HTTPS. Never use a Supabase secret/service-role key in the frontend.

## Shared rate limiting
Creating a research run is limited to five requests per direct client IP and five requests per authenticated account per ten-minute sliding window. Production uses Redis with one atomic Lua script to enforce both limits across workers and replicas. If Redis is unavailable, requests fail with 503 instead of silently downgrading to a weaker per-process limit. Local development can omit `REDIS_URL` and use an in-memory fallback.

The limiter uses the direct ASGI client address, not arbitrary `X-Forwarded-For` input. Configure trusted proxies carefully. Account limits reduce simple IP-rotation bypasses; they complement rather than replace edge abuse protection. Store Redis credentials in deployment secrets and use `rediss://` when supported.

## Before real users
1. Configure Supabase Email auth, site URLs, and confirmation policy; set backend `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`, and frontend `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`.
2. Provision Redis and set `REDIS_URL` in the deployment secret manager.
3. Serve frontend/API over HTTPS and restrict CORS.
4. Verify one user cannot access another user's status, sources, report, or graph.
5. Define sharing, retention, deletion, and logging policies.

## Research data retention and deletion

The default application retention window is 90 days from run creation. Set `RESEARCH_RETENTION_DAYS` to a value from 1 to 3650 to change it. The background worker periodically removes expired terminal runs in bounded batches; active runs are not removed by automatic retention. Keep the policy aligned with user disclosures and any applicable institutional/legal requirements.

An authenticated owner can delete a terminal run with `DELETE /api/research-runs/{run_id}`. Active or queued runs return HTTP 409 so deletion cannot race with in-flight worker writes. The API removes the run, stored source text and metadata, claims, report, evidence links, and claim relations in one database transaction. Non-owners and unknown IDs receive the same 404 response. The frontend exposes a confirmation-protected delete action for the current run after processing has stopped.

Application deletion does not instantly erase copies in database backups, provider logs, hosting logs, or external backups. Define backup expiry and provider-side logging/retention separately, avoid putting source content or credentials into logs, and test a deletion against a non-production copy before production rollout.

## Health probes
- `GET /api/health` is liveness and does not check dependencies.
- `GET /api/health/ready` checks database connectivity and, in production, Redis connectivity for the required rate limiter. It returns 503 if either check fails. It does not verify TinyFish or LLM availability.

## Remote research URL fetching and SSRF boundary

Search results and submitted source URLs are untrusted input. The backend canonicalizes HTTP(S) URLs, rejects credentials, blocks non-global IP literals and common local hostnames, and permits only standard HTTP/HTTPS ports before sending URLs to TinyFish Fetch. These checks are defense in depth, **not a complete SSRF guarantee**: a public-looking hostname can resolve to a private address, DNS answers can change, and the backend cannot inspect a redirect until after the remote request. Validating the returned `final_url` cannot undo a request already made.

TinyFish's public Fetch API documentation states that Fetch applies SSRF protections before execution, blocks private/reserved IP ranges, and denies cloud metadata endpoints ([TinyFish Fetch API security notes](https://www.tinyfish.ai/blog/production-grade-web-fetching-for-ai-agents)). This is an important provider-side control, but the public statement does not fully specify DNS-rebinding resistance or validation on every redirect hop. Before production use with untrusted URLs, confirm those details with the provider and test the deployed configuration. If the controls cannot be confirmed, use a fetch service with enforceable egress policy or disable arbitrary remote fetching. Track the required tests in [`docs/ssrf-provider-verification.md`](ssrf-provider-verification.md). Never include credentials or sensitive tokens in source URLs. Treat fetched page content as untrusted data, not instructions.


## Frontend/API deployment topology

The frontend calls API routes under `/api/`. In local development, Vite proxies these requests to `http://127.0.0.1:8000`. In production, either configure a same-origin reverse proxy that routes `/api/` to the backend, or set the frontend build variable `VITE_API_BASE_URL` to the HTTPS backend origin (for example, `https://api.example.com`). When using separate origins, add the exact frontend origin to backend `FRONTEND_ORIGIN`; do not use a wildcard. The API base URL is public configuration, not a secret.
