"""Response schemas for local speech-to-text transcription."""
from pydantic import BaseModel, ConfigDict, Field


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str


class TranscriptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_id: str
    filename: str
    model_name: str
    language: str | None = None
    language_probability: float | None = Field(default=None, ge=0, le=1)
    duration_seconds: float | None = Field(default=None, ge=0)
    transcription_status: str
    segments: list[TranscriptSegment]
    full_text: str
    message: str
