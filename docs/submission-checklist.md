# Final submission checklist

## Before recording or submitting
- [ ] Run the app locally and verify the health endpoint.
- [ ] Configure TinyFish and LLM keys only in `backend/.env`; never commit or share the file.
- [ ] Complete one live end-to-end research run using the procedure in [live-smoke-test.md](live-smoke-test.md).
- [ ] Record the research question, run ID, timestamp, final status, source count, retrieved-source count, and warnings.
- [ ] Manually inspect source URLs and evidence excerpts. Confirm excerpts match retrieved text and candidate gaps are described as tentative.
- [ ] Capture a clean demo recording or screenshots only after verifying that the displayed evidence is real and source-linked.
- [ ] Rehearse a short explanation of the pipeline, TinyFish's role, evidence validation, limitations, and what remains unverified.
- [ ] Confirm the GitHub Actions checks are green on the final commit.
- [ ] Review the repository for secrets, local databases, debug output, and unrelated files.
- [ ] Verify the hackathon submission form requirements, team details, repository visibility, and submission deadline before submitting.

## Demo fallback
If a live provider call fails, do not fabricate a successful result or present mocked tests as live evidence. Explain the limitation and show the verified implementation, passing automated checks, and the documented smoke-test procedure.

## Scope and claims
ResearchPilot produces an evidence-linked report draft and tentative candidate research gaps. It does not establish global novelty or guarantee scientific correctness. State clearly whether the demo used live providers or mocked tests.
