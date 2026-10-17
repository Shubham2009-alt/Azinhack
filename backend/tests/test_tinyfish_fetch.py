import httpx
import pytest

from app.services import tinyfish_fetch
from app.services.tinyfish_fetch import (
    FetchBatchResult,
    TinyFishFetchError,
    fetch_pages,
)


def test_fetch_pages_maps_markdown_and_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tinyfish_fetch.settings, "tinyfish_api_key", "test-key")

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "results": [{
                    "url": "https://example.org/paper",
                    "final_url": "https://example.org/paper",
                    "title": "Research Paper",
                    "description": "Summary",
                    "published_date": "2024-04-01",
                    "author": "A. Researcher",
                    "text": "# Research Paper\n\nFull page content.",
                }],
                "errors": [],
            }

    def fake_post(url, *, headers, json, timeout):
        assert url == tinyfish_fetch.FETCH_API_URL
        assert headers["X-API-Key"] == "test-key"
        assert json["urls"] == ["https://example.org/paper"]
        assert json["format"] == "markdown"
        assert json["page_metadata"] is True
        assert json["per_url_timeout_ms"] == 25_000
        assert timeout == 35.0
        return FakeResponse()

    monkeypatch.setattr(tinyfish_fetch.httpx, "post", fake_post)
    result = fetch_pages(
        ["https://example.org/paper"],
        purpose="Fetch research-paper evidence",
    )

    assert isinstance(result, FetchBatchResult)
    assert result.errors == []
    assert result.results[0].title == "Research Paper"
    assert result.results[0].published_date == "2024-04-01"
    assert "Full page content" in result.results[0].text


def test_fetch_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tinyfish_fetch.settings, "tinyfish_api_key", "")
    with pytest.raises(TinyFishFetchError, match="not configured"):
        fetch_pages(["https://example.org/paper"], purpose="Fetch evidence")


def test_fetch_wraps_http_errors_without_leaking_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tinyfish_fetch.settings, "tinyfish_api_key", "test-key")

    def fail(*args, **kwargs):
        raise httpx.TimeoutException("sensitive provider response")

    monkeypatch.setattr(tinyfish_fetch.httpx, "post", fail)
    with pytest.raises(TinyFishFetchError, match="request failed") as error:
        fetch_pages(["https://example.org/paper"], purpose="Fetch evidence")
    assert "sensitive provider response" not in str(error.value)


def test_fetch_validates_response_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tinyfish_fetch.settings, "tinyfish_api_key", "test-key")

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"items": []}

    monkeypatch.setattr(tinyfish_fetch.httpx, "post", lambda *args, **kwargs: FakeResponse())
    with pytest.raises(TinyFishFetchError, match="unexpected response"):
        fetch_pages(["https://example.org/paper"], purpose="Fetch evidence")


def test_fetch_caps_batch_and_deduplicates_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tinyfish_fetch.settings, "tinyfish_api_key", "test-key")
    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"results": [], "errors": []}

    def fake_post(url, *, headers, json, timeout):
        captured["urls"] = json["urls"]
        return FakeResponse()

    monkeypatch.setattr(tinyfish_fetch.httpx, "post", fake_post)
    urls = ["https://example.org/paper"] * 2 + [f"https://example.org/{i}" for i in range(12)]
    fetch_pages(urls, purpose="Fetch evidence")
    assert len(captured["urls"]) == 10
    assert len(set(captured["urls"])) == 10
