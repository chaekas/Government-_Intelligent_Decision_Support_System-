from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.services.media_ingestion as media_ingestion

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_media_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(media_ingestion, "MEDIA_UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(media_ingestion, "MEDIA_METADATA_DIR", tmp_path / "metadata")


def test_upload_wav_returns_metadata_and_does_not_claim_transcription() -> None:
    # Minimal RIFF/WAVE-shaped synthetic test bytes; no real recording.
    content = b"RIFF" + (4).to_bytes(4, "little") + b"WAVE" + b"test"
    response = client.post(
        "/api/v1/media/upload",
        files={"file": ("sample.wav", content, "audio/wav")},
    )
    assert response.status_code == 201
    media = response.json()["media"]
    assert media["filename"] == "sample.wav"
    assert media["media_type"] == "audio"
    assert media["mime_type"] == "audio/wav"
    assert media["size_bytes"] == len(content)
    assert len(media["sha256"]) == 64
    assert media["duration_seconds"] is None
    assert media["processing_status"] == "uploaded"
    assert media["transcription_status"] == "not_started"

    detail = client.get(f"/api/v1/media/{media['media_id']}")
    assert detail.status_code == 200
    assert detail.json()["sha256"] == media["sha256"]


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("clip.wav", b"not a wav"),
        ("clip.mp3", b"not an mp3"),
        ("clip.m4a", b"not an m4a"),
        ("clip.mp4", b"not an mp4"),
    ],
)
def test_media_extension_with_wrong_signature_is_rejected(filename: str, content: bytes) -> None:
    response = client.post(
        "/api/v1/media/upload",
        files={"file": (filename, content, "application/octet-stream")},
    )
    assert response.status_code == 422
    assert "content does not match" in response.json()["detail"]


def test_unsupported_media_extension_is_rejected() -> None:
    response = client.post(
        "/api/v1/media/upload",
        files={"file": ("payload.exe", b"fake", "application/octet-stream")},
    )
    assert response.status_code == 422
    assert "Unsupported media type" in response.json()["detail"]


def test_empty_media_is_rejected() -> None:
    response = client.post(
        "/api/v1/media/upload",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert response.status_code == 422


def test_oversized_media_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "MAX_UPLOAD_BYTES", 8)
    response = client.post(
        "/api/v1/media/upload",
        files={"file": ("large.wav", b"RIFFxxxxWAVE" + b"x" * 20, "audio/wav")},
    )
    assert response.status_code == 413


def test_unknown_media_id_returns_404() -> None:
    response = client.get("/api/v1/media/not-a-uuid")
    assert response.status_code == 404


def test_media_routes_appear_in_openapi() -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/v1/media/upload" in schema["paths"]
    assert "/api/v1/media/{media_id}" in schema["paths"]
