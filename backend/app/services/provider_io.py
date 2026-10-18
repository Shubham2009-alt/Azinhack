import json
from typing import Any

import httpx

READ_CHUNK_BYTES = 64 * 1024


class ProviderResponseTooLarge(ValueError):
    """Raised when a provider response exceeds its configured byte budget."""


def request_json_limited(
    method: str,
    url: str,
    *,
    max_bytes: int,
    **request_kwargs: Any,
) -> Any:
    """Read provider JSON with a bounded streaming body accumulator.

    HTTPX streaming avoids buffering the whole response in Response.content.
    The byte budget is enforced on decoded chunks (including decompressed
    bodies) before each chunk is appended. HTTPX transport/decoder buffers and
    one yielded chunk are additional bounded overhead.
    """
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")

    with httpx.stream(method, url, **request_kwargs) as response:
        response.raise_for_status()
        headers = getattr(response, "headers", None)
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

        return json.loads(bytes(body))
