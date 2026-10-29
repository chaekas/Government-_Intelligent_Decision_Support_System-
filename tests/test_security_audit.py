from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.core import security


def test_api_token_is_required_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("IDSS_API_TOKEN", "test-only-token")
    client = TestClient(app)
    assert client.post("/api/v1/search/evidence", json={"query": "road repair"}).status_code == 401
    assert client.post(
        "/api/v1/search/evidence",
        json={"query": "road repair"},
        headers={"Authorization": "Bearer test-only-token"},
    ).status_code == 200


def test_health_remains_public_when_token_configured(monkeypatch) -> None:
    monkeypatch.setenv("IDSS_API_TOKEN", "test-only-token")
    assert TestClient(app).get("/health").status_code == 200


def test_audit_event_omits_secrets_and_content(monkeypatch, tmp_path: Path) -> None:
    destination = tmp_path / "audit.jsonl"
    monkeypatch.setenv("IDSS_AUDIT_LOG_PATH", str(destination))
    monkeypatch.setenv("IDSS_AUDIT_EVENTS_ENABLED", "true")
    security.write_audit_event(
        request_id="test-request",
        method="POST",
        route="/api/v1/search/evidence",
        status_code=200,
        duration_ms=2.5,
        auth_required=True,
        authorized=True,
    )
    raw = destination.read_text(encoding="utf-8")
    event = json.loads(raw)
    assert event["request_id"] == "test-request"
    assert event["route"] == "/api/v1/search/evidence"
    assert "test-only-token" not in raw
    assert "authorization" not in raw.casefold()
    assert "document text" not in raw.casefold()


def test_audit_route_uses_template_not_record_id() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/documents/12345678-1234-1234-1234-123456789012")
    assert response.status_code == 404
