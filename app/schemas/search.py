"""Schemas for evidence retrieval requests and provenance-bearing results."""
from pydantic import BaseModel, ConfigDict, Field


class EvidenceSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=500, description="Words or phrase to find in ingested documents.")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of matching evidence chunks to return.")


class EvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    filename: str
    chunk_index: int = Field(ge=0)
    page_number: int = Field(ge=1)
    text: str
    score: float = Field(ge=0, le=1, description="Heuristic lexical relevance score, not a probability.")
    matched_terms: list[str]


class EvidenceSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    total_matches: int = Field(ge=0)
    results: list[EvidenceResult]
