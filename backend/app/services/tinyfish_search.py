from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from app.settings import settings

SEARCH_API_URL = "https://api.search.tinyfish.ai"


class TinyFishConfigurationError(RuntimeError):
    """Raised when the TinyFish API key is not configured."""


class TinyFishSearchError(RuntimeError):
    """Raised when TinyFish search fails or returns an invalid response."""


@dataclass(frozen=True)
class PaperSearchResult:
    title: str
    url: str
    snippet: str | None = None
    publisher: str | None = None
    publication_year: int | None = None
    authors: list[str] | None = None
    venue: str | None = None
    citation_count: int | None = None


def search_research_papers(
    query: str,
    *,
    year_min: int | None = None,
    year_max: int | None = None,
    limit: int = 10,
) -> list[PaperSearchResult]:
    """Search academic literature using TinyFish's documented Search API."""
    api_key = settings.tinyfish_api_key.strip()
    if not api_key:
        raise TinyFishConfigurationError("TinyFish API key is not configured.")

    params: dict[str, Any] = {
        "query": query,
        "domain_type": "research_paper",
        "page": 0,
    }
    if year_min is not None:
        params["pub_year_min"] = year_min
    if year_max is not None:
        params["pub_year_max"] = year_max

    try:
        response = httpx.get(
            SEARCH_API_URL,
            params=params,
            headers={"X-API-Key": api_key},
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise TinyFishSearchError("TinyFish search request failed.") from exc

    raw_results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(raw_results, list):
        raise TinyFishSearchError("TinyFish returned an unexpected response format.")

    results: list[PaperSearchResult] = []
    seen_urls: set[str] = set()
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        title = item.get("title")
        if not isinstance(url, str) or not isinstance(title, str) or not title.strip():
            continue
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        normalized_url = url.strip()
        if normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)

        year = item.get("publication_year", item.get("year"))
        if not isinstance(year, int) or not 0 <= year <= 9999:
            year = None
        authors = item.get("authors")
        if not isinstance(authors, list):
            authors = None
        else:
            authors = [author for author in authors if isinstance(author, str)]

        citation_count = item.get("citation_count")
        if not isinstance(citation_count, int) or citation_count < 0:
            citation_count = None

        results.append(
            PaperSearchResult(
                title=title.strip(),
                url=normalized_url,
                snippet=item.get("snippet") if isinstance(item.get("snippet"), str) else None,
                publisher=item.get("site_name") if isinstance(item.get("site_name"), str) else None,
                publication_year=year,
                authors=authors,
                venue=item.get("venue") if isinstance(item.get("venue"), str) else None,
                citation_count=citation_count,
            )
        )
        if len(results) >= max(1, min(limit, 10)):
            break

    return results
