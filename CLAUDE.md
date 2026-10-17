# Claude Code Project Rules

## Project purpose
ResearchPilot AI turns a scientific research question into a source-linked research report.
It compares retrieved evidence and proposes candidate research gaps without claiming global novelty from missing search results.

## Authoritative documents
- Follow docs/prd-researchpilot.md for product scope and success metrics.
- Follow docs/spec-research-report.md for observable behavior and API/data contracts.
- Follow docs/architecture.md for module boundaries and pipeline design.
- If implementation conflicts with an approved spec, stop and ask before changing the spec or code.

## Repository status
The repository was empty when these documents were drafted. The directory structure below is proposed, not detected. Do not describe a convention as existing until code is added and inspected.

## Planned stack
- Python 3.12; FastAPI; Pydantic; HTTPX.
- SQLAlchemy 2.x; Alembic; SQLite for the single-instance MVP.
- React; Vite; TypeScript; lightweight CSS or Tailwind (choose one before frontend scaffold).
- pytest and Ruff for Python checks.
- Exact dependency versions must be pinned in project manifests/lockfiles when the app is scaffolded. Do not claim an installed version until verified.

## Commands
No application commands can be run yet because manifests and source files do not exist. After scaffold, define and verify these commands in README:
- DEV: start backend and frontend in development mode.
- BUILD: build the frontend for production.
- TEST: run pytest and frontend tests.
- LINT: run Ruff and the selected frontend linter.
Do not report commands as passing until they have been executed.

## Planned module boundaries
- Keep FastAPI routing and HTTP status mapping in backend/app/api/.
- Put request, response and extraction schemas in backend/app/schemas/.
- Keep database models in backend/app/models/ and database operations in backend/app/repositories/.
- Isolate TinyFish and LLM integrations in backend/app/providers/.
- Put query planning, extraction, comparison, gap analysis and reporting in separate service modules.
- Keep UI components in frontend/src/components/ and route/page composition in frontend/src/pages/.
- Add unit, API, provider-mock and end-to-end tests under tests/ or the frontend's configured test location.

## Non-negotiable rules
- Inspect the actual files and current diff before editing.
- Do not overwrite or delete existing functionality without explaining the impact and getting approval when behavior changes.
- Never commit API keys, tokens, credentials, real .env files or sensitive user/source data.
- Keep secrets on the backend; never expose provider keys to the browser.
- Use TinyFish only through the provider adapter; verify current official API docs before choosing endpoints or request shapes.
- Do not bypass paywalls, logins or source access controls.
- Never fabricate a paper, URL, quote, dataset, finding, contradiction or evaluation result.
- Preserve source title, URL, retrieval status and the excerpt used to support each displayed claim.
- Validate all model-generated structured output before storing or displaying it.
- Label model inference separately from source-reported findings.
- Treat confidence as an explicit rubric, not a calibrated probability.
- Do not call a topic globally novel because search returned no result.
- Distinguish insufficient evidence from a supported research gap.
- Keep external calls timed out and handle rate limits, malformed responses and inaccessible sources.
- Add or update a regression test for each behavior change.
- Keep dependencies minimal; justify new dependencies before adding them.
- Do not add authentication, production infrastructure, PDF export or paper-to-prototype generation to v1 without approval.
- Do not change approved API contracts or database schema silently; update the spec and request approval first.
- Do not claim tests, lint, builds, live integrations or evaluation metrics passed unless actually run.

## Evidence integrity
For every displayed factual claim, ensure there is a resolvable source/evidence link or visibly label it as an inference/unsupported. Contradiction edges require evidence and rationale. If source content is inaccessible, disclose it; do not fill gaps with invented text.

## Change workflow
1. Read the relevant PRD/spec and every file the task will touch.
2. State current behavior, target behavior, proposed files and risks before a non-trivial change.
3. Make the smallest independently verifiable change.
4. Run the relevant tests and lint/build commands; report exact results.
5. Update documentation when setup, behavior, contracts or dependencies change.
6. Stop and ask before scope expansion, destructive migrations, production data access or changes to authentication/payment/security boundaries.
