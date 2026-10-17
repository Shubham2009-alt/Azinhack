from sqlalchemy import select

from app.database import SessionLocal
from app.models import ResearchRun, Source
from app.services.tinyfish_search import (
    TinyFishConfigurationError,
    TinyFishSearchError,
    search_research_papers,
)


def run_research_discovery(run_id: str) -> None:
    """Discover and persist academic source candidates for an existing run."""
    with SessionLocal() as db:
        run = db.get(ResearchRun, run_id)
        if run is None:
            return

        run.status = "searching"
        run.stage = "source_discovery"
        run.progress = 10
        run.error_code = None
        db.commit()

        try:
            results = search_research_papers(
                run.question,
                year_min=run.year_min,
                year_max=run.year_max,
                limit=10,
            )
        except TinyFishConfigurationError:
            run.status = "failed"
            run.stage = "source_discovery_failed"
            run.error_code = "TINYFISH_NOT_CONFIGURED"
            run.warning_summary = "Source discovery is unavailable: configure TINYFISH_API_KEY on the backend."
            db.commit()
            return
        except TinyFishSearchError:
            run.status = "failed"
            run.stage = "source_discovery_failed"
            run.error_code = "TINYFISH_SEARCH_FAILED"
            run.warning_summary = "TinyFish source discovery failed. Retry the research run after checking provider availability."
            db.commit()
            return

        for result in results:
            existing = db.scalar(
                select(Source.id).where(
                    Source.run_id == run.id,
                    Source.canonical_url == result.url,
                )
            )
            if existing:
                continue
            db.add(
                Source(
                    run_id=run.id,
                    canonical_url=result.url,
                    title=result.title,
                    publisher=result.publisher,
                    publication_year=result.publication_year,
                    authors=result.authors or [],
                    venue=result.venue,
                    citation_count=result.citation_count,
                    retrieval_status="discovered",
                    excerpt=result.snippet,
                    query_provenance=[run.question],
                )
            )

        run.status = "awaiting_analysis"
        run.stage = "source_discovery_complete"
        run.progress = 35
        run.warning_summary = (
            "No academic sources were returned by the search provider; this does not establish that no prior work exists."
            if not results
            else None
        )
        db.commit()
