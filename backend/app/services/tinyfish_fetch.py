from dataclasses import dataclass
from typing import Any

import httpx

from app.services.provider_io import request_json_limited
from app.services.tinyfish_search import canonicalize_url
from app.settings import settings

FETCH_API_URL = "https://api.fetch.tinyfish.ai"
MAX_CONTENT_CHARS = 60_000
MAX_PROVIDER_RESPONSE_BYTES = 2_000_000
MAX_FETCH_ERRORS = 10
MAX_FETCH_RESULTS_TO_SCAN = 100
MAX_TITLE_CHARS = 1000
MAX_DESCRIPTION_CHARS = 2000
MAX_AUTHOR_CHARS = 300
MAX_DATE_CHARS = 100
ALLOWED_FAILURE_CODES = {
    "FETCH_FAILED", "TIMEOUT", "BLOCKED_URL", "ROBOTS_DENIED", "HTTP_ERROR",
    "UNSUPPORTED_CONTENT_TYPE", "CONTENT_TOO_LARGE", "PROVIDER_ERROR", "RATE_LIMITED",
}


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
    url_limit = max(1, min(limit, 10))
    for url in urls:
        if not isinstance(url, str):
            raise ValueError("Only safe public HTTP(S) URLs can be fetched.")
        normalized_url = canonicalize_url(url)
        if normalized_url is None:
            raise ValueError("Only safe public HTTP(S) URLs can be fetched.")
        if normalized_url not in seen_urls:
            seen_urls.add(normalized_url)
            normalized_urls.append(normalized_url)
            if len(normalized_urls) >= url_limit:
                break

    bounded_urls = normalized_urls
    if not bounded_urls:
        return FetchBatchResult(results=[], errors=[])

    try:
        payload = request_json_limited(
            "POST",
            FETCH_API_URL,
            max_bytes=MAX_PROVIDER_RESPONSE_BYTES,
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
    for item in raw_results[:MAX_FETCH_RESULTS_TO_SCAN]:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            continue
        result_url = canonicalize_url(item["url"])
        if result_url not in requested_urls or result_url in seen_result_urls:
            continue
        seen_result_urls.add(result_url)
        raw_final_url = item.get("final_url")
        final_url = canonicalize_url(raw_final_url) if isinstance(raw_final_url, str) else None
        # Do not persist page content when the provider reports an unsafe redirect
        # destination. This is post-fetch validation, not a substitute for provider
        # side DNS and redirect protections.
        if isinstance(raw_final_url, str) and final_url is None:
            continue
        text_value = item.get("text")
        if not isinstance(text_value, str):
            text_value = ""
        if len(pages) >= len(bounded_urls):
            break
        pages.append(
            FetchedPage(
                url=result_url,
                final_url=final_url,
                title=(item["title"][:MAX_TITLE_CHARS] if isinstance(item.get("title"), str) else None),
                description=(item["description"][:MAX_DESCRIPTION_CHARS] if isinstance(item.get("description"), str) else None),
                published_date=(item["published_date"][:MAX_DATE_CHARS] if isinstance(item.get("published_date"), str) else None),
                author=(item["author"][:MAX_AUTHOR_CHARS] if isinstance(item.get("author"), str) else None),
                text=text_value[:MAX_CONTENT_CHARS],
            )
        )
    seen_error_urls: set[str] = set()
    for item in raw_errors[:MAX_FETCH_ERRORS]:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            continue
        error_url = canonicalize_url(item["url"])
        if error_url not in requested_urls or error_url in seen_error_urls:
            continue
        seen_error_urls.add(error_url)
        raw_code: Any = item.get("code")
        if not isinstance(raw_code, str):
            raw_code = item.get("error")
        candidate_code = str(raw_code or "FETCH_FAILED").strip().upper().replace(" ", "_")[:80]
        code = candidate_code if candidate_code in ALLOWED_FAILURE_CODES else "FETCH_FAILED"
        failures.append(FetchFailure(url=error_url, code=code))
    return FetchBatchResult(results=pages, errors=failures)
