"""Models for Markdown/Quarto manuscript collaboration workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = 1


@dataclass(slots=True)
class RoundManifest:
    schema_version: int
    round_id: str
    created_at: str
    source_path: str
    source_hash_sha256: str
    build_cmd: str
    artifacts: dict[str, Any]
    git: dict[str, Any]
    defaults: dict[str, Any]


@dataclass(slots=True)
class FeedbackEvent:
    event_id: str
    channel: str
    kind: str
    severity: str
    author: str
    created_at: str
    anchor: dict[str, Any] = field(default_factory=dict)
    content: dict[str, Any] = field(default_factory=dict)
    trace: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FeedbackBundle:
    schema_version: int
    round_id: str
    events: list[FeedbackEvent] = field(default_factory=list)
    counts: dict[str, Any] = field(default_factory=dict)
    ingestion_warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SafeEditProposal:
    proposal_id: str
    file: str
    find_text: str
    replace_text: str
    match_policy: str
    status: str
    origin_event_ids: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
