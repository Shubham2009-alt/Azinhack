# Deployment security boundary

## Authentication and ownership
ResearchPilot uses Supabase Auth to authenticate API requests. The backend validates bearer tokens and stores the authenticated user ID on each new research run. Every run-specific endpoint checks ownership; unknown and non-owned IDs return the same 404. Older runs without an owner are intentionally inaccessible.

Keep provider credentials in environment variables or a secret manager. Use HTTPS at the public edge, restrict CORS to exact frontend origins, and review retention/deletion before collecting real user research data.

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

## Health probes
- `GET /api/health` is liveness and does not check dependencies.
- `GET /api/health/ready` checks database connectivity and returns 503 if unavailable. It does not verify Redis, TinyFish, or LLM availability.
