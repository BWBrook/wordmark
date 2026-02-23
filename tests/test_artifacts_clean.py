from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from typer.testing import CliRunner

from wordmark.cli import app


def _write_file(path: Path, text: str, *, age_days: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if age_days > 0:
        ts = (datetime.now(tz=timezone.utc) - timedelta(days=age_days)).timestamp()
        os.utime(path, (ts, ts))
    return path


def test_artifacts_clean_preview_respects_age_filter(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    _write_file(artifacts_dir / ".gitkeep", "")
    old_sidecar = _write_file(artifacts_dir / "old.comments.json", "{}", age_days=10)
    new_sidecar = _write_file(artifacts_dir / "new.comments.json", "{}")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "artifacts",
            "clean",
            "--path",
            str(artifacts_dir),
            "--older-than-days",
            "7",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)

    assert payload["apply"] is False
    assert payload["matched_count"] == 1
    assert "old.comments.json" in payload["matched_files"]
    assert "new.comments.json" not in payload["matched_files"]
    assert ".gitkeep" not in payload["matched_files"]
    assert old_sidecar.exists()
    assert new_sidecar.exists()


def test_artifacts_clean_apply_can_keep_transcripts(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    _write_file(artifacts_dir / ".gitkeep", "")
    stale_sidecar = _write_file(artifacts_dir / "stale.revisions.json", "{}", age_days=9)
    transcript = _write_file(artifacts_dir / "transcripts" / "operations.jsonl", "{}", age_days=9)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "artifacts",
            "clean",
            "--path",
            str(artifacts_dir),
            "--older-than-days",
            "7",
            "--keep-transcripts",
            "--apply",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)

    assert payload["deleted_count"] == 1
    assert "stale.revisions.json" in payload["deleted_files"]
    assert stale_sidecar.exists() is False
    assert transcript.exists()
    assert (artifacts_dir / ".gitkeep").exists()


def test_artifacts_clean_apply_prunes_empty_directories(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    _write_file(artifacts_dir / ".gitkeep", "")
    nested_file = _write_file(artifacts_dir / "sample.render" / "page-1.png", "png-bytes")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "artifacts",
            "clean",
            "--path",
            str(artifacts_dir),
            "--apply",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)

    assert payload["deleted_count"] == 1
    assert "sample.render/page-1.png" in payload["deleted_files"]
    assert "sample.render" in payload["deleted_dirs"]
    assert nested_file.exists() is False
    assert (artifacts_dir / ".gitkeep").exists()
