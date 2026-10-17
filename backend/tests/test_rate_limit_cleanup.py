from collections import deque

from starlette.requests import Request

from app import rate_limit


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


def test_rate_limiter_prunes_expired_entries_for_inactive_ips(
    monkeypatch,
) -> None:
    rate_limit.clear_rate_limit_state()
    rate_limit._requests["stale-client"] = deque([0.0, 1.0])
    monkeypatch.setattr(rate_limit, "monotonic", lambda: 1000.0)

    rate_limit.enforce_create_run_rate_limit(_request("new-client"))

    assert "stale-client" not in rate_limit._requests
    assert list(rate_limit._requests["new-client"]) == [1000.0]
    rate_limit.clear_rate_limit_state()


def test_rate_limiter_keeps_active_entries(monkeypatch) -> None:
    rate_limit.clear_rate_limit_state()
    rate_limit._requests["active-client"] = deque([950.0])
    monkeypatch.setattr(rate_limit, "monotonic", lambda: 1000.0)

    rate_limit.enforce_create_run_rate_limit(_request("new-client"))

    assert list(rate_limit._requests["active-client"]) == [950.0]
    rate_limit.clear_rate_limit_state()
