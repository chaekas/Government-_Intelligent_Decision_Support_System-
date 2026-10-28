"""Schemas for non-sensitive application metadata."""
from pydantic import BaseModel, ConfigDict, Field


class AppInfoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    default_language: str
    supported_languages: list[str] = Field(min_length=1)
    environment: str
    model_mode: str
    remote_apis_enabled: bool
