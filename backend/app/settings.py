from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    tinyfish_api_key: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    database_url: str = "sqlite:///./researchpilot.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def validate_deployment_configuration(self) -> None:
        """Fail closed on unsafe or incomplete settings for production deployments."""
        if self.app_env.strip().lower() not in {"production", "prod"}:
            return

        required = {
            "TINYFISH_API_KEY": self.tinyfish_api_key,
            "LLM_API_KEY": self.llm_api_key,
            "LLM_BASE_URL": self.llm_base_url,
            "LLM_MODEL": self.llm_model,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(
                "Production configuration is incomplete; set: " + ", ".join(missing)
            )

        origins = self.frontend_origins
        if not origins:
            raise ValueError("Production requires at least one explicit FRONTEND_ORIGIN.")

        for origin in origins:
            parsed = urlsplit(origin)
            hostname = (parsed.hostname or "").lower()
            if parsed.scheme != "https":
                raise ValueError("Production FRONTEND_ORIGIN values must use HTTPS.")
            if hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(".localhost"):
                raise ValueError("Production FRONTEND_ORIGIN must not point to localhost.")

        provider_url = urlsplit(self.llm_base_url.strip())
        if provider_url.scheme != "https" or not provider_url.hostname:
            raise ValueError("Production LLM_BASE_URL must be an absolute HTTPS URL.")
        if provider_url.username or provider_url.password:
            raise ValueError("Production LLM_BASE_URL must not include embedded credentials.")
        if provider_url.query or provider_url.fragment:
            raise ValueError(
                "Production LLM_BASE_URL must not include a query string or fragment."
            )
        try:
            port = provider_url.port
        except ValueError as exc:
            raise ValueError(
                "Production LLM_BASE_URL must include a valid port if specified."
            ) from exc
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("Production LLM_BASE_URL must include a valid port if specified.")

    @property
    def frontend_origins(self) -> list[str]:
        raw_values = [part.strip() for part in self.frontend_origin.split(",") if part.strip()]
        if not raw_values:
            return []

        origins: list[str] = []
        for raw_value in raw_values:
            parsed = urlsplit(raw_value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("FRONTEND_ORIGIN must be a valid http(s) origin, not a URL path or wildcard.")
            if parsed.username or parsed.password or parsed.path not in {"", "/"}:
                raise ValueError("FRONTEND_ORIGIN must not include credentials or URL paths.")
            if parsed.query or parsed.fragment:
                raise ValueError("FRONTEND_ORIGIN must not include a query string or fragment.")
            hostname = parsed.hostname.lower() if parsed.hostname else ""
            port = parsed.port
            origin = f"{parsed.scheme.lower()}://{hostname}"
            if port is not None and not (
                (parsed.scheme.lower() == "http" and port == 80)
                or (parsed.scheme.lower() == "https" and port == 443)
            ):
                origin = f"{origin}:{port}"
            origins.append(origin)
        return origins


settings = Settings()
