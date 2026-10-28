from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.main as main_module
import app.services.media_ingestion as media_ingestion
import app.services.transcription as transcription

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_transcription_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    metadata_dir = tmp_path / "metadata"
    transcript_dir = tmp_path / "transcripts"
    uploads.mkdir()
    metadata_dir.mkdir()
    monkeypatch.setattr(media_ingestion, "MEDIA_UPLOAD_DIR", uploads)
    monkeypatch.setattr(media_ingestion, "MEDIA_METADATA_DIR", metadata_dir)
    monkeypatch.setattr(transcription, "MEDIA_UPLOAD_DIR", uploads)
    monkeypatch.setattr(transcription, "MEDIA_METADATA_DIR", metadata_dir)
    monkeypatch.setattr(transcription, "TRANSCRIPT_DIR", transcript_dir)


def _upload_synthetic_wav() -> dict:
    content = b"RIFF" + (4).to_bytes(4, "little") + b"WAVE" + b"test"
    response = client.post(
        "/api/v1/media/upload",
        files={"file": ("sample.wav", content, "audio/wav")},
    )
    assert response.status_code == 201
    return response.json()["media"]


def test_transcribe_media_returns_timestamped_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    media = _upload_synthetic_wav()

    def fake_transcribe(media_id: str, language: str | None = None) -> dict:
        assert media_id == media["media_id"]
        assert language == "en"
        return {
            "media_id": media_id,
            "filename": "sample.wav",
            "model_name": "base",
            "language": "en",
            "language_probability": 0.99,
            "duration_seconds": 2.0,
            "transcription_status": "completed",
            "segments": [{"start_seconds": 0.0, "end_seconds": 1.2, "text": "Synthetic test."}],
            "full_text": "Synthetic test.",
            "message": "Mocked transcription for API test.",
        }

    monkeypatch.setattr(main_module, "transcribe_media", fake_transcribe)
    response = client.post(f"/api/v1/media/{media['media_id']}/transcribe?language=en")
    assert response.status_code == 200
    body = response.json()
    assert body["full_text"] == "Synthetic test."
    assert body["segments"][0]["start_seconds"] == 0.0
    assert body["segments"][0]["end_seconds"] == 1.2


def test_unknown_media_transcription_returns_404() -> None:
    response = client.post("/api/v1/media/00000000-0000-0000-0000-000000000000/transcribe")
    assert response.status_code == 404


def test_transcription_unavailable_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    media = _upload_synthetic_wav()

    def unavailable(media_id: str, language: str | None = None) -> dict:
        raise transcription.TranscriptionUnavailableError("Engine unavailable")

    monkeypatch.setattr(main_module, "transcribe_media", unavailable)
    response = client.post(f"/api/v1/media/{media['media_id']}/transcribe")
    assert response.status_code == 503


def test_transcription_failure_returns_422(monkeypatch: pytest.MonkeyPatch) -> None:
    media = _upload_synthetic_wav()

    def fail(media_id: str, language: str | None = None) -> dict:
        raise transcription.TranscriptionFailedError("Failed")

    monkeypatch.setattr(main_module, "transcribe_media", fail)
    response = client.post(f"/api/v1/media/{media['media_id']}/transcribe")
    assert response.status_code == 422


def test_transcription_route_is_documented() -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/v1/media/{media_id}/transcribe" in schema["paths"]
