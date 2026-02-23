"""Shared JSON output helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def dumps(value: Any) -> str:
    return json.dumps(_normalize(value), indent=2, ensure_ascii=True, sort_keys=True)
