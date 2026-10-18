from __future__ import annotations

import pytest

from app.settings import Settings


def production_settings(**overrides: str) -> Settings:
    values: dict[str, str] = {
        "app_env": "production",
        "frontend_origin": "https://researchpilot.example",
        "tinyfish_api_key": "tinyfish-test-key",
        "llm_api_key": "llm-test-key",
        "llm_base_url": "https://api.example/v1",
        "llm_model": "test-model",
        "supabase_url": "https://project-ref.supabase.co",
        "supabase_publishable_key": "sb_publishable_test-key",
        "redis_url": "rediss://redis.example:6379/0",
    }
    values.update(overrides)
    return Settings(**values)


def test_development_configuration_does_not_require_provider_keys() -> None:
    Settings(app_env="development").validate_deployment_configuration()


def test_production_configuration_accepts_explicit_https_origins_and_provider_settings() -> None:
    production_settings().validate_deployment_configuration()


def test_production_requires_provider_configuration() -> None:
    settings = production_settings(llm_api_key="", tinyfish_api_key="")

    with pytest.raises(ValueError, match="TINYFISH_API_KEY, LLM_API_KEY"):
        settings.validate_deployment_configuration()


def test_production_rejects_http_frontend_origin() -> None:
    settings = production_settings(frontend_origin="http://researchpilot.example")

    with pytest.raises(ValueError, match="must use HTTPS"):
        settings.validate_deployment_configuration()


@pytest.mark.parametrize(
    "origin",
    ["https://localhost", "https://127.0.0.1", "https://demo.localhost"],
)
def test_production_rejects_local_frontend_origins(origin: str) -> None:
    settings = production_settings(frontend_origin=origin)

    with pytest.raises(ValueError, match="must not point to localhost"):
        settings.validate_deployment_configuration()


@pytest.mark.parametrize(
    "origin",
    [
        "https://researchpilot.example?debug=true",
        "https://researchpilot.example#section",
    ],
)
def test_frontend_origin_rejects_query_strings_and_fragments(origin: str) -> None:
    settings = Settings(frontend_origin=origin)

    with pytest.raises(ValueError, match="must not include a query string or fragment"):
        _ = settings.frontend_origins


def test_production_rejects_non_https_llm_base_url() -> None:
    settings = production_settings(llm_base_url="http://api.example/v1")

    with pytest.raises(ValueError, match="LLM_BASE_URL must be an absolute HTTPS URL"):
        settings.validate_deployment_configuration()


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user:password@api.example/v1",
        "https://token@api.example/v1",
    ],
)
def test_production_rejects_embedded_llm_base_url_credentials(base_url: str) -> None:
    settings = production_settings(llm_base_url=base_url)

    with pytest.raises(ValueError, match="LLM_BASE_URL must not include embedded credentials"):
        settings.validate_deployment_configuration()


@pytest.mark.parametrize(
    "base_url",
    [
        "https://api.example/v1?token=accidental",
        "https://api.example/v1#section",
    ],
)
def test_production_rejects_query_strings_and_fragments_in_llm_base_url(
    base_url: str,
) -> None:
    settings = production_settings(llm_base_url=base_url)

    with pytest.raises(
        ValueError,
        match="LLM_BASE_URL must not include a query string or fragment",
    ):
        settings.validate_deployment_configuration()


@pytest.mark.parametrize(
    "base_url",
    [
        "https://api.example:99999/v1",
        "https://api.example:abc/v1",
    ],
)
def test_production_rejects_invalid_llm_base_url_ports(base_url: str) -> None:
    settings = production_settings(llm_base_url=base_url)

    with pytest.raises(ValueError, match="LLM_BASE_URL must include a valid port"):
        settings.validate_deployment_configuration()



@pytest.mark.parametrize(
    "supabase_url",
    [
        "http://project-ref.supabase.co",
        "https://user:password@project-ref.supabase.co",
        "https://project-ref.supabase.co/auth/v1",
        "https://project-ref.supabase.co?debug=true",
    ],
)
def test_production_rejects_unsafe_supabase_urls(supabase_url: str) -> None:
    settings = production_settings(supabase_url=supabase_url)

    with pytest.raises(ValueError, match="SUPABASE_URL"):
        settings.validate_deployment_configuration()


def test_production_requires_supabase_auth_configuration() -> None:
    settings = production_settings(supabase_url="", supabase_publishable_key="")

    with pytest.raises(ValueError, match="SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY"):
        settings.validate_deployment_configuration()


def test_production_requires_shared_rate_limit_store() -> None:
    settings = production_settings(redis_url="")
    with pytest.raises(ValueError, match="REDIS_URL"):
        settings.validate_deployment_configuration()
