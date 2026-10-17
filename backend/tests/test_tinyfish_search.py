import httpx
import pytest

from app.services import tinyfish_search
from app.services.tinyfish_search import (
    TinyFishConfigurationError,
    TinyFishSearchError,
    canonicalize_url,
    search_research_papers,
)


def test_search_research_papers_maps_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tinyfish_search.settings, "tinyfish_api_key", "test-key")

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "results": [{
                    "title": "Satellite-Based River Monitoring",
                    "url": "https://example.org/paper",
                    "snippet": "A study summary.",
                    "site_name": "Example Journal",
                    "publication_year": 2023,
                    "authors": ["A. Researcher"],
                    "venue": "Example Journal",
                    "citation_count": 12,
                }]
            }

    def fake_get(url, *, params, headers, timeout):
        assert url == tinyfish_search.SEARCH_API_URL
        assert params["domain_type"] == "research_paper"
        assert params["pub_year_min"] == 2020
        assert params["pub_year_max"] == 2025
        assert headers["X-API-Key"] == "test-key"
        assert timeout == 20.0
        return FakeResponse()

    monkeypatch.setattr(tinyfish_search.httpx, "get", fake_get)
    results = search_research_papers("satellite river monitoring", year_min=2020, year_max=2025)

    assert len(results) == 1
    assert results[0].title == "Satellite-Based River Monitoring"
    assert results[0].publication_year == 2023
    assert results[0].authors == ["A. Researcher"]
    assert results[0].citation_count == 12


def test_search_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tinyfish_search.settings, "tinyfish_api_key", "")
    with pytest.raises(TinyFishConfigurationError):
        search_research_papers("research question")


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        (
            "HTTPS://Example.ORG:443/paper?utm_source=mail&id=7#abstract",
            "https://example.org/paper?id=7",
        ),
        ("https://example.org/paper?id=7&utm_campaign=test", "https://example.org/paper?id=7"),
        ("https://example.org", "https://example.org/"),
        ("javascript:alert(1)", None),
        ("https://user:password@example.org/paper", None),
        ("not a URL", None),
    ],
)
def test_canonicalize_url(raw_url: str, expected: str | None) -> None:
    assert canonicalize_url(raw_url) == expected


def test_search_deduplicates_urls_and_ignores_invalid_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tinyfish_search.settings, "tinyfish_api_key", "test-key")

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "results": [
                    {"title": "First", "url": "https://example.org/paper?utm_source=a"},
                    {"title": "Duplicate", "url": "https://EXAMPLE.org/paper#section"},
                    {"title": "Bad scheme", "url": "javascript:alert(1)"},
                    {"title": "Missing title", "url": "https://example.org/other"},
                    {"title": "Second", "url": "https://example.org/second"},
                ]
            }

    monkeypatch.setattr(tinyfish_search.httpx, "get", lambda *args, **kwargs: FakeResponse())
    results = search_research_papers("research question", limit=10)
    assert [result.title for result in results] == ["First", "Second"]
    assert results[0].url == "https://example.org/paper"


def test_search_wraps_http_and_invalid_json_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tinyfish_search.settings, "tinyfish_api_key", "test-key")

    def raise_http_error(*args, **kwargs):
        raise httpx.TimeoutException("sensitive upstream detail")

    monkeypatch.setattr(tinyfish_search.httpx, "get", raise_http_error)
    with pytest.raises(TinyFishSearchError, match="request failed") as error:
        search_research_papers("research question")
    assert "sensitive upstream detail" not in str(error.value)


def test_search_rejects_unexpected_response_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tinyfish_search.settings, "tinyfish_api_key", "test-key")

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"items": []}

    monkeypatch.setattr(tinyfish_search.httpx, "get", lambda *args, **kwargs: FakeResponse())
    with pytest.raises(TinyFishSearchError, match="unexpected response"):
        search_research_papers("research question")


@pytest.mark.parametrize(
    ("query", "year_min", "year_max"),
    [
        ("   ", None, None),
        ("valid question", 2025, 2020),
    ],
)
def test_search_rejects_invalid_arguments(query: str, year_min: int | None, year_max: int | None) -> None:
    with pytest.raises(ValueError):
        search_research_papers(query, year_min=year_min, year_max=year_max)
