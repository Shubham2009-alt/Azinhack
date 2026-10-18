from collections.abc import Callable

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, Claim, ClaimRelation, Report, ResearchRun, Source
from app.services.comparison_gap_analysis import ComparisonGapResult
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
    monkeypatch.setattr(
        research_analysis,
        "verify_source_claims",
        lambda *, claims, content: {0: "supported", 1: "supported"},
    )
    monkeypatch.setattr(
        research_analysis,
        "compare_claims_and_identify_gaps",
        lambda **kwargs: ComparisonGapResult(relations=[], candidate_gaps=[]),
    )
    research_analysis.run_research_analysis(run_id)
    with analysis_db() as db:
        run = db.get(ResearchRun, run_id)
        claims = list(db.scalars(select(Claim).where(Claim.run_id == run_id)))
        assert run is not None and run.status == "succeeded"
        assert run.stage == "cross_source_analysis_complete"
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


def test_unretrieved_sources_keep_completed_run_partial(
    analysis_db: Callable[[], Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, _ = create_retrieved_run(analysis_db)
    with analysis_db() as db:
        db.add(
            Source(
                run_id=run_id,
                canonical_url="https://example.org/unavailable",
                title="Unavailable paper",
                retrieval_status="fetch_failed",
            )
        )
        db.commit()
    monkeypatch.setattr(research_analysis, "extract_source_claims", lambda **kwargs: [])

    research_analysis.run_research_analysis(run_id)

    with analysis_db() as db:
        run = db.get(ResearchRun, run_id)
        assert run is not None and run.status == "partial"
        assert "1 source(s) could not be retrieved" in (run.warning_summary or "")


def test_persists_cross_source_relations_and_tentative_gaps(
    analysis_db: Callable[[], Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import research_analysis
    from app.services.comparison_gap_analysis import (
        CandidateGap,
        ComparisonGapResult,
        ProposedRelation,
    )

    run_id, source_a_id = create_retrieved_run(analysis_db)
    with analysis_db() as db:
        run = db.get(ResearchRun, run_id)
        assert run is not None
        source_b = Source(
            run_id=run_id,
            canonical_url="https://example.org/second-paper",
            title="Second river monitoring study",
            retrieval_status="retrieved",
            content_text="A second independently retrieved study reported lower accuracy.",
        )
        db.add(source_b)
        db.commit()

    def fake_extract(**kwargs):
        if kwargs["source_id"] == source_a_id:
            return [
                ExtractedClaim(
                    claim_text="The first evaluation reported higher detection accuracy.",
                    claim_type="finding",
                    evidence_excerpt="Detection accuracy increased from 71% to 84%.",
                    confidence_label="moderate",
                )
            ]
        return [
            ExtractedClaim(
                claim_text="The second evaluation reported lower detection accuracy.",
                claim_type="finding",
                evidence_excerpt="A second independently retrieved study reported lower accuracy.",
                confidence_label="moderate",
            )
        ]

    monkeypatch.setattr(research_analysis, "extract_source_claims", fake_extract)
    monkeypatch.setattr(
        research_analysis,
        "verify_source_claims",
        lambda *, claims, content: {index: "supported" for index, _ in enumerate(claims)},
    )
    monkeypatch.setattr(
        research_analysis,
        "compare_claims_and_identify_gaps",
        lambda **kwargs: ComparisonGapResult(
            relations=[
                ProposedRelation(
                    claim_a_id=kwargs["claims"][0]["id"],
                    claim_b_id=kwargs["claims"][1]["id"],
                    relationship="qualifies",
                    rationale="The studies report different outcomes under their own evaluation conditions.",
                    confidence_label="low",
                )
            ],
            candidate_gaps=[
                CandidateGap(
                    title="Evaluation conditions need comparison",
                    description="The available claims do not establish whether the evaluations used comparable conditions.",
                    evidence_level="low",
                    basis_claim_ids=[item["id"] for item in kwargs["claims"]],
                    rationale="Both claims describe results but the extracted evidence does not fully specify comparable settings.",
                )
            ],
        ),
    )

    research_analysis.run_research_analysis(run_id)
    with analysis_db() as db:
        claims = list(db.scalars(select(Claim).where(Claim.run_id == run_id)))
        relations = list(
            db.scalars(
                select(ClaimRelation).where(
                    ClaimRelation.from_claim_id.in_([item.id for item in claims])
                )
            )
        )
        report = db.scalar(select(Report).where(Report.run_id == run_id))
        assert len(claims) == 2
        assert len(relations) == 1
        assert relations[0].relationship == "qualifies"
        assert report is not None
        gap = report.structured_sections["candidate_research_gaps"][0]
        assert gap["is_confirmed_novelty"] is False
        assert len(gap["basis_claim_ids"]) == 2


def test_persists_inferences_as_inferences_and_drops_unsupported_claims(
    analysis_db: Callable[[], Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, _ = create_retrieved_run(analysis_db)
    source_text = "Accuracy increased from 71% to 84%. Further rural testing is recommended."
    with analysis_db() as db:
        source = db.scalar(select(Source).where(Source.run_id == run_id))
        assert source is not None
        source.content_text = source_text
        db.commit()

    monkeypatch.setattr(
        research_analysis,
        "extract_source_claims",
        lambda **kwargs: [
            ExtractedClaim(
                claim_text="Accuracy increased in the reported evaluation.",
                claim_type="finding",
                evidence_excerpt="Accuracy increased from 71% to 84%.",
                confidence_label="moderate",
            ),
            ExtractedClaim(
                claim_text="The method may need rural validation.",
                claim_type="limitation",
                evidence_excerpt="Further rural testing is recommended.",
                confidence_label="low",
            ),
            ExtractedClaim(
                claim_text="The method works everywhere.",
                claim_type="finding",
                evidence_excerpt="Accuracy increased from 71% to 84%.",
                confidence_label="high",
            ),
        ],
    )
    monkeypatch.setattr(
        research_analysis,
        "verify_source_claims",
        lambda **kwargs: {0: "supported", 1: "inferred", 2: "unsupported"},
    )
    monkeypatch.setattr(
        research_analysis,
        "compare_claims_and_identify_gaps",
        lambda **kwargs: ComparisonGapResult(relations=[], candidate_gaps=[]),
    )

    research_analysis.run_research_analysis(run_id)

    with analysis_db() as db:
        claims = list(db.scalars(select(Claim).where(Claim.run_id == run_id)))
        assert len(claims) == 2
        assert sorted(claim.is_inference for claim in claims) == [False, True]
        assert all(claim.claim_text != "The method works everywhere." for claim in claims)
