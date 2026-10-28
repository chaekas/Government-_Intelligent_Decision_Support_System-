"""Local audio/video upload validation and metadata persistence.

This module does not decode, transcribe, or send media to remote services.
Only synthetic test media should be uploaded to this development instance.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import DEFAULT_CONFIG_PATH, load_app_config

REPOSITORY_ROOT = DEFAULT_CONFIG_PATH.parent
MEDIA_UPLOAD_DIR = REPOSITORY_ROOT / "data" / "media_uploads"
MEDIA_METADATA_DIR = REPOSITORY_ROOT / "data" / "media_metadata"

# MIME values are assigned from the validated extension, never trusted from the client.
MEDIA_TYPES: dict[str, tuple[str, str]] = {
    ".wav": ("audio", "audio/wav"),
    ".mp3": ("audio", "audio/mpeg"),
    ".m4a": ("audio", "audio/mp4"),
    ".mp4": ("video", "video/mp4"),
}


class InvalidMediaError(ValueError):
    """Raised when a media upload is unsupported or has an invalid signature."""


def _has_valid_signature(extension: str, content: bytes) -> bool:
    """Perform conservative container/header checks; this is not a malware scan."""
    if extension == ".wav":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE"
    if extension == ".mp3":
        if content.startswith(b"ID3"):
            return len(content) >= 10
        # MPEG audio frame sync: 11 consecutive leading one bits.
        return len(content) >= 2 and content[0] == 0xFF and (content[1] & 0xE0) == 0xE0
    if extension in {".m4a", ".mp4"}:
        if len(content) < 12 or content[4:8] != b"ftyp":
            return False
        brand = content[8:12]
        if extension == ".m4a":
            return brand in {b"M4A ", b"M4B ", b"isom", b"mp42"}
        return brand in {b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"M4V ", b"MSNV"}
    return False


def ingest_media(filename: str, content: bytes) -> dict[str, Any]:
    """Validate and store an audio/video file, then persist its metadata."""
    safe_name = Path(filename or "").name.strip()
    extension = Path(safe_name).suffix.lower()
    if not safe_name or safe_name in {".", ".."}:
        raise InvalidMediaError("A valid filename is required.")
    if extension not in MEDIA_TYPES:
        raise InvalidMediaError("Unsupported media type. Checkpoint 5A accepts WAV, MP3, M4A, and MP4.")
    if not content:
        raise InvalidMediaError("The uploaded media file is empty.")

    config = load_app_config()
    max_bytes = int(config["storage"].get("max_upload_size_mb", 25)) * 1024 * 1024
    if len(content) > max_bytes:
        raise InvalidMediaError(
            f"File exceeds the configured {max_bytes // (1024 * 1024)} MB upload limit."
        )
    if not _has_valid_signature(extension, content):
        raise InvalidMediaError(
            f"The file content does not match a supported {extension[1:].upper()} media header."
        )

    media_type, mime_type = MEDIA_TYPES[extension]
    media_id = str(uuid.uuid4())
    metadata: dict[str, Any] = {
        "media_id": media_id,
        "filename": safe_name,
        "extension": extension,
        "media_type": media_type,
        "mime_type": mime_type,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Duration needs a media probe/decoder; deliberately unknown in Checkpoint 5A.
        "duration_seconds": None,
        "processing_status": "uploaded",
        "transcription_status": "not_started",
    }

    MEDIA_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_METADATA_DIR.mkdir(parents=True, exist_ok=True)
    media_path = MEDIA_UPLOAD_DIR / f"{media_id}{extension}"
    metadata_path = MEDIA_METADATA_DIR / f"{media_id}.json"
    try:
        media_path.write_bytes(content)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        media_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        raise
    return metadata


def get_media_metadata(media_id: str) -> dict[str, Any] | None:
    """Retrieve metadata only using a canonical UUID, not a user-supplied path."""
    try:
        canonical_id = str(uuid.UUID(media_id))
    except (ValueError, AttributeError, TypeError):
        return None
    path = MEDIA_METADATA_DIR / f"{canonical_id}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
