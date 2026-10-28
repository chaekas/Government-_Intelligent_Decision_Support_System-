from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
import app.services.media_evidence_search as search_service

client = TestClient(app)


def _write_transcript(directory: Path, media_id: str = "synthetic-media-1") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{media_id}.json").write_text(
        json.dumps({
            "media_id": media_id,
            "filename": "fictional_meeting.wav",
            "segments": [
                {"start_seconds": 0.0, "end_seconds": 2.4, "text": "The road repair budget is forty thousand rupees."},
                {"start_seconds": 2.4, "end_seconds": 4.0, "text": "The inspection team found three potholes."},
                {"start_seconds": 4.0, "end_seconds": 6.1, "text": "The road repair should begin next month."},
            ],
        }),
        encoding="utf-8",
    )


def test_search_returns_timestamped_matching_transcript_segments(tmp_path: Path, monkeypatch) -> None:
    transcript_dir = tmp_path / "transcripts"
    _write_transcript(transcript_dir)
    monkeypatch.setattr(search_service, "TRANSCRIPT_DIR", transcript_dir)

    response = client.post(
        "/api/v1/search/media-evidence",
        json={"query": "road repair", "top_k": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_matches"] == 2
    first = body["results"][0]
    assert first["media_id"] == "synthetic-media-1"
    assert first["filename"] == "fictional_meeting.wav"
    assert first["start_seconds"] == 0.0
    assert first["end_seconds"] == 2.4
    assert "road" in first["matched_terms"]
    assert 0 <= first["score"] <= 1


def test_media_search_respects_top_k(tmp_path: Path, monkeypatch) -> None:
    transcript_dir = tmp_path / "transcripts"
    _write_transcript(transcript_dir)
    monkeypatch.setattr(search_service, "TRANSCRIPT_DIR", transcript_dir)
    response = client.post(
        "/api/v1/search/media-evidence",
        json={"query": "road repair", "top_k": 1},
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    assert response.json()["total_matches"] == 2


def test_media_search_skips_corrupt_transcripts(tmp_path: Path, monkeypatch) -> None:
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    (transcript_dir / "broken.json").write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(search_service, "TRANSCRIPT_DIR", transcript_dir)
    response = client.post(
        "/api/v1/search/media-evidence",
        json={"query": "road repair", "top_k": 5},
    )
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_media_search_validates_request() -> None:
    response = client.post("/api/v1/search/media-evidence", json={"query": "x"})
    assert response.status_code == 422


def test_media_search_route_is_documented() -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/v1/search/media-evidence" in schema["paths"]
