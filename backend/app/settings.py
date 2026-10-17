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
