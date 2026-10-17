import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestSecurityMiddleware:
    """Bound request-body memory use and add baseline browser security headers."""

    def __init__(self, app: ASGIApp, max_body_bytes: int = 1_048_576) -> None:
        if max_body_bytes < 0:
            raise ValueError("max_body_bytes must be non-negative")
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Enforce our cache policy even if downstream middleware set a weaker
                # Cache-Control header. Keep all unrelated response headers intact.
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"cache-control"
                ]
                headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cross-origin-resource-policy", b"same-site"),
                    (b"x-frame-options", b"DENY"),
                    (b"cache-control", b"no-store"),
                ])
                message["headers"] = headers
            await send(message)

        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue

            chunk = message.get("body", b"")
            # Check before extending: a single oversized ASGI chunk must not be
            # copied into the buffer before the limit is enforced.
            if len(body) + len(chunk) > self.max_body_bytes:
                payload = json.dumps({
                    "error": {
                        "code": "REQUEST_TOO_LARGE",
                        "message": "Request body exceeds the 1 MiB limit.",
                    }
                }).encode("utf-8")
                await send_with_security_headers({
                    "type": "http.response.start",
                    "status": 413,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(payload)).encode("ascii")),
                    ],
                })
                await send_with_security_headers({
                    "type": "http.response.body",
                    "body": payload,
                    "more_body": False,
                })
                return

            body.extend(chunk)
            more_body = message.get("more_body", False)

        replayed = False

        async def receive_buffered() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, receive_buffered, send_with_security_headers)
