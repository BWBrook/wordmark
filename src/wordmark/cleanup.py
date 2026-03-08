"""Artifact cleanup helpers shared by CLI commands."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def collect_artifact_files(
    root: Path,
    *,
    older_than_days: int | None,
    keep_names: set[str],
    keep_transcripts: bool,
) -> list[Path]:
    if not root.exists():
        return []

    cutoff_ts: float | None = None
    if older_than_days is not None:
        cutoff_ts = datetime.now(tz=timezone.utc).timestamp() - float(older_than_days * 86400)

    selected: list[Path] = []
    for candidate in sorted(root.rglob("*")):
        if candidate.is_dir():
            continue

        if candidate.name in keep_names:
            continue

        relative = candidate.relative_to(root)
        if keep_transcripts and relative.parts and relative.parts[0] == "transcripts":
            continue

        if cutoff_ts is not None:
            try:
                modified_ts = candidate.stat().st_mtime
            except OSError:
                continue
            if modified_ts > cutoff_ts:
                continue

        selected.append(candidate)
    return selected


def prune_empty_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []

    removed: list[Path] = []
    directories = sorted((item for item in root.rglob("*") if item.is_dir()), key=lambda item: len(item.parts), reverse=True)
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            continue
        removed.append(directory)
    return removed


def safe_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def to_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
