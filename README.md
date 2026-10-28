# Government Intelligent Decision Support System (IDSS)

An open-source, local-first foundation for evidence-grounded government decision support. The system is intended to help authorized staff search, compare, and summarize permitted records while keeping human decision-makers in control.

> **Development status:** Checkpoints 1–4 are implemented; Checkpoint 5A adds audio/video upload validation and metadata only. This is not a production-ready government system. Do not upload real government records, personal data, credentials, or other sensitive information to this public repository or its development server.

## Project goals
- Process text, PDFs, scanned PDFs, images, and (Checkpoint 5A) validate/store WAV, MP3, M4A, and MP4 uploads; transcription is planned for a later checkpoint.
- Ground retrieval and future reports in traceable evidence, including page or timestamp references when available.
- Communicate conflicting or insufficient evidence rather than inventing facts.
- Plan for English and Swahili support, with quality to be evaluated.
- Prefer open-source/local-first components; current search requires no model download, paid AI API, or remote service.

## Repository map
- `SPEC.md` — scope, architecture, safety requirements, and checkpoint plan.
- `config.yaml` — development defaults, including upload and retrieval settings.
- `requirements.txt` — Python dependencies.
- `app/core/config.py` — validated YAML loader and runtime settings.
- `app/services/document_ingestion.py` — local text/PDF/image extraction, OCR integration, chunking, and provenance.
- `app/services/evidence_retrieval.py` — deterministic local keyword retrieval over stored chunks.
- `app/services/media_ingestion.py` — basic audio/video signature validation and local metadata persistence (no decoding or transcription).
- `app/schemas/` — API request and response schemas.
- `tests/` — automated foundation, API, ingestion, and search tests.

## Local setup
Requires Python 3.12 or newer compatible with the dependencies. A virtual environment is recommended.

```bash
python -m venv .venv
```

Activate the environment:

- macOS/Linux: `source .venv/bin/activate`
- Windows PowerShell: `.venv\\Scripts\\Activate.ps1`

Install dependencies and run the tests:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
PYTHONPATH=. python -m pytest
```

If running in GitHub Codespaces, `PYTHONPATH=.` makes the repository root explicit for Python imports.

## Run the API

```bash
PYTHONPATH=. python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open these paths on your local server or on the forwarded port-8000 address supplied by Codespaces:

- Health check: `/health`
- Application metadata: `/api/v1/info`
- Interactive API docs: `/docs`
- OpenAPI schema: `/openapi.json`

## Checkpoint 3: document ingestion

The API accepts `TXT`, `PDF`, `PNG`, `JPG`, and `JPEG` files at `POST /api/v1/documents/upload`. It validates the file extension and size, extracts text, preserves page numbers, creates overlapping text chunks, calculates a SHA-256 source hash, and stores the source and processed record locally. Retrieve extracted text and chunks with `GET /api/v1/documents/{document_id}`.

Example upload (run from a terminal where `sample.txt` exists):

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/documents/upload" -F "file=@sample.txt"
```

### OCR setup

PDFs with selectable text are processed with PyMuPDF. Scanned PDFs and image uploads use local Tesseract OCR; no remote OCR service is called. The Python package alone is not enough: the Tesseract executable and English language data must also be installed.

On Ubuntu or GitHub Codespaces:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
```

If Tesseract is unavailable, OCR uploads return a clear `503` response. Ordinary text PDFs and TXT files do not require Tesseract.

## Checkpoint 4: evidence retrieval

`POST /api/v1/search/evidence` searches locally stored document chunks and returns matching passages with `document_id`, `filename`, `page_number`, `chunk_index`, matched query terms, and a relevance score. Example request:

```json
{
  "query": "potholes repair cost",
  "top_k": 5
}
```

Use the Swagger UI at `/docs` to submit a request. Search is deterministic lexical matching; it does not generate an AI answer and does not require an external model. The score is a heuristic ranking signal, **not** a probability or calibrated confidence. A result's source and page references should be checked against the original document before use. No matching chunks means no evidence was retrieved; it does not prove that a fact is false.



## Checkpoint 5A: audio/video upload validation

The new POST /api/v1/media/upload endpoint accepts WAV, MP3, M4A, and MP4 uploads. It enforces the configured size limit, checks a basic file/container signature (not a malware scan or full media validation), computes SHA-256, assigns a media ID, and stores the file and metadata locally. Retrieve metadata with GET /api/v1/media/{media_id}.

Metadata includes the filename, extension, media type, MIME type inferred from the validated extension, byte size, SHA-256, upload timestamp, and processing/transcription statuses. Duration is intentionally null because Checkpoint 5A does not run a media probe. transcription_status remains not_started: this checkpoint does not transcribe audio or video.

Use the Swagger UI at /docs to test the upload and metadata endpoints with synthetic sample media only. Audio/video uploads are stored in data/media_uploads/; metadata JSON is stored in data/media_metadata/. These paths are ignored by Git. Do not commit recordings or upload real government, personal, confidential, or otherwise sensitive material.

## Local data and limitations

- Original uploads are written to `data/uploads/`; processed text and page-aware chunks are written to `data/processed/`. These runtime folders are ignored by Git.
- Current upload and search endpoints have **no authentication or record-level authorization**. Search can retrieve any document stored in this local development instance. Use synthetic documents only and do not expose the development API to untrusted networks.
- Extraction and OCR can be imperfect. Human reviewers must verify source text and page references.
- Semantic/vector retrieval, grounded answer generation, audio/video transcription, user permissions, auditing, and production deployment are not implemented yet.

## Development checkpoints
1. Foundation and tests.
2. FastAPI backend and API schemas.
3. Safe text/PDF ingestion and OCR integration.
4. Evidence retrieval, RAG groundwork, citations, and abstention.
5. Audio/video transcription and provenance.
6. Web frontend.
7. Evidence comparison and report workflows.
8. Authorization, auditing, and evaluation.
9. End-to-end integration and release checklist.

## Safety note
This project is decision support, not autonomous decision-making. Authorization, data protection, auditability, model evaluation, and human review must be validated before any operational use.
