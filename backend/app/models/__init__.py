from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.research import Claim, Report, ResearchRun, Source

__all__ = ["Base", "Claim", "Report", "ResearchRun", "Source"]
