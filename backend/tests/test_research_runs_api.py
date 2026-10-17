from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
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
