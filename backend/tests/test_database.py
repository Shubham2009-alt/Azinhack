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



def test_init_db_adds_content_column_to_existing_source_table(monkeypatch) -> None:
    from sqlalchemy import inspect, text

    from app import database

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE research_runs (id VARCHAR(36) PRIMARY KEY, question TEXT NOT NULL)")
        )
        connection.execute(
            text(
                "CREATE TABLE sources (id VARCHAR(36) PRIMARY KEY, "
                "run_id VARCHAR(36) NOT NULL, canonical_url TEXT NOT NULL, title TEXT NOT NULL)"
            )
        )

    monkeypatch.setattr(database, "engine", engine)
    database.init_db()
    columns = {column["name"] for column in inspect(engine).get_columns("sources")}
    assert "content_text" in columns
    engine.dispose()
