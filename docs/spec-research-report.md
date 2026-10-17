# Specification — Research Report and Evidence Graph

**Status:** Backend report/source/graph APIs and the first frontend results workspace are implemented; runtime verification and further report polish remain.  
**Product:** ResearchPilot AI MVP.

## 1. Behavior (Given / When / Then)

### Submit and plan
- Given a non-empty scientific question within the configured length limit, when the user submits it, then the API validates it, creates a research run, returns a run ID and starts processing.
- Given empty, whitespace-only, or over-limit input, when submitted, then return a validation error and do not create a run.
- Given optional year bounds where start > end or outside supported bounds, when submitted, then reject with a field-level validation message.
- Given a valid question, when query planning completes, then record focused queries and the original question. If planning fails, mark the stage failed and explain that research could not continue.

### Discovery and retrieval
- Given valid TinyFish credentials, when discovery runs, then query TinyFish Search and fetch accessible source pages with TinyFish Fetch, preserving URLs, available metadata, query provenance, extracted Markdown content and retrieval status.
- Given duplicate canonical URLs, when results are normalized, then retain one source record per canonical URL while preserving useful query provenance.
- Given an inaccessible, restricted, timed-out or rate-limited source, when retrieval fails, then record its failure state and continue with other sources where possible.
- Given zero usable sources, when processing ends, then return an explicit empty/insufficient-evidence result; never invent source records.
- Given missing credentials or an upstream provider error, when live search is requested, then return a safe actionable error or a clearly marked partial result if usable evidence already exists.

### Extraction and comparison
- Given retrieved content, when extraction runs, then return schema-valid claims, methods, datasets, limitations and publication metadata where present; each claim must reference the source and evidence excerpt used.
- Given malformed LLM output or unknown source IDs, when validation runs, then reject invalid fields, retry only within a bounded policy, and record a validation warning if unresolved.
- Given claims with materially incompatible findings, when comparison runs, then create a contradiction relation only with rationale and source evidence.
- Given claims differing only because populations, datasets, metrics or experimental conditions differ, when comparison runs, then label the scope difference instead of asserting contradiction.
- Given incomplete or weak evidence, when the gap engine runs, then mark “Insufficient evidence to assess” or “Low evidence”; absence of retrieved results must never be treated as proof of novelty.

### Report and graph
- Given validated evidence, when report generation completes, then render summary, methods/findings overview, agreement/contradiction analysis, candidate gaps, confidence rubric, limitations and source list.
- Given any factual report claim, when displayed, then show a source link and evidence excerpt, or explicitly label it as inference/unsupported.
- Given a graph node, when selected, then show its claim text, relationship type, source details, excerpt and rationale.
- Given a run with partial failures, when the report is displayed, then show partial status and failed source/stage warnings.
- Given an unknown run ID, when a report or graph is requested, then return 404.
- Given an internal error, when the API responds, then return a safe error ID/message without stack trace, credentials or provider secrets.

## 2. API contract
Base path: /api. Requests and responses use JSON.

### POST /api/research-runs
Request:
~~~json
{"question":"Can AI detect river pollution using satellite imagery?","year_min":2018,"year_max":2026}
~~~
Response 202 Accepted:
~~~json
{"run_id":"<uuid>","status":"queued"}
~~~
Validation failure: 422 Unprocessable Entity.

### GET /api/research-runs/{run_id}
Response 200: run_id, status (queued|searching|awaiting_analysis|succeeded|partial|failed), stage, progress (0–100), timestamps, source counts and safe warnings.

### GET /api/research-runs/{run_id}/report
Response 200: run status, structured report sections, claim records, source references, confidence labels, limitations and validation warnings. Return partial report where available.

### GET /api/research-runs/{run_id}/graph
Response 200:
~~~json
{"nodes":[{"id":"claim-id","type":"claim","label":"...","confidence":"moderate"}],"edges":[{"source":"claim-id","target":"source-id","type":"supports","rationale":"..."}]}
~~~
Allowed edge types: supports, contradicts, qualifies, derived_from.

### GET /api/research-runs/{run_id}/sources
Response 200: source IDs, title, canonical URL, publisher/date when known, retrieval status, excerpt and associated claims.

### GET /api/health
Response 200: application readiness; do not reveal secrets or full environment configuration.

### Error shape
~~~json
{"error":{"code":"VALIDATION_ERROR","message":"The research question is required.","details":[{"field":"question","reason":"must not be empty"}],"request_id":"<id>"}}
~~~
Use 422 for invalid input, 404 for unknown run/source, 502 for an upstream failure when no usable partial result exists, 503 for unavailable dependencies when appropriate, and 500 for unexpected errors. Do not return stack traces or raw provider response bodies.

## 3. Data model
- research_runs: id UUID, question, status, stage, progress, created_at, updated_at, error_code, warning summary.
- sources: id UUID, run_id FK, canonical_url, title, publisher, published_at nullable, publication_year nullable, authors, venue, citation_count, retrieved_at, retrieval_status, content_hash, bounded content_text (up to 60,000 characters), excerpt, failure_code. Unique (run_id, canonical_url).
- claims: id UUID, run_id FK, source_id FK nullable only for explicitly labelled inference, claim_text, claim_type, evidence_excerpt, confidence_label, is_inference, created_at.
- evidence_links: id UUID, claim_id FK, source_id FK, relationship (supports|contradicts|qualifies), excerpt, rationale, confidence_label.
- claim_relations: id UUID, from_claim_id FK, to_claim_id FK, relationship, rationale, confidence_label.
- reports: id UUID, run_id FK unique, structured_sections JSON, validation_warnings JSON, generated_at.
- Index run foreign keys and (run_id, retrieval_status); enforce canonical URL uniqueness per run. SQLite migrations must be reversible where practical. Do not store API keys or unnecessary personal data.

## 4. UI states
- Initial: explain capability and show question form.
- Submitting/loading: stage and progress updates; prevent accidental duplicate submissions.
- Success: cited report, source list, candidate gaps and graph.
- Partial: show usable evidence plus missing-source/stage warnings.
- Empty: explain no relevant sources were retrieved and offer query refinement.
- Error: actionable safe message and retry option when safe.
- Insufficient evidence: distinguish it from proof that no research exists.
- Graph empty: explain that no validated relationships were available; do not show invented edges.

## 5. Non-goals
No account system, multi-tenancy, paywall/login bypass, custom training, paper-to-code generation, global novelty guarantee, PDF/Word export, or production-scale queue in v1.

## 6. Acceptance checklist
- [x] Valid question creates a run and returns a run ID.
- [x] Invalid question/year range creates no run.
- [x] TinyFish Search academic-paper discovery is called in configured live mode.
- [x] TinyFish Fetch retrieves accessible source content, stores a bounded text copy and content hash, and records per-source failures.
- [x] Discovered sources retain original URLs, metadata and a discovered status.
- [x] Duplicate URLs are normalized within a run.
- [x] Extracted claims are linked to stored sources and persisted only when evidence excerpts occur verbatim in retrieved source text.\n- [x] Frontend report view renders extracted claims with available evidence excerpts and source links; inference claims are labelled.
- [x] Frontend displays run progress, source cards, candidate gaps, limitations and warnings.
- [x] Frontend graph view supports selecting source/claim nodes and inspecting relationship rationale.
- [x] Malformed LLM output is rejected safely; claims with excerpts not found in the stored source text are discarded.\n- [x] Cross-source relation IDs are validated before persistence; report/source/graph APIs return the stored evidence references.
- [ ] Contradictions include rationale and evidence; scope differences are not mislabelled.
- [ ] Contradictions include rationale and evidence; scope differences are not mislabelled.
- [ ] Low evidence is not presented as a globally novel gap.
- [ ] Partial, empty, timeout, rate-limit and provider-failure paths are visible.
- [x] Graph API and frontend view use persisted claim/source records and stored relationships.
- [ ] API errors are structured and do not leak secrets or stack traces.
- [ ] Clean setup, tests and documented demo run are reproducible; test/build commands have not yet been run in this environment.
