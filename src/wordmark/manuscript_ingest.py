"""Feedback ingestion for manuscript collaboration rounds."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from wordmark.external_tools import gh_auth_available, gh_available
from wordmark.manuscript_models import FeedbackBundle, FeedbackEvent, SCHEMA_VERSION
from wordmark.manuscript_rounds import load_manifest
from wordmark.sidecar import write_json, write_text
from wordmark import ooxml_engine

GH_TIMEOUT_S = 60
GIT_TIMEOUT_S = 15


def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _infer_severity(text: str) -> str:
    token = text.lower()
    if any(k in token for k in ["critical", "major", "must", "fatal", "blocking"]):
        return "high"
    if any(k in token for k in ["minor", "nit", "optional", "polish", "typo"]):
        return "low"
    return "medium"


def _extract_suggestion_block(text: str) -> str | None:
    match = re.search(r"```suggestion\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    suggestion = match.group(1).rstrip("\n")
    return suggestion if suggestion else None


def _parse_notes(notes_path: Path) -> list[FeedbackEvent]:
    lines = notes_path.read_text(encoding="utf-8").splitlines()
    events: list[FeedbackEvent] = []
    for line_no, line in enumerate(lines, start=1):
        raw = line.strip()
        if not raw:
            continue
        if raw.startswith("#"):
            continue
        text = re.sub(r"^[-*+]\s+", "", raw)
        text = re.sub(r"^\d+\.\s+", "", text)
        if not text:
            continue

        anchor: dict[str, Any] = {
            "file": str(notes_path),
            "line_start": line_no,
            "line_end": line_no,
        }
        anchored = re.match(
            r"^(?P<file>[^:\s]+\.(?:md|qmd)):(?P<line_start>\d+)(?:-(?P<line_end>\d+))?:\s*(?P<body>.+)$",
            text,
        )
        if anchored:
            anchor = {
                "file": anchored.group("file"),
                "line_start": int(anchored.group("line_start")),
                "line_end": int(anchored.group("line_end") or anchored.group("line_start")),
            }
            text = anchored.group("body").strip()

        events.append(
            FeedbackEvent(
                event_id="",
                channel="notes_md",
                kind="comment",
                severity=_infer_severity(text),
                author="notes",
                created_at=_now_utc(),
                anchor=anchor,
                content={
                    "summary": text,
                },
                trace={
                    "source_ref": f"{notes_path.name}:{line_no}",
                },
            )
        )
    return events


def _parse_pr_number(value: str) -> int:
    stripped = value.strip()
    if stripped.isdigit():
        return int(stripped)
    match = re.search(r"/pull/(\d+)", stripped)
    if match:
        return int(match.group(1))
    raise ValueError(f"Unable to parse PR number from: {value}")


def _origin_repo_slug(cwd: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    origin = proc.stdout.strip()
    if not origin:
        return None

    https_match = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)(?:\.git)?$", origin)
    if https_match:
        owner = https_match.group(1)
        repo = https_match.group(2)
        return f"{owner}/{repo}"
    return None


def _gh_json(args: list[str], *, cwd: Path) -> tuple[Any, str | None]:
    try:
        proc = subprocess.run(["gh", *args], cwd=cwd, capture_output=True, text=True, timeout=GH_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None, f"gh command timed out after {GH_TIMEOUT_S}s"
    if proc.returncode != 0:
        return None, proc.stderr.strip() or proc.stdout.strip() or "gh command failed"
    try:
        return json.loads(proc.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON from gh command: {exc}"


def _collect_github_pr_feedback(*, from_pr: str, cwd: Path) -> tuple[list[FeedbackEvent], list[str]]:
    warnings: list[str] = []
    events: list[FeedbackEvent] = []

    if not gh_available():
        warnings.append("gh CLI is not installed; skipping GitHub PR ingestion.")
        return events, warnings

    if not gh_auth_available(cwd=cwd):
        warnings.append("gh auth is not available; skipping GitHub PR ingestion.")
        return events, warnings

    repo_slug = _origin_repo_slug(cwd)
    if repo_slug is None:
        warnings.append("Could not determine GitHub repo slug from remote.origin.url.")
        return events, warnings

    pr_number = _parse_pr_number(from_pr)

    pull_comments, pull_err = _gh_json(
        ["api", f"repos/{repo_slug}/pulls/{pr_number}/comments", "--paginate"],
        cwd=cwd,
    )
    if pull_err:
        warnings.append(f"Failed to fetch PR review comments: {pull_err}")
        pull_comments = []

    issue_comments, issue_err = _gh_json(
        ["api", f"repos/{repo_slug}/issues/{pr_number}/comments", "--paginate"],
        cwd=cwd,
    )
    if issue_err:
        warnings.append(f"Failed to fetch PR issue comments: {issue_err}")
        issue_comments = []

    if isinstance(pull_comments, list):
        for item in pull_comments:
            if not isinstance(item, dict):
                continue
            body = str(item.get("body", "")).strip()
            if not body:
                continue
            suggestion = _extract_suggestion_block(body)
            line = item.get("line")
            start_line = item.get("start_line")
            line_start = int(start_line or line or item.get("original_line") or 0)
            line_end = int(line or line_start or 0)
            path_value = str(item.get("path", ""))
            events.append(
                FeedbackEvent(
                    event_id="",
                    channel="github_pr",
                    kind="suggestion" if suggestion else "comment",
                    severity=_infer_severity(body),
                    author=str((item.get("user") or {}).get("login", "unknown")),
                    created_at=str(item.get("created_at") or _now_utc()),
                    anchor={
                        "file": path_value,
                        "line_start": line_start if line_start > 0 else None,
                        "line_end": line_end if line_end > 0 else None,
                    },
                    content={
                        "summary": body.splitlines()[0][:400],
                        "proposed_text": suggestion,
                        "rationale": body,
                    },
                    trace={
                        "source_ref": f"pull_comment:{item.get('id')}",
                        "url": item.get("html_url"),
                    },
                )
            )

    if isinstance(issue_comments, list):
        for item in issue_comments:
            if not isinstance(item, dict):
                continue
            body = str(item.get("body", "")).strip()
            if not body:
                continue
            events.append(
                FeedbackEvent(
                    event_id="",
                    channel="github_pr",
                    kind="comment",
                    severity=_infer_severity(body),
                    author=str((item.get("user") or {}).get("login", "unknown")),
                    created_at=str(item.get("created_at") or _now_utc()),
                    anchor={},
                    content={
                        "summary": body.splitlines()[0][:400],
                        "rationale": body,
                    },
                    trace={
                        "source_ref": f"issue_comment:{item.get('id')}",
                        "url": item.get("html_url"),
                    },
                )
            )

    return events, warnings


def _comment_signature(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("author", "")),
        str(item.get("initials", "")),
        str(item.get("text", "")),
    )


def _revision_signature(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("type", "")),
        str(item.get("author", "")),
        str(item.get("text", "")),
    )


def _counter_from_items(items: list[dict[str, Any]], signature_fn: Any) -> Counter[Any]:
    counter: Counter[Any] = Counter()
    for item in items:
        if isinstance(item, dict):
            counter[signature_fn(item)] += 1
    return counter


def _subtract_items(
    reviewed: list[dict[str, Any]],
    baseline_counter: Counter[Any],
    signature_fn: Any,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: Counter[Any] = Counter()
    for item in reviewed:
        if not isinstance(item, dict):
            continue
        key = signature_fn(item)
        seen[key] += 1
        if seen[key] <= baseline_counter.get(key, 0):
            continue
        out.append(item)
    return out


def _collect_docx_feedback(*, baseline_docx: Path | None, reviewed_docx: Path) -> tuple[list[FeedbackEvent], list[str]]:
    warnings: list[str] = []
    events: list[FeedbackEvent] = []

    reviewed_data = ooxml_engine.list_review(reviewed_docx, text_mode="review-visible")
    reviewed_comments = reviewed_data.get("comments", [])
    reviewed_revisions = reviewed_data.get("revisions", [])

    baseline_comments: list[dict[str, Any]] = []
    baseline_revisions: list[dict[str, Any]] = []
    if baseline_docx is not None and baseline_docx.exists():
        baseline_data = ooxml_engine.list_review(baseline_docx, text_mode="review-visible")
        baseline_comments = list(baseline_data.get("comments", []))
        baseline_revisions = list(baseline_data.get("revisions", []))
    else:
        warnings.append("Baseline DOCX missing for comparison; treating all review state as new.")

    new_comments = _subtract_items(
        list(reviewed_comments),
        _counter_from_items(baseline_comments, _comment_signature),
        _comment_signature,
    )
    new_revisions = _subtract_items(
        list(reviewed_revisions),
        _counter_from_items(baseline_revisions, _revision_signature),
        _revision_signature,
    )

    for item in new_comments:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        events.append(
            FeedbackEvent(
                event_id="",
                channel="docx_comment",
                kind="comment",
                severity=_infer_severity(text),
                author=str(item.get("author") or "unknown"),
                created_at=str(item.get("created_at") or _now_utc()),
                anchor={},
                content={
                    "summary": text,
                },
                trace={
                    "source_ref": f"docx_comment:{item.get('id')}",
                    "docx_path": str(reviewed_docx),
                },
            )
        )

    for item in new_revisions:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        rtype = str(item.get("type", "revision"))
        events.append(
            FeedbackEvent(
                event_id="",
                channel="docx_revision",
                kind="suggestion",
                severity="medium",
                author=str(item.get("author") or "unknown"),
                created_at=str(item.get("created_at") or _now_utc()),
                anchor={},
                content={
                    "summary": f"{rtype}: {text}",
                    "rationale": "Imported from DOCX tracked changes review state.",
                },
                trace={
                    "source_ref": f"docx_revision:{item.get('revision_id')}",
                    "docx_path": str(reviewed_docx),
                },
            )
        )

    return events, warnings


def _count_events(events: list[FeedbackEvent]) -> dict[str, Any]:
    by_channel: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for event in events:
        by_channel[event.channel] = by_channel.get(event.channel, 0) + 1
        by_severity[event.severity] = by_severity.get(event.severity, 0) + 1
        by_kind[event.kind] = by_kind.get(event.kind, 0) + 1
    return {
        "total": len(events),
        "by_channel": by_channel,
        "by_severity": by_severity,
        "by_kind": by_kind,
    }


def _timeline_markdown(bundle: FeedbackBundle) -> str:
    lines: list[str] = []
    lines.append(f"# Feedback Timeline — {bundle.round_id}")
    lines.append("")
    lines.append(f"- Total events: {bundle.counts.get('total', 0)}")
    lines.append("")

    for event in bundle.events:
        summary = str(event.content.get("summary", "")).strip()
        source_ref = str(event.trace.get("source_ref", ""))
        anchor_bits: list[str] = []
        if event.anchor.get("file"):
            anchor_bits.append(str(event.anchor["file"]))
        if event.anchor.get("line_start"):
            line_end = event.anchor.get("line_end") or event.anchor.get("line_start")
            anchor_bits.append(f"L{event.anchor['line_start']}-{line_end}")
        anchor_str = f" ({', '.join(anchor_bits)})" if anchor_bits else ""
        lines.append(
            f"- [{event.severity}] `{event.channel}`/{event.kind} by `{event.author}`{anchor_str}: "
            f"{summary} ({source_ref})"
        )
    lines.append("")
    return "\n".join(lines)


def _event_sort_key(event: FeedbackEvent) -> tuple[str, str, str, str, str]:
    summary = str(event.content.get("summary", "")).strip()
    source_ref = str(event.trace.get("source_ref", ""))
    return (
        event.created_at,
        event.channel,
        source_ref,
        event.author,
        summary,
    )


def collect_feedback(
    round_dir: Path,
    *,
    from_pr: str | None,
    notes_path: Path | None,
    reviewed_docx: Path | None,
) -> dict[str, Any]:
    manifest = load_manifest(round_dir)
    warnings: list[str] = []
    events: list[FeedbackEvent] = []

    if from_pr:
        github_events, github_warnings = _collect_github_pr_feedback(from_pr=from_pr, cwd=round_dir)
        events.extend(github_events)
        warnings.extend(github_warnings)

    if notes_path is not None:
        events.extend(_parse_notes(notes_path))

    if reviewed_docx is not None:
        baseline_docx: Path | None = None
        docx_meta = manifest.get("artifacts", {}).get("docx")
        if isinstance(docx_meta, dict) and isinstance(docx_meta.get("path"), str):
            baseline_docx = round_dir / str(docx_meta["path"])
        docx_events, docx_warnings = _collect_docx_feedback(
            baseline_docx=baseline_docx,
            reviewed_docx=reviewed_docx,
        )
        events.extend(docx_events)
        warnings.extend(docx_warnings)

    events = sorted(events, key=_event_sort_key)
    for idx, event in enumerate(events, start=1):
        event.event_id = f"evt-{idx:05d}"

    bundle = FeedbackBundle(
        schema_version=SCHEMA_VERSION,
        round_id=str(manifest.get("round_id", round_dir.name)),
        events=events,
        counts=_count_events(events),
        ingestion_warnings=warnings,
    )

    bundle_path = write_json(
        round_dir / "feedback.bundle.json",
        {
            "schema_version": bundle.schema_version,
            "round_id": bundle.round_id,
            "events": [asdict(event) for event in bundle.events],
            "counts": bundle.counts,
            "ingestion_warnings": bundle.ingestion_warnings,
        },
    )
    timeline_path = write_text(round_dir / "feedback.timeline.md", _timeline_markdown(bundle))
    report_path = write_json(
        round_dir / "collect.report.json",
        {
            "schema_version": SCHEMA_VERSION,
            "round_id": bundle.round_id,
            "bundle": str(bundle_path),
            "timeline": str(timeline_path),
            "warnings": warnings,
            "counts": bundle.counts,
            "inputs": {
                "from_pr": from_pr,
                "notes_path": str(notes_path) if notes_path else None,
                "reviewed_docx": str(reviewed_docx) if reviewed_docx else None,
            },
        },
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "round_id": bundle.round_id,
        "bundle": str(bundle_path),
        "timeline": str(timeline_path),
        "report": str(report_path),
        "counts": bundle.counts,
        "warnings": warnings,
    }
