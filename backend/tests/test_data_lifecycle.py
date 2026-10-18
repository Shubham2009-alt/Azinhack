from datetime import timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base,
    Claim,
    ClaimRelation,
    EvidenceLink,
    Report,
    ResearchRun,
    Source,
)
from app.models.research import utc_now
from app.services.data_lifecycle import delete_research_run, purge_expired_runs


def isolated_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    return engine, factory


def seed_complete_run(factory, *, status: str = "partial", created_at=None) -> str:
    with factory() as db:
        run = ResearchRun(
            owner_id="owner-1",
            question="Test retention and evidence deletion",
            status=status,
            stage=status,
            progress=100 if status == "partial" else 0,
            created_at=created_at or utc_now(),
        )
        db.add(run)
        db.flush()
        source = Source(
            run_id=run.id,
            canonical_url="https://example.org/paper",
            title="Example paper",
            content_text="Evidence text",
            excerpt="Evidence text",
        )
        db.add(source)
        db.flush()
        claim = Claim(
            run_id=run.id,
            source_id=source.id,
            claim_text="A source-grounded test claim.",
            claim_type="finding",
            evidence_excerpt="Evidence text",
            confidence_label="moderate",
        )
        db.add(claim)
        db.flush()
        db.add_all([
            EvidenceLink(
                claim_id=claim.id,
                source_id=source.id,
                relationship="supports",
                excerpt="Evidence text",
                rationale="The excerpt directly supports the claim.",
                confidence_label="moderate",
            ),
            ClaimRelation(
                from_claim_id=claim.id,
                to_claim_id=claim.id,
                relationship="derived_from",
                rationale="Seed relation for cascade validation.",
                confidence_label="low",
            ),
            Report(
                run_id=run.id,
                structured_sections={"summary": "test"},
                validation_warnings=[],
            ),
        ])
        db.commit()
        return run.id


def table_count(db: Session, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def test_delete_research_run_removes_all_evidence_including_graph_links() -> None:
    engine, factory = isolated_db()
    try:
        run_id = seed_complete_run(factory)
        with factory() as db:
            assert delete_research_run(db, run_id)
            db.commit()
            assert db.get(ResearchRun, run_id) is None
            for model in (Source, Claim, Report, EvidenceLink, ClaimRelation):
                assert table_count(db, model) == 0
            assert not delete_research_run(db, run_id)
    finally:
        engine.dispose()


def test_retention_purges_only_expired_terminal_runs_and_respects_batch_size() -> None:
    engine, factory = isolated_db()
    try:
        old = utc_now() - timedelta(days=120)
        old_one = seed_complete_run(factory, status="partial", created_at=old)
        old_two = seed_complete_run(factory, status="failed", created_at=old)
        active = seed_complete_run(factory, status="analyzing", created_at=old)
        recent = seed_complete_run(factory, status="succeeded", created_at=utc_now())

        deleted = purge_expired_runs(
            now=utc_now(),
            retention_days=90,
            batch_size=1,
            session_factory=factory,
        )
        assert deleted == 1
        with factory() as db:
            remaining_ids = set(db.scalars(select(ResearchRun.id)))
            assert len(remaining_ids) == 3
            assert (old_one in remaining_ids) != (old_two in remaining_ids)
            assert active in remaining_ids
            assert recent in remaining_ids

        deleted_remaining = purge_expired_runs(
            now=utc_now(),
            retention_days=90,
            batch_size=200,
            session_factory=factory,
        )
        assert deleted_remaining == 1
        with factory() as db:
            remaining_ids = set(db.scalars(select(ResearchRun.id)))
            assert remaining_ids == {active, recent}
            assert table_count(db, EvidenceLink) == 2
    finally:
        engine.dispose()
