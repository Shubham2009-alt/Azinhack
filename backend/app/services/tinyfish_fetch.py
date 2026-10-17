from dataclasses import dataclass
from typing import Any

import httpx

from app.services.tinyfish_search import canonicalize_url
from app.settings import settings

FETCH_API_URL = "https://api.fetch.tinyfish.ai"
MAX_CONTENT_CHARS = 60_000


class TinyFishFetchError(RuntimeError):
    """Raised when TinyFish Fetch fails or returns an invalid response."""


@dataclass(frozen=True)
class FetchedPage:
    url: str
    final_url: str | None
    title: str | None
    description: str | None
    published_date: str | None
    author: str | None
    text: str


@dataclass(frozen=True)
class FetchFailure:
    url: str
    code: str


@dataclass(frozen=True)
class FetchBatchResult:
    results: list[FetchedPage]
    errors: list[FetchFailure]


def fetch_pages(urls: list[str], *, purpose: str, limit: int = 10) -> FetchBatchResult:
    """Fetch accessible source pages using TinyFish's documented Fetch API."""
    api_key = settings.tinyfish_api_key.strip()
    if not api_key:
        raise TinyFishFetchError("TinyFish API key is not configured.")
    normalized_urls: list[str] = []
    seen_urls: set[str] = set()
    for url in urls:
        if not isinstance(url, str):
            raise ValueError("Only safe public HTTP(S) URLs can be fetched.")
        normalized_url = canonicalize_url(url)
        if normalized_url is None:
            raise ValueError("Only safe public HTTP(S) URLs can be fetched.")
        if normalized_url not in seen_urls:
            seen_urls.add(normalized_url)
            normalized_urls.append(normalized_url)

    bounded_urls = normalized_urls[: max(1, min(limit, 10))]
    if not bounded_urls:
        return FetchBatchResult(results=[], errors=[])

    try:
        response = httpx.post(
            FETCH_API_URL,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={
                "urls": bounded_urls,
                "format": "markdown",
                "links": False,
                "image_links": False,
                "iframe_links": False,
                "page_metadata": True,
                "purpose": purpose[:2000],
                "per_url_timeout_ms": 25_000,
            },
            timeout=35.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise TinyFishFetchError("TinyFish Fetch request failed.") from exc

    if not isinstance(payload, dict):
        raise TinyFishFetchError("TinyFish Fetch returned an unexpected response format.")
    raw_results = payload.get("results")
    raw_errors = payload.get("errors", [])
    if not isinstance(raw_results, list) or not isinstance(raw_errors, list):
        raise TinyFishFetchError("TinyFish Fetch returned an unexpected response format.")

    requested_urls = set(bounded_urls)
    pages: list[FetchedPage] = []
    failures: list[FetchFailure] = []
    seen_result_urls: set[str] = set()
    for item in raw_results:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            continue
        result_url = canonicalize_url(item["url"])
        if result_url not in requested_urls or result_url in seen_result_urls:
            continue
        seen_result_urls.add(result_url)
        raw_final_url = item.get("final_url")
        final_url = canonicalize_url(raw_final_url) if isinstance(raw_final_url, str) else None
        text_value = item.get("text")
        if not isinstance(text_value, str):
            text_value = ""
        pages.append(
            FetchedPage(
                url=result_url,
                final_url=final_url,
                title=item.get("title") if isinstance(item.get("title"), str) else None,
                description=item.get("description") if isinstance(item.get("description"), str) else None,
                published_date=item.get("published_date") if isinstance(item.get("published_date"), str) else None,
                author=item.get("author") if isinstance(item.get("author"), str) else None,
                text=text_value[:MAX_CONTENT_CHARS],
            )
        )
    seen_error_urls: set[str] = set()
    for item in raw_errors:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            continue
        error_url = canonicalize_url(item["url"])
        if error_url not in requested_urls or error_url in seen_error_urls:
            continue
        seen_error_urls.add(error_url)
        error_value: Any = item.get("error")
        if not isinstance(error_value, str):
            error_value = item.get("code")
        code = str(error_value or "FETCH_FAILED").strip().upper().replace(" ", "_")[:80]
        failures.append(FetchFailure(url=error_url, code=code))
    return FetchBatchResult(results=pages, errors=failures)
