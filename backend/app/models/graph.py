from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.research import new_id


class EvidenceLink(Base):
    __tablename__ = "evidence_links"
    __table_args__ = (CheckConstraint("relationship IN ('supports', 'contradicts', 'qualifies')", name="ck_evidence_relationship"), Index("ix_evidence_claim", "claim_id"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    relationship: Mapped[str] = mapped_column(String(20), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_label: Mapped[str] = mapped_column(String(20), nullable=False, default="low")


class ClaimRelation(Base):
    __tablename__ = "claim_relations"
    __table_args__ = (CheckConstraint("relationship IN ('supports', 'contradicts', 'qualifies', 'derived_from')", name="ck_claim_relation_type"), Index("ix_relation_from", "from_claim_id"), Index("ix_relation_to", "to_claim_id"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    from_claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    to_claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    relationship: Mapped[str] = mapped_column(String(20), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_label: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
