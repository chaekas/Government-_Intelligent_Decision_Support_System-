from __future__ import annotations

import io
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
import app.services.document_ingestion as ingestion

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_document_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ingestion, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(ingestion, "PROCESSED_DIR", tmp_path / "processed")


def test_upload_txt_extracts_text_and_preserves_page_reference() -> None:
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("budget-note.txt", b"Approved budget: 250000 units.", "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    document = body["document"]
    assert document["filename"] == "budget-note.txt"
    assert document["extraction_method"] == "text"
    assert document["page_count"] == 1
    assert document["chunk_count"] == 1
    assert len(document["sha256"]) == 64
    assert "text" not in document

    detail = client.get(f"/api/v1/documents/{document['document_id']}")
    assert detail.status_code == 200
    assert "Approved budget: 250000 units." in detail.json()["text"]
    assert detail.json()["chunks"][0]["page_number"] == 1
    assert detail.json()["chunks"][0]["text"] == "Approved budget: 250000 units."


def test_upload_pdf_extracts_text_and_tracks_page_numbers() -> None:
    pdf = fitz.open()
    first = pdf.new_page()
    first.insert_text((72, 72), "First page: project overview.")
    second = pdf.new_page()
    second.insert_text((72, 72), "Second page: budget summary.")
    content = pdf.tobytes()
    pdf.close()

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("report.pdf", content, "application/pdf")},
    )
    assert response.status_code == 201
    document = response.json()["document"]
    assert document["page_count"] == 2
    assert document["extraction_method"] == "pdf_text"

    detail = client.get(f"/api/v1/documents/{document['document_id']}").json()
    assert [chunk["page_number"] for chunk in detail["chunks"]] == [1, 2]
    assert "First page: project overview." in detail["text"]
    assert "Second page: budget summary." in detail["text"]


def test_upload_image_uses_local_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingestion, "_ocr_image", lambda image: "OCR result from sample image")
    image_buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(image_buffer, format="PNG")

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("scan.png", image_buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 201
    document = response.json()["document"]
    assert document["extraction_method"] == "ocr"
    detail = client.get(f"/api/v1/documents/{document['document_id']}").json()
    assert "OCR result from sample image" in detail["text"]


def test_unsupported_extension_is_rejected() -> None:
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("payload.exe", b"not an executable", "application/octet-stream")},
    )
    assert response.status_code == 422
    assert "Unsupported file type" in response.json()["detail"]


def test_invalid_pdf_is_rejected() -> None:
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("broken.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 422
    assert "valid PDF header" in response.json()["detail"]


def test_oversized_upload_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "MAX_UPLOAD_BYTES", 10)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("note.txt", b"x" * 11, "text/plain")},
    )
    assert response.status_code == 413


def test_unknown_document_id_returns_404() -> None:
    response = client.get("/api/v1/documents/not-a-uuid")
    assert response.status_code == 404


def test_document_routes_appear_in_openapi() -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/v1/documents/upload" in schema["paths"]
    assert "/api/v1/documents/{document_id}" in schema["paths"]
