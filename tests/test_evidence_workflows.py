from fastapi.testclient import TestClient

from app.main import app
import app.services.evidence_workflows as workflows

client = TestClient(app)


def _document_result(text="The fictional project estimate is 45000 rupees."):
    return {
        "query": "project estimate",
        "total_matches": 1,
        "results": [{
            "document_id": "doc-123",
            "filename": "budget_note.txt",
            "chunk_index": 0,
            "page_number": 2,
            "text": text,
            "score": 0.8,
            "matched_terms": ["project", "estimate"],
        }],
    }


def _media_result(text="The meeting mentioned an estimated project cost of 45000 rupees."):
    return {
        "query": "project estimate",
        "total_matches": 1,
        "results": [{
            "media_id": "media-456",
            "filename": "meeting.wav",
            "segment_index": 3,
            "start_seconds": 12.5,
            "end_seconds": 18.0,
            "text": text,
            "score": 0.7,
            "matched_terms": ["project", "estimate"],
        }],
    }


def test_compare_endpoint_preserves_both_modalities(monkeypatch):
    monkeypatch.setattr(workflows, "search_evidence", lambda query, top_k: _document_result())
    monkeypatch.setattr(workflows, "search_media_evidence", lambda query, top_k: _media_result())
    response = client.post("/api/v1/evidence/compare", json={"query": "project estimate"})
    assert response.status_code == 200
    body = response.json()
    assert body["coverage"] == "both_modalities"
    assert body["assessment"] == "UNCERTAIN"
    assert body["evidence_count"] == 2
    assert body["document_results"][0]["location"] == "page 2, chunk 0"
    assert "12.50s–18.00s" in body["media_results"][0]["location"]
    assert body["review_required"] is True


def test_compare_endpoint_reports_single_modality(monkeypatch):
    monkeypatch.setattr(workflows, "search_evidence", lambda query, top_k: _document_result())
    monkeypatch.setattr(workflows, "search_media_evidence", lambda query, top_k: {"results": [], "total_matches": 0, "query": query})
    response = client.post("/api/v1/evidence/compare", json={"query": "project estimate"})
    assert response.status_code == 200
    assert response.json()["coverage"] == "documents_only"
    assert response.json()["assessment"] == "SINGLE_MODALITY"


def test_report_draft_contains_citations_and_limitations(monkeypatch):
    monkeypatch.setattr(workflows, "search_evidence", lambda query, top_k: _document_result())
    monkeypatch.setattr(workflows, "search_media_evidence", lambda query, top_k: _media_result())
    response = client.post("/api/v1/reports/draft", json={"title": "Project Review", "question": "project estimate"})
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Project Review"
    assert body["evidence_count"] == 2
    assert "[E1]" in body["draft_markdown"]
    assert "budget_note.txt" in body["draft_markdown"]
    assert "Human review is required" in body["draft_markdown"]
    assert body["human_review_required"] is True


def test_report_draft_rejects_extra_fields():
    response = client.post("/api/v1/reports/draft", json={"title": "Test", "question": "topic", "unexpected": True})
    assert response.status_code == 422


def test_workflow_routes_are_in_openapi():
    schema = client.get("/openapi.json").json()
    assert "/api/v1/evidence/compare" in schema["paths"]
    assert "/api/v1/reports/draft" in schema["paths"]
