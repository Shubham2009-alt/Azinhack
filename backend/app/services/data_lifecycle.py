from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Claim, ClaimRelation, EvidenceLink, Report, ResearchRun, Source
from app.models.research import utc_now
from app.settings import settings

TERMINAL_STATUSES = ("completed", "succeeded", "partial", "failed", "error")
MAX_PURGE_BATCH_SIZE = 2000


def delete_research_run(db: Session, run_id: str) -> bool:
    """Delete a run and every child evidence record in the caller's transaction."""
    run = db.get(ResearchRun, run_id)
    if run is None:
        return False

    claim_ids = list(db.scalars(select(Claim.id).where(Claim.run_id == run_id)))
    source_ids = list(db.scalars(select(Source.id).where(Source.run_id == run_id)))

    if claim_ids:
        db.execute(
            delete(ClaimRelation).where(
                or_(
                    ClaimRelation.from_claim_id.in_(claim_ids),
                    ClaimRelation.to_claim_id.in_(claim_ids),
                )
            )
        )
    evidence_conditions = []
    if claim_ids:
        evidence_conditions.append(EvidenceLink.claim_id.in_(claim_ids))
    if source_ids:
        evidence_conditions.append(EvidenceLink.source_id.in_(source_ids))
    if evidence_conditions:
        db.execute(delete(EvidenceLink).where(or_(*evidence_conditions)))

    db.execute(delete(Report).where(Report.run_id == run_id))
    db.execute(delete(Claim).where(Claim.run_id == run_id))
    db.execute(delete(Source).where(Source.run_id == run_id))
    db.execute(delete(ResearchRun).where(ResearchRun.id == run_id))
    return True


def purge_expired_runs(
    *,
    now: datetime | None = None,
    retention_days: int | None = None,
    batch_size: int = 200,
    session_factory: Callable[[], Session] | None = None,
) -> int:
    """Purge at most one batch of terminal runs past the configured retention age."""
    days = settings.research_retention_days if retention_days is None else retention_days
    if days < 1:
        raise ValueError("retention_days must be at least 1")
    if not 1 <= batch_size <= MAX_PURGE_BATCH_SIZE:
        raise ValueError(f"batch_size must be between 1 and {MAX_PURGE_BATCH_SIZE}")

    cutoff = (now or utc_now()) - timedelta(days=days)
    factory = session_factory or SessionLocal
    with factory() as db:
        expired_ids = list(
            db.scalars(
                select(ResearchRun.id)
                .where(
                    ResearchRun.status.in_(TERMINAL_STATUSES),
                    ResearchRun.created_at < cutoff,
                )
                .order_by(ResearchRun.created_at, ResearchRun.id)
                .limit(batch_size)
            )
        )
        for run_id in expired_ids:
            delete_research_run(db, run_id)
        db.commit()
        return len(expired_ids)
