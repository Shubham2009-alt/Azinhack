from collections import deque
from threading import Lock
from time import monotonic, time
from uuid import uuid4

import redis
from fastapi import Depends, HTTPException, Request, status
from redis.exceptions import RedisError

from app.auth import AuthenticatedUser, get_current_user
from app.settings import settings

CREATE_RUN_LIMIT = 5
CREATE_RUN_WINDOW_SECONDS = 600
_SCRIPT = """
local now = tonumber(ARGV[1])
local cutoff = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local window = tonumber(ARGV[4])
for i, key in ipairs(KEYS) do
  redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
  local count = redis.call('ZCARD', key)
  if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    return {0, math.max(1, math.ceil(tonumber(oldest[2]) + window - now))}
  end
end
for i, key in ipairs(KEYS) do
  redis.call('ZADD', key, now, ARGV[5])
  redis.call('EXPIRE', key, window)
end
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


def _enforce_local_limit(client_ip: str, user_id: str) -> None:
    now = monotonic()
    cutoff = now - CREATE_RUN_WINDOW_SECONDS
    keys = (client_ip, f"user:{user_id}")
    with _lock:
        for key, timestamps in list(_requests.items()):
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if not timestamps:
                del _requests[key]
        retry_after = 0
        for key in keys:
            timestamps = _requests.get(key)
            if timestamps and len(timestamps) >= CREATE_RUN_LIMIT:
                retry_after = max(retry_after, int(timestamps[0] + CREATE_RUN_WINDOW_SECONDS - now))
        if retry_after:
            _reject(retry_after)
        for key in keys:
            _requests.setdefault(key, deque()).append(now)


def enforce_create_run_rate_limit(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    """Enforce shared per-IP and per-account limits; local fallback is development-only."""
    client_ip = request.client.host if request.client else "unknown"
    user_id = current_user.id
    if not settings.redis_url:
        if settings.app_env.strip().lower() in {"production", "prod"}:
            raise HTTPException(status_code=503, detail={"code": "RATE_LIMIT_UNAVAILABLE", "message": "Request protection is temporarily unavailable."})
        _enforce_local_limit(client_ip, user_id)
        return
    now = time()
    # The hash tag keeps both keys in the same Redis Cluster slot.
    keys = [
        f"researchpilot:rate-limit:{{create-run}}:ip:{client_ip}",
        f"researchpilot:rate-limit:{{create-run}}:user:{user_id}",
    ]
    try:
        result = _get_redis_client().eval(
            _SCRIPT,
            len(keys),
            *keys,
            now,
            now - CREATE_RUN_WINDOW_SECONDS,
            CREATE_RUN_LIMIT,
            CREATE_RUN_WINDOW_SECONDS,
            f"{now}:{uuid4().hex}",
        )
    except RedisError as exc:
        raise HTTPException(status_code=503, detail={"code": "RATE_LIMIT_UNAVAILABLE", "message": "Request protection is temporarily unavailable."}) from exc
    if not result or int(result[0]) != 1:
        _reject(int(result[1]) if result and len(result) > 1 else CREATE_RUN_WINDOW_SECONDS)


def check_rate_limit_store() -> bool:
    """Return whether the configured Redis rate-limit store is reachable."""
    try:
        return bool(_get_redis_client().ping())
    except (RedisError, ValueError):
        return False


def clear_rate_limit_state() -> None:
    """Clear local limiter state and cached Redis client for isolated tests."""
    global _redis_client
    with _lock:
        _requests.clear()
    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None
