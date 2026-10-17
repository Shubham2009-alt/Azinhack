import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestSecurityMiddleware:
    """Bound request-body memory use and add baseline browser security headers."""

    def __init__(self, app: ASGIApp, max_body_bytes: int = 1_048_576) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {key.lower() for key, _ in headers}
                security_headers = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cross-origin-resource-policy", b"same-site"),
                    (b"x-frame-options", b"DENY"),
                ]
                headers.extend((key, value) for key, value in security_headers if key not in existing)
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
            body.extend(message.get("body", b""))
            if len(body) > self.max_body_bytes:
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
            more_body = message.get("more_body", False)

        replayed = False

        async def receive_buffered() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, receive_buffered, send_with_security_headers)
