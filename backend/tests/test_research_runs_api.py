from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base
from app.rate_limit import clear_rate_limit_state


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("app.main.run_research_discovery", lambda _run_id: None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_create_and_retrieve_research_run(client: TestClient) -> None:
    response = client.post(
        "/api/research-runs",
        json={
            "question": "Can satellite imagery detect river pollution?",
            "year_min": 2018,
            "year_max": 2025,
        },
    )
    assert response.status_code == 202
    created = response.json()
    assert created["status"] == "queued"
    assert created["run_id"]

    status_response = client.get(f"/api/research-runs/{created['run_id']}")
    assert status_response.status_code == 200
    run = status_response.json()
    assert run["question"] == "Can satellite imagery detect river pollution?"
    assert run["status"] == "queued"
    assert run["stage"] == "queued"
    assert run["progress"] == 0
    assert run["source_count"] == 0
    assert run["usable_source_count"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "   "},
        {"question": ""},
        {"question": "x" * 1001},
        {"question": "Valid question", "year_min": 2025, "year_max": 2018},
        {"question": "Valid question", "year_min": 1800},
    ],
)
def test_invalid_research_request_is_rejected(client: TestClient, payload: dict) -> None:
    response = client.post("/api/research-runs", json=payload)
    assert response.status_code == 422


def test_unknown_run_returns_404(client: TestClient) -> None:
    response = client.get("/api/research-runs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "RESEARCH_RUN_NOT_FOUND"
    assert payload["error"]["message"] == "No research run exists for this ID."
    assert "request_id" in payload["error"]


def test_validation_errors_are_structured_and_safe(client: TestClient) -> None:
    response = client.post(
        "/api/research-runs",
        json={"question": "   ", "year_min": 2025, "year_max": 2018},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "The request payload is invalid."
    assert payload["error"]["details"]
    assert "question" in str(payload["error"]["details"]) or "year_min" in str(payload["error"]["details"])


def test_unexpected_errors_are_sanitized(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*_args, **_kwargs):
        raise RuntimeError("super-secret-debug-info")

    monkeypatch.setattr("app.main._get_run_or_404", explode)
    response = client.get("/api/research-runs/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "super-secret-debug-info" not in payload["error"]["message"]
    assert "request_id" in payload["error"]


def test_create_research_run_is_rate_limited(client: TestClient) -> None:
    clear_rate_limit_state()
    payload = {"question": "Can satellite imagery detect river pollution?"}

    for _ in range(5):
        response = client.post("/api/research-runs", json=payload)
        assert response.status_code == 202

    limited = client.post("/api/research-runs", json=payload)
    assert limited.status_code == 429
    assert limited.headers.get("Retry-After", "").isdigit()
    assert limited.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    clear_rate_limit_state()
