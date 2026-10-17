from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, ResearchRun, Source
from app.services import research_discovery
from app.services.tinyfish_fetch import FetchBatchResult, FetchedPage, TinyFishFetchError
from app.services.tinyfish_search import (
    PaperSearchResult,
    TinyFishConfigurationError,
    TinyFishSearchError,
)


@pytest.fixture()
def discovery_db(monkeypatch: pytest.MonkeyPatch) -> Callable[[], Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def session_factory() -> Session:
        return Session(engine, expire_on_commit=False)

    monkeypatch.setattr(research_discovery, "SessionLocal", session_factory)
    yield session_factory
    engine.dispose()


def create_run(session_factory: Callable[[], Session]) -> str:
    with session_factory() as db:
        run = ResearchRun(question="Can satellites detect river pollution?")
        db.add(run)
        db.commit()
        return run.id


def test_discovery_fetches_and_persists_source_content(
    discovery_db: Callable[[], Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = create_run(discovery_db)
    monkeypatch.setattr(
        research_discovery,
        "search_research_papers",
        lambda *args, **kwargs: [
            PaperSearchResult(
                title="Satellite River Monitoring",
                url="https://example.org/paper?utm_source=search",
                snippet="A source-provided summary.",
                publisher="Example",
                publication_year=2024,
                authors=["A. Researcher"],
                venue="Example Journal",
                citation_count=8,
            ),
            PaperSearchResult(title="Duplicate URL", url="https://example.org/paper"),
        ],
    )
    monkeypatch.setattr(
        research_discovery,
        "fetch_pages",
        lambda urls, **kwargs: FetchBatchResult(
            results=[
                FetchedPage(
                    url="https://example.org/paper",
                    final_url="https://example.org/paper",
                    title="Fetched Paper Title",
                    description="Page description",
                    published_date="2024-04-01",
                    author="B. Researcher",
                    text="# Fetched Paper Title\n\nFull paper content and methods.",
                )
            ],
            errors=[],
        ),
    )

    research_discovery.run_research_discovery(run_id)

    with discovery_db() as db:
        run = db.get(ResearchRun, run_id)
        sources = list(db.scalars(select(Source).where(Source.run_id == run_id)))
        assert run is not None
        assert run.status == "awaiting_analysis"
        assert run.stage == "source_retrieval_complete"
        assert run.progress == 60
        assert run.warning_summary is None
        assert len(sources) == 1
        assert sources[0].canonical_url == "https://example.org/paper"
        assert sources[0].retrieval_status == "retrieved"
        assert sources[0].publication_year == 2024
        assert sources[0].query_provenance == [run.question]
        assert sources[0].title == "Fetched Paper Title"
        assert sources[0].content_text is not None
        assert "Full paper content" in sources[0].content_text
        assert sources[0].content_hash
        assert sources[0].published_at is not None


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (TinyFishConfigurationError("secret detail"), "TINYFISH_NOT_CONFIGURED"),
        (TinyFishSearchError("secret detail"), "TINYFISH_SEARCH_FAILED"),
    ],
)
def test_discovery_records_safe_search_failure(
    discovery_db: Callable[[], Session],
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_code: str,
) -> None:
    run_id = create_run(discovery_db)

    def fail_search(*args: Any, **kwargs: Any) -> list[PaperSearchResult]:
        raise error

    monkeypatch.setattr(research_discovery, "search_research_papers", fail_search)
    research_discovery.run_research_discovery(run_id)

    with discovery_db() as db:
        run = db.get(ResearchRun, run_id)
        assert run is not None
        assert run.status == "failed"
        assert run.error_code == expected_code
        assert run.stage == "source_discovery_failed"
        assert run.warning_summary is not None
        assert "secret detail" not in run.warning_summary


def test_empty_search_is_not_presented_as_proof_of_no_research(
    discovery_db: Callable[[], Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = create_run(discovery_db)
    monkeypatch.setattr(research_discovery, "search_research_papers", lambda *args, **kwargs: [])

    research_discovery.run_research_discovery(run_id)

    with discovery_db() as db:
        run = db.get(ResearchRun, run_id)
        assert run is not None
        assert run.status == "awaiting_analysis"
        assert run.warning_summary is not None
        assert "does not establish that no prior work exists" in run.warning_summary


def test_fetch_failure_preserves_search_metadata(
    discovery_db: Callable[[], Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = create_run(discovery_db)
    monkeypatch.setattr(
        research_discovery,
        "search_research_papers",
        lambda *args, **kwargs: [
            PaperSearchResult(title="Found Paper", url="https://example.org/paper")
        ],
    )

    def fail_fetch(*args: Any, **kwargs: Any) -> FetchBatchResult:
        raise TinyFishFetchError("private upstream details")

    monkeypatch.setattr(research_discovery, "fetch_pages", fail_fetch)
    research_discovery.run_research_discovery(run_id)

    with discovery_db() as db:
        run = db.get(ResearchRun, run_id)
        source = db.scalar(select(Source).where(Source.run_id == run_id))
        assert run is not None and source is not None
        assert run.status == "partial"
        assert run.stage == "source_retrieval_complete"
        assert source.retrieval_status == "fetch_failed"
        assert source.failure_code == "TINYFISH_FETCH_FAILED"
        assert "private upstream details" not in (run.warning_summary or "")


def test_per_url_fetch_failure_does_not_discard_other_sources(
    discovery_db: Callable[[], Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = create_run(discovery_db)
    monkeypatch.setattr(
        research_discovery,
        "search_research_papers",
        lambda *args, **kwargs: [
            PaperSearchResult(title="Available Paper", url="https://example.org/ok"),
            PaperSearchResult(title="Blocked Paper", url="https://example.org/blocked"),
        ],
    )
    monkeypatch.setattr(
        research_discovery,
        "fetch_pages",
        lambda urls, **kwargs: FetchBatchResult(
            results=[
                FetchedPage(
                    url="https://example.org/ok",
                    final_url=None,
                    title="Available Paper",
                    description=None,
                    published_date=None,
                    author=None,
                    text="Accessible full page content.",
                )
            ],
            errors=[],
        ),
    )

    research_discovery.run_research_discovery(run_id)

    with discovery_db() as db:
        run = db.get(ResearchRun, run_id)
        sources = list(db.scalars(select(Source).where(Source.run_id == run_id).order_by(Source.canonical_url)))
        assert run is not None
        assert run.status == "awaiting_analysis"
        assert run.warning_summary is not None
        assert "1 of 2" in run.warning_summary
        assert sources[0].retrieval_status == "fetch_failed"
        assert sources[1].retrieval_status == "retrieved"
