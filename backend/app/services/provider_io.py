import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

READ_CHUNK_BYTES = 64 * 1024


class ProviderResponseTooLarge(ValueError):
    """Raised when a provider response exceeds its configured byte budget."""


@dataclass(frozen=True)
class LimitedResponse:
    """A response whose decoded body was consumed within a fixed byte budget."""

    status_code: int
    headers: Mapping[str, str]
    content: bytes

    def json(self) -> Any:
        """Parse the already bounded body as JSON."""
        return json.loads(self.content)


def request_bytes_limited(
    method: str,
    url: str,
    *,
    max_bytes: int,
    check_status: bool = True,
    **request_kwargs: Any,
) -> LimitedResponse:
    """Read a response through HTTPX streaming with a bounded body accumulator.

    The byte budget is enforced on decoded chunks (including decompressed
    bodies) before each chunk is appended. HTTPX transport/decoder buffers and
    one yielded chunk are additional bounded overhead. Set check_status=False
    when the caller must inspect non-success status codes (for example, auth
    rejection) without trusting/parsing the upstream error body.
    """
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")

    with httpx.stream(method, url, **request_kwargs) as response:
        if check_status:
            response.raise_for_status()

        headers = getattr(response, "headers", {})
        raw_length = headers.get("content-length") if headers is not None else None
        try:
            declared_size = int(raw_length)
        except (TypeError, ValueError):
            declared_size = 0
        if declared_size > max_bytes:
            raise ProviderResponseTooLarge("Provider response exceeded the byte limit.")

        body = bytearray()
        for chunk in response.iter_bytes(chunk_size=READ_CHUNK_BYTES):
            if not chunk:
                continue
            if len(chunk) > max_bytes - len(body):
                raise ProviderResponseTooLarge("Provider response exceeded the byte limit.")
            body.extend(chunk)

        return LimitedResponse(
            status_code=int(getattr(response, "status_code", 200)),
            headers=dict(headers or {}),
            content=bytes(body),
        )


def request_json_limited(
    method: str,
    url: str,
    *,
    max_bytes: int,
    **request_kwargs: Any,
) -> Any:
    """Read, bound and parse provider JSON without buffering an unbounded body."""
    return request_bytes_limited(
        method,
        url,
        max_bytes=max_bytes,
        **request_kwargs,
    ).json()
