from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base, Claim, ClaimRelation, Report, ResearchRun, Source


@pytest.fixture()
def client_and_session(monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("app.main.run_research_discovery", lambda _run_id: None)
    with TestClient(app) as test_client:
        yield test_client, session
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def seed_run(session: Session) -> tuple[ResearchRun, Source, Source, Claim, Claim]:
    run = ResearchRun(
        question="How well do low-cost sensors detect urban air pollution?",
        status="partial",
        stage="cross_source_analysis_complete",
        progress=92,
        warning_summary="Candidate gaps are tentative.",
    )
    session.add(run)
    session.flush()
    source_a = Source(
        run_id=run.id,
        canonical_url="https://example.org/a",
        title="Sensor evaluation A",
        retrieval_status="retrieved",
        content_text="Accuracy was 84%.",
        excerpt="Accuracy was 84%.",
    )
    source_b = Source(
        run_id=run.id,
        canonical_url="https://example.org/b",
        title="Sensor evaluation B",
        retrieval_status="retrieved",
        content_text="Accuracy was 76%.",
        excerpt="Accuracy was 76%.",
    )
    session.add_all([source_a, source_b])
    session.flush()
    claim_a = Claim(
        run_id=run.id,
        source_id=source_a.id,
        claim_text="The first sensor reached 84% accuracy.",
        claim_type="finding",
        evidence_excerpt="Accuracy was 84%.",
        confidence_label="moderate",
    )
    claim_b = Claim(
        run_id=run.id,
        source_id=source_b.id,
        claim_text="The second sensor reached 76% accuracy.",
        claim_type="finding",
        evidence_excerpt="Accuracy was 76%.",
        confidence_label="low",
    )
    session.add_all([claim_a, claim_b])
    session.flush()
    session.add(
        ClaimRelation(
            from_claim_id=claim_a.id,
            to_claim_id=claim_b.id,
            relationship="qualifies",
            rationale="Different sensor evaluation conditions may explain the different outcomes.",
            confidence_label="low",
        )
    )
    session.add(
        Report(
            run_id=run.id,
            structured_sections={
                "candidate_research_gaps": [
                    {
                        "title": "Comparable field evaluations",
                        "description": "Compare sensor performance under consistent field conditions.",
                        "evidence_level": "low",
                        "basis_claim_ids": [claim_a.id, claim_b.id],
                        "is_confirmed_novelty": False,
                    }
                ]
            },
            validation_warnings=["Partial source coverage."],
        )
    )
    session.commit()
    return run, source_a, source_b, claim_a, claim_b


def test_report_returns_partial_evidence_and_warnings(client_and_session) -> None:
    client, db = client_and_session
    run, _, _, _, _ = seed_run(db)
    response = client.get(f"/api/research-runs/{run.id}/report")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert len(body["claims"]) == 2
    assert len(body["sources"]) == 2
    assert body["claims"][0]["evidence_excerpt"]
    assert body["validation_warnings"] == ["Partial source coverage."]
    assert body["structured_sections"]["candidate_research_gaps"][0]["is_confirmed_novelty"] is False


def test_sources_endpoint_does_not_expose_full_source_text(client_and_session) -> None:
    client, db = client_and_session
    run, _, _, _, _ = seed_run(db)
    response = client.get(f"/api/research-runs/{run.id}/sources")
    assert response.status_code == 200
    body = response.json()
    assert len(body["sources"]) == 2
    assert body["sources"][0]["claims"]
    assert "content_text" not in body["sources"][0]


def test_graph_returns_source_claim_and_relation_edges(client_and_session) -> None:
    client, db = client_and_session
    run, _, _, claim_a, claim_b = seed_run(db)
    response = client.get(f"/api/research-runs/{run.id}/graph")
    assert response.status_code == 200
    body = response.json()
    assert len(body["nodes"]) == 4
    edge_types = [edge["type"] for edge in body["edges"]]
    assert edge_types.count("supports") == 2
    assert "qualifies" in edge_types
    source_ids = {node["id"] for node in body["nodes"] if node["type"] == "source"}
    claim_ids = {node["id"] for node in body["nodes"] if node["type"] == "claim"}
    support_edges = [edge for edge in body["edges"] if edge["type"] == "supports"]
    assert all(edge["source"] in source_ids and edge["target"] in claim_ids for edge in support_edges)
    assert any(edge["source"] == claim_a.id and edge["target"] == claim_b.id for edge in body["edges"])


@pytest.mark.parametrize("endpoint", ["report", "sources", "graph"])
def test_unknown_run_returns_404(client_and_session, endpoint: str) -> None:
    client, _ = client_and_session
    response = client.get(
        f"/api/research-runs/00000000-0000-0000-0000-000000000000/{endpoint}"
    )
    assert response.status_code == 404
