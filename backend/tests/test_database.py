from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, ResearchRun, Source


def test_run_and_source_persist() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        run = ResearchRun(question="Can satellite imagery detect river pollution?")
        run.sources.append(Source(canonical_url="https://example.org/paper", title="Example paper"))
        session.add(run)
        session.commit()
        session.refresh(run)
        assert run.id
        assert run.sources[0].canonical_url == "https://example.org/paper"
    engine.dispose()
