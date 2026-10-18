from collections import deque
from threading import Lock
from time import monotonic, time
from uuid import uuid4

import redis
from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

from app.settings import settings

CREATE_RUN_LIMIT = 5
CREATE_RUN_WINDOW_SECONDS = 600
_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local cutoff = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local window = tonumber(ARGV[4])
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  return {0, math.max(1, math.ceil(tonumber(oldest[2]) + window - now))}
end
redis.call('ZADD', key, now, ARGV[5])
redis.call('EXPIRE', key, window)
return {1, 0}
"""
_redis_client: redis.Redis | None = None
_requests: dict[str, deque[float]] = {}
_lock = Lock()


def _get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        if not settings.redis_url:
            raise RedisError("REDIS_URL is not configured")
        _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2, health_check_interval=30)
    return _redis_client


def _reject(retry_after: int) -> None:
    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail={"code": "RATE_LIMIT_EXCEEDED", "message": "Too many research requests. Wait before starting another run."}, headers={"Retry-After": str(max(1, retry_after))})


def _enforce_local_limit(client_ip: str) -> None:
    now = monotonic()
    cutoff = now - CREATE_RUN_WINDOW_SECONDS
    with _lock:
        for ip, timestamps in list(_requests.items()):
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if not timestamps:
                del _requests[ip]
        timestamps = _requests.setdefault(client_ip, deque())
        if len(timestamps) >= CREATE_RUN_LIMIT:
            _reject(int(timestamps[0] + CREATE_RUN_WINDOW_SECONDS - now))
        timestamps.append(now)


def enforce_create_run_rate_limit(request: Request) -> None:
    """Use shared Redis limits in production; local fallback is development-only."""
    client_ip = request.client.host if request.client else "unknown"
    if not settings.redis_url:
        if settings.app_env.strip().lower() in {"production", "prod"}:
            raise HTTPException(status_code=503, detail={"code": "RATE_LIMIT_UNAVAILABLE", "message": "Request protection is temporarily unavailable."})
        _enforce_local_limit(client_ip)
        return
    now = time()
    try:
        result = _get_redis_client().eval(_SCRIPT, 1, f"researchpilot:rate-limit:create-run:{client_ip}", now, now - CREATE_RUN_WINDOW_SECONDS, CREATE_RUN_LIMIT, CREATE_RUN_WINDOW_SECONDS, f"{now}:{uuid4().hex}")
    except RedisError as exc:
        raise HTTPException(status_code=503, detail={"code": "RATE_LIMIT_UNAVAILABLE", "message": "Request protection is temporarily unavailable."}) from exc
    if not result or int(result[0]) != 1:
        _reject(int(result[1]) if result and len(result) > 1 else CREATE_RUN_WINDOW_SECONDS)


def clear_rate_limit_state() -> None:
    """Clear local limiter state and cached Redis client for isolated tests."""
    global _redis_client
    with _lock:
        _requests.clear()
    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None
