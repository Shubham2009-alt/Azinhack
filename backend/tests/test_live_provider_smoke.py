"""Opt-in end-to-end smoke test for a deployed ResearchPilot environment.

Set RUN_LIVE_PROVIDER_TESTS=1, LIVE_API_BASE_URL, and
LIVE_SUPABASE_ACCESS_TOKEN in a private shell/IDE environment. The test creates
one live research run and deletes it after checking the provider-backed result.
"""

from __future__ import annotations

import os
import time
from urllib.parse import urlsplit

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_PROVIDER_TESTS") != "1",
    reason="set RUN_LIVE_PROVIDER_TESTS=1 to run against a real deployment",
)

TERMINAL_STATUSES = {"completed", "succeeded", "partial", "failed", "error"}
SUCCESS_STATUSES = {"completed", "succeeded", "partial"}


def test_live_deployed_provider_stack() -> None:
    """Exercise auth, database/Redis readiness, TinyFish, LLM analysis, and deletion."""
    base_url = os.getenv("LIVE_API_BASE_URL", "").strip().rstrip("/")
    access_token = os.getenv("LIVE_SUPABASE_ACCESS_TOKEN", "").strip()
    if not base_url or not access_token:
        pytest.fail(
            "Set LIVE_API_BASE_URL and LIVE_SUPABASE_ACCESS_TOKEN in the test environment."
        )

    parsed = urlsplit(base_url)
    if not parsed.hostname or parsed.scheme not in {"https", "http"}:
        pytest.fail("LIVE_API_BASE_URL must be an absolute HTTP(S) origin.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Non-local live smoke tests must use HTTPS.")

    try:
        max_wait_seconds = int(os.getenv("LIVE_PROVIDER_SMOKE_TIMEOUT_SECONDS", "300"))
    except ValueError:
        pytest.fail("LIVE_PROVIDER_SMOKE_TIMEOUT_SECONDS must be an integer.")
    if not 30 <= max_wait_seconds <= 900:
        pytest.fail("LIVE_PROVIDER_SMOKE_TIMEOUT_SECONDS must be between 30 and 900.")

    timeout = httpx.Timeout(15.0, connect=5.0)
    run_id: str | None = None
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        try:
            readiness = client.get(f"{base_url}/api/health/ready")
            assert readiness.status_code == 200, (
                "Deployment readiness must verify the database and production Redis store."
            )

            headers = {"Authorization": f"Bearer {access_token}"}
            started = client.post(
                f"{base_url}/api/research-runs",
                headers=headers,
                json={
                    "question": (
                        "What methods for monitoring urban air quality with low-cost sensor "
                        "networks have been evaluated, and what limitations do recent studies report?"
                    ),
                    "year_min": 2021,
                    "year_max": 2026,
                },
            )
            assert started.status_code == 202, (
                f"Live research submission returned HTTP {started.status_code}."
            )
            run_id = started.json().get("run_id")
            assert isinstance(run_id, str) and run_id

            deadline = time.monotonic() + max_wait_seconds
            final_status = ""
            while time.monotonic() < deadline:
                status_response = client.get(
                    f"{base_url}/api/research-runs/{run_id}",
                    headers=headers,
                )
                assert status_response.status_code == 200, (
                    f"Could not read live run status (HTTP {status_response.status_code})."
                )
                state = status_response.json()
                final_status = str(state.get("status", "")).lower()
                if final_status in TERMINAL_STATUSES:
                    break
                time.sleep(2.0)

            assert final_status in TERMINAL_STATUSES, (
                f"Live research run did not reach a terminal state within {max_wait_seconds}s."
            )
            assert final_status in SUCCESS_STATUSES, (
                f"Live provider-backed run ended with status {final_status!r}."
            )

            sources_response = client.get(
                f"{base_url}/api/research-runs/{run_id}/sources",
                headers=headers,
            )
            report_response = client.get(
                f"{base_url}/api/research-runs/{run_id}/report",
                headers=headers,
            )
            graph_response = client.get(
                f"{base_url}/api/research-runs/{run_id}/graph",
                headers=headers,
            )
            assert sources_response.status_code == 200
            assert report_response.status_code == 200
            assert graph_response.status_code == 200

            source_data = sources_response.json()
            report_data = report_response.json()
            graph_data = graph_response.json()
            assert isinstance(source_data.get("sources"), list)
            assert isinstance(report_data.get("claims"), list)
            assert isinstance(graph_data.get("nodes"), list)
            assert isinstance(graph_data.get("edges"), list)
            assert all("content_text" not in source for source in source_data["sources"])

            # Verify that a user can remove the run after inspecting its results.
            removed = client.delete(
                f"{base_url}/api/research-runs/{run_id}",
                headers=headers,
            )
            assert removed.status_code == 204
            run_id = None
        finally:
            if run_id:
                # Best-effort cleanup if an earlier assertion fails.
                try:
                    client.delete(
                        f"{base_url}/api/research-runs/{run_id}",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                except httpx.HTTPError:
                    pass
