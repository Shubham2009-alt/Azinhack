import asyncio
import json

from app.security import RequestSecurityMiddleware


def test_oversized_single_chunk_is_rejected_before_app_runs() -> None:
    app_called = False
    sent = []

    async def app(scope, receive, send):
        nonlocal app_called
        app_called = True

    async def receive():
        return {"type": "http.request", "body": b"x" * 11, "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 12345),
        "http_version": "1.1",
    }

    asyncio.run(RequestSecurityMiddleware(app, max_body_bytes=10)(scope, receive, send))

    assert app_called is False
    assert sent[0]["status"] == 413
    response_body = json.loads(sent[1]["body"])
    assert response_body["error"]["code"] == "REQUEST_TOO_LARGE"
    response_headers = dict(sent[0]["headers"])
    assert response_headers[b"x-content-type-options"] == b"nosniff"
