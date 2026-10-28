# Government Intelligent Decision Support System (IDSS)

An open-source, local-first foundation for evidence-grounded government decision support. The system is intended to help authorized staff search, compare, and summarize permitted records while keeping human decision-makers in control.

> **Development status:** Checkpoints 1–2 are implemented; Checkpoint 3 document ingestion is under development. This is not a production-ready government system. Do not upload real government records, personal data, credentials, or other sensitive information to this public repository or its development server.

## Project goals
- Process text, PDFs, scanned PDFs, images, audio, and video as capabilities are added in later checkpoints.
- Ground answers and reports in traceable evidence, including page or timestamp references when available.
- Communicate conflicting or insufficient evidence rather than inventing facts.
- Plan for English and Swahili support, with quality to be evaluated.
- Prefer open-source/local-first components; initial tests require no model downloads or paid AI APIs.

## Repository map
- `SPEC.md` — scope, architecture, safety requirements, and checkpoint plan.
- `config.yaml` — development defaults, including the maximum upload size.
- `requirements.txt` — Python dependencies.
- `app/core/config.py` — validated YAML loader and runtime settings.
- `app/services/document_ingestion.py` — local text/PDF/image extraction, OCR integration, chunking, and provenance.
- `app/schemas/documents.py` — document API response schemas.
- `tests/` — automated foundation, API, and ingestion tests.

## Local setup
Requires Python 3.12. A virtual environment is recommended.

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
Start the development server from the repository root:

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
curl -X POST "http://127.0.0.1:8000/api/v1/documents/upload" \
  -F "file=@sample.txt"
```

The upload response includes a `document_id`. Use it to retrieve the processed text:

```bash
curl "http://127.0.0.1:8000/api/v1/documents/REPLACE_WITH_DOCUMENT_ID"
```

### OCR setup

PDFs with selectable text are processed with PyMuPDF. Scanned PDFs and image uploads use local Tesseract OCR; no remote OCR service is called. The Python package alone is not enough: the Tesseract executable and English language data must also be installed.

On Ubuntu or GitHub Codespaces:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
```

If Tesseract is unavailable, OCR uploads return a clear `503` response. Ordinary text PDFs and TXT files do not require Tesseract.

### Local data and limitations

- Original uploads are written to `data/uploads/`; processed text and page-aware chunks are written to `data/processed/`.
- These runtime folders are ignored by Git and should remain local. Never commit real records.
- Current upload endpoints have **no authentication or authorization**. Do not expose this development API to untrusted networks or use it for operational government data.
- Extraction quality can be imperfect. Human reviewers must verify OCR output and source-page references before relying on it.
- Audio/video, semantic retrieval/RAG, user permissions, auditing, and production deployment are not implemented yet.

## Configuration
The defaults are in `config.yaml`. Environment variables can override runtime settings. For example:

- `IDSS_API_PORT=8123`
- `IDSS_MODELS_MODE=mock`
- `IDSS_MODELS_ALLOW_REMOTE_APIS=false`

Copy `.env.example` to `.env` if you want local overrides. Never commit the real `.env` file or any secrets.

## Development checkpoints
1. Foundation and tests.
2. FastAPI backend and API schemas.
3. Safe text/PDF ingestion and OCR integration.
4. Evidence retrieval, RAG, citations, and abstention.
5. Audio/video transcription and provenance.
6. Web frontend.
7. Evidence comparison and report workflows.
8. Authorization, auditing, and evaluation.
9. End-to-end integration and release checklist.

## Safety note
This project is decision support, not autonomous decision-making. Authorization, data protection, auditability, model evaluation, and human review must be validated before any operational use.
