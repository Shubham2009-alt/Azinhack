import pytest

from app.services import tinyfish_search
from app.services.tinyfish_search import TinyFishConfigurationError, search_research_papers


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
