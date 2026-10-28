"""Local speech-to-text using faster-whisper; no audio is sent to an API.

The model weights are downloaded from the model registry on first use unless
already cached. Inference after download runs locally on the configured device.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.core.config import DEFAULT_CONFIG_PATH, load_app_config
from app.services.media_ingestion import (
    MEDIA_METADATA_DIR,
    MEDIA_UPLOAD_DIR,
    get_media_metadata,
)

TRANSCRIPT_DIR = DEFAULT_CONFIG_PATH.parent / "data" / "transcripts"
_MODEL: Any = None
_MODEL_NAME: str | None = None
_MODEL_LOCK = threading.Lock()


class TranscriptionUnavailableError(RuntimeError):
    """Raised when the local transcription engine is not installed or unavailable."""


class TranscriptionFailedError(RuntimeError):
    """Raised when local inference fails."""


def _get_model(model_name: str) -> Any:
    """Load and cache the configured local Whisper model."""
    global _MODEL, _MODEL_NAME
    if _MODEL is not None and _MODEL_NAME == model_name:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is not None and _MODEL_NAME == model_name:
            return _MODEL
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscriptionUnavailableError(
                "The local transcription engine is not installed. Install requirements-transcription.txt in a supported Python environment and retry."
            ) from exc
        try:
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
        except Exception as exc:
            raise TranscriptionUnavailableError(
                "The local Whisper model could not be loaded. Check internet access for the first model download, then retry."
            ) from exc
        _MODEL = model
        _MODEL_NAME = model_name
        return model


def transcribe_media(media_id: str, language: str | None = None) -> dict[str, Any]:
    """Transcribe a previously uploaded audio or video file and persist results."""
    metadata = get_media_metadata(media_id)
    if metadata is None:
        raise FileNotFoundError("Media not found.")

    extension = str(metadata.get("extension", "")).lower()
    if extension not in {".wav", ".mp3", ".m4a", ".mp4"}:
        raise TranscriptionFailedError("This media format is not supported for transcription.")
    media_path = MEDIA_UPLOAD_DIR / f"{media_id}{extension}"
    if not media_path.is_file():
        raise FileNotFoundError("The uploaded media file is missing from local storage.")

    config = load_app_config()
    model_name = str(config.get("models", {}).get("transcription_model") or "base")
    metadata_path = MEDIA_METADATA_DIR / f"{media_id}.json"
    metadata["transcription_status"] = "processing"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        model = _get_model(model_name)
        segments_iter, info = model.transcribe(
            str(media_path),
            language=language,
            vad_filter=True,
            beam_size=5,
        )
        segments = [
            {
                "start_seconds": max(0.0, float(segment.start)),
                "end_seconds": max(0.0, float(segment.end)),
                "text": str(segment.text).strip(),
            }
            for segment in segments_iter
        ]
        full_text = " ".join(segment["text"] for segment in segments if segment["text"]).strip()
        duration = float(info.duration) if getattr(info, "duration", None) is not None else None
        detected_language = getattr(info, "language", None)
        language_probability = getattr(info, "language_probability", None)
        result: dict[str, Any] = {
            "media_id": media_id,
            "filename": str(metadata.get("filename", media_path.name)),
            "model_name": model_name,
            "language": detected_language,
            "language_probability": (
                float(language_probability) if language_probability is not None else None
            ),
            "duration_seconds": duration,
            "transcription_status": "completed",
            "segments": segments,
            "full_text": full_text,
            "message": "Transcription completed locally. Review the transcript against the original media before relying on it.",
        }
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        (TRANSCRIPT_DIR / f"{media_id}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        metadata["transcription_status"] = "completed"
        metadata["duration_seconds"] = duration
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    except (TranscriptionUnavailableError, TranscriptionFailedError):
        metadata["transcription_status"] = "failed"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    except Exception as exc:
        metadata["transcription_status"] = "failed"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        raise TranscriptionFailedError(
            "Local transcription failed. Check the media file and local model setup, then retry."
        ) from exc


def get_transcript(media_id: str) -> dict[str, Any] | None:
    """Read a saved transcript using a UUID-validated filename."""
    metadata = get_media_metadata(media_id)
    if metadata is None:
        return None
    try:
        import uuid
        canonical_id = str(uuid.UUID(media_id))
    except (ValueError, AttributeError, TypeError):
        return None
    path = TRANSCRIPT_DIR / f"{canonical_id}.json"
    if not path.is_file():
        return None
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return result if isinstance(result, dict) else None
