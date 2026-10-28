from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import AppSettings, load_app_config

ROOT = Path(__file__).resolve().parents[1]


def test_default_configuration_loads_required_sections() -> None:
    config = load_app_config(ROOT / "config.yaml")
    assert {"app", "api", "storage", "models", "retrieval", "security", "evidence"}.issubset(config)
    assert config["models"]["mode"] == "mock"
    assert config["models"]["allow_remote_apis"] is False


def test_evidence_outcome_labels_include_uncertainty() -> None:
    config = load_app_config(ROOT / "config.yaml")
    labels = config["evidence"]["outcome_labels"]
    assert "UNCERTAIN" in labels
    assert "CONFLICT" in labels


def test_missing_required_section_is_rejected(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.yaml"
    invalid_path.write_text("app: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required sections"):
        load_app_config(invalid_path)


def test_environment_variables_override_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IDSS_API_PORT", "8123")
    monkeypatch.setenv("IDSS_MODELS_MODE", "mock")
    settings = AppSettings(_env_file=None)
    assert settings.api_port == 8123
    assert settings.models_mode == "mock"


def test_labels_file_is_valid_json_and_has_unknown_options() -> None:
    labels = json.loads((ROOT / "data" / "labels.json").read_text(encoding="utf-8"))
    assert "unknown" in labels["document_types"]
    assert "unknown" in labels["topic_families"]
    assert "UNCERTAIN" in labels["evidence_outcomes"]
