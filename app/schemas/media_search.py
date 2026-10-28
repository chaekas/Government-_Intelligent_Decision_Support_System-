"""Schemas for searching transcript segments with timestamp provenance."""
from pydantic import BaseModel, ConfigDict, Field


class MediaEvidenceSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=500, description="Words or phrase to find in saved audio/video transcripts.")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum matching transcript segments to return.")


class MediaEvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_id: str
    filename: str
    segment_index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str
    score: float = Field(ge=0, le=1, description="Heuristic lexical relevance score, not a probability.")
    matched_terms: list[str]


class MediaEvidenceSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    total_matches: int = Field(ge=0)
    results: list[MediaEvidenceResult]
