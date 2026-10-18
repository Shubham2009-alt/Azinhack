from types import SimpleNamespace

import pytest

from app.services import llm_analysis
from app.services.llm_analysis import (
    AnalysisConfigurationError,
    AnalysisProviderError,
    extract_source_claims,
)


def configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_analysis.settings, "llm_api_key", "test-key")
    monkeypatch.setattr(llm_analysis.settings, "llm_model", "test-model")
    monkeypatch.setattr(llm_analysis.settings, "llm_base_url", "https://llm.example/v1")


def test_extracts_only_claims_with_exact_source_excerpts(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    body = (
        '{"claims":['
        '{"claim_text":"The model improves detection accuracy.","claim_type":"finding",'
        '"evidence_excerpt":"Detection accuracy increased from 71% to 84%.","confidence_label":"moderate"},'
        '{"claim_text":"Unsupported claim from model.","claim_type":"finding",'
        '"evidence_excerpt":"The study proved universal success.","confidence_label":"high"}]}'
    )
    seen = {}

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["kwargs"] = kwargs
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": body}}]},
        )

    monkeypatch.setattr(llm_analysis.httpx, "post", fake_post)
    claims = extract_source_claims(
        question="Does the method work?",
        source_id="source-1",
        title="Study",
        url="https://example.org/paper",
        content="Detection accuracy increased from 71% to 84%.",
    )
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["kwargs"]["headers"]["Authorization"] == "Bearer test-key"
    assert len(claims) == 1
    assert claims[0].evidence_excerpt == "Detection accuracy increased from 71% to 84%."


def test_requires_provider_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_analysis.settings, "llm_api_key", "")
    with pytest.raises(AnalysisConfigurationError):
        extract_source_claims(
            question="Question",
            source_id="source-1",
            title="Study",
            url="https://example.org",
            content="A sufficiently long source passage for extraction.",
        )


def test_rejects_malformed_provider_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    monkeypatch.setattr(
        llm_analysis.httpx,
        "post",
        lambda *args, **kwargs: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": []},
        ),
    )
    with pytest.raises(AnalysisProviderError):
        extract_source_claims(
            question="Question",
            source_id="source-1",
            title="Study",
            url="https://example.org",
            content="A sufficiently long source passage for extraction.",
        )


def test_llm_rejects_oversized_provider_response_before_json_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)

    class FakeResponse:
        content = b"x" * (llm_analysis.MAX_PROVIDER_RESPONSE_BYTES + 1)

        def raise_for_status(self) -> None:
            pass

        def json(self):
            pytest.fail("oversized response must be rejected before JSON parsing")

    monkeypatch.setattr(llm_analysis.httpx, "post", lambda *args, **kwargs: FakeResponse())
    with pytest.raises(AnalysisProviderError, match="request failed"):
        extract_source_claims(
            question="Question",
            source_id="source-1",
            title="Study",
            url="https://example.org/paper",
            content="A sufficiently long source passage for extraction.",
        )


def test_verifier_distinguishes_supported_inferred_and_unsupported_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    from app.services.llm_analysis import ExtractedClaim, verify_source_claims

    claims = [
        ExtractedClaim(
            claim_text="Accuracy increased in the reported evaluation.",
            claim_type="finding",
            evidence_excerpt="Accuracy increased from 71% to 84%.",
            confidence_label="moderate",
        ),
        ExtractedClaim(
            claim_text="The method may generalize to rural areas.",
            claim_type="finding",
            evidence_excerpt="The authors recommend evaluation in rural areas.",
            confidence_label="low",
        ),
        ExtractedClaim(
            claim_text="The method is universally effective.",
            claim_type="finding",
            evidence_excerpt="This sentence does not exist in the source.",
            confidence_label="high",
        ),
    ]
    response_body = (
        '{"decisions":['
        '{"claim_index":0,"verdict":"supported"},'
        '{"claim_index":1,"verdict":"inferred"},'
        '{"claim_index":2,"verdict":"supported"}]}'
    )
    monkeypatch.setattr(
        llm_analysis.httpx,
        "post",
        lambda *args, **kwargs: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": response_body}}]},
        ),
    )

    decisions = verify_source_claims(
        claims=claims,
        content=(
            "Accuracy increased from 71% to 84%. "
            "The authors recommend evaluation in rural areas."
        ),
    )
    assert decisions == {0: "supported", 1: "inferred", 2: "unsupported"}


def test_verifier_fails_closed_when_a_decision_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    from app.services.llm_analysis import ExtractedClaim, verify_source_claims

    claims = [
        ExtractedClaim(
            claim_text="The source directly reports a result.",
            claim_type="finding",
            evidence_excerpt="The result was 84%.",
            confidence_label="moderate",
        ),
        ExtractedClaim(
            claim_text="A second claim needs verification.",
            claim_type="limitation",
            evidence_excerpt="Further testing is needed.",
            confidence_label="low",
        ),
    ]
    monkeypatch.setattr(
        llm_analysis.httpx,
        "post",
        lambda *args, **kwargs: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"choices": [{"message": {"content": '{"decisions":[{"claim_index":0,"verdict":"supported"}]}'}}]},
        ),
    )
    decisions = verify_source_claims(
        claims=claims,
        content="The result was 84%. Further testing is needed.",
    )
    assert decisions == {0: "supported"}
