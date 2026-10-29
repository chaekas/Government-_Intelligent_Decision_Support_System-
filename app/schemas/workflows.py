"""Validated request and response models for evidence workflows."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=500, description="Question or topic to investigate.")
    document_query: str | None = Field(default=None, min_length=2, max_length=500)
    media_query: str | None = Field(default=None, min_length=2, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class ComparedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modality: Literal["document", "audio_video"]
    source_id: str
    filename: str
    location: str
    text: str
    score: float = Field(ge=0, le=1)
    matched_terms: list[str]


class EvidenceComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    document_query: str
    media_query: str
    coverage: Literal["both_modalities", "documents_only", "media_only", "no_evidence"]
    assessment: Literal["SINGLE_MODALITY", "UNCERTAIN"]
    assessment_note: str
    document_results: list[ComparedEvidence]
    media_results: list[ComparedEvidence]
    evidence_count: int = Field(ge=0)
    review_required: bool = True


class ReportDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    question: str
    assessment: Literal["SINGLE_MODALITY", "UNCERTAIN"]
    evidence_count: int = Field(ge=0)
    evidence: list[ComparedEvidence]
    draft_markdown: str
    limitations: list[str]
    human_review_required: bool = True
