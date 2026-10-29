"""Development security helpers: optional bearer auth and metadata-only audit events.

This is a foundation, not a complete identity or record-level authorization system.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse


def configured_api_token() -> str | None:
    """Return the configured shared API token, if present."""
    token = os.getenv("IDSS_API_TOKEN", "").strip()
    return token or None


def audit_enabled() -> bool:
    """Audit events are enabled by default and can be disabled for tests only."""
    return os.getenv("IDSS_AUDIT_EVENTS_ENABLED", "true").strip().casefold() not in {
        "0", "false", "no", "off"
    }


def request_requires_auth(path: str) -> bool:
    """Protect API routes while leaving health and safe application metadata public."""
    return path.startswith("/api/v1/") and path != "/api/v1/info"


def authorize_request(request: Request) -> bool:
    """Validate a shared bearer token using constant-time comparison.

    Shared-token auth does not identify an individual and does not implement
    department- or record-level authorization.
    """
    expected = configured_api_token()
    if expected is None:
        return True  # Local development compatibility; configure a token to enforce auth.
    header = request.headers.get("authorization", "")
    scheme, _, supplied = header.partition(" ")
    if scheme.casefold() != "bearer" or not supplied:
        return False
    return hmac.compare_digest(expected, supplied.strip())


def audit_path() -> Path:
    """Resolve audit output path; override with IDSS_AUDIT_LOG_PATH if needed."""
    raw = os.getenv("IDSS_AUDIT_LOG_PATH", "data/audit/events.jsonl")
    return Path(raw)


def write_audit_event(
    *,
    request_id: str,
    method: str,
    route: str,
    status_code: int,
    duration_ms: float,
    auth_required: bool,
    authorized: bool,
) -> None:
    """Append a compact event without tokens, query strings, bodies, or source text."""
    if not audit_enabled():
        return
    event: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "method": method,
        "route": route,
        "status_code": int(status_code),
        "duration_ms": round(max(0.0, duration_ms), 2),
        "auth_required": auth_required,
        "authorized": authorized,
        "actor": "bearer_token" if authorized and auth_required else "anonymous",
    }
    destination = audit_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def audit_route(request: Request) -> str:
    """Return the route template, not a raw URL that might contain record IDs."""
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str):
        return template
    # Do not include arbitrary path fragments before routing has selected a route.
    path = request.url.path
    if path.startswith("/api/"):
        return "/api/{unmatched}"
    return re.sub(r"[^/]+", "{segment}", path)


def new_request_id(request: Request) -> str:
    """Use a caller-provided request ID only if it is a conservative UUID-like token."""
    supplied = request.headers.get("x-request-id", "")
    if supplied and re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied):
        return supplied
    return str(uuid4())


def unauthorized_response() -> JSONResponse:
    """Return a generic response that does not disclose token configuration."""
    return JSONResponse(status_code=401, content={"detail": "Valid bearer token required."},
                        headers={"WWW-Authenticate": "Bearer"})
