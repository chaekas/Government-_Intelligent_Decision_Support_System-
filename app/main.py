"""FastAPI application entry point for the Government IDSS foundation."""
from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import re

from app.core.config import environment_summary, load_app_config
from app.schemas.documents import DocumentDetail, DocumentSummary, DocumentUploadResponse
from app.schemas.health import HealthResponse
from app.schemas.meta import AppInfoResponse
from app.schemas.media import MediaMetadata, MediaUploadResponse
from app.schemas.search import EvidenceSearchRequest, EvidenceSearchResponse
from app.schemas.transcription import TranscriptionResponse
from app.services.document_ingestion import (
    InvalidDocumentError,
    OCRUnavailableError,
    get_document,
    ingest_document,
)
from app.services.evidence_retrieval import search_evidence
from app.services.media_ingestion import InvalidMediaError, get_media_metadata, ingest_media
from app.services.transcription import (
    TranscriptionFailedError,
    TranscriptionUnavailableError,
    get_transcript,
    transcribe_media,
)

CONFIG = load_app_config()
APP_INFO = CONFIG["app"]
MAX_UPLOAD_BYTES = int(CONFIG["storage"].get("max_upload_size_mb", 25)) * 1024 * 1024

app = FastAPI(
    title=str(APP_INFO.get("name", "Government IDSS")),
    version=str(APP_INFO.get("version", "0.1.0")),
    description=(
        "Evidence-grounded decision support for authorized public-sector staff. "
        "This API is an early development foundation, not a production system."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# The API is intentionally same-origin by default. Configure allowed origins
# explicitly before enabling browser clients in a deployed environment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    """Return a lightweight liveness response without accessing user data."""
    return HealthResponse(status="ok", service="government-idss-api", version=app.version)


@app.get("/api/v1/info", response_model=AppInfoResponse, tags=["system"])
def application_info() -> AppInfoResponse:
    """Return safe application metadata and non-secret runtime configuration."""
    summary = environment_summary()
    return AppInfoResponse(
        name=str(APP_INFO.get("name", "Government IDSS")),
        version=app.version,
        default_language=str(APP_INFO.get("default_language", "en")),
        supported_languages=list(APP_INFO.get("supported_languages", ["en"])),
        environment=str(summary["environment"]),
        model_mode=str(summary["models_mode"]),
        remote_apis_enabled=bool(summary["remote_apis_enabled"]),
    )


@app.post(
    "/api/v1/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=201,
    tags=["documents"],
    summary="Upload and extract a TXT, PDF, or image document",
)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    """Extract text locally and persist source/page/chunk provenance.

    This development endpoint has no authentication yet. Do not expose it to
    untrusted networks or upload sensitive/real government records.
    """
    filename = file.filename or ""
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the configured {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
        )
    try:
        record = ingest_document(filename, content)
    except InvalidDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OCRUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the processed document locally.") from exc

    summary_data = {field: record[field] for field in DocumentSummary.model_fields}
    summary = DocumentSummary.model_validate(summary_data)
    return DocumentUploadResponse(document=summary)


@app.get(
    "/api/v1/documents/{document_id}",
    response_model=DocumentDetail,
    tags=["documents"],
    summary="Retrieve extracted text and page-aware chunks",
)
def read_document(document_id: str) -> DocumentDetail:
    """Return a processed document record, including page references and chunks."""
    record = get_document(document_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentDetail.model_validate(record)


@app.post(
    "/api/v1/search/evidence",
    response_model=EvidenceSearchResponse,
    tags=["evidence search"],
    summary="Search ingested documents and return source-linked evidence chunks",
)
def evidence_search(request: EvidenceSearchRequest) -> EvidenceSearchResponse:
    """Search local extracted chunks; this endpoint does not generate AI answers.

    Search is lexical and deterministic. Scores are heuristic ranking signals,
    not confidence probabilities. Authentication and record-level authorization
    have not yet been implemented; use synthetic documents only.
    """
    result = search_evidence(request.query, request.top_k)
    return EvidenceSearchResponse.model_validate(result)



@app.post(
    "/api/v1/media/upload",
    response_model=MediaUploadResponse,
    status_code=201,
    tags=["audio/video"],
    summary="Validate and store an audio/video file (no transcription yet)",
)
async def upload_media(file: UploadFile = File(...)) -> MediaUploadResponse:
    """Validate basic media signatures and save metadata locally.

    Checkpoint 5A does not inspect duration or transcribe audio/video. This
    development endpoint has no authentication; use synthetic test media only.
    """
    filename = file.filename or ""
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the configured {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
        )
    try:
        metadata = ingest_media(filename, content)
    except InvalidMediaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the media file locally.") from exc
    return MediaUploadResponse(media=MediaMetadata.model_validate(metadata))


@app.get(
    "/api/v1/media/{media_id}",
    response_model=MediaMetadata,
    tags=["audio/video"],
    summary="Retrieve metadata for an uploaded audio/video file",
)
def read_media_metadata(media_id: str) -> MediaMetadata:
    """Return stored metadata; this endpoint does not stream or transcribe media."""
    metadata = get_media_metadata(media_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Media not found.")
    return MediaMetadata.model_validate(metadata)



@app.post(
    "/api/v1/media/{media_id}/transcribe",
    response_model=TranscriptionResponse,
    tags=["audio/video"],
    summary="Transcribe uploaded media locally with Whisper",
)
def transcribe_uploaded_media(media_id: str, language: str | None = None) -> TranscriptionResponse:
    """Run local speech-to-text; the first call may download model weights."""
    if language is not None and not re.fullmatch(r"[a-z]{2,3}", language):
        raise HTTPException(
            status_code=422,
            detail="Language must be a two- or three-letter lowercase language code, such as en or sw.",
        )
    if get_media_metadata(media_id) is None:
        raise HTTPException(status_code=404, detail="Media not found.")
    try:
        result = transcribe_media(media_id, language=language)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TranscriptionUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TranscriptionFailedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not save the transcription result locally.") from exc
    return TranscriptionResponse.model_validate(result)


@app.get(
    "/api/v1/media/{media_id}/transcript",
    response_model=TranscriptionResponse,
    tags=["audio/video"],
    summary="Retrieve a previously saved local transcript",
)
def read_saved_transcript(media_id: str) -> TranscriptionResponse:
    """Return transcript segments with timestamps for an already transcribed file."""
    result = get_transcript(media_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Transcript not found. Transcribe the media first.")
    return TranscriptionResponse.model_validate(result)
