import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select, update

from app.database import SessionLocal
from app.models import ResearchRun
from app.models.research import utc_now
from app.services.data_lifecycle import purge_expired_runs
from app.services.research_discovery import run_research_discovery
from app.settings import settings

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
    """Poll the persisted queue and periodically enforce the research-data lifecycle."""
    loop = asyncio.get_running_loop()
    next_retention_cleanup = 0.0
    while True:
        try:
            fail_stale_runs()
            if loop.time() >= next_retention_cleanup:
                try:
                    removed = await asyncio.to_thread(purge_expired_runs)
                    if removed:
                        logger.info("Research retention removed %d expired runs", removed)
                except Exception:
                    # Retention failures must be visible without taking down the queue worker.
                    logger.exception("Research retention cleanup failed")
                next_retention_cleanup = loop.time() + settings.retention_cleanup_interval_seconds
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
