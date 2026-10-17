from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.research import Claim, ClaimRelation, EvidenceLink, Report, ResearchRun, Source

__all__ = [
    "Base",
    "Claim",
    "ClaimRelation",
    "EvidenceLink",
    "Report",
    "ResearchRun",
    "Source",
]
