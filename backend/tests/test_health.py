from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_health_endpoint_returns_safe_status() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "researchpilot-api",
    }


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, _statement):
        return 1


class HealthyEngine:
    def connect(self):
        return FakeConnection()


class UnavailableEngine:
    def connect(self):
        raise RuntimeError("database unavailable")


def test_readiness_endpoint_returns_ready_when_database_query_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(main, "engine", HealthyEngine())

    response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "researchpilot-api",
    }


def test_readiness_endpoint_returns_503_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(main, "engine", UnavailableEngine())

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "researchpilot-api",
    }


def test_production_readiness_returns_503_when_redis_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(main, "engine", HealthyEngine())
    monkeypatch.setattr(main.settings, "app_env", "production")
    monkeypatch.setattr(main, "check_rate_limit_store", lambda: False)

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "researchpilot-api",
    }


def test_production_readiness_returns_ready_when_redis_is_available(monkeypatch) -> None:
    monkeypatch.setattr(main, "engine", HealthyEngine())
    monkeypatch.setattr(main.settings, "app_env", "production")
    monkeypatch.setattr(main, "check_rate_limit_store", lambda: True)

    response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "researchpilot-api",
    }
