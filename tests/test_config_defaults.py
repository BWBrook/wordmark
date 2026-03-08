from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import yaml

from wordmark.config import AppConfig, load_config


def _normalize(value: object) -> object:
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    return value


def test_missing_config_uses_dataclass_defaults(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "missing-wordmark.yaml")
    assert cfg.fidelity_profiles == ("business-docs", "review-edit")
    assert cfg.engine_order == ("ooxml", "uno")


def test_repo_wordmark_yaml_matches_code_defaults() -> None:
    repo_cfg = yaml.safe_load(Path("wordmark.yaml").read_text(encoding="utf-8"))
    code_defaults = _normalize(asdict(AppConfig()))
    assert repo_cfg == code_defaults
