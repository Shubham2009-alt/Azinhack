import json
from pathlib import Path
from collections.abc import Callable
from typing import Any

import httpx
import pytest


class _StreamingResponseAdapter:
    """Expose existing mocked HTTP responses through the HTTPX streaming API."""

    def __init__(self, response: Any) -> None:
        self._response = response

    @property
    def headers(self) -> Any:
        return getattr(self._response, "headers", {})

    @property
    def status_code(self) -> int:
        return int(getattr(self._response, "status_code", 200))

    def raise_for_status(self) -> None:
        self._response.raise_for_status()

    def iter_bytes(self, chunk_size: int = 65_536):
        body = getattr(self._response, "content", None)
        if body is None:
            body = json.dumps(self._response.json(), ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        if not isinstance(body, bytes):
            raise TypeError("Mock response body must be bytes or JSON-serializable.")
        for offset in range(0, len(body), chunk_size):
            yield body[offset : offset + chunk_size]


class _StreamingResponseContext:
    def __init__(self, response_factory: Callable[[], Any]) -> None:
        self._response_factory = response_factory
        self._response: Any = None

    def __enter__(self) -> _StreamingResponseAdapter:
        self._response = self._response_factory()
        return _StreamingResponseAdapter(self._response)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        close = getattr(self._response, "close", None)
        if callable(close):
            close()
        return False


@pytest.fixture(autouse=True)
def adapt_existing_provider_mocks_to_streaming(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep legacy provider unit-test doubles while production uses HTTPX streaming."""
    module_path = getattr(request.module, "__file__", "")
    if Path(module_path).name not in {
        "test_tinyfish_fetch.py",
        "test_tinyfish_search.py",
        "test_llm_analysis.py",
        "test_comparison_gap_analysis.py",
        "test_auth.py",
    }:
        return

    def stream(method: str, url: str, **kwargs: Any) -> _StreamingResponseContext:
        request_function = getattr(httpx, method.lower())
        return _StreamingResponseContext(lambda: request_function(url, **kwargs))

    monkeypatch.setattr(httpx, "stream", stream)
