# ResearchPilot AI — Architecture

## System boundaries
The MVP is a single-instance application for a controlled hackathon demo. It uses React/Vite/TypeScript for the UI, FastAPI/Pydantic for the API, SQLAlchemy/Alembic with SQLite for persistence, TinyFish for live-web source discovery/retrieval and evidence-validated claim extraction, and a configurable LLM provider for structured research analysis.

## End-to-end data flow
~~~text
Research question + year bounds
          |
          v
Query planning (focused sub-questions and queries)
          |
          v
TinyFish Search -> normalize/deduplicate sources -> TinyFish Fetch
          |                                     |
          +-------- source metadata/content ----+
                                                v
                                   Schema-constrained extraction
                                                |
                                                v
                            Evidence validation and provenance checks
                                                |
                                                v
                         Cross-source claim comparison and relations
                                                |
                                                v
                              Candidate-gap rubric and limitations
                                                |
                                                v
                        Structured report + claim/source evidence graph
                                                |
                                                v
                         FastAPI responses -> React report and graph
~~~

## Module responsibilities
- backend/app/main.py: application creation, middleware and router registration.
- backend/app/api/: request/response contracts and HTTP status mapping; keep business logic out of route handlers.
- backend/app/schemas/: Pydantic request, response, extraction and report schemas.
- backend/app/models/: SQLAlchemy persistence models.
- backend/app/repositories/: typed database operations; do not scatter SQL through routes/services.
- backend/app/services/tinyfish_search.py: TinyFish Search API adapter, timeout, error normalization and academic metadata normalization.
- backend/app/services/research_discovery.py: source persistence and research-run stage updates.
- backend/app/services/comparison_gap_analysis.py: schema-constrained cross-source relations and tentative candidate gaps, with claim-ID and cross-source validation.
- backend/app/providers/llm.py: configurable LLM client; no provider-specific logic in analysis services.
- backend/app/services/query_planner.py: focused query generation.
- backend/app/services/extraction.py: structured extraction and schema validation.
- backend/app/services/comparison.py: agreement, contradiction and scope-difference analysis.
- backend/app/services/gap_analysis.py: evidence-backed candidate gaps and uncertainty labels.
- backend/app/services/reporting.py: report assembly and citation validation.
- frontend/src/components/: reusable input, progress, source, report and graph UI.
- frontend/src/pages/: primary research flow.
- tests/: unit, API, provider-mock and end-to-end tests.
- docs/: requirements, behavior contracts and project decisions.

The architecture above describes the target design. The current implementation includes a FastAPI app, SQLAlchemy models, TinyFish Search and Fetch adapters, background source discovery/retrieval, evidence-validated LLM claim extraction, cross-source relation persistence, a tentative candidate-gap draft, report/source/graph APIs, and a frontend results workspace. Query planning and a fully polished final report remain future work; candidate gaps do not establish global novelty.

## Integration rules
- TinyFish Search uses GET https://api.search.tinyfish.ai and Fetch uses POST https://api.fetch.tinyfish.ai; both require X-API-Key authentication. Keep provider calls behind separate adapters so endpoint or response changes do not leak into services. Fetch stores at most 60,000 characters per source in the initial MVP.
- Use environment variables for TinyFish credentials, LLM API key, model and optional base URL. Never put secrets in source, frontend environment variables, committed settings, fixtures or logs.
- Set explicit HTTP timeouts and bounded retries only for retry-safe operations. Handle rate limits and inaccessible sources as structured source statuses.
- Use typed, schema-constrained LLM outputs where supported. Validate source IDs, excerpts and required fields before persistence.
- Claim extraction and claim verification are separate model calls. An exact source excerpt is a minimum provenance check, not proof that the claim follows from the excerpt.
- Persist only claims with an exact excerpt and a verifier verdict of supported or inferred. Store inferred claims with `is_inference=true`; exclude unsupported claims and missing/ambiguous verdicts. Verification is still model-based and may be wrong, so reports must not describe it as a formal factuality guarantee.
- Verification errors fail closed for that source: do not persist unverified claims, and surface a warning so users can see that evidence coverage may be incomplete.
- Keep the LLM provider configurable; do not assume credentials or silently fall back to fabricated content.
- Treat report confidence as a transparent evidence rubric, not a calibrated probability.

## Evidence graph
Nodes represent claims and sources; edges represent supports, contradicts, qualifies, or derived_from. Each relationship must store a rationale and evidence reference. Graph edges must point to persisted entities. The UI must expose the underlying source/excerpt when a relationship is selected.

## Reliability and security
- Persist run state and partial results before attempting later stages.
- Use safe structured errors and request IDs; never return raw upstream errors or stack traces.
- Store only content needed for evidence traceability; cap fetched page text at 60,000 characters per source, respect source access restrictions and avoid unnecessary personal data.
- No login/paywall bypass. No production credentials in the repository.
- Use SQLite for the initial single-instance demo; reassess before multi-user concurrent deployment.
- Source discovery currently uses FastAPI BackgroundTasks for the single-instance demo; this is not a durable production queue. Revisit only if deployment or run duration requires it.

## Verification
Mock external providers for deterministic tests. Keep a small manually reviewed evaluation set and record sample size. Measure citation support, extraction completeness, contradiction quality, candidate-gap relevance, end-to-end completion and latency before claiming quality or performance.


## Durable research job execution

Research-run requests are persisted as `queued` rows before the API returns HTTP 202. A lifespan-managed worker polls the database and atomically changes one queued row to `starting` before processing it; competing workers cannot claim the same row through the same conditional update. This removes reliance on FastAPI `BackgroundTasks`, whose work is tied to the serving process.

The database is the queue of record, so queued work remains available after an API restart. Active runs that have not updated their heartbeat/stage timestamp for 30 minutes are marked failed with `WORKER_INTERRUPTED` instead of remaining active indefinitely. Unexpected worker exceptions are recorded with a generic error code and safe user-facing message; details stay in server logs. To retry a failed run, create a new research run.

This is a lightweight database-backed worker, not a replacement for a dedicated broker/worker deployment at higher scale. Run processing is synchronous within one worker slot per API process; multiple API processes can compete safely for queued rows. Long-running provider operations should update the run state periodically so stale-run detection does not misclassify a healthy job. Schema changes for this feature were avoided; versioned migrations and explicit attempt counters remain part of the production database-hardening step.
