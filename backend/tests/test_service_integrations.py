from __future__ import annotations

import os
from uuid import uuid4

import pytest
import redis
from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app import database, rate_limit
from app.auth import AuthenticatedUser
from app.models import ResearchRun, Source
from app.settings import settings

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "").strip()
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "").strip()


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not configured")
def test_postgres_alembic_migrations_and_research_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run the production migration path against a disposable real PostgreSQL service."""
    engine = database.build_engine(TEST_DATABASE_URL)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(settings, "database_url", TEST_DATABASE_URL)

    try:
        database.init_db()
        database.init_db()  # Applying the current revision twice must be idempotent.

        tables = set(inspect(engine).get_table_names())
        assert {
            "alembic_version",
            "research_runs",
            "sources",
            "claims",
            "reports",
            "evidence_links",
            "claim_relations",
        }.issubset(tables)

        run_id = str(uuid4())
        with Session(engine) as session:
            run = ResearchRun(
                id=run_id,
                owner_id=str(uuid4()),
                question="Can the production database persist evidence-linked research?",
                status="queued",
                stage="queued",
                progress=0,
            )
            run.sources.append(
                Source(
                    canonical_url="https://example.org/postgres-integration-test",
                    title="Disposable PostgreSQL integration test source",
                    content_text="Temporary test evidence.",
                    excerpt="Temporary test evidence.",
                )
            )
            session.add(run)
            session.commit()

        with Session(engine) as session:
            stored = session.scalar(select(ResearchRun).where(ResearchRun.id == run_id))
            assert stored is not None
            assert stored.sources[0].canonical_url == "https://example.org/postgres-integration-test"
            session.delete(stored)
            session.commit()

        with Session(engine) as session:
            assert session.get(ResearchRun, run_id) is None
    finally:
        engine.dispose()


@pytest.mark.skipif(not TEST_REDIS_URL, reason="TEST_REDIS_URL not configured")
def test_real_redis_enforces_atomic_rate_limit_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the actual Lua-based shared rate limiter against a disposable Redis service."""
    client = redis.Redis.from_url(
        TEST_REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    client.flushdb()
    monkeypatch.setattr(settings, "redis_url", TEST_REDIS_URL)
    rate_limit.clear_rate_limit_state()
    account_id = f"redis-integration-{uuid4()}"

    def request_for(ip: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/research-runs",
                "headers": [],
                "query_string": b"",
                "server": ("testserver", 80),
                "client": (ip, 12345),
                "scheme": "http",
                "http_version": "1.1",
            }
        )

    try:
        assert rate_limit.check_rate_limit_store()
        user = AuthenticatedUser(id=account_id)
        for index in range(rate_limit.CREATE_RUN_LIMIT):
            rate_limit.enforce_create_run_rate_limit(
                request_for(f"198.51.100.{index + 1}"), user
            )

        with pytest.raises(HTTPException) as exc:
            rate_limit.enforce_create_run_rate_limit(request_for("203.0.113.250"), user)

        assert exc.value.status_code == 429
        assert exc.value.headers["Retry-After"].isdigit()
    finally:
        rate_limit.clear_rate_limit_state()
        client.flushdb()
        client.close()
