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
    assert response_headers[b"cache-control"] == b"no-store"


def test_api_responses_override_weaker_cache_control_header() -> None:
    sent = []

    async def app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
                (b"cache-control", b"public, max-age=3600"),
            ],
        })
        await send({"type": "http.response.body", "body": b"{}", "more_body": False})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/research-runs/test",
        "headers": [],
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 12345),
        "http_version": "1.1",
    }

    asyncio.run(RequestSecurityMiddleware(app)(scope, receive, send))

    response_start_headers = sent[0]["headers"]
    cache_headers = [value for key, value in response_start_headers if key.lower() == b"cache-control"]
    assert cache_headers == [b"no-store"]
