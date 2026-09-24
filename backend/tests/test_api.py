"""API contract tests."""

from __future__ import annotations

import pytest

from tests.conftest import requires_db

pytestmark = requires_db


@pytest.fixture
def client(engine, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.deps import get_analytics_service
    from app.database.connection import get_read_session
    from app.main import app
    from sqlalchemy.orm import Session

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_read_session] = override_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] in {"healthy", "degraded"}
    assert "database" in body


def test_health_never_exposes_credentials(client):
    body = client.get("/api/health").text
    for leak in ("password", "postgresql://", "api_key", "Bearer"):
        assert leak not in body


def test_iterations(client):
    response = client.get("/api/iterations")
    assert response.status_code == 200
    assert "Product\\Sprint 24" in response.json()


def test_dashboard_summary(client):
    response = client.get("/api/dashboard/summary", params={"iteration_path": "Product\\Sprint 24"})
    assert response.status_code == 200
    body = response.json()
    assert body["total_hours"] == pytest.approx(46.5)
    assert body["filters_applied"] == {"iteration_path": "Product\\Sprint 24"}
    assert len(body["top_work_items"]) <= 10


def test_analytics_time(client):
    body = client.get("/api/analytics/time", params={"memo_code": "QA"}).json()
    assert body["total_hours"] == pytest.approx(7.0)


def test_analytics_by_capability(client):
    rows = client.get("/api/analytics/by-capability").json()
    assert {r["capability"] for r in rows} == {"Authentication", "Scheduling"}


def test_analytics_compare(client):
    body = client.get(
        "/api/analytics/compare",
        params={
            "iteration_path": "Product\\Sprint 23",
            "iteration_path_b": "Product\\Sprint 24",
            "label_a": "Sprint 23",
            "label_b": "Sprint 24",
        },
    ).json()
    assert body["absolute_difference"] == pytest.approx(34.5)


def test_work_item_detail(client):
    body = client.get("/api/work-items/1234").json()
    assert body["title"] == "Implement SSO"
    assert body["total_hours"] == pytest.approx(25.5)


def test_missing_work_item_returns_404(client):
    response = client.get("/api/work-items/424242")
    assert response.status_code == 404
    assert "424242" in response.json()["detail"]


def test_validation_error_returns_422_with_field_detail(client):
    response = client.get("/api/analytics/time", params={"work_item_id": 0})
    assert response.status_code == 422
    assert response.json()["details"]


def test_inverted_date_range_is_rejected(client):
    response = client.get(
        "/api/analytics/time",
        params={"date_from": "2026-09-30", "date_to": "2026-09-01"},
    )
    assert response.status_code == 422


def test_data_quality_endpoint(client):
    body = client.get("/api/data-quality").json()
    assert body["total_issues"] > 0
    assert "MISSING_WORK_ITEM" in body["by_type"]


def test_data_quality_severity_filter_is_constrained(client):
    assert client.get("/api/data-quality", params={"severity": "critical"}).status_code == 422


def test_pagination_limits_are_enforced(client):
    assert client.get("/api/analytics/by-user", params={"limit": 10_000}).status_code == 422


def test_every_response_carries_a_request_id(client):
    assert client.get("/api/health").headers.get("x-request-id")


def test_errors_never_include_sql_or_stack_traces(client):
    response = client.get("/api/analytics/by-date", params={"granularity": "century"})
    assert response.status_code in {400, 422}
    body = response.text
    assert "vw_worklog" not in body
    assert "Traceback" not in body
