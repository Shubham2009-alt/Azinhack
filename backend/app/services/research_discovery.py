import hashlib
from datetime import datetime

from sqlalchemy import select

from app.database import SessionLocal
from app.models import ResearchRun, Source
from app.services.research_analysis import run_research_analysis
from app.services.tinyfish_fetch import TinyFishFetchError, fetch_pages
from app.services.tinyfish_search import (
    TinyFishConfigurationError,
    TinyFishSearchError,
    canonicalize_url,
    search_research_papers,
)


def _parse_published_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


def run_research_discovery(run_id: str) -> None:
    """Discover candidate papers, fetch accessible pages, and persist partial outcomes."""
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

        sources_by_url: dict[str, Source] = {}
        for result in results:
            canonical_url = canonicalize_url(result.url)
            if canonical_url is None:
                continue
            existing = db.scalar(
                select(Source).where(
                    Source.run_id == run.id,
                    Source.canonical_url == canonical_url,
                )
            )
            if existing:
                sources_by_url[canonical_url] = existing
                continue
            source = Source(
                run_id=run.id,
                canonical_url=canonical_url,
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
            db.add(source)
            sources_by_url[canonical_url] = source

        db.flush()
        db.commit()

        if not sources_by_url:
            run.status = "awaiting_analysis"
            run.stage = "source_discovery_complete"
            run.progress = 35
            run.warning_summary = (
                "No academic sources were returned by the search provider; "
                "this does not establish that no prior work exists."
            )
            db.commit()
            return

        run.status = "fetching"
        run.stage = "source_retrieval"
        run.progress = 40
        run.warning_summary = None
        db.commit()

        source_urls = list(sources_by_url)
        try:
            fetched = fetch_pages(
                source_urls,
                purpose=f"Retrieve accessible research-paper content relevant to: {run.question}",
                limit=10,
            )
        except TinyFishFetchError:
            for source in sources_by_url.values():
                source.retrieval_status = "fetch_failed"
                source.failure_code = "TINYFISH_FETCH_FAILED"
            run.status = "partial"
            run.stage = "source_retrieval_complete"
            run.progress = 55
            run.warning_summary = (
                "Paper search succeeded, but page retrieval failed. Search metadata was retained; "
                "full-text evidence is unavailable for this run."
            )
            db.commit()
            return

        outcomes: set[str] = set()
        for page in fetched.results:
            candidate_urls = [page.url]
            if page.final_url:
                candidate_urls.append(page.final_url)
            source = next(
                (
                    sources_by_url[canonical]
                    for url in candidate_urls
                    if (canonical := canonicalize_url(url)) in sources_by_url
                ),
                None,
            )
            if source is None:
                continue
            outcomes.add(source.canonical_url)
            if not page.text.strip():
                source.retrieval_status = "fetch_failed"
                source.failure_code = "EMPTY_PAGE_CONTENT"
                continue

            source.content_text = page.text
            source.content_hash = hashlib.sha256(page.text.encode("utf-8")).hexdigest()
            source.retrieval_status = "retrieved"
            source.failure_code = None
            if page.title and page.title.strip():
                source.title = page.title.strip()
            if page.description and not source.excerpt:
                source.excerpt = page.description[:2000]
            if page.author and not source.authors:
                source.authors = [page.author]
            if page.published_date and source.published_at is None:
                source.published_at = _parse_published_date(page.published_date)

        for failure in fetched.errors:
            canonical_url = canonicalize_url(failure.url)
            source = sources_by_url.get(canonical_url or "")
            if source is not None:
                outcomes.add(source.canonical_url)
                source.retrieval_status = "fetch_failed"
                source.failure_code = "FETCH_FAILED"

        for canonical_url, source in sources_by_url.items():
            if canonical_url not in outcomes and source.retrieval_status == "discovered":
                source.retrieval_status = "fetch_failed"
                source.failure_code = "FETCH_NO_RESULT"

        retrieved_count = sum(
            1 for source in sources_by_url.values() if source.retrieval_status == "retrieved"
        )
        failed_count = len(sources_by_url) - retrieved_count
        run.status = "awaiting_analysis" if retrieved_count else "partial"
        run.stage = "source_retrieval_complete"
        run.progress = 60 if retrieved_count else 55
        run.warning_summary = (
            f"Retrieved full content for {retrieved_count} of {len(sources_by_url)} sources; "
            f"{failed_count} source(s) could not be retrieved."
            if failed_count
            else None
        )
        db.commit()
        run_research_analysis(run.id)
