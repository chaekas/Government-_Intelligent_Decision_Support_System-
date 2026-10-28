"""FastAPI application entry point for the Government IDSS foundation."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import environment_summary, load_app_config
from app.schemas.health import HealthResponse
from app.schemas.meta import AppInfoResponse

CONFIG = load_app_config()
APP_INFO = CONFIG["app"]

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
