"""Core types used by review and mutation workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Anchor:
    selector: str
    paragraph_index: int | None = None
    text_hint: str | None = None


@dataclass(slots=True)
class CommentRecord:
    comment_id: int
    author: str
    initials: str
    created_at: str | None
    text: str
    anchor: Anchor | None = None


@dataclass(slots=True)
class RevisionRecord:
    type: str
    revision_id: str | None
    author: str | None
    created_at: str | None
    text: str


@dataclass(slots=True)
class InspectReport:
    path: Path
    paragraph_count: int
    text_mode: str
    text_value: str
    comments: list[CommentRecord] = field(default_factory=list)
    revisions: list[RevisionRecord] = field(default_factory=list)


@dataclass(slots=True)
class OperationResult:
    command: str
    path: Path
    engine: str
    changed: bool
    author: str
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def now(command: str, path: Path, engine: str, changed: bool, author: str, details: dict[str, Any] | None = None) -> "OperationResult":
        return OperationResult(
            command=command,
            path=path,
            engine=engine,
            changed=changed,
            author=author,
            timestamp=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            details=details or {},
        )
