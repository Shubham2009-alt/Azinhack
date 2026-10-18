from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, ResearchRun
from app.models.research import utc_now
from app.services import job_worker


def isolated_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(job_worker, "SessionLocal", factory)
    return engine, factory


def make_run(factory, *, status="queued", updated_at=None):
    with factory() as db:
        run = ResearchRun(
            owner_id="owner-1",
            question="Test durable job processing",
            status=status,
            stage=status,
            progress=0,
            updated_at=updated_at or utc_now(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run.id


def test_claim_next_run_atomically_moves_queued_run_to_starting(monkeypatch) -> None:
    engine, factory = isolated_db(monkeypatch)
    try:
        run_id = make_run(factory)
        assert job_worker.claim_next_run() == run_id
        assert job_worker.claim_next_run() is None
        with factory() as db:
            run = db.get(ResearchRun, run_id)
            assert run is not None
            assert run.status == "starting"
            assert run.stage == "worker_claimed"
    finally:
        engine.dispose()


def test_stale_active_runs_are_failed_with_safe_recovery_message(monkeypatch) -> None:
    engine, factory = isolated_db(monkeypatch)
    try:
        run_id = make_run(
            factory,
            status="analyzing",
            updated_at=utc_now() - timedelta(hours=1),
        )
        assert job_worker.fail_stale_runs() == 1
        with factory() as db:
            run = db.get(ResearchRun, run_id)
            assert run is not None
            assert run.status == "failed"
            assert run.error_code == "WORKER_INTERRUPTED"
            assert "new research run" in (run.warning_summary or "")
    finally:
        engine.dispose()
