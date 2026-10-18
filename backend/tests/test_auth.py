from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException

from app import auth


def test_missing_bearer_token_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        auth.get_current_user(None)
    assert error.value.status_code == 401
    assert error.value.detail["code"] == "AUTHENTICATION_REQUIRED"
    assert error.value.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer a b", "bearer "])
def test_malformed_bearer_token_is_rejected(header: str) -> None:
    with pytest.raises(HTTPException) as error:
        auth.get_current_user(header)
    assert error.value.status_code == 401
    assert error.value.detail["code"] == "INVALID_ACCESS_TOKEN"


def test_valid_token_is_verified_by_supabase_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = "a9d9f7bb-57a8-4cc9-8a7e-2b0f9a4c61b8"
    monkeypatch.setattr(auth.settings, "supabase_url", "https://project-ref.supabase.co/")
    monkeypatch.setattr(auth.settings, "supabase_publishable_key", "sb_publishable_test")
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append((url, headers, timeout))
        return SimpleNamespace(status_code=200, json=lambda: {"id": user_id, "email": "person@example.test"})

    monkeypatch.setattr(auth.httpx, "get", fake_get)
    user = auth.get_current_user("Bearer test-token")
    assert user.id == str(UUID(user_id))
    assert calls == [(
        "https://project-ref.supabase.co/auth/v1/user",
        {"apikey": "sb_publishable_test", "Authorization": "Bearer test-token"},
        5.0,
    )]


def test_invalid_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.settings, "supabase_url", "https://project-ref.supabase.co")
    monkeypatch.setattr(auth.settings, "supabase_publishable_key", "sb_publishable_test")
    monkeypatch.setattr(auth.httpx, "get", lambda *_args, **_kwargs: SimpleNamespace(status_code=401, json=lambda: {}))
    with pytest.raises(HTTPException) as error:
        auth.get_current_user("Bearer invalid-token")
    assert error.value.status_code == 401
    assert error.value.detail["code"] == "INVALID_ACCESS_TOKEN"


def test_auth_provider_outage_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.settings, "supabase_url", "https://project-ref.supabase.co")
    monkeypatch.setattr(auth.settings, "supabase_publishable_key", "sb_publishable_test")

    def fail(*_args, **_kwargs):
        raise httpx.ConnectError("provider offline")

    monkeypatch.setattr(auth.httpx, "get", fail)
    with pytest.raises(HTTPException) as error:
        auth.get_current_user("Bearer token")
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "AUTH_PROVIDER_UNAVAILABLE"


def test_missing_auth_provider_configuration_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.settings, "supabase_url", "")
    monkeypatch.setattr(auth.settings, "supabase_publishable_key", "sb_publishable_test")
    with pytest.raises(HTTPException) as error:
        auth.get_current_user("Bearer token")
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "AUTH_PROVIDER_NOT_CONFIGURED"


def test_invalid_identity_response_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.settings, "supabase_url", "https://project-ref.supabase.co")
    monkeypatch.setattr(auth.settings, "supabase_publishable_key", "sb_publishable_test")
    monkeypatch.setattr(auth.httpx, "get", lambda *_args, **_kwargs: SimpleNamespace(status_code=200, json=lambda: {"id": "not-a-uuid"}))
    with pytest.raises(HTTPException) as error:
        auth.get_current_user("Bearer token")
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "AUTH_PROVIDER_INVALID_RESPONSE"
