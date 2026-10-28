"""Configuration loading and environment-backed application settings."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPOSITORY_ROOT / "config.yaml"


class AppSettings(BaseSettings):
    """Runtime overrides; environment variables use the IDSS_ prefix."""

    model_config = SettingsConfigDict(
        env_prefix="IDSS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_environment: str = "development"
    app_debug: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    models_mode: str = "mock"
    models_allow_remote_apis: bool = False


def load_app_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load YAML configuration and validate the required top-level sections."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            data = yaml.safe_load(config_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Configuration file not found: {config_path}") from exc

    if not isinstance(data, dict):
        raise ValueError("Configuration must be a YAML mapping.")

    required_sections = {"app", "api", "storage", "models", "retrieval", "security", "evidence"}
    missing = sorted(required_sections.difference(data.keys()))
    if missing:
        raise ValueError(f"Configuration is missing required sections: {', '.join(missing)}")

    if not isinstance(data["evidence"].get("outcome_labels"), list) or not data["evidence"]["outcome_labels"]:
        raise ValueError("evidence.outcome_labels must be a non-empty list.")

    return data


def get_settings() -> AppSettings:
    """Create settings using defaults, .env, and environment variable overrides."""
    return AppSettings()


def environment_summary() -> dict[str, str | bool | int]:
    """Return safe, non-secret runtime details for diagnostics."""
    settings = get_settings()
    return {
        "environment": settings.app_environment,
        "debug": settings.app_debug,
        "api_host": settings.api_host,
        "api_port": settings.api_port,
        "models_mode": settings.models_mode,
        "remote_apis_enabled": settings.models_allow_remote_apis,
    }
