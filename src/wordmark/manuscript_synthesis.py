"""Synthesis and safe-apply helpers for manuscript feedback bundles."""

from __future__ import annotations

import difflib
from dataclasses import asdict
import json
from pathlib import Path
import re
from typing import Any

from wordmark.manuscript_models import SCHEMA_VERSION, SafeEditProposal
from wordmark.sidecar import write_json, write_text


def _replace_once(text: str, find_text: str, replace_text: str) -> tuple[str, bool]:
    idx = text.find(find_text)
    if idx < 0:
        return text, False
    return text[:idx] + replace_text + text[idx + len(find_text) :], True


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


def _proposal_from_event(event: dict[str, Any], source_path: Path, source_text: str, source_lines: list[str]) -> SafeEditProposal | None:
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
        if isinstance(line_start, int) and isinstance(line_end, int) and line_start > 0 and line_end > 0:
            current = _line_slice(source_lines, line_start, line_end)
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
                    details={"line_start": line_start, "line_end": line_end},
                )

    candidate = _extract_replace_directive(summary)
    if candidate:
        find_text, replace_text = candidate
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


def _apply_critic_markup(source_text: str, proposals: list[SafeEditProposal], unresolved: list[dict[str, Any]]) -> str:
    marked = source_text
    for proposal in proposals:
        if proposal.status not in {"proposed_safe", "applied"}:
            continue
        marker = "{--" + proposal.find_text + "--}{++" + proposal.replace_text + "++}"
        marked, changed = _replace_once(marked, proposal.find_text, marker)
        if not changed:
            continue

    if unresolved:
        comments = "\n".join("{>> " + item.get("summary", "").strip() + " <<}" for item in unresolved if item.get("summary"))
        if comments:
            marked = marked.rstrip() + "\n\n" + comments + "\n"
    return marked


def synthesize_feedback(
    round_dir: Path,
    *,
    source: Path,
    apply_safe: bool,
    export_critic: bool,
) -> dict[str, Any]:
    bundle_path = round_dir / "feedback.bundle.json"
    if not bundle_path.exists():
        raise FileNotFoundError(f"Missing feedback bundle: {bundle_path}")

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    raw_events = bundle.get("events", [])
    if not isinstance(raw_events, list):
        raise ValueError("feedback.bundle.json has invalid events payload")

    source = source.resolve()
    original_text = source.read_text(encoding="utf-8")
    source_lines = original_text.splitlines(keepends=True)

    proposals: list[SafeEditProposal] = []
    for raw_event in raw_events:
        if not isinstance(raw_event, dict):
            continue
        proposal = _proposal_from_event(raw_event, source, original_text, source_lines)
        if proposal is not None:
            proposals.append(proposal)

    deduped: dict[tuple[str, str, str], SafeEditProposal] = {}
    for proposal in proposals:
        key = (proposal.file, proposal.find_text, proposal.replace_text)
        if key in deduped:
            merged = deduped[key]
            merged.origin_event_ids.extend([eid for eid in proposal.origin_event_ids if eid not in merged.origin_event_ids])
            continue
        deduped[key] = proposal
    proposals = list(deduped.values())

    simulated_text = original_text
    applied_count = 0
    ambiguous_count = 0
    not_found_count = 0
    for idx, proposal in enumerate(proposals, start=1):
        proposal.proposal_id = f"prop-{idx:05d}"
        if not proposal.find_text:
            proposal.status = "not_found"
            not_found_count += 1
            continue

        occurrences = simulated_text.count(proposal.find_text)
        proposal.details["occurrences"] = occurrences
        if occurrences == 0:
            proposal.status = "not_found"
            not_found_count += 1
            continue
        if occurrences > 1 and proposal.match_policy != "anchored_exact":
            proposal.status = "ambiguous"
            ambiguous_count += 1
            continue

        simulated_text, changed = _replace_once(simulated_text, proposal.find_text, proposal.replace_text)
        if changed:
            proposal.status = "applied" if apply_safe else "proposed_safe"
            applied_count += 1
        else:
            proposal.status = "not_found"
            not_found_count += 1

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
    else:
        open_lines.append("- None.")
    open_lines.append("")
    open_issues_path = write_text(round_dir / "open_issues.md", "\n".join(open_lines))

    summary_lines: list[str] = []
    summary_lines.append(f"# Review Summary — {round_dir.name}")
    summary_lines.append("")
    summary_lines.append(f"- Source: `{source}`")
    summary_lines.append(f"- Proposed edits: {len(proposals)}")
    summary_lines.append(f"- Safe/proposed or applied: {applied_count}")
    summary_lines.append(f"- Ambiguous: {ambiguous_count}")
    summary_lines.append(f"- Not found: {not_found_count}")
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
            "counts": {
                "proposals_total": len(proposals),
                "safe_or_applied": applied_count,
                "ambiguous": ambiguous_count,
                "not_found": not_found_count,
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
        "counts": {
            "proposals_total": len(proposals),
            "safe_or_applied": applied_count,
            "ambiguous": ambiguous_count,
            "not_found": not_found_count,
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
