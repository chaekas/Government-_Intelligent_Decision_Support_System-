# Checkpoint 8 Threat Review

## Scope and current state

This review covers the local-development FastAPI IDSS foundation, document and media uploads, local extracted text/transcripts, lexical search, report drafts, and the browser workspace. It is not a formal security assessment or approval for operational use.

## Assets to protect

- Uploaded documents, recordings, transcripts, and extracted text.
- Source identifiers, page/segment provenance, and generated report drafts.
- API tokens, environment configuration, and audit records.
- Integrity of evidence and traceability of reviewer actions.

## Threats and safeguards

| Threat | Current safeguard | Remaining gap |
| --- | --- | --- |
| Unauthenticated API use | If `IDSS_API_TOKEN` is configured, protected `/api/v1/*` endpoints require a bearer token. | Shared token is not user identity, rotation, SSO, or role-based access. Without the variable, local development remains unauthenticated. |
| Unauthorized cross-department/record access | None in the current file-based storage layer. | Must implement authenticated identities and enforce tenant/department and record permissions inside every data-access operation. |
| Secret leakage through logs | Audit events intentionally omit headers, request bodies, query strings, filenames, and extracted content. | Review server, proxy, hosting, and exception logs separately. |
| Malicious uploads | Existing extension, size, and basic file-signature validation. | Signature checks are not malware scanning, sandboxing, content disarm, or comprehensive parser hardening. |
| Prompt/document injection | Extracted text is currently searched lexically, not executed as instructions. | Any future LLM integration must treat source text as untrusted data and isolate system instructions/tools. |
| Evidence manipulation or mistaken conclusions | Source identifiers and page/segment references are retained; report drafts require human review. | Add tamper-evident provenance, reviewer identity, decision history, and source-integrity checks. |
| Audit log tampering or disk exhaustion | JSON Lines metadata events are appended locally. | No access controls, rotation, retention enforcement, centralized immutable storage, or alerting yet. |
| Sensitive data exposure | Repository excludes runtime data directories; guidance requires synthetic data. | Local files are not encrypted and the development server is not suitable for real government data. |
| Retrieval omissions or ranking bias | Deterministic synthetic evaluation cases and explicit heuristic-score limitations. | Current evaluation set is small and synthetic; it is not representative of production data or languages. |

## Safe local configuration

Set a long random token in the environment before starting the server:

- macOS/Linux: `export IDSS_API_TOKEN='replace-with-a-long-random-secret'`
- Windows PowerShell: `$env:IDSS_API_TOKEN = 'replace-with-a-long-random-secret'`

Then send `Authorization: Bearer <token>` to protected API endpoints. Do not commit the token to Git, place it in frontend JavaScript, or paste it into issue reports. The browser UI does not currently provide a secure token-entry/session mechanism; use the API docs or a properly designed authenticated client when token enforcement is enabled.

Audit output defaults to `data/audit/events.jsonl`; set `IDSS_AUDIT_LOG_PATH` to change it. Protect the file and its parent directory. Audit logging is enabled by default; `IDSS_AUDIT_EVENTS_ENABLED=false` is intended for isolated tests only.

## Release blockers before real government use

1. Integrate a supported identity provider (SSO/OIDC) and MFA where required.
2. Enforce department and record-level authorization in every read, search, transcript, and report workflow; test cross-tenant denial.
3. Store files and metadata in an access-controlled database/object store with encryption, backups, retention, and deletion policies.
4. Add malware scanning, parser isolation, rate limits, upload quotas, CSRF protections if cookie sessions are introduced, and abuse monitoring.
5. Move audit events to restricted, durable, tamper-evident storage with retention and monitoring.
6. Perform independent security, privacy, accessibility, and threat-model reviews.
7. Evaluate extraction, retrieval, citation correctness, abstention, latency, and English/Swahili performance on approved representative data.
8. Establish human approval, incident response, access reviews, disaster recovery, and change-management procedures.

**Conclusion:** Checkpoint 8 adds useful development safeguards and tests; it does not establish production readiness.
