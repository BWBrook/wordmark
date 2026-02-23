"""Sidecar artifact writers used for review-friendly outputs in Git."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from wordmark.config import AppConfig


def _resolve_template(template: str, stem: str) -> Path:
    return Path(template.format(stem=stem))


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_text(path: Path, payload: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def render_sidecar_paths(config: AppConfig, doc_path: Path) -> dict[str, Path]:
    stem = doc_path.stem
    paths = config.sidecar.paths
    return {
        "text": _resolve_template(paths.text, stem),
        "comments": _resolve_template(paths.comments, stem),
        "revisions": _resolve_template(paths.revisions, stem),
        "xml_manifest": _resolve_template(paths.xml_manifest, stem),
        "report": _resolve_template(paths.report, stem),
        "render_diff": _resolve_template(paths.render_diff, stem),
    }
