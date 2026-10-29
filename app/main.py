"""FastAPI application entry point for the Government IDSS foundation."""
from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
import re
from time import perf_counter

from app.core.config import environment_summary, load_app_config
from app.core.security import (
    audit_route,
    authorize_request,
    new_request_id,
    request_requires_auth,
    unauthorized_response,
    write_audit_event,
)
from app.schemas.documents import DocumentDetail, DocumentSummary, DocumentUploadResponse
from app.schemas.health import HealthResponse
from app.schemas.meta import AppInfoResponse
from app.schemas.media import MediaMetadata, MediaUploadResponse
from app.schemas.media_search import MediaEvidenceSearchRequest, MediaEvidenceSearchResponse
from app.schemas.search import EvidenceSearchRequest, EvidenceSearchResponse
from app.schemas.transcription import TranscriptionResponse
from app.schemas.workflows import (
    EvidenceComparisonResponse,
    EvidenceWorkflowRequest,
    ReportDraftRequest,
    ReportDraftResponse,
)
from app.services.document_ingestion import (
    InvalidDocumentError,
    OCRUnavailableError,
    get_document,
    ingest_document,
)
from app.services.evidence_retrieval import search_evidence
from app.services.media_ingestion import InvalidMediaError, get_media_metadata, ingest_media
from app.services.media_evidence_search import search_media_evidence
from app.services.evidence_workflows import compare_evidence, draft_report
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

@app.middleware("http")
async def security_and_audit_middleware(request, call_next):
    """Apply optional bearer-token protection and append metadata-only audit events."""
    started = perf_counter()
    request_id = new_request_id(request)
    auth_required = request_requires_auth(request.url.path)
    authorized = authorize_request(request) if auth_required else True
    if auth_required and not authorized:
        response = unauthorized_response()
    else:
        try:
            response = await call_next(request)
        except Exception:
            try:
                write_audit_event(
                    request_id=request_id,
                    method=request.method,
                    route=audit_route(request),
                    status_code=500,
                    duration_ms=(perf_counter() - started) * 1000,
                    auth_required=auth_required,
                    authorized=authorized,
                )
            except OSError:
                pass
            raise
    response.headers["X-Request-ID"] = request_id
    try:
        write_audit_event(
            request_id=request_id,
            method=request.method,
            route=audit_route(request),
            status_code=response.status_code,
            duration_ms=(perf_counter() - started) * 1000,
            auth_required=auth_required,
            authorized=authorized,
        )
    except OSError:
        # Do not expose filesystem details in HTTP responses. Operational
        # deployments must monitor audit storage and use protected durable logs.
        pass
    return response


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

    Authentication is enforced when IDSS_API_TOKEN is configured. This shared-token
    guard does not enforce record-level permissions; do not expose the development
    service to untrusted networks or upload sensitive/real government records.
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
    not confidence probabilities. Shared-token authentication is optional; record-level
    authorization is not implemented. Use synthetic documents only.
    """
    result = search_evidence(request.query, request.top_k)
    return EvidenceSearchResponse.model_validate(result)



@app.post(
    "/api/v1/search/media-evidence",
    response_model=MediaEvidenceSearchResponse,
    tags=["audio/video evidence"],
    summary="Search saved audio/video transcripts with timestamp provenance",
)
def media_evidence_search(request: MediaEvidenceSearchRequest) -> MediaEvidenceSearchResponse:
    """Search locally saved transcript segments and return matching media timestamps.

    This is lexical search over existing transcripts, not a search of raw media.
    Scores are heuristic ranking signals. Shared-token authentication is optional;
    record-level permissions are not implemented. Use synthetic/non-sensitive media only.
    """
    result = search_media_evidence(request.query, request.top_k)
    return MediaEvidenceSearchResponse.model_validate(result)


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


@app.post(
    "/api/v1/evidence/compare",
    response_model=EvidenceComparisonResponse,
    tags=["evidence workflows"],
    summary="Compare retrieved document and audio/video evidence",
)
def compare_retrieved_evidence(request: EvidenceWorkflowRequest) -> EvidenceComparisonResponse:
    """Retrieve evidence from both modalities and organize it for human comparison.

    The endpoint reports evidence coverage, not truth or source agreement.
    Conflicts must be assessed by a reviewer using the cited original sources.
    """
    result = compare_evidence(
        query=request.query,
        top_k=request.top_k,
        document_query=request.document_query,
        media_query=request.media_query,
    )
    return EvidenceComparisonResponse.model_validate(result)


@app.post(
    "/api/v1/reports/draft",
    response_model=ReportDraftResponse,
    tags=["evidence workflows"],
    summary="Draft a Markdown report with source-linked evidence",
)
def create_evidence_report_draft(request: ReportDraftRequest) -> ReportDraftResponse:
    """Create a review-ready draft from retrieved passages; no unsupported facts are generated."""
    result = draft_report(
        title=request.title,
        question=request.question,
        top_k=request.top_k,
        document_query=request.document_query,
        media_query=request.media_query,
    )
    return ReportDraftResponse.model_validate(result)


# Serve the lightweight same-origin browser workspace and its static assets.
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def workspace_home() -> RedirectResponse:
    """Send the browser root to the web workspace."""
    return RedirectResponse(url="/ui")


@app.get("/ui", include_in_schema=False)
def workspace_page() -> FileResponse:
    """Serve the single-page evidence workspace."""
    return FileResponse(STATIC_DIR / "index.html")
