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
