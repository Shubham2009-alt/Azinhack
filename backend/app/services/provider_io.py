from typing import Any


class ProviderResponseTooLarge(ValueError):
    """Raised when a provider response exceeds its configured byte budget."""


def response_json_limited(response: Any, max_bytes: int) -> Any:
    """Reject oversized provider responses before JSON parsing.

    HTTPX buffers ordinary responses before returning, so this check bounds JSON
    parsing and downstream work; Content-Length also rejects declared oversize
    responses without touching the body. Use streaming reads for a strict
    network-memory ceiling.
    """
    headers = getattr(response, "headers", None)
    if headers is not None:
        try:
            declared_size = int(headers.get("content-length", ""))
        except (TypeError, ValueError):
            declared_size = 0
        if declared_size > max_bytes:
            raise ProviderResponseTooLarge("Provider response exceeded the byte limit.")

    body = getattr(response, "content", None)
    if isinstance(body, (bytes, bytearray)) and len(body) > max_bytes:
        raise ProviderResponseTooLarge("Provider response exceeded the byte limit.")
    if isinstance(body, str) and len(body.encode("utf-8")) > max_bytes:
        raise ProviderResponseTooLarge("Provider response exceeded the byte limit.")
    return response.json()
