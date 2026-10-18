# Deployment security boundary

## Current deployment model

ResearchPilot uses Supabase Auth to authenticate API requests. The backend validates bearer tokens against the configured Supabase Auth user endpoint and stores the authenticated user ID on each newly created research run. Every run-specific endpoint checks that the caller owns the run; unknown and non-owned run IDs return the same `404` response. Older runs without an owner are intentionally inaccessible through the API after this migration.

Until authentication and ownership checks are implemented consistently across every run-specific endpoint:

- Use only public or synthetic research questions in shared demos.
- Do not submit personal, confidential, regulated, or otherwise sensitive material.
- Do not advertise the deployment as a private workspace or multi-user service.
- Treat run IDs and report URLs as potentially shareable; do not rely on UUID unpredictability to protect sensitive data.
- Keep provider credentials on the backend in environment variables or a secret manager. Never put them in frontend variables or commits.
- Use HTTPS at the public edge, restrict CORS to the exact frontend origin(s), and place the service behind platform-level abuse protection where available.
- Review retention and deletion needs before collecting real user research data.

## Production startup guard

Set `APP_ENV=production` for a production deployment. Startup validation requires non-empty `TINYFISH_API_KEY`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `SUPABASE_URL`, and `SUPABASE_PUBLISHABLE_KEY`; requires explicit HTTPS frontend and Supabase URLs; rejects localhost frontend/Supabase URLs; and requires the LLM base URL to use HTTPS.

These checks reduce common misconfiguration risks but do not validate the security of a hosting provider or replace a deployment review. Keep `APP_ENV=development` for the documented local workflow. The Supabase publishable key is designed for client use; never configure a Supabase secret/service-role key in the frontend or use it as the backend verification key.

## Before opening the service to real users

1. Configure Supabase Email authentication, site URLs, and confirmation policy; set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` on the backend and `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` on the frontend.
2. Ensure the frontend and API are served over HTTPS and CORS is restricted to the exact frontend origin.
3. Test that one user cannot access another user's run through status, sources, report, or graph endpoints.
4. Define run-sharing behavior explicitly; sharing is not enabled by default.
5. Define data retention, deletion, logging, and rate-limit policies, then review the deployed service.


## Health and readiness probes

- `GET /api/health` is a liveness probe. It confirms that the API process is responding and intentionally does not verify database availability.
- `GET /api/health/ready` is a readiness probe. It executes a lightweight database query and returns `200` when the database is reachable or `503` when the check fails. The response body does not expose database exception details.

Configure hosting-platform probes according to their purpose: use liveness to detect a stuck or stopped process, and readiness to decide whether the instance should receive traffic. A successful readiness check does not verify TinyFish or LLM provider availability and does not establish that a complete research run will succeed.
