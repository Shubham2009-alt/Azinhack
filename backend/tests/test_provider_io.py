import pytest

from app.services import provider_io
from app.services.provider_io import ProviderResponseTooLarge, request_json_limited


class FakeStreamingResponse:
    def __init__(self, chunks: list[bytes], *, headers: dict[str, str] | None = None) -> None:
        self.chunks = chunks
        self.headers = headers or {}
        self.iteration_count = 0
        self.requested_chunk_size: int | None = None
        self.closed = False

    def __enter__(self) -> "FakeStreamingResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.closed = True
        return False

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self, chunk_size: int = 65_536):
        self.requested_chunk_size = chunk_size
        for chunk in self.chunks:
            self.iteration_count += 1
            yield chunk


def test_request_json_limited_streams_and_decodes_json(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeStreamingResponse([b'{"ok":', b' true,', b' "n": 2}'])
    captured: dict[str, object] = {}

    def fake_stream(method: str, url: str, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["kwargs"] = kwargs
        return response

    monkeypatch.setattr(provider_io.httpx, "stream", fake_stream)

    result = request_json_limited(
        "GET",
        "https://provider.example/data",
        max_bytes=100,
        timeout=10.0,
    )

    assert result == {"ok": True, "n": 2}
    assert captured["method"] == "GET"
    assert captured["url"] == "https://provider.example/data"
    assert captured["kwargs"] == {"timeout": 10.0}
    assert response.requested_chunk_size == provider_io.READ_CHUNK_BYTES
    assert response.closed


def test_request_json_limited_rejects_declared_oversize_before_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeStreamingResponse(
        [b'{"ok": true}'],
        headers={"content-length": "100"},
    )
    monkeypatch.setattr(provider_io.httpx, "stream", lambda *args, **kwargs: response)

    with pytest.raises(ProviderResponseTooLarge):
        request_json_limited("GET", "https://provider.example/data", max_bytes=10)

    assert response.iteration_count == 0
    assert response.closed


def test_request_json_limited_stops_when_chunked_body_exceeds_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeStreamingResponse(
        [b'{"x":', b'"this chunk exceeds the remaining budget"}', b'{"must_not": "be read"}']
    )
    monkeypatch.setattr(provider_io.httpx, "stream", lambda *args, **kwargs: response)

    with pytest.raises(ProviderResponseTooLarge):
        request_json_limited("GET", "https://provider.example/data", max_bytes=14)

    assert response.iteration_count == 2
    assert response.closed


def test_request_json_limited_rejects_non_positive_budget() -> None:
    with pytest.raises(ValueError, match="max_bytes must be positive"):
        request_json_limited("GET", "https://provider.example/data", max_bytes=0)
