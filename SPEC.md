# Government Intelligent Decision Support System (IDSS)
Version: 0.1.0  
Status: Checkpoint 7 implementation branch; automated test run pending

## 1. Purpose
Build a practical, evidence-grounded decision-support platform for authorized public-sector staff. Users should be able to search and understand permitted government records, compare evidence, and prepare traceable reports. The platform supports human decisions; it does not autonomously make consequential government decisions.

## 2. Initial objectives
- Ingest and process text, PDFs (including scanned PDFs), document images/photos, audio recordings, and video clips with audio.
- Extract text and metadata where supported.
- Retrieve only records the current user is authorized to access.
- Answer questions using retrieved evidence, with document and page references when available.
- Summarize records, extract structured facts, compare documents, and draft evidence-grounded reports.
- Clearly communicate uncertainty, conflicting evidence, missing evidence, and unsupported questions.
- Plan for English and Swahili support; language quality must be evaluated rather than assumed.

## 3. Initial technology choices
- Runtime: Python 3.12.
- API: FastAPI with Pydantic validation.
- Configuration: YAML plus environment variables for deployment-specific settings.
- Testing: pytest.
- Initial metadata store: SQLite for local development; production storage requires a separate security and deployment review.
- Frontend: React, TypeScript, and Next.js in a later checkpoint.
- AI components: open-source/local-first models and libraries, introduced incrementally.
- No paid commercial LLM API is required for the initial foundation. Mock/test mode must work without downloading model weights.

## 4. Core workflows
1. Authenticate the user and establish permissions.
2. Accept a supported file or a question about authorized records.
3. Validate type and size, record provenance, and process the input.
4. Extract text/transcripts and preserve source references.
5. Retrieve relevant permitted evidence.
6. Produce an answer or report tied to evidence.
7. Show citations, uncertainty, limitations, and missing evidence.
8. Record appropriate audit events without logging secrets or unnecessary sensitive content.

## 5. Evidence and uncertainty
Every evidence item should preserve, where available: source ID, source title, page/segment, extraction method, timestamp, and retrieval metadata. The system must not invent citations.

Suggested outcome labels:
- MATCH: available evidence supports the relevant claim.
- PARTIAL: evidence supports only part of the claim.
- CONFLICT: sources materially disagree.
- SINGLE_MODALITY: evidence is available from only one relevant modality.
- UNCERTAIN: evidence is insufficient, ambiguous, or unreliable.

When evidence is insufficient, the system should say so and request clarification or additional records rather than presenting speculation as fact.

## 6. Security and privacy requirements
- Use least-privilege, department- and record-level access controls as the application evolves.
- Never commit credentials, access tokens, private records, or real personal data.
- Validate uploads and enforce file-size/type limits.
- Treat extracted document text as untrusted input; it must not override system instructions or permissions.
- Keep secrets in environment variables or an approved secret manager.
- Include auditability, retention, backup, and deployment review before any real government use.
- Public repository contents must use synthetic/sample data only.

## 7. Evaluation and testing
- Unit tests for configuration, validation, access checks, citation formatting, and uncertainty handling.
- Integration tests for API workflows using synthetic fixtures.
- Evaluate retrieval relevance, citation correctness, extraction quality, latency, and language performance on a documented test set.
- Measure unsupported-answer rate and ensure the system can abstain.
- Do not claim production readiness based solely on passing unit tests.

## 8. Checkpoints
1. Foundation: specification, configuration, dependency manifest, label taxonomy, tests.
2. Backend: FastAPI application, health endpoint, structured schemas.
3. Ingestion: text/PDF extraction and safe upload validation.
4. Retrieval and RAG: indexing, evidence retrieval, cited answers, abstention.
5. Audio/video: transcription and segment-level provenance.
6. Frontend: accessible web interface and API integration.
7. Evidence workflows: comparison, uncertainty, and report generation.
8. Security/evaluation: authorization, audit events, evaluation suite, threat review.
9. Integration: end-to-end tests, run instructions, limitations, and release checklist.

## 9. Acceptance criteria for Checkpoint 1
- Configuration loads from the repository's YAML file.
- Required configuration sections and uncertainty labels are present.
- Settings can be overridden with environment variables.
- Tests run without downloading AI models or using paid APIs.
- No secrets or real government data are committed.


## 10. Checkpoint 7 workflow contract

- `POST /api/v1/evidence/compare` searches the local document chunks and saved transcript segments independently, then returns grouped passages with source IDs and page/chunk or segment/timestamp provenance.
- `POST /api/v1/reports/draft` assembles a Markdown draft from retrieved passages. Each included passage has a stable in-report evidence label and a source location; the draft includes reviewer actions and limitations.
- Evidence coverage and truth assessment are separate. Results in both modalities mean both modalities returned matches, not that the sources agree. A reviewer must compare the original sources before marking a claim MATCH, PARTIAL, or CONFLICT.
- Empty retrieval results must be described as “no matching evidence retrieved,” not as proof that evidence does not exist.
- Scores are lexical ranking signals, not calibrated confidence or probabilities. Human review is mandatory before operational use.
