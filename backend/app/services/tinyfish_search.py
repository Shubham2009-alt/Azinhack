import ipaddress
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.services.provider_io import response_json_limited
from app.settings import settings

SEARCH_API_URL = "https://api.search.tinyfish.ai"
MAX_PROVIDER_RESPONSE_BYTES = 2_000_000
MAX_SEARCH_RESULTS_TO_SCAN = 100
MAX_QUERY_CHARS = 1000
TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


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


def canonicalize_url(value: str) -> str | None:
    """Normalize safe HTTP(S) URLs and remove common tracking parameters."""
    try:
        parsed = urlsplit(value.strip())
        hostname = parsed.hostname
        port = parsed.port
    except (AttributeError, ValueError):
        return None

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not hostname:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    # Remote research fetches do not need arbitrary service ports. Restrict
    # targets to standard web ports to reduce the reachable attack surface.
    if port is not None and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        return None

    hostname = hostname.lower().rstrip(".")
    # Some HTTP clients accept legacy numeric IPv4 spellings such as 127.1,
    # 2130706433, or 0x7f000001. Reject numeric-only hostnames rather than
    # relying on this parser's interpretation before handing URLs to a fetcher.
    if re.fullmatch(r"(?:[0-9]+|0x[0-9a-f]+)(?:\.(?:[0-9]+|0x[0-9a-f]+))*", hostname):
        return None
    # Search results are untrusted. Do not ask the fetch provider to visit
    # loopback, private, link-local, or other non-public IP addresses.
    try:
        ip_address = ipaddress.ip_address(hostname)
    except ValueError:
        ip_address = None
    if ip_address is not None and not ip_address.is_global:
        return None
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        return None

    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{netloc}:{port}"

    query_items = []
    for key, item_value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered_key = key.lower()
        if lowered_key.startswith("utm_") or lowered_key in TRACKING_PARAMS:
            continue
        query_items.append((key, item_value))
    query_items.sort()

    return urlunsplit(
        (scheme, netloc, parsed.path or "/", urlencode(query_items, doseq=True), "")
    )


def search_research_papers(
    query: str,
    *,
    year_min: int | None = None,
    year_max: int | None = None,
    limit: int = 10,
) -> list[PaperSearchResult]:
    """Search academic literature using TinyFish's documented Search API."""
    if not query.strip():
        raise ValueError("query must not be blank")
    bounded_query = query.strip()[:MAX_QUERY_CHARS]
    if year_min is not None and year_max is not None and year_min > year_max:
        raise ValueError("year_min must be less than or equal to year_max")

    api_key = settings.tinyfish_api_key.strip()
    if not api_key:
        raise TinyFishConfigurationError("TinyFish API key is not configured.")

    params: dict[str, Any] = {
        "query": bounded_query,
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
        payload = response_json_limited(response, MAX_PROVIDER_RESPONSE_BYTES)
    except (httpx.HTTPError, ValueError) as exc:
        raise TinyFishSearchError("TinyFish search request failed.") from exc

    raw_results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(raw_results, list):
        raise TinyFishSearchError("TinyFish returned an unexpected response format.")

    results: list[PaperSearchResult] = []
    seen_urls: set[str] = set()
    result_limit = max(1, min(limit, 10))
    for item in raw_results[:MAX_SEARCH_RESULTS_TO_SCAN]:
        if not isinstance(item, dict):
            continue
        raw_url = item.get("url")
        title = item.get("title")
        if not isinstance(raw_url, str) or not isinstance(title, str) or not title.strip():
            continue
        normalized_url = canonicalize_url(raw_url)
        if normalized_url is None or normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)

        year = item.get("publication_year")
        if year is None:
            year = item.get("year")
        if not isinstance(year, int) or isinstance(year, bool) or not 0 <= year <= 9999:
            year = None
        authors = item.get("authors")
        if not isinstance(authors, list):
            authors = None
        else:
            authors = [author for author in authors if isinstance(author, str)]

        citation_count = item.get("citation_count")
        if (
            not isinstance(citation_count, int)
            or isinstance(citation_count, bool)
            or citation_count < 0
        ):
            citation_count = None

        results.append(
            PaperSearchResult(
                title=title.strip()[:1000],
                url=normalized_url,
                snippet=(item.get("snippet")[:2000] if isinstance(item.get("snippet"), str) else None),
                publisher=(item.get("site_name", "")[:300] or None if isinstance(item.get("site_name"), str) else None),
                publication_year=year,
                authors=[author.strip()[:300] for author in (authors or [])[:50] if author.strip()],
                venue=(item.get("venue", "")[:500] or None if isinstance(item.get("venue"), str) else None),
                citation_count=citation_count,
            )
        )
        if len(results) >= result_limit:
            break

    return results
