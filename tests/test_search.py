from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.services.document_ingestion as ingestion
import app.services.evidence_retrieval as retrieval

client = TestClient(app)


@pytest.fixture
def isolated_search_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    uploads = tmp_path / "uploads"
    processed = tmp_path / "processed"
    uploads.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ingestion, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(ingestion, "PROCESSED_DIR", processed)
    monkeypatch.setattr(retrieval, "PROCESSED_DIR", processed)
    return processed


def test_search_uploaded_document_returns_text_and_provenance(isolated_search_storage: Path) -> None:
    upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("road_report.txt", b"The fictional North Road inspection identified three potholes. Repair cost is 45000 rupees.", "text/plain")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["document"]["document_id"]
    response = client.post("/api/v1/search/evidence", json={"query": "potholes repair cost", "top_k": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["total_matches"] == 1
    result = body["results"][0]
    assert result["document_id"] == document_id
    assert result["filename"] == "road_report.txt"
    assert result["page_number"] == 1
    assert "potholes" in result["text"]
    assert "repair" in result["matched_terms"]
    assert 0 <= result["score"] <= 1


def test_search_returns_empty_results_when_no_terms_match(isolated_search_storage: Path) -> None:
    client.post("/api/v1/documents/upload", files={"file": ("note.txt", b"A fictional park needs new benches.", "text/plain")})
    response = client.post("/api/v1/search/evidence", json={"query": "airport runway", "top_k": 5})
    assert response.status_code == 200
    assert response.json()["total_matches"] == 0
    assert response.json()["results"] == []


def test_search_respects_top_k(isolated_search_storage: Path) -> None:
    client.post("/api/v1/documents/upload", files={"file": ("road.txt", b"Road repair budget. Road repair schedule. Road repair contractor.", "text/plain")})
    response = client.post("/api/v1/search/evidence", json={"query": "road repair", "top_k": 1})
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    assert response.json()["total_matches"] >= 1


def test_search_rejects_query_shorter_than_two_characters() -> None:
    response = client.post("/api/v1/search/evidence", json={"query": "x"})
    assert response.status_code == 422


def test_search_rejects_top_k_outside_allowed_range() -> None:
    response = client.post("/api/v1/search/evidence", json={"query": "road", "top_k": 100})
    assert response.status_code == 422


def test_search_ignores_corrupt_processed_records(isolated_search_storage: Path) -> None:
    (isolated_search_storage / "broken.json").write_text("{invalid", encoding="utf-8")
    response = client.post("/api/v1/search/evidence", json={"query": "budget", "top_k": 5})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_route_is_documented_in_openapi() -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/v1/search/evidence" in schema["paths"]
    assert "post" in schema["paths"]["/api/v1/search/evidence"]
