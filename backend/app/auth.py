from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import httpx
from fastapi import Header, HTTPException, status

from app.settings import settings


@dataclass(frozen=True)
class AuthenticatedUser:
    """A Supabase-authenticated user identity trusted by the API."""

    id: str


def _auth_error(status_code: int, code: str, message: str, *, bearer_challenge: bool = False) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer"} if bearer_challenge else None
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
        headers=headers,
    )


def get_current_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    """Validate a bearer token with Supabase Auth, including projects using HS256."""
    if not authorization:
        raise _auth_error(401, "AUTHENTICATION_REQUIRED", "Sign in to access this resource.", bearer_challenge=True)

    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip() or " " in token.strip():
        raise _auth_error(401, "INVALID_ACCESS_TOKEN", "A valid bearer access token is required.", bearer_challenge=True)

    supabase_url = settings.supabase_url.strip().rstrip("/")
    publishable_key = settings.supabase_publishable_key.strip()
    if not supabase_url or not publishable_key:
        raise _auth_error(503, "AUTH_PROVIDER_NOT_CONFIGURED", "Authentication is not configured on this server.")

    try:
        response = httpx.get(
            f"{supabase_url}/auth/v1/user",
            headers={"apikey": publishable_key, "Authorization": f"Bearer {token.strip()}"},
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise _auth_error(503, "AUTH_PROVIDER_UNAVAILABLE", "Authentication provider is temporarily unavailable.") from exc

    if response.status_code == 429 or response.status_code >= 500:
        raise _auth_error(503, "AUTH_PROVIDER_UNAVAILABLE", "Authentication provider is temporarily unavailable.")
    if response.status_code != 200:
        raise _auth_error(401, "INVALID_ACCESS_TOKEN", "The access token is invalid or expired.", bearer_challenge=True)

    try:
        user_id = str(UUID(str(response.json()["id"])))
    except (ValueError, TypeError, KeyError):
        raise _auth_error(503, "AUTH_PROVIDER_INVALID_RESPONSE", "Authentication provider returned an invalid user identity.") from None

    return AuthenticatedUser(id=user_id)
