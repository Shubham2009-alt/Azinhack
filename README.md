# ResearchPilot AI

ResearchPilot turns a scientific research question into a structured, evidence-backed report with source-linked claims, cross-source comparisons, candidate research gaps and an interactive evidence graph.

It is an evidence-traceability tool for early-stage literature exploration—not a guarantee of scientific correctness or global novelty.

## Status
Documentation and implementation plan are being established first. The application scaffold has not been added yet.

## MVP pipeline
Research question → query planning → TinyFish discovery/retrieval → structured extraction → evidence validation → claim comparison → candidate-gap analysis → cited report and evidence graph.

## Planned stack
- Frontend: React, Vite, TypeScript.
- Backend: Python 3.12, FastAPI, Pydantic, HTTPX.
- Analysis: configurable LLM API with structured output and deterministic validation.
- Research discovery: TinyFish Search and Fetch integration, subject to current official API contract verification.
- Persistence: SQLAlchemy 2.x, Alembic, SQLite.
- Quality: pytest and Ruff; frontend test/lint tools to be selected during scaffold.

## Documentation
- Product requirements: docs/prd-researchpilot.md
- Research report specification: docs/spec-research-report.md
- Architecture: docs/architecture.md
- Claude Code project rules: CLAUDE.md

## Setup
Setup commands will be added and verified when the backend/frontend scaffold and dependency lockfiles exist. Do not assume the repository is runnable yet.

## Environment configuration
The implementation is expected to read credentials from local environment variables, including TinyFish and the selected LLM provider. A later scaffold step will add a safe .env.example containing names only and a .gitignore that excludes real secrets. Never commit API keys or real environment files.

## Evidence integrity
- Preserve original source URLs and excerpts supporting claims.
- Separate source-reported findings from model interpretations.
- Mark weak evidence and inaccessible sources clearly.
- Never claim global novelty based solely on an unsuccessful search.
- Never bypass paywalls or access controls.
