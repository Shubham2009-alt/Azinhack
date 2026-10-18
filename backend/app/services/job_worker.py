import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select, update

from app.database import SessionLocal
from app.models import ResearchRun
from app.models.research import utc_now
from app.services.research_discovery import run_research_discovery

logger = logging.getLogger("researchpilot.jobs")
POLL_INTERVAL_SECONDS = 1.0
STALE_AFTER = timedelta(minutes=30)
ACTIVE_STATUSES = ("starting", "searching", "fetching", "awaiting_analysis", "analyzing")
TERMINAL_STATUSES = {"succeeded", "partial", "failed"}


def claim_next_run() -> str | None:
    """Atomically claim one persisted queued run, safe across competing workers."""
    with SessionLocal() as db:
        run_id = db.scalar(
            select(ResearchRun.id)
            .where(ResearchRun.status == "queued")
            .order_by(ResearchRun.created_at, ResearchRun.id)
            .limit(1)
        )
        if run_id is None:
            return None

        result = db.execute(
            update(ResearchRun)
            .where(ResearchRun.id == run_id, ResearchRun.status == "queued")
            .values(status="starting", stage="worker_claimed", updated_at=utc_now())
            .execution_options(synchronize_session=False)
        )
        db.commit()
        return run_id if result.rowcount == 1 else None


def fail_stale_runs() -> int:
    """Fail abandoned active runs so a process crash cannot leave them 'running' forever."""
    cutoff = utc_now() - STALE_AFTER
    with SessionLocal() as db:
        result = db.execute(
            update(ResearchRun)
            .where(
                ResearchRun.status.in_(ACTIVE_STATUSES),
                ResearchRun.updated_at < cutoff,
            )
            .values(
                status="failed",
                stage="worker_interrupted",
                error_code="WORKER_INTERRUPTED",
                warning_summary=(
                    "Processing stopped before completion. Start a new research run to retry."
                ),
                updated_at=utc_now(),
            )
            .execution_options(synchronize_session=False)
        )
        db.commit()
        return int(result.rowcount or 0)


def _mark_worker_failure(run_id: str) -> None:
    with SessionLocal() as db:
        run = db.get(ResearchRun, run_id)
        if run is None or run.status in TERMINAL_STATUSES:
            return
        run.status = "failed"
        run.stage = "worker_failed"
        run.error_code = "RESEARCH_WORKER_FAILED"
        run.warning_summary = "Research processing stopped unexpectedly. Start a new research run to retry."
        db.commit()


async def run_job_worker() -> None:
    """Poll the database-backed queue; queued jobs survive API process restarts."""
    while True:
        try:
            fail_stale_runs()
            run_id = claim_next_run()
            if run_id is None:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                continue
            try:
                await asyncio.to_thread(run_research_discovery, run_id)
            except Exception:
                logger.exception("Research job failed unexpectedly")
                _mark_worker_failure(run_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Research job worker loop failed")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
