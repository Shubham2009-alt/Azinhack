# Deployment security boundary

## Current deployment model

ResearchPilot is a demo-first MVP. It does **not** implement user authentication, sessions, or per-user ownership for research runs. The run ID is an identifier, not an authorization mechanism. Anyone who obtains a run ID may be able to read the corresponding status, source list, report, and evidence graph through the API.

Until authentication and ownership checks are implemented consistently across every run-specific endpoint:

- Use only public or synthetic research questions in shared demos.
- Do not submit personal, confidential, regulated, or otherwise sensitive material.
- Do not advertise the deployment as a private workspace or multi-user service.
- Treat run IDs and report URLs as potentially shareable; do not rely on UUID unpredictability to protect sensitive data.
- Keep provider credentials on the backend in environment variables or a secret manager. Never put them in frontend variables or commits.
- Use HTTPS at the public edge, restrict CORS to the exact frontend origin(s), and place the service behind platform-level abuse protection where available.
- Review retention and deletion needs before collecting real user research data.

## Production startup guard

Set `APP_ENV=production` for a production deployment. Startup validation then requires non-empty `TINYFISH_API_KEY`, `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`; requires an explicit HTTPS `FRONTEND_ORIGIN`; rejects localhost frontend origins; and requires the LLM base URL to use HTTPS.

These checks reduce common misconfiguration risks. They do **not** add authentication, enforce research-run ownership, validate the security of a hosting provider, or replace a deployment review. Keep `APP_ENV=development` for the documented local workflow.

## Before opening the service to real users

1. Choose an identity provider or implement a well-reviewed authentication flow.
2. Persist an owner identifier on every research run.
3. Require authentication on all run-specific endpoints and verify ownership on every request, including status, sources, report, and graph.
4. Define run-sharing behavior explicitly; do not treat possession of a run ID as authorization by default.
5. Add tests proving one user cannot read or mutate another user's runs.
6. Define data retention, deletion, logging, and rate-limit policies, then review the deployed service.


## Health and readiness probes

- `GET /api/health` is a liveness probe. It confirms that the API process is responding and intentionally does not verify database availability.
- `GET /api/health/ready` is a readiness probe. It executes a lightweight database query and returns `200` when the database is reachable or `503` when the check fails. The response body does not expose database exception details.

Configure hosting-platform probes according to their purpose: use liveness to detect a stuck or stopped process, and readiness to decide whether the instance should receive traffic. A successful readiness check does not verify TinyFish or LLM provider availability and does not establish that a complete research run will succeed.
