"""API schemas for document ingestion and extracted evidence chunks."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DocumentChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_index: int = Field(ge=0)
    page_number: int = Field(ge=1)
    text: str


class DocumentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    filename: str
    extension: str
    size_bytes: int
    sha256: str
    created_at: datetime
    extraction_method: str
    page_count: int
    chunk_count: int


class DocumentDetail(DocumentSummary):
    text: str
    chunks: list[DocumentChunk]


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: DocumentSummary
    message: str = "Document processed successfully. Review extracted text before relying on it."
