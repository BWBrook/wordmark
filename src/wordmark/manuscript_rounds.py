"""Round preparation and status helpers for manuscript workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from typing import Any, Sequence

from wordmark.manuscript_models import RoundManifest, SCHEMA_VERSION
from wordmark.sidecar import write_json


def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _safe_round_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("-")
    return cleaned or "round"


def _default_round_id(source: Path) -> str:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    return _safe_round_id(f"{source.stem}_{stamp}")


def _parse_formats(formats: Sequence[str] | str) -> list[str]:
    if isinstance(formats, str):
        items = [token.strip().lower() for token in formats.split(",")]
    else:
        items = [str(token).strip().lower() for token in formats]
    allowed = {"docx", "pdf"}
    parsed = [fmt for fmt in items if fmt]
    if not parsed:
        raise ValueError("At least one output format must be provided")
    unknown = sorted({fmt for fmt in parsed if fmt not in allowed})
    if unknown:
        raise ValueError(f"Unsupported format(s): {', '.join(unknown)}")
    deduped: list[str] = []
    for fmt in parsed:
        if fmt not in deduped:
            deduped.append(fmt)
    return deduped


def _run_shell(command: str, *, cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(
        ["bash", "-lc", command],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return {
        "command": command,
        "cwd": str(cwd),
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _git_value(args: list[str], *, cwd: Path) -> str | None:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def _git_metadata(*, cwd: Path) -> dict[str, Any]:
    return {
        "repo_root": _git_value(["rev-parse", "--show-toplevel"], cwd=cwd),
        "branch": _git_value(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd),
        "head_sha": _git_value(["rev-parse", "HEAD"], cwd=cwd),
    }


def _detect_artifact(round_dir: Path, fmt: str) -> tuple[Path | None, list[str]]:
    warnings: list[str] = []
    expected = round_dir / f"rendered.{fmt}"
    if expected.exists():
        return expected, warnings

    matches = sorted(round_dir.rglob(f"*.{fmt}"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not matches:
        return None, warnings
    if len(matches) > 1:
        warnings.append(f"Multiple .{fmt} files found; using newest: {matches[0].name}")
    return matches[0], warnings


def prepare_round(
    source: Path,
    *,
    build_cmd: str | None,
    formats: Sequence[str] | str,
    out_root: Path,
    round_id: str | None,
) -> dict[str, Any]:
    if source.suffix.lower() not in {".md", ".qmd"}:
        raise ValueError("Source must be a .md or .qmd file")

    selected_formats = _parse_formats(formats)
    resolved_round_id = _safe_round_id(round_id) if round_id else _default_round_id(source)
    round_dir = (out_root / resolved_round_id).resolve()
    round_dir.mkdir(parents=True, exist_ok=True)
    if any(round_dir.iterdir()):
        raise ValueError(f"Round directory is not empty: {round_dir}")

    source = source.resolve()
    snapshot_path = round_dir / f"source_snapshot{source.suffix.lower()}"
    shutil.copy2(source, snapshot_path)

    commands: list[dict[str, Any]] = []
    warnings: list[str] = []

    if build_cmd is None:
        if source.suffix.lower() != ".qmd":
            raise ValueError("For .md sources, provide --build-cmd")
        for fmt in selected_formats:
            output_name = f"rendered.{fmt}"
            cmd = (
                f"quarto render {shlex.quote(str(source))} --to {fmt} "
                f"--output {shlex.quote(output_name)} --output-dir {shlex.quote(str(round_dir))}"
            )
            run = _run_shell(cmd, cwd=source.parent)
            commands.append(run)
            if run["exit_code"] != 0:
                raise RuntimeError(f"Build command failed for format {fmt}: {run['stderr']}")
        resolved_build_cmd = "quarto render (default multi-format)"
    else:
        placeholders = {
            "input": str(source),
            "input_q": shlex.quote(str(source)),
            "outdir": str(round_dir),
            "outdir_q": shlex.quote(str(round_dir)),
            "round_id": resolved_round_id,
            "docx_out": str(round_dir / "rendered.docx"),
            "docx_out_q": shlex.quote(str(round_dir / "rendered.docx")),
            "pdf_out": str(round_dir / "rendered.pdf"),
            "pdf_out_q": shlex.quote(str(round_dir / "rendered.pdf")),
        }
        try:
            rendered_command = build_cmd.format_map(placeholders)
        except KeyError as exc:
            raise ValueError(f"Unknown placeholder in --build-cmd: {exc}") from exc

        run = _run_shell(rendered_command, cwd=source.parent)
        commands.append(run)
        if run["exit_code"] != 0:
            raise RuntimeError(f"Build command failed: {run['stderr']}")
        resolved_build_cmd = build_cmd

    artifacts: dict[str, Any] = {
        "source_snapshot": {
            "path": str(snapshot_path.relative_to(round_dir)),
            "sha256": _sha256_file(snapshot_path),
            "bytes": snapshot_path.stat().st_size,
        }
    }
    for fmt in selected_formats:
        artifact_path, artifact_warnings = _detect_artifact(round_dir, fmt)
        warnings.extend(artifact_warnings)
        if artifact_path is None:
            warnings.append(f"Requested output format not found after build: {fmt}")
            continue
        artifacts[fmt] = {
            "path": str(artifact_path.relative_to(round_dir)),
            "sha256": _sha256_file(artifact_path),
            "bytes": artifact_path.stat().st_size,
        }

    manifest = RoundManifest(
        schema_version=SCHEMA_VERSION,
        round_id=resolved_round_id,
        created_at=_now_utc(),
        source_path=str(source),
        source_hash_sha256=_sha256_file(source),
        build_cmd=resolved_build_cmd,
        artifacts=artifacts,
        git=_git_metadata(cwd=source.parent),
        defaults={
            "canonical_source": "qmd_md",
            "comment_sink": "sidecar_json",
            "hybrid_mode": True,
        },
    )

    manifest_path = write_json(round_dir / "manifest.json", asdict(manifest))
    report_payload = {
        "schema_version": SCHEMA_VERSION,
        "round_id": resolved_round_id,
        "round_dir": str(round_dir),
        "commands": commands,
        "warnings": warnings,
        "manifest": str(manifest_path),
    }
    report_path = write_json(round_dir / "prepare.report.json", report_payload)
    return {
        "schema_version": SCHEMA_VERSION,
        "round_id": resolved_round_id,
        "round_dir": str(round_dir),
        "manifest": str(manifest_path),
        "report": str(report_path),
        "warnings": warnings,
        "artifacts": artifacts,
    }


def load_manifest(round_dir: Path) -> dict[str, Any]:
    manifest_path = round_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def manuscript_status(round_dir: Path) -> dict[str, Any]:
    manifest_path = round_dir / "manifest.json"
    bundle_path = round_dir / "feedback.bundle.json"
    safe_edits_path = round_dir / "proposed.safe_edits.json"
    summary_path = round_dir / "review_summary.md"

    stages = {
        "prepare": manifest_path.exists(),
        "collect": bundle_path.exists(),
        "synthesize": safe_edits_path.exists() and summary_path.exists(),
    }

    counts: dict[str, Any] = {"events": 0, "channels": {}, "safe_edit_status": {}}
    warnings: list[str] = []

    if bundle_path.exists():
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        events = bundle.get("events", [])
        counts["events"] = len(events)
        channel_counts: dict[str, int] = {}
        for event in events:
            if not isinstance(event, dict):
                continue
            channel = str(event.get("channel", "unknown"))
            channel_counts[channel] = channel_counts.get(channel, 0) + 1
        counts["channels"] = channel_counts
        if isinstance(bundle.get("ingestion_warnings"), list):
            warnings.extend(str(item) for item in bundle["ingestion_warnings"])

    if safe_edits_path.exists():
        safe = json.loads(safe_edits_path.read_text(encoding="utf-8"))
        proposals = safe.get("proposals", [])
        status_counts: dict[str, int] = {}
        for proposal in proposals:
            if not isinstance(proposal, dict):
                continue
            status = str(proposal.get("status", "unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1
        counts["safe_edit_status"] = status_counts

    return {
        "schema_version": SCHEMA_VERSION,
        "round_dir": str(round_dir),
        "stages": stages,
        "complete": all(stages.values()),
        "counts": counts,
        "warnings": warnings,
    }
