# ResearchPilot AI — Architecture

## System boundaries
The MVP is a single-instance application for a controlled hackathon demo. It uses React/Vite/TypeScript for the UI, FastAPI/Pydantic for the API, SQLAlchemy/Alembic with SQLite for persistence, TinyFish for live-web source discovery/retrieval, and a configurable LLM provider for structured research analysis.

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

The architecture above describes the target design. Current implementation has a FastAPI app, SQLAlchemy models, a TinyFish academic-search adapter, and a background source-discovery service; query planning, page fetching, LLM analysis, report generation and graph endpoints remain future steps.

## Integration rules
- TinyFish Search currently uses the documented GET https://api.search.tinyfish.ai endpoint and X-API-Key authentication. Keep provider calls behind one adapter so endpoint or response changes do not leak into services. TinyFish Fetch remains unimplemented.
- Use environment variables for TinyFish credentials, LLM API key, model and optional base URL. Never put secrets in source, frontend environment variables, committed settings, fixtures or logs.
- Set explicit HTTP timeouts and bounded retries only for retry-safe operations. Handle rate limits and inaccessible sources as structured source statuses.
- Use typed, schema-constrained LLM outputs where supported. Validate source IDs, excerpts and required fields before persistence.
- Keep the LLM provider configurable; do not assume credentials or silently fall back to fabricated content.
- Treat report confidence as a transparent evidence rubric, not a calibrated probability.

## Evidence graph
Nodes represent claims and sources; edges represent supports, contradicts, qualifies, or derived_from. Each relationship must store a rationale and evidence reference. Graph edges must point to persisted entities. The UI must expose the underlying source/excerpt when a relationship is selected.

## Reliability and security
- Persist run state and partial results before attempting later stages.
- Use safe structured errors and request IDs; never return raw upstream errors or stack traces.
- Store only content needed for evidence traceability; respect source access restrictions and avoid unnecessary personal data.
- No login/paywall bypass. No production credentials in the repository.
- Use SQLite for the initial single-instance demo; reassess before multi-user concurrent deployment.
- Source discovery currently uses FastAPI BackgroundTasks for the single-instance demo; this is not a durable production queue. Revisit only if deployment or run duration requires it.

## Verification
Mock external providers for deterministic tests. Keep a small manually reviewed evaluation set and record sample size. Measure citation support, extraction completeness, contradiction quality, candidate-gap relevance, end-to-end completion and latency before claiming quality or performance.
