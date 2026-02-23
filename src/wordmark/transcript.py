"""Operation transcript writer for auditability."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from wordmark.config import AppConfig
from wordmark.models import OperationResult


def append_transcript(config: AppConfig, result: OperationResult) -> Path:
    transcript = Path(config.transcript_path)
    transcript.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(result)
    payload["path"] = str(result.path)
    with transcript.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
    return transcript
