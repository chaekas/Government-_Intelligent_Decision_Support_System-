from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_expected_payload() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "government-idss-api"
    assert body["version"] == app.version


def test_info_endpoint_returns_safe_metadata() -> None:
    response = client.get("/api/v1/info")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Government Intelligent Decision Support System"
    assert body["supported_languages"] == ["en", "sw"]
    assert body["model_mode"] == "mock"
    assert body["remote_apis_enabled"] is False
    assert "api_port" not in body


def test_openapi_document_is_available() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/health" in schema["paths"]
    assert "/api/v1/info" in schema["paths"]
