from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class ResearchRun(Base):
    __tablename__ = "research_runs"
    __table_args__ = (CheckConstraint("progress >= 0 AND progress <= 100", name="ck_run_progress"), Index("ix_run_status_created", "status", "created_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    year_min: Mapped[int | None] = mapped_column(nullable=True)
    year_max: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    stage: Mapped[str] = mapped_column(String(80), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    warning_summary: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list["Source"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    claims: Mapped[list["Claim"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    report: Mapped["Report | None"] = relationship(back_populates="run", cascade="all, delete-orphan", uselist=False)


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("run_id", "canonical_url", name="uq_source_run_url"), Index("ix_source_run_status", "run_id", "retrieval_status"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(300))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    retrieval_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    content_hash: Mapped[str | None] = mapped_column(String(128))
    excerpt: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    query_provenance: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    run: Mapped[ResearchRun] = relationship(back_populates="sources")
    claims: Mapped[list["Claim"]] = relationship(back_populates="source")


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (Index("ix_claim_run_type", "run_id", "claim_type"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(40), nullable=False, default="finding")
    evidence_excerpt: Mapped[str | None] = mapped_column(Text)
    confidence_label: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    is_inference: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    run: Mapped[ResearchRun] = relationship(back_populates="claims")
    source: Mapped[Source | None] = relationship(back_populates="claims")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("run_id", name="uq_report_run_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False)
    structured_sections: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    validation_warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    run: Mapped[ResearchRun] = relationship(back_populates="report")
