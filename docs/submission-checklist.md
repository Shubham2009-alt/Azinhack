# Final submission checklist

This is the last pass before you record a demo or submit the project. The goal is simple: make sure the evidence is real, the app still works, and nothing sensitive is exposed.

## Before you record or submit

- [ ] Start the app locally and confirm the health endpoint responds successfully
- [ ] Keep TinyFish and LLM credentials only in `backend/.env`; never commit or share that file
- [ ] Run one live end-to-end research flow using the steps in [live-smoke-test.md](live-smoke-test.md)
- [ ] Write down the research question, run ID, timestamp, final status, source count, retrieved-source count, and warnings
- [ ] Open the source URLs and check the evidence excerpts manually
- [ ] Confirm each claim matches actual retrieved text and that candidate gaps are clearly described as tentative
- [ ] Capture a clean demo recording or screenshots only after the evidence has been validated
- [ ] Rehearse a short explanation of how the app works, what TinyFish does, what evidence validation means, and what remains uncertain
- [ ] Make sure the final commit is passing CI checks
- [ ] Review the repo for secrets, local database files, debug output, and unrelated artifacts
- [ ] Double-check the submission form, team details, repo visibility, and deadline before submitting

## If the live provider call fails

Do not invent a successful result or present mocked output as if it were live evidence. If a provider fails, explain the limitation honestly and show the verified implementation, the passing automated checks, and the documented smoke-test path instead.

## Scope and claims

ResearchPilot produces a draft, evidence-linked report and tentative candidate research gaps. It is not a guarantee of global novelty, and it is not a claim of scientific certainty.

Before you present the demo, clearly say whether the run used live provider calls or mocked tests.
