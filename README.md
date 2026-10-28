# Government Intelligent Decision Support System (IDSS)

An open-source, local-first foundation for evidence-grounded government decision support. The system is intended to help authorized staff search, compare, and summarize permitted records while keeping human decision-makers in control.

> **Development status:** Checkpoint 1 — project foundation. This is not a production-ready government system. Do not upload real government records, personal data, credentials, or other sensitive information to this public repository.

## Project goals
- Process text, PDFs, scanned PDFs, images, audio, and video as capabilities are added in later checkpoints.
- Ground answers and reports in traceable evidence, including page or timestamp references when available.
- Communicate conflicting or insufficient evidence rather than inventing facts.
- Plan for English and Swahili support, with quality to be evaluated.
- Prefer open-source/local-first components; initial tests require no model downloads or paid AI APIs.

## Repository map
- `SPEC.md` — scope, architecture, safety requirements, and checkpoint plan.
- `config.yaml` — development defaults.
- `.env.example` — safe environment-variable template.
- `requirements.txt` — initial Python dependencies.
- `data/labels.json` — starter document/topic/evidence labels.
- `app/core/config.py` — validated YAML loader and runtime settings.
- `tests/` — automated foundation tests.

## Local setup
Requires Python 3.12.

```bash
python -m venv .venv
```

Activate the environment:

- macOS/Linux: `source .venv/bin/activate`
- Windows PowerShell: `.venv\\Scripts\\Activate.ps1`

Install dependencies and run the tests:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest
```

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


## Run the API (Checkpoint 2)
After installing dependencies and activating your virtual environment, start the development server:

```bash
uvicorn app.main:app --reload
```

Then open these local endpoints in your browser:
- Health check: `http://127.0.0.1:8000/health`
- Application metadata: `http://127.0.0.1:8000/api/v1/info`
- Interactive API docs: `http://127.0.0.1:8000/docs`

Run all automated tests with:

```bash
pytest
```

The API currently exposes only health and safe metadata endpoints. Authentication, authorization enforcement, ingestion, retrieval, and decision-support operations are not implemented yet; do not expose this development server to untrusted networks.
