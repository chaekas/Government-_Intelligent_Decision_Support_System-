"""Safe local document ingestion for text, PDF, and image files.

Original uploads and extracted text are stored only in local runtime directories.
Do not use real government records in this public development environment.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, UnidentifiedImageError

from app.core.config import DEFAULT_CONFIG_PATH, load_app_config

REPOSITORY_ROOT = DEFAULT_CONFIG_PATH.parent
UPLOAD_DIR = REPOSITORY_ROOT / "data" / "uploads"
PROCESSED_DIR = REPOSITORY_ROOT / "data" / "processed"
SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".png", ".jpg", ".jpeg"}
CHUNK_SIZE = 1_000
CHUNK_OVERLAP = 150


class InvalidDocumentError(ValueError):
    """Raised when an upload is unsupported or cannot be safely extracted."""


class OCRUnavailableError(RuntimeError):
    """Raised when OCR is needed but the Tesseract executable is unavailable."""


def _ocr_image(image: Image.Image) -> str:
    """Run local Tesseract OCR; no document content is sent to a remote service."""
    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError

        try:
            return pytesseract.image_to_string(image, lang="eng").strip()
        except TesseractNotFoundError as exc:
            raise OCRUnavailableError(
                "OCR requires the Tesseract system executable. Install Tesseract and "
                "the English language data, then retry the upload."
            ) from exc
    except ImportError as exc:
        raise OCRUnavailableError(
            "OCR requires pytesseract and the Tesseract system executable."
        ) from exc


def _extract_pdf(content: bytes) -> tuple[list[dict[str, Any]], str]:
    pages: list[dict[str, Any]] = []
    methods: set[str] = set()
    try:
        with fitz.open(stream=content, filetype="pdf") as pdf:
            if pdf.is_encrypted:
                raise InvalidDocumentError("Password-protected PDFs are not supported.")
            if pdf.page_count == 0:
                raise InvalidDocumentError("The PDF contains no pages.")
            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if text:
                    methods.add("pdf_text")
                else:
                    pixmap = page.get_pixmap(dpi=200, alpha=False)
                    image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
                    text = _ocr_image(image).strip()
                    methods.add("pdf_ocr")
                pages.append({"page_number": page_number, "text": text})
    except InvalidDocumentError:
        raise
    except OCRUnavailableError:
        raise
    except Exception as exc:
        raise InvalidDocumentError("The PDF is invalid or could not be read.") from exc

    if not any(page["text"] for page in pages):
        raise InvalidDocumentError(
            "No readable text was found in this PDF. Check its quality or OCR language."
        )
    if methods == {"pdf_text"}:
        method = "pdf_text"
    elif methods == {"pdf_ocr"}:
        method = "pdf_ocr"
    else:
        method = "pdf_text_and_ocr"
    return pages, method


def _extract_image(content: bytes) -> tuple[list[dict[str, Any]], str]:
    try:
        with Image.open(io.BytesIO(content)) as source:
            source.verify()
        with Image.open(io.BytesIO(content)) as source:
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidDocumentError("The image file is invalid or unsupported.") from exc

    text = _ocr_image(image).strip()
    if not text:
        raise InvalidDocumentError(
            "OCR did not detect readable text in this image."
        )
    return [{"page_number": 1, "text": text}], "ocr"


def _chunk_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split page text into overlapping chunks while preserving source page numbers."""
    chunks: list[dict[str, Any]] = []
    for page in pages:
        text = re.sub(r"\s+", " ", str(page["text"])).strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + CHUNK_SIZE // 2, end)
                if boundary > start:
                    end = boundary
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(
                    {
                        "chunk_index": len(chunks),
                        "page_number": int(page["page_number"]),
                        "text": chunk,
                    }
                )
            if end >= len(text):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def ingest_document(filename: str, content: bytes) -> dict[str, Any]:
    """Validate, extract, chunk, and persist one uploaded document locally."""
    safe_name = Path(filename or "").name.strip()
    extension = Path(safe_name).suffix.lower()
    if not safe_name or safe_name in {".", ".."}:
        raise InvalidDocumentError("A valid filename is required.")
    if extension not in SUPPORTED_EXTENSIONS:
        raise InvalidDocumentError(
            "Unsupported file type. Stage 3 accepts TXT, PDF, PNG, JPG, and JPEG."
        )

    config = load_app_config()
    max_bytes = int(config["storage"].get("max_upload_size_mb", 25)) * 1024 * 1024
    if not content:
        raise InvalidDocumentError("The uploaded file is empty.")
    if len(content) > max_bytes:
        raise InvalidDocumentError(
            f"File exceeds the configured {max_bytes // (1024 * 1024)} MB upload limit."
        )

    if extension == ".txt":
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidDocumentError("TXT files must use UTF-8 encoding.") from exc
        pages = [{"page_number": 1, "text": text}]
        extraction_method = "text"
    elif extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise InvalidDocumentError("The uploaded file does not have a valid PDF header.")
        pages, extraction_method = _extract_pdf(content)
    else:
        pages, extraction_method = _extract_image(content)

    chunks = _chunk_pages(pages)
    if not chunks:
        raise InvalidDocumentError("No readable text was found in the uploaded document.")

    document_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    record: dict[str, Any] = {
        "document_id": document_id,
        "filename": safe_name,
        "extension": extension,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "created_at": created_at,
        "extraction_method": extraction_method,
        "page_count": len(pages),
        "chunk_count": len(chunks),
        "text": "\n\n".join(
            f"[Page {page['page_number']}]\n{page['text'].strip()}"
            for page in pages
            if str(page["text"]).strip()
        ),
        "chunks": chunks,
    }

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    stored_upload = UPLOAD_DIR / f"{document_id}{extension}"
    stored_record = PROCESSED_DIR / f"{document_id}.json"
    try:
        stored_upload.write_bytes(content)
        stored_record.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        stored_upload.unlink(missing_ok=True)
        stored_record.unlink(missing_ok=True)
        raise
    return record


def get_document(document_id: str) -> dict[str, Any] | None:
    """Read an ingested document by its UUID, never by a user-supplied path."""
    try:
        canonical_id = str(uuid.UUID(document_id))
    except (ValueError, AttributeError, TypeError):
        return None
    record_path = PROCESSED_DIR / f"{canonical_id}.json"
    if not record_path.is_file():
        return None
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return record if isinstance(record, dict) else None
