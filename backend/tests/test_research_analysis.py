from collections.abc import Callable

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, Claim, ResearchRun, Source
from app.services import research_analysis
from app.services.llm_analysis import (
    AnalysisConfigurationError,
    ExtractedClaim,
)


@pytest.fixture()
def analysis_db(monkeypatch: pytest.MonkeyPatch) -> Callable[[], Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def session_factory() -> Session:
        return Session(engine, expire_on_commit=False)

    monkeypatch.setattr(research_analysis, "SessionLocal", session_factory)
    yield session_factory
    engine.dispose()


def create_retrieved_run(session_factory: Callable[[], Session]) -> tuple[str, str]:
    with session_factory() as db:
        run = ResearchRun(question="Does satellite imagery detect river pollution?")
        db.add(run)
        db.flush()
        source = Source(
            run_id=run.id,
            canonical_url="https://example.org/paper",
            title="River monitoring study",
            retrieval_status="retrieved",
            content_text="Detection accuracy increased from 71% to 84%.",
        )
        db.add(source)
        db.commit()
        return run.id, source.id


def test_persists_only_validated_source_claims(
    analysis_db: Callable[[], Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, source_id = create_retrieved_run(analysis_db)
    monkeypatch.setattr(
        research_analysis,
        "extract_source_claims",
        lambda **kwargs: [
            ExtractedClaim(
                claim_text="Detection accuracy increased in the reported evaluation.",
                claim_type="finding",
                evidence_excerpt="Detection accuracy increased from 71% to 84%.",
                confidence_label="moderate",
            ),
            ExtractedClaim(
                claim_text="This excerpt is not actually in the source.",
                claim_type="finding",
                evidence_excerpt="A fabricated sentence from a model.",
                confidence_label="high",
            ),
        ],
    )
    research_analysis.run_research_analysis(run_id)
    with analysis_db() as db:
        run = db.get(ResearchRun, run_id)
        claims = list(db.scalars(select(Claim).where(Claim.run_id == run_id)))
        assert run is not None and run.status == "partial"
        assert run.stage == "claim_extraction_complete"
        assert len(claims) == 1
        assert claims[0].source_id == source_id
        assert claims[0].is_inference is False
        assert claims[0].evidence_excerpt == "Detection accuracy increased from 71% to 84%."


def test_missing_llm_configuration_keeps_run_partial(
    analysis_db: Callable[[], Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, _ = create_retrieved_run(analysis_db)
    monkeypatch.setattr(
        research_analysis,
        "extract_source_claims",
        lambda **kwargs: (_ for _ in ()).throw(AnalysisConfigurationError("secret")),
    )
    research_analysis.run_research_analysis(run_id)
    with analysis_db() as db:
        run = db.get(ResearchRun, run_id)
        assert run is not None
        assert run.status == "partial"
        assert "not configured" in (run.warning_summary or "")
        assert "secret" not in (run.warning_summary or "")
