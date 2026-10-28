"""Schemas for validated audio/video uploads (transcription is a later checkpoint)."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class MediaMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_id: str
    filename: str
    extension: str
    media_type: str = Field(pattern="^(audio|video)$")
    mime_type: str
    size_bytes: int = Field(ge=1)
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    created_at: datetime
    duration_seconds: float | None = Field(default=None, ge=0)
    processing_status: str = "uploaded"
    transcription_status: str = "not_started"


class MediaUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media: MediaMetadata
    message: str = (
        "Media validated and stored locally. Transcription is not implemented in Checkpoint 5A."
    )
