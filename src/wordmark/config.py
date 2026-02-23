"""Configuration loading for Wordmark."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class SidecarPaths:
    text: str = "artifacts/{stem}.text.md"
    comments: str = "artifacts/{stem}.comments.json"
    revisions: str = "artifacts/{stem}.revisions.json"
    xml_manifest: str = "artifacts/{stem}.xml-manifest.json"
    report: str = "artifacts/{stem}.report.json"
    render_diff: str = "artifacts/{stem}.render"


@dataclass(slots=True)
class SidecarConfig:
    enabled: bool = True
    paths: SidecarPaths = field(default_factory=SidecarPaths)


@dataclass(slots=True)
class AppConfig:
    default_author: str = "Barry Brook"
    default_initials: str = "BB"
    track_changes_default: bool = True
    engine_order: tuple[str, ...] = ("ooxml", "uno")
    fidelity_profiles: tuple[str, ...] = ("business-docs",)
    sidecar: SidecarConfig = field(default_factory=SidecarConfig)
    transcript_path: str = "artifacts/transcripts/operations.jsonl"


DEFAULT_CONFIG_PATH = Path("wordmark.yaml")


def _merge_dict(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge_dict(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path | None = None) -> AppConfig:
    cfg_path = path or DEFAULT_CONFIG_PATH
    raw = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    defaults = {
        "default_author": "Barry Brook",
        "default_initials": "BB",
        "track_changes_default": True,
        "engine_order": ["ooxml", "uno"],
        "fidelity_profiles": ["business-docs"],
        "sidecar": {
            "enabled": True,
            "paths": {
                "text": "artifacts/{stem}.text.md",
                "comments": "artifacts/{stem}.comments.json",
                "revisions": "artifacts/{stem}.revisions.json",
                "xml_manifest": "artifacts/{stem}.xml-manifest.json",
                "report": "artifacts/{stem}.report.json",
                "render_diff": "artifacts/{stem}.render",
            },
        },
        "transcript_path": "artifacts/transcripts/operations.jsonl",
    }
    merged = _merge_dict(defaults, raw)
    paths = SidecarPaths(**merged["sidecar"]["paths"])
    sidecar = SidecarConfig(enabled=bool(merged["sidecar"]["enabled"]), paths=paths)
    return AppConfig(
        default_author=str(merged["default_author"]),
        default_initials=str(merged["default_initials"]),
        track_changes_default=bool(merged["track_changes_default"]),
        engine_order=tuple(str(x) for x in merged["engine_order"]),
        fidelity_profiles=tuple(str(x) for x in merged["fidelity_profiles"]),
        sidecar=sidecar,
        transcript_path=str(merged["transcript_path"]),
    )
