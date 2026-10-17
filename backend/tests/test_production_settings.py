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


def test_production_rejects_non_https_llm_base_url() -> None:
    settings = production_settings(llm_base_url="http://api.example/v1")

    with pytest.raises(ValueError, match="LLM_BASE_URL must be an absolute HTTPS URL"):
        settings.validate_deployment_configuration()
