# Product Requirements — ResearchPilot AI

## Product overview
ResearchPilot turns a scientific research question into a structured, source-linked research report. It discovers accessible sources, extracts evidence, compares claims, and proposes research gaps with explicit uncertainty.

## Problem
Students and early-stage researchers spend substantial time locating papers, comparing methods and limitations, and checking whether a proposed gap is supported. Search snippets and generic LLM summaries can hide weak evidence or produce unsupported novelty claims.

## Users and primary use case
**Primary:** undergraduate/postgraduate students, research scholars, academic project teams, and researchers beginning a literature review. **Secondary:** supervisors and faculty reviewing preliminary research directions.

Example: a user asks, “Can AI detect river pollution using satellite imagery?” ResearchPilot searches relevant sources, extracts methods and limitations, compares findings, and presents candidate gaps with evidence links.

## MVP scope
1. Submit a research question and optional year bounds.
2. Plan focused search queries.
3. Discover and retrieve publicly accessible sources through TinyFish.
4. Extract structured findings, methods, datasets, dates and limitations using a configurable LLM.
5. Compare claims and identify qualified agreements or contradictions.
6. Propose evidence-linked candidate gaps with a transparent rubric and limitations.
7. Produce a cited report and interactive claim/source evidence graph.
8. Show pipeline progress, partial results, source failures and safe retry states.
9. Persist research runs, sources, claims, evidence links and reports in SQLite.

## Not in v1
PDF/Word export; paper-to-prototype/code generation; custom model training; cross-disciplinary gap discovery; user accounts/multi-tenancy; production-scale job queues; paywall/login bypass; claims of globally verified novelty.

## Functional requirements
- Every displayed factual claim must link to retrieved evidence or be explicitly labelled as an inference/unsupported.
- Store source title, URL, publication date when available, retrieval status and excerpt/content used.
- Validate LLM outputs against typed schemas and verify source references before display.
- Distinguish a true source-supported disagreement from different experimental scope.
- Distinguish “insufficient evidence in this run” from “no research exists.”
- Preserve partial results and report inaccessible sources instead of silently dropping them.
- Keep provider keys and model configuration in environment variables.

## Non-functional requirements
- Python 3.12 backend with FastAPI/Pydantic; React + Vite + TypeScript frontend; SQLite for the single-instance MVP.
- Deterministic unit tests for scoring/validation and mocked tests for external services.
- Clean setup documented; minimal dependencies; no committed credentials or private source material.
- Source attribution and failure state remain available throughout the report UI.

## Success metrics and evaluation
Create a manually reviewed set of at least 20 research questions/source excerpts before making quality claims. Measure claim-to-source support rate, citation URL preservation/reachability, required-field extraction completeness, precision of reviewed contradiction labels, reviewer rating of candidate-gap relevance, end-to-end completion rate, and median report-generation time.

Initial target: 100% of displayed factual claims have a resolvable source reference or an explicit unsupported/inferred label; at least 80% required-field completeness on the reviewed extraction set. These are targets, not measured results.

## Architecture and data
React UI → FastAPI orchestration → TinyFish discovery/retrieval + configurable LLM extraction/comparison → validation and gap rubric → SQLite repositories → cited report and graph. Tables: research_runs, sources, claims, evidence_links, claim_relations, reports. See architecture.md and spec-research-report.md.

## Safety and delivery
Use only public/access-permitted source content. Do not bypass access controls. Never invent citations or claim global novelty from a limited search. Treat model confidence as a rubric label, not a calibrated probability. Handle timeouts, rate limits, malformed responses and unavailable content.

Build in checkpoints: documentation/contracts; runnable skeleton; persistence; TinyFish; structured extraction; comparison/gaps/report; frontend/evidence graph; evaluation and submission. Four owners: backend/orchestration; TinyFish/source collection; AI analysis; frontend/graph. Each member reviews the end-to-end flow and can explain their module.

## Open decisions
1. Confirm whether Research-to-Prototype AI is a later stretch goal (recommended) rather than a change to v1.
2. Select the LLM provider/model and provide credentials through local environment configuration.
3. Confirm the target demo environment; default is Codespaces/local development before hosting.
