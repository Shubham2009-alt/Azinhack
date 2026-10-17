from collections import deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

# This in-memory limiter protects a single API process. Use a shared limiter at
# the edge (or a Redis-backed implementation) when deploying multiple workers.
CREATE_RUN_LIMIT = 5
CREATE_RUN_WINDOW_SECONDS = 600

_requests: dict[str, deque[float]] = {}
_lock = Lock()


def enforce_create_run_rate_limit(request: Request) -> None:
    """Limit expensive research-run creation requests by the direct client IP."""
    client_ip = request.client.host if request.client else "unknown"
    now = monotonic()
    cutoff = now - CREATE_RUN_WINDOW_SECONDS

    with _lock:
        timestamps = _requests.setdefault(client_ip, deque())
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

        if len(timestamps) >= CREATE_RUN_LIMIT:
            retry_after = max(1, int(timestamps[0] + CREATE_RUN_WINDOW_SECONDS - now))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many research requests. Wait before starting another run.",
                },
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)


def clear_rate_limit_state() -> None:
    """Clear limiter state; intended for isolated tests."""
    with _lock:
        _requests.clear()
