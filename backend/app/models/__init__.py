from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.research import Claim, Report, ResearchRun, Source
from app.models.graph import ClaimRelation, EvidenceLink

__all__ = ["Base", "Claim", "ClaimRelation", "EvidenceLink", "Report", "ResearchRun", "Source"]
