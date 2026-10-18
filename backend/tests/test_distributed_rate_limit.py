from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError
from starlette.requests import Request

from app import rate_limit
from app.auth import AuthenticatedUser
from app.settings import settings


def request_for(ip: str = "198.51.100.10") -> Request:
    return Request({"type": "http", "method": "POST", "path": "/api/research-runs", "headers": [], "query_string": b"", "server": ("testserver", 80), "client": (ip, 12345), "scheme": "http", "http_version": "1.1"})


def user(user_id: str = "00000000-0000-0000-0000-000000000001") -> AuthenticatedUser:
    return AuthenticatedUser(id=user_id)


def test_redis_allows_request(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Mock()
    fake.eval.return_value = [1, 0]
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(rate_limit, "_redis_client", fake)
    rate_limit.enforce_create_run_rate_limit(request_for(), user())
    fake.eval.assert_called_once()
    assert fake.eval.call_args.args[1] == 2


def test_redis_limit_returns_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Mock()
    fake.eval.return_value = [0, 42]
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(rate_limit, "_redis_client", fake)
    with pytest.raises(HTTPException) as exc:
        rate_limit.enforce_create_run_rate_limit(request_for(), user())
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "42"


def test_redis_outage_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Mock()
    fake.eval.side_effect = RedisConnectionError("unavailable")
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(rate_limit, "_redis_client", fake)
    with pytest.raises(HTTPException) as exc:
        rate_limit.enforce_create_run_rate_limit(request_for(), user())
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "RATE_LIMIT_UNAVAILABLE"


def test_production_without_redis_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(HTTPException) as exc:
        rate_limit.enforce_create_run_rate_limit(request_for(), user())
    assert exc.value.status_code == 503
