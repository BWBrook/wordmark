"""Synthesis and safe-apply helpers for manuscript feedback bundles."""

from __future__ import annotations

import difflib
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from wordmark.manuscript_models import SCHEMA_VERSION, SafeEditProposal
from wordmark.sidecar import write_json, write_text


def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _source_drift_status(round_dir: Path, source: Path) -> dict[str, Any]:
    manifest_path = round_dir / "manifest.json"
    status: dict[str, Any] = {
        "checked": False,
        "drifted": False,
        "manifest": str(manifest_path),
        "expected_sha256": None,
        "current_sha256": None,
    }
    if not manifest_path.exists():
        status["reason"] = "manifest_missing"
        return status

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_hash = manifest.get("source_hash_sha256")
    if not isinstance(expected_hash, str) or not expected_hash:
        status["reason"] = "source_hash_missing"
        return status

    current_hash = _sha256_file(source)
    status.update(
        {
            "checked": True,
            "expected_sha256": expected_hash,
            "current_sha256": current_hash,
            "drifted": current_hash != expected_hash,
        }
    )
    manifest_source = manifest.get("source_path")
    if isinstance(manifest_source, str) and manifest_source:
        status["manifest_source_path"] = manifest_source
        status["source_path_match"] = Path(manifest_source).resolve() == source
    return status


def _extract_replace_directive(text: str) -> tuple[str, str] | None:
    patterns = [
        r"replace\s+['\"](.+?)['\"]\s+with\s+['\"](.+?)['\"]",
        r"`(.+?)`\s*->\s*`(.+?)`",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1), match.group(2)
    return None


def _line_slice(lines: list[str], start: int, end: int) -> str:
    if start < 1 or end < start:
        return ""
    if start > len(lines):
        return ""
    e = min(end, len(lines))
    return "".join(lines[start - 1 : e])


def _line_starts(lines: list[str]) -> list[int]:
    starts: list[int] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line)
    return starts


def _line_slice_with_span(lines: list[str], starts: list[int], start: int, end: int) -> tuple[str, tuple[int, int] | None]:
    text = _line_slice(lines, start, end)
    if not text:
        return "", None
    e = min(end, len(lines))
    span_start = starts[start - 1]
    span_end = starts[e - 1] + len(lines[e - 1])
    return text, (span_start, span_end)


def _span_details(line_start: int, line_end: int, span: tuple[int, int] | None) -> dict[str, Any]:
    details: dict[str, Any] = {"line_start": line_start, "line_end": line_end}
    if span is not None:
        details["span_start"] = span[0]
        details["span_end"] = span[1]
    return details


def _anchor_targets_source(anchor: dict[str, Any], source_path: Path) -> bool:
    raw_file = anchor.get("file")
    if not isinstance(raw_file, str) or not raw_file:
        return True
    anchor_path = Path(raw_file)
    return anchor_path == source_path or anchor_path.name == source_path.name


def _proposal_from_event(
    event: dict[str, Any],
    source_path: Path,
    source_text: str,
    source_lines: list[str],
    source_line_starts: list[int],
) -> SafeEditProposal | None:
    content = event.get("content")
    anchor = event.get("anchor")
    if not isinstance(content, dict):
        content = {}
    if not isinstance(anchor, dict):
        anchor = {}

    summary = str(content.get("summary", "")).strip()
    proposed_text = content.get("proposed_text")
    if not isinstance(proposed_text, str):
        proposed_text = None
    kind = str(event.get("kind", "comment"))
    event_id = str(event.get("event_id", ""))

    if kind == "suggestion" and proposed_text:
        line_start = anchor.get("line_start")
        line_end = anchor.get("line_end") or line_start
        if (
            isinstance(line_start, int)
            and isinstance(line_end, int)
            and line_start > 0
            and line_end > 0
            and _anchor_targets_source(anchor, source_path)
        ):
            current, span = _line_slice_with_span(source_lines, source_line_starts, line_start, line_end)
            if current:
                replacement = proposed_text
                if current.endswith("\n") and not replacement.endswith("\n"):
                    replacement = replacement + "\n"
                return SafeEditProposal(
                    proposal_id="",
                    file=str(source_path),
                    find_text=current,
                    replace_text=replacement,
                    match_policy="anchored_exact",
                    status="proposed",
                    origin_event_ids=[event_id],
                    details=_span_details(line_start, line_end, span),
                )

    candidate = _extract_replace_directive(summary)
    if candidate:
        find_text, replace_text = candidate
        line_start = anchor.get("line_start")
        line_end = anchor.get("line_end") or line_start
        if (
            isinstance(line_start, int)
            and isinstance(line_end, int)
            and line_start > 0
            and line_end > 0
            and _anchor_targets_source(anchor, source_path)
        ):
            current, span = _line_slice_with_span(source_lines, source_line_starts, line_start, line_end)
            if current:
                submatches = current.count(find_text)
                replacement = current.replace(find_text, replace_text, 1)
                if replacement != current:
                    details = _span_details(line_start, line_end, span)
                    details.update(
                        {
                            "directive": "replace_with",
                            "anchor_submatch_occurrences": submatches,
                        }
                    )
                    return SafeEditProposal(
                        proposal_id="",
                        file=str(source_path),
                        find_text=current,
                        replace_text=replacement,
                        match_policy="anchored_exact",
                        status="proposed",
                        origin_event_ids=[event_id],
                        details=details,
                    )
        return SafeEditProposal(
            proposal_id="",
            file=str(source_path),
            find_text=find_text,
            replace_text=replace_text,
            match_policy="unique_exact",
            status="proposed",
            origin_event_ids=[event_id],
            details={"directive": "replace_with"},
        )

    excerpt = anchor.get("excerpt")
    if isinstance(excerpt, str) and excerpt and proposed_text:
        line_start = anchor.get("line_start")
        line_end = anchor.get("line_end") or line_start
        if (
            isinstance(line_start, int)
            and isinstance(line_end, int)
            and line_start > 0
            and line_end > 0
            and _anchor_targets_source(anchor, source_path)
        ):
            current, span = _line_slice_with_span(source_lines, source_line_starts, line_start, line_end)
            if current:
                submatches = current.count(excerpt)
                replacement = current.replace(excerpt, proposed_text, 1)
                if replacement != current:
                    details = _span_details(line_start, line_end, span)
                    details.update(
                        {
                            "directive": "excerpt_to_proposed_text",
                            "anchor_submatch_occurrences": submatches,
                        }
                    )
                    return SafeEditProposal(
                        proposal_id="",
                        file=str(source_path),
                        find_text=current,
                        replace_text=replacement,
                        match_policy="anchored_exact",
                        status="proposed",
                        origin_event_ids=[event_id],
                        details=details,
                    )
        if excerpt in source_text:
            return SafeEditProposal(
                proposal_id="",
                file=str(source_path),
                find_text=excerpt,
                replace_text=proposed_text,
                match_policy="unique_exact",
                status="proposed",
                origin_event_ids=[event_id],
                details={"directive": "excerpt_to_proposed_text"},
            )

    return None


def _coerce_span(value: Any) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _proposal_span(proposal: SafeEditProposal) -> tuple[int, int] | None:
    start = _coerce_span(proposal.details.get("span_start"))
    end = _coerce_span(proposal.details.get("span_end"))
    if start is None or end is None or end < start:
        return None
    return start, end


def _dedupe_key(proposal: SafeEditProposal) -> tuple[str, str, str, int | None, int | None]:
    span = _proposal_span(proposal) if proposal.match_policy == "anchored_exact" else None
    span_start, span_end = span if span is not None else (None, None)
    return proposal.file, proposal.find_text, proposal.replace_text, span_start, span_end


def _intersects(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _protected_block_ranges(text: str) -> list[tuple[str, int, int]]:
    ranges: list[tuple[str, int, int]] = []
    lines = text.splitlines(keepends=True)
    starts = _line_starts(lines)

    if lines and lines[0].strip() == "---":
        for idx, line in enumerate(lines[1:], start=1):
            if line.strip() in {"---", "..."}:
                ranges.append(("yaml_front_matter", 0, starts[idx] + len(line)))
                break

    fence_open: tuple[str, int, int] | None = None
    fence_re = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
    for idx, line in enumerate(lines):
        match = fence_re.match(line)
        if not match:
            continue
        token = match.group(1)
        marker = token[0]
        length = len(token)
        if fence_open is None:
            fence_open = (marker, length, starts[idx])
            continue
        open_marker, open_length, open_start = fence_open
        if marker == open_marker and length >= open_length:
            ranges.append(("fenced_code_block", open_start, starts[idx] + len(line)))
            fence_open = None
    if fence_open is not None:
        ranges.append(("fenced_code_block", fence_open[2], len(text)))

    return ranges


def _inline_markdown_ranges(text: str) -> list[tuple[str, int, int]]:
    ranges: list[tuple[str, int, int]] = []
    patterns = [
        ("inline_code", r"`[^`\n]+`"),
        ("link_or_image", r"!?\[[^\]\n]*\]\([^\)\n]*\)"),
        ("bracketed_citation", r"\[[^\]\n]*@[A-Za-z0-9_:.#/\-]+[^\]\n]*\]"),
        ("bare_citation", r"(?<![\w@])@[A-Za-z0-9_:.#/\-]+"),
    ]
    for kind, pattern in patterns:
        for match in re.finditer(pattern, text):
            ranges.append((kind, match.start(), match.end()))
    return ranges


def _markdown_guard_issues(text: str, span: tuple[int, int], replacement: str) -> list[str]:
    issues: list[str] = []
    for kind, start, end in _protected_block_ranges(text):
        if _intersects(span, (start, end)):
            issues.append(kind)
    for kind, start, end in _inline_markdown_ranges(text):
        if _intersects(span, (start, end)):
            issues.append(kind)
    if re.search(r"(^|\n)[ \t]{0,3}(`{3,}|~{3,})", replacement):
        issues.append("replacement_contains_fence")
    if replacement.startswith("---\n") or "\n---\n" in replacement:
        issues.append("replacement_contains_front_matter_marker")
    return sorted(set(issues))


def _resolve_proposal_span(proposal: SafeEditProposal, source_text: str) -> tuple[int, int] | None:
    if proposal.match_policy == "anchored_exact":
        span = _proposal_span(proposal)
        if span is None:
            proposal.details["reason"] = "missing_anchor_span"
            return None
        start, end = span
        if end > len(source_text) or source_text[start:end] != proposal.find_text:
            proposal.details["reason"] = "anchor_span_text_mismatch"
            return None
        return span

    occurrences = source_text.count(proposal.find_text)
    proposal.details["occurrences"] = occurrences
    if occurrences == 0:
        return None
    if occurrences > 1:
        proposal.details["reason"] = "duplicate_unanchored_match"
        return None
    start = source_text.find(proposal.find_text)
    end = start + len(proposal.find_text)
    proposal.details["span_start"] = start
    proposal.details["span_end"] = end
    return start, end


def _apply_edit_spans(source_text: str, edits: list[tuple[int, int, str]]) -> str:
    updated = source_text
    for start, end, replacement in sorted(edits, key=lambda item: item[0], reverse=True):
        updated = updated[:start] + replacement + updated[end:]
    return updated


def _plan_proposals(
    source_text: str,
    proposals: list[SafeEditProposal],
    *,
    apply_safe: bool,
) -> tuple[str, dict[str, int]]:
    counts = {
        "safe_or_applied": 0,
        "ambiguous": 0,
        "not_found": 0,
        "guarded_markdown": 0,
        "conflict": 0,
    }
    accepted_spans: list[tuple[int, int]] = []
    edits: list[tuple[int, int, str]] = []

    for proposal in proposals:
        if not proposal.find_text:
            proposal.status = "not_found"
            counts["not_found"] += 1
            continue

        if proposal.match_policy == "anchored_exact":
            proposal.details["occurrences"] = source_text.count(proposal.find_text)
            submatches = proposal.details.get("anchor_submatch_occurrences")
            if isinstance(submatches, int) and submatches != 1:
                proposal.status = "ambiguous"
                proposal.details["reason"] = "ambiguous_replacement_within_anchor"
                counts["ambiguous"] += 1
                continue

        span = _resolve_proposal_span(proposal, source_text)
        if span is None:
            if proposal.details.get("reason") == "duplicate_unanchored_match":
                proposal.status = "ambiguous"
                counts["ambiguous"] += 1
            else:
                proposal.status = "not_found"
                counts["not_found"] += 1
            continue

        guard_issues = _markdown_guard_issues(source_text, span, proposal.replace_text)
        if guard_issues:
            proposal.status = "guarded_markdown"
            proposal.details["markdown_guard_issues"] = guard_issues
            counts["guarded_markdown"] += 1
            continue

        if any(_intersects(span, accepted) for accepted in accepted_spans):
            proposal.status = "conflict"
            proposal.details["reason"] = "overlaps_existing_safe_proposal"
            counts["conflict"] += 1
            continue

        proposal.status = "applied" if apply_safe else "proposed_safe"
        counts["safe_or_applied"] += 1
        accepted_spans.append(span)
        edits.append((span[0], span[1], proposal.replace_text))

    return _apply_edit_spans(source_text, edits), counts


def _escape_critic_text(text: str) -> str:
    replacements = [
        ("{--", r"{\--"),
        ("--}", r"--\}"),
        ("{++", r"{\++"),
        ("++}", r"++\}"),
        ("{>>", r"{\>>"),
        ("<<}", r"<<\}"),
        ("{~~", r"{\~~"),
        ("~~}", r"~~\}"),
        ("{==", r"{\=="),
        ("==}", r"==\}"),
    ]
    escaped = text
    for old, new in replacements:
        escaped = escaped.replace(old, new)
    return escaped


def _apply_critic_markup(source_text: str, proposals: list[SafeEditProposal], unresolved: list[dict[str, Any]]) -> str:
    edits: list[tuple[int, int, str]] = []
    for proposal in proposals:
        if proposal.status not in {"proposed_safe", "applied"}:
            continue
        span = _proposal_span(proposal)
        if span is None:
            if source_text.count(proposal.find_text) != 1:
                continue
            start = source_text.find(proposal.find_text)
            span = (start, start + len(proposal.find_text))
        if source_text[span[0] : span[1]] != proposal.find_text:
            continue
        marker = (
            "{>> "
            + _escape_critic_text(proposal.proposal_id)
            + " <<}{--"
            + _escape_critic_text(proposal.find_text)
            + "--}{++"
            + _escape_critic_text(proposal.replace_text)
            + "++}"
        )
        edits.append((span[0], span[1], marker))

    marked = _apply_edit_spans(source_text, edits)

    if unresolved:
        comments = "\n".join(
            "{>> "
            + _escape_critic_text(str(item.get("event_id", "")).strip())
            + ": "
            + _escape_critic_text(str(item.get("summary", "")).strip())
            + " <<}"
            for item in unresolved
            if item.get("summary")
        )
        if comments:
            marked = marked.rstrip() + "\n\n" + comments + "\n"
    return marked


def _proposal_from_payload(raw: dict[str, Any]) -> SafeEditProposal:
    details = raw.get("details")
    origin_event_ids = raw.get("origin_event_ids")
    return SafeEditProposal(
        proposal_id=str(raw.get("proposal_id", "")),
        file=str(raw.get("file", "")),
        find_text=str(raw.get("find_text", "")),
        replace_text=str(raw.get("replace_text", "")),
        match_policy=str(raw.get("match_policy", "unique_exact")),
        status=str(raw.get("status", "proposed")),
        origin_event_ids=[str(item) for item in origin_event_ids] if isinstance(origin_event_ids, list) else [],
        details=dict(details) if isinstance(details, dict) else {},
    )


def _load_safe_edit_proposals(round_dir: Path) -> list[SafeEditProposal]:
    safe_edits_path = round_dir / "proposed.safe_edits.json"
    if not safe_edits_path.exists():
        raise FileNotFoundError(f"Missing safe edits file: {safe_edits_path}")
    payload = json.loads(safe_edits_path.read_text(encoding="utf-8"))
    raw_proposals = payload.get("proposals", [])
    if not isinstance(raw_proposals, list):
        raise ValueError("proposed.safe_edits.json has invalid proposals payload")
    proposals: list[SafeEditProposal] = []
    for raw in raw_proposals:
        if isinstance(raw, dict):
            proposals.append(_proposal_from_payload(raw))
    return proposals


def _decision_log_path(round_dir: Path) -> Path:
    return round_dir / "proposal.decisions.jsonl"


def _read_decision_log(round_dir: Path) -> list[dict[str, Any]]:
    path = _decision_log_path(round_dir)
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            entries.append(value)
    return entries


def _latest_decisions(round_dir: Path) -> dict[str, str]:
    latest: dict[str, str] = {}
    for entry in _read_decision_log(round_dir):
        proposal_id = str(entry.get("proposal_id", ""))
        decision = str(entry.get("decision", ""))
        if proposal_id and decision:
            latest[proposal_id] = decision
    return latest


def _write_decision_summary(round_dir: Path) -> Path:
    entries = _read_decision_log(round_dir)
    latest = _latest_decisions(round_dir)
    return write_json(
        round_dir / "proposal.decisions.summary.json",
        {
            "schema_version": SCHEMA_VERSION,
            "entries": entries,
            "latest": latest,
        },
    )


def record_proposal_decision(round_dir: Path, *, proposal_id: str, decision: str, note: str | None = None) -> dict[str, Any]:
    proposals = _load_safe_edit_proposals(round_dir)
    known_ids = {proposal.proposal_id for proposal in proposals}
    if proposal_id not in known_ids:
        raise ValueError(f"Unknown proposal id: {proposal_id}")
    if decision not in {"accept", "reject", "defer"}:
        raise ValueError("--decision must be one of: accept, reject, defer")

    entry = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now_utc(),
        "proposal_id": proposal_id,
        "decision": decision,
        "note": note or "",
    }
    log_path = _decision_log_path(round_dir)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")
    summary_path = _write_decision_summary(round_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "decision": entry,
        "outputs": {
            "decision_log": str(log_path),
            "decision_summary": str(summary_path),
        },
    }


def apply_selected_proposals(
    round_dir: Path,
    *,
    source: Path,
    proposal_ids: list[str],
    accepted: bool,
    allow_source_drift: bool = False,
) -> dict[str, Any]:
    source = source.resolve()
    source_drift = _source_drift_status(round_dir, source)
    if source_drift.get("drifted") and not allow_source_drift:
        raise ValueError(
            "Source has changed since manuscript prepare; rerun prepare/collect/synthesize or pass "
            "--allow-source-drift after reviewing the current source."
        )

    proposals = _load_safe_edit_proposals(round_dir)
    by_id = {proposal.proposal_id: proposal for proposal in proposals}
    selected_ids = set(proposal_ids)
    if accepted:
        latest = _latest_decisions(round_dir)
        selected_ids.update(proposal_id for proposal_id, decision in latest.items() if decision == "accept")
    if not selected_ids:
        raise ValueError("No proposals selected; provide --proposal-id or --accepted")

    unknown_ids = sorted(selected_ids.difference(by_id))
    if unknown_ids:
        raise ValueError(f"Unknown proposal ids: {', '.join(unknown_ids)}")

    selected = [by_id[proposal_id] for proposal_id in sorted(selected_ids)]
    blocked = [
        proposal.proposal_id
        for proposal in selected
        if proposal.status not in {"proposed_safe", "applied"}
    ]
    if blocked:
        raise ValueError(f"Selected proposals are not currently safe to apply: {', '.join(blocked)}")

    current_text = source.read_text(encoding="utf-8")
    updated_text, counts = _plan_proposals(current_text, selected, apply_safe=True)
    applied_ids = [proposal.proposal_id for proposal in selected if proposal.status == "applied"]
    skipped = [asdict(proposal) for proposal in selected if proposal.status != "applied"]

    if updated_text != current_text:
        source.write_text(updated_text, encoding="utf-8")

    log_path = _decision_log_path(round_dir)
    applied_at = _now_utc()
    with log_path.open("a", encoding="utf-8") as handle:
        for proposal_id in applied_ids:
            entry = {
                "schema_version": SCHEMA_VERSION,
                "created_at": applied_at,
                "proposal_id": proposal_id,
                "decision": "applied",
                "note": "Applied selected proposal to source.",
            }
            handle.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")
    summary_path = _write_decision_summary(round_dir)

    report_path = write_json(
        round_dir / "proposal.apply.report.json",
        {
            "schema_version": SCHEMA_VERSION,
            "source": str(source),
            "selected_proposal_ids": sorted(selected_ids),
            "applied_proposal_ids": applied_ids,
            "skipped": skipped,
            "counts": counts,
            "source_drift": source_drift,
            "outputs": {
                "decision_log": str(log_path),
                "decision_summary": str(summary_path),
            },
        },
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source": str(source),
        "selected_proposal_ids": sorted(selected_ids),
        "applied_proposal_ids": applied_ids,
        "skipped_count": len(skipped),
        "counts": counts,
        "source_drift": source_drift,
        "outputs": {
            "apply_report": str(report_path),
            "decision_log": str(log_path),
            "decision_summary": str(summary_path),
        },
    }


def synthesize_feedback(
    round_dir: Path,
    *,
    source: Path,
    apply_safe: bool,
    export_critic: bool,
    allow_source_drift: bool = False,
) -> dict[str, Any]:
    bundle_path = round_dir / "feedback.bundle.json"
    if not bundle_path.exists():
        raise FileNotFoundError(f"Missing feedback bundle: {bundle_path}")

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    raw_events = bundle.get("events", [])
    if not isinstance(raw_events, list):
        raise ValueError("feedback.bundle.json has invalid events payload")

    source = source.resolve()
    source_drift = _source_drift_status(round_dir, source)
    if apply_safe and source_drift.get("drifted") and not allow_source_drift:
        raise ValueError(
            "Source has changed since manuscript prepare; rerun prepare/collect or pass "
            "--allow-source-drift after reviewing the current source."
        )

    original_text = source.read_text(encoding="utf-8")
    source_lines = original_text.splitlines(keepends=True)
    source_line_starts = _line_starts(source_lines)

    proposals: list[SafeEditProposal] = []
    for raw_event in raw_events:
        if not isinstance(raw_event, dict):
            continue
        proposal = _proposal_from_event(raw_event, source, original_text, source_lines, source_line_starts)
        if proposal is not None:
            proposals.append(proposal)

    deduped: dict[tuple[str, str, str, int | None, int | None], SafeEditProposal] = {}
    for proposal in proposals:
        key = _dedupe_key(proposal)
        if key in deduped:
            merged = deduped[key]
            merged.origin_event_ids.extend([eid for eid in proposal.origin_event_ids if eid not in merged.origin_event_ids])
            continue
        deduped[key] = proposal
    proposals = list(deduped.values())

    for idx, proposal in enumerate(proposals, start=1):
        proposal.proposal_id = f"prop-{idx:05d}"
    simulated_text, plan_counts = _plan_proposals(original_text, proposals, apply_safe=apply_safe)

    if apply_safe and simulated_text != original_text:
        source.write_text(simulated_text, encoding="utf-8")

    from_label = f"a/{source.name}"
    to_label = f"b/{source.name}"
    unified = "".join(
        difflib.unified_diff(
            original_text.splitlines(keepends=True),
            simulated_text.splitlines(keepends=True),
            fromfile=from_label,
            tofile=to_label,
        )
    )
    patch_path = write_text(round_dir / "proposed.patch", unified)

    proposals_payload = {
        "schema_version": SCHEMA_VERSION,
        "source": str(source),
        "apply_safe": apply_safe,
        "allow_source_drift": allow_source_drift,
        "source_drift": source_drift,
        "proposals": [asdict(proposal) for proposal in proposals],
    }
    safe_edits_path = write_json(round_dir / "proposed.safe_edits.json", proposals_payload)

    consumed_event_ids = {eid for proposal in proposals for eid in proposal.origin_event_ids}
    unresolved: list[dict[str, Any]] = []
    for raw_event in raw_events:
        if not isinstance(raw_event, dict):
            continue
        event_id = str(raw_event.get("event_id", ""))
        if event_id in consumed_event_ids:
            continue
        content = raw_event.get("content")
        if not isinstance(content, dict):
            content = {}
        unresolved.append(
            {
                "event_id": event_id,
                "channel": str(raw_event.get("channel", "unknown")),
                "kind": str(raw_event.get("kind", "comment")),
                "severity": str(raw_event.get("severity", "medium")),
                "summary": str(content.get("summary", "")),
            }
        )

    open_lines: list[str] = []
    open_lines.append("# Open Issues")
    open_lines.append("")
    if unresolved:
        for item in unresolved:
            open_lines.append(
                f"- [{item['severity']}] `{item['channel']}`/{item['kind']} ({item['event_id']}): {item['summary']}"
            )
    guarded_or_conflicted = [
        proposal
        for proposal in proposals
        if proposal.status in {"guarded_markdown", "conflict", "ambiguous", "not_found"}
    ]
    if guarded_or_conflicted:
        for proposal in guarded_or_conflicted:
            reason = proposal.details.get("reason") or ", ".join(proposal.details.get("markdown_guard_issues", []))
            open_lines.append(f"- [{proposal.status}] `{proposal.proposal_id}`: {reason or 'manual review required'}")
    if not unresolved and not guarded_or_conflicted:
        open_lines.append("- None.")
    open_lines.append("")
    open_issues_path = write_text(round_dir / "open_issues.md", "\n".join(open_lines))

    summary_lines: list[str] = []
    summary_lines.append(f"# Review Summary — {round_dir.name}")
    summary_lines.append("")
    summary_lines.append(f"- Source: `{source}`")
    summary_lines.append(f"- Proposed edits: {len(proposals)}")
    summary_lines.append(f"- Safe/proposed or applied: {plan_counts['safe_or_applied']}")
    summary_lines.append(f"- Ambiguous: {plan_counts['ambiguous']}")
    summary_lines.append(f"- Not found: {plan_counts['not_found']}")
    summary_lines.append(f"- Guarded by Markdown context: {plan_counts['guarded_markdown']}")
    summary_lines.append(f"- Conflicting safe spans: {plan_counts['conflict']}")
    summary_lines.append(f"- Unresolved conceptual comments: {len(unresolved)}")
    summary_lines.append("")
    summary_path = write_text(round_dir / "review_summary.md", "\n".join(summary_lines))

    critic_path: str | None = None
    if export_critic:
        critic_text = _apply_critic_markup(original_text, proposals, unresolved)
        critic_file = write_text(round_dir / "source_review.critic.md", critic_text)
        critic_path = str(critic_file)

    report_path = write_json(
        round_dir / "synthesize.report.json",
        {
            "schema_version": SCHEMA_VERSION,
            "source": str(source),
            "apply_safe": apply_safe,
            "export_critic": export_critic,
            "allow_source_drift": allow_source_drift,
            "source_drift": source_drift,
            "counts": {
                "proposals_total": len(proposals),
                "safe_or_applied": plan_counts["safe_or_applied"],
                "ambiguous": plan_counts["ambiguous"],
                "not_found": plan_counts["not_found"],
                "guarded_markdown": plan_counts["guarded_markdown"],
                "conflict": plan_counts["conflict"],
                "unresolved": len(unresolved),
            },
            "outputs": {
                "patch": str(patch_path),
                "safe_edits": str(safe_edits_path),
                "open_issues": str(open_issues_path),
                "summary": str(summary_path),
                "critic": critic_path,
            },
        },
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "source": str(source),
        "apply_safe": apply_safe,
        "export_critic": export_critic,
        "allow_source_drift": allow_source_drift,
        "source_drift": source_drift,
        "counts": {
            "proposals_total": len(proposals),
            "safe_or_applied": plan_counts["safe_or_applied"],
            "ambiguous": plan_counts["ambiguous"],
            "not_found": plan_counts["not_found"],
            "guarded_markdown": plan_counts["guarded_markdown"],
            "conflict": plan_counts["conflict"],
            "unresolved": len(unresolved),
        },
        "outputs": {
            "patch": str(patch_path),
            "safe_edits": str(safe_edits_path),
            "open_issues": str(open_issues_path),
            "summary": str(summary_path),
            "critic": critic_path,
            "report": str(report_path),
        },
    }
