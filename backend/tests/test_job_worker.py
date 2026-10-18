from datetime import timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.models import ResearchRun
from app.models.research import utc_now
from app.services.job_worker import claim_next_run, fail_stale_runs


def test_claim_next_run_atomically_moves_queued_run_to_starting(client) -> None:
    created = client.post(
        "/api/research-runs",
        json={"question": "How does durable queueing work?"},
        headers={"Authorization": "Bearer test-token"},
    )
    # The API test client replaces auth with a test user; use its returned ID.
    assert created.status_code == 202
    run_id = created.json()["run_id"]

    # The API fixture replaces discovery with a no-op, so the persisted run stays queued.
    with SessionLocal() as db:
        run = db.get(ResearchRun, run_id)
        if run is not None:
            run.status = "queued"
            run.stage = "queued"
            db.commit()

    claimed = claim_next_run()
    assert claimed == run_id
    with SessionLocal() as db:
        run = db.get(ResearchRun, run_id)
        assert run is not None
        assert run.status == "starting"
        assert run.stage == "worker_claimed"


def test_stale_active_runs_are_failed_with_safe_recovery_message(client) -> None:
    created = client.post(
        "/api/research-runs",
        json={"question": "Test stale run recovery"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert created.status_code == 202
    run_id = created.json()["run_id"]

    with SessionLocal() as db:
        run = db.get(ResearchRun, run_id)
        assert run is not None
        run.status = "analyzing"
        run.stage = "claim_extraction"
        run.updated_at = utc_now() - timedelta(hours=1)
        db.commit()

    assert fail_stale_runs() >= 1
    with SessionLocal() as db:
        run = db.get(ResearchRun, run_id)
        assert run is not None
        assert run.status == "failed"
        assert run.error_code == "WORKER_INTERRUPTED"
        assert "new research run" in (run.warning_summary or "")
