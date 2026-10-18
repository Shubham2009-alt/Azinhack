from types import SimpleNamespace

import pytest

from app.services import comparison_gap_analysis as service
from app.services.comparison_gap_analysis import (
    compare_claims_and_identify_gaps,
)
from app.services.llm_analysis import AnalysisProviderError


def configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service.settings, "llm_api_key", "test-key")
    monkeypatch.setattr(service.settings, "llm_model", "test-model")
    monkeypatch.setattr(service.settings, "llm_base_url", "https://llm.example/v1")


def test_filters_unknown_ids_and_same_source_relations(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    response_json = (
        '{"relations":['
        '{"claim_a_id":"c1","claim_b_id":"c2","relationship":"contradicts",'
        '"rationale":"The reported outcomes are materially incompatible.","confidence_label":"moderate"},'
        '{"claim_a_id":"c1","claim_b_id":"c3","relationship":"supports",'
        '"rationale":"These claims point in a similar direction.","confidence_label":"low"},'
        '{"claim_a_id":"c1","claim_b_id":"unknown","relationship":"qualifies",'
        '"rationale":"The second claim is not present in this corpus.","confidence_label":"low"}],'
        '"candidate_gaps":[{"title":"Understudied rural settings","description":"The supplied studies offer little direct evidence for rural deployments.","evidence_level":"low","basis_claim_ids":["c1","unknown"],"rationale":"The retrieved claim describes an urban evaluation only."}]}'
    )
    monkeypatch.setattr(
        service.httpx,
        "post",
        lambda *args, **kwargs: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": response_json}}]},
        ),
    )
    claims = [
        {"id": "c1", "source_id": "s1", "claim_text": "Urban test.", "evidence_excerpt": "Urban."},
        {"id": "c2", "source_id": "s2", "claim_text": "Rural test.", "evidence_excerpt": "Rural."},
        {"id": "c3", "source_id": "s1", "claim_text": "Another urban test.", "evidence_excerpt": "Urban."},
    ]
    result = compare_claims_and_identify_gaps(question="Research question", claims=claims)
    assert len(result.relations) == 1
    assert result.relations[0].claim_a_id == "c1"
    assert result.candidate_gaps[0].basis_claim_ids == ["c1"]


def test_no_claims_does_not_call_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        service.httpx,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not call provider")),
    )
    result = compare_claims_and_identify_gaps(question="Question", claims=[])
    assert result.relations == []
    assert result.candidate_gaps == []


def test_comparison_rejects_oversized_provider_response(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)

    class FakeResponse:
        content = b"x" * (service.MAX_PROVIDER_RESPONSE_BYTES + 1)

        def raise_for_status(self) -> None:
            pass

        def json(self):
            pytest.fail("oversized response must be rejected before JSON parsing")

    monkeypatch.setattr(service.httpx, "post", lambda *args, **kwargs: FakeResponse())
    with pytest.raises(AnalysisProviderError, match="validation"):
        compare_claims_and_identify_gaps(
            question="Question",
            claims=[{"id": "c1", "source_id": "s1", "claim_text": "Claim", "evidence_excerpt": "Evidence"}],
        )
