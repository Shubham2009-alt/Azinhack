from collections import deque

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import rate_limit
from app.auth import AuthenticatedUser


def _request(client_ip: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/research-runs",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": (client_ip, 12345),
            "scheme": "http",
            "http_version": "1.1",
        }
    )


def test_rate_limiter_prunes_expired_entries_for_inactive_ips(monkeypatch) -> None:
    rate_limit.clear_rate_limit_state()
    rate_limit._requests["stale-client"] = deque([0.0, 1.0])
    monkeypatch.setattr(rate_limit, "monotonic", lambda: 1000.0)

    rate_limit.enforce_create_run_rate_limit(
        _request("new-client"), AuthenticatedUser(id="user-new")
    )

    assert "stale-client" not in rate_limit._requests
    assert list(rate_limit._requests["new-client"]) == [1000.0]
    assert list(rate_limit._requests["user:user-new"]) == [1000.0]
    rate_limit.clear_rate_limit_state()


def test_rate_limiter_keeps_active_entries(monkeypatch) -> None:
    rate_limit.clear_rate_limit_state()
    rate_limit._requests["active-client"] = deque([950.0])
    monkeypatch.setattr(rate_limit, "monotonic", lambda: 1000.0)

    rate_limit.enforce_create_run_rate_limit(
        _request("new-client"), AuthenticatedUser(id="user-new")
    )

    assert list(rate_limit._requests["active-client"]) == [950.0]
    rate_limit.clear_rate_limit_state()


def test_local_limit_is_shared_across_ips_for_same_user(monkeypatch) -> None:
    rate_limit.clear_rate_limit_state()
    monkeypatch.setattr(rate_limit, "monotonic", lambda: 1000.0)
    account = AuthenticatedUser(id="same-user")

    for index in range(rate_limit.CREATE_RUN_LIMIT):
        rate_limit.enforce_create_run_rate_limit(
            _request(f"198.51.100.{index + 1}"), account
        )

    with pytest.raises(HTTPException) as exc:
        rate_limit.enforce_create_run_rate_limit(_request("203.0.113.8"), account)
    assert exc.value.status_code == 429
    rate_limit.clear_rate_limit_state()
