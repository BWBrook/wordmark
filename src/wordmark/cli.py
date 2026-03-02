"""CLI entrypoint for wordmark."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
import fcntl
import json
from pathlib import Path
import re
from typing import Any

import typer

from wordmark import __version__
from wordmark.config import AppConfig, load_config
from wordmark import interop_drift
from wordmark.jsonio import dumps
from wordmark import manuscript_ingest
from wordmark import manuscript_rounds
from wordmark import manuscript_synthesis
from wordmark.models import OperationResult
from wordmark import ooxml_engine
from wordmark import uno_engine
from wordmark import verify as verify_mod
from wordmark.render import render_docx
from wordmark.sidecar import render_sidecar_paths, write_json, write_text
from wordmark.transcript import append_transcript

app = typer.Typer(help="CLI-first DOCX and manuscript review tooling", no_args_is_help=True)
comment_app = typer.Typer(help="Comment operations")
edit_app = typer.Typer(help="Document edit operations")
review_app = typer.Typer(help="Review operations")
artifacts_app = typer.Typer(help="Artifact housekeeping")
manuscript_app = typer.Typer(help="Markdown/Quarto manuscript collaboration workflows")

app.add_typer(comment_app, name="comment")
app.add_typer(edit_app, name="edit")
app.add_typer(review_app, name="review")
app.add_typer(artifacts_app, name="artifacts")
app.add_typer(manuscript_app, name="manuscript")


def _payload(value: Any) -> Any:
    if is_dataclass(value):
        out = asdict(value)
        if "path" in out:
            out["path"] = str(out["path"])
        return out
    return value


def _echo(value: Any, *, json_output: bool) -> None:
    if json_output:
        typer.echo(dumps(value))
    else:
        if isinstance(value, str):
            typer.echo(value)
        else:
            typer.echo(json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True))


def _load_app_config(config_path: Path | None) -> AppConfig:
    return load_config(config_path)


def _resolve_author(author: str | None, config: AppConfig) -> str:
    return author or config.default_author


def _resolve_initials(initials: str | None, config: AppConfig) -> str:
    return initials or config.default_initials


def _resolve_track_changes(raw: str, config: AppConfig) -> bool:
    token = raw.strip().lower()
    if token == "default":
        return config.track_changes_default
    if token in {"on", "true", "1", "yes"}:
        return True
    if token in {"off", "false", "0", "no"}:
        return False
    raise ValueError("--track-changes must be one of: default, on, off")


def _resolve_choice(name: str, value: str, allowed: set[str]) -> str:
    token = value.strip().lower()
    if token not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {allowed_list}")
    return token


def _resolve_edit_policy(
    config: AppConfig,
    *,
    fidelity_mode: str | None,
    on_unsupported: str | None,
    on_uno_fail: str | None,
    allow_paragraph_rewrite: bool | None,
) -> dict[str, Any]:
    mode = _resolve_choice("fidelity_mode", fidelity_mode or config.fidelity_mode, {"strict", "balanced", "aggressive"})
    unsupported_policy = _resolve_choice(
        "on_unsupported",
        on_unsupported or config.fallback_policy.on_ooxml_unsupported,
        {"fail", "comment", "uno"},
    )
    uno_fail_policy = _resolve_choice(
        "on_uno_fail",
        on_uno_fail or config.fallback_policy.on_uno_fail,
        {"fail", "comment"},
    )

    if allow_paragraph_rewrite is not None:
        allow_rewrite = bool(allow_paragraph_rewrite)
    elif mode == "strict":
        allow_rewrite = False
    elif mode == "aggressive":
        allow_rewrite = True
    else:
        allow_rewrite = bool(config.allow_paragraph_rewrite_tracked)

    return {
        "fidelity_mode": mode,
        "on_unsupported": unsupported_policy,
        "on_uno_fail": uno_fail_policy,
        "allow_paragraph_rewrite_tracked": allow_rewrite,
    }


def _safe_template(template: str, values: dict[str, Any]) -> str:
    text = template
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def _shorten(value: Any, limit: int = 140) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _apply_comment_fallback(
    *,
    docx: Path,
    patch_data: dict[str, Any],
    preflight: dict[str, Any],
    reason: str,
    author: str,
    initials: str,
    config: AppConfig,
    dry_run: bool,
) -> OperationResult:
    ops = patch_data.get("operations", [])
    preflight_ops = preflight.get("operations", [])
    created: list[dict[str, Any]] = []

    if not config.comment_fallback.enabled:
        raise RuntimeError("Comment fallback is disabled by config")

    reason_short = _shorten(str(reason).splitlines()[0] if str(reason) else "fallback requested")

    for i, op in enumerate(ops):
        pinfo = preflight_ops[i] if i < len(preflight_ops) else {}
        paragraph_index = pinfo.get("paragraph_index")
        selector = f"p:{paragraph_index}" if isinstance(paragraph_index, int) and paragraph_index >= 0 else "p:0"

        values = {
            "find": _shorten(op.get("find", op.get("expected_text", "<paragraph text>"))),
            "replace": _shorten(op.get("replace", op.get("new_text", "<new value>"))),
            "type": op.get("type", ""),
            "reason": reason_short,
            "classification": pinfo.get("classification", "unknown"),
        }
        comment_text = _safe_template(config.comment_fallback.template, values)

        if dry_run:
            created.append(
                {
                    "selector": selector,
                    "text": comment_text,
                    "dry_run": True,
                }
            )
            continue

        result = ooxml_engine.add_comment(
            docx,
            selector=selector,
            anchor=None,
            text=comment_text,
            author=author,
            initials=initials,
            dry_run=False,
        )
        created.append(
            {
                "selector": selector,
                "comment_id": result.details.get("comment_id"),
                "paragraph_index": result.details.get("paragraph_index"),
                "classification": pinfo.get("classification"),
            }
        )

    return OperationResult.now(
        command="edit apply",
        path=docx,
        engine="comment_fallback",
        changed=bool(created) and not dry_run,
        author=author,
        details={
            "fallback_reason": reason,
            "dry_run": dry_run,
            "comments_created": created,
            "operations_count": len(ops),
        },
    )


def _replacement_delta(old_text: str, new_text: str) -> tuple[str, str, str, str]:
    """Return common prefix/suffix and changed middle segments."""
    prefix_len = 0
    max_prefix = min(len(old_text), len(new_text))
    while prefix_len < max_prefix and old_text[prefix_len] == new_text[prefix_len]:
        prefix_len += 1

    old_tail = len(old_text)
    new_tail = len(new_text)
    while old_tail > prefix_len and new_tail > prefix_len and old_text[old_tail - 1] == new_text[new_tail - 1]:
        old_tail -= 1
        new_tail -= 1

    common_prefix = old_text[:prefix_len]
    old_middle = old_text[prefix_len:old_tail]
    common_suffix = old_text[old_tail:]
    new_middle = new_text[prefix_len:new_tail]
    return common_prefix, old_middle, common_suffix, new_middle


def _find_nth_bounds(text: str, needle: str, occurrence: int) -> tuple[int, int] | None:
    if occurrence < 1 or not needle:
        return None

    count = 0
    search_from = 0
    while True:
        idx = text.find(needle, search_from)
        if idx < 0:
            return None
        count += 1
        if count == occurrence:
            return (idx, idx + len(needle))
        search_from = idx + max(1, len(needle))


def _occurrence_for_start(text: str, needle: str, start_index: int) -> int | None:
    if not needle:
        return None

    count = 0
    search_from = 0
    while True:
        idx = text.find(needle, search_from)
        if idx < 0:
            return None
        count += 1
        if idx == start_index:
            return count
        search_from = idx + max(1, len(needle))


def _replace_nth(text: str, find_text: str, replace_text: str, occurrence: int) -> tuple[str, bool]:
    bounds = _find_nth_bounds(text, find_text, occurrence)
    if bounds is None:
        return text, False
    start, end = bounds
    return text[:start] + replace_text + text[end:], True


def _build_minimal_uno_replace_once(
    *,
    op: dict[str, Any],
    op_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    find_text = op.get("find")
    replace_text = op.get("replace")

    if not isinstance(find_text, str) or not isinstance(replace_text, str):
        return op, {
            "index": op_index,
            "type": str(op.get("type")),
            "status": "passthrough",
            "reason": "non_string_find_or_replace",
        }

    try:
        occurrence = int(op.get("occurrence", 1))
    except (TypeError, ValueError):
        occurrence = 1

    if occurrence < 1:
        return op, {
            "index": op_index,
            "type": str(op.get("type")),
            "status": "passthrough",
            "reason": "invalid_occurrence",
        }

    if find_text == replace_text:
        return op, {
            "index": op_index,
            "type": str(op.get("type")),
            "status": "passthrough",
            "reason": "no_text_delta",
        }

    common_prefix, old_middle, common_suffix, new_middle = _replacement_delta(find_text, replace_text)
    if not old_middle and not new_middle:  # pragma: no cover - defensive (find!=replace already guards this)
        return op, {
            "index": op_index,
            "type": str(op.get("type")),
            "status": "passthrough",
            "reason": "no_middle_delta",
        }

    span_start = len(common_prefix)
    span_length = len(old_middle)
    if span_start == 0 and span_length == len(find_text):
        return op, {
            "index": op_index,
            "type": str(op.get("type")),
            "status": "passthrough",
            "reason": "no_precision_gain",
        }

    def _is_word_char(ch: str) -> bool:
        return ch.isalnum() or ch in {"-", "_", "'"}

    # If the computed replacement span cuts through a token, widen boundaries
    # for substitution cases so tracked revisions do not show partial stems.
    if old_middle and new_middle:
        span_end = span_start + span_length
        if (
            span_start > 0
            and span_start < len(find_text)
            and _is_word_char(find_text[span_start - 1])
            and _is_word_char(find_text[span_start])
        ):
            left = span_start
            while left > 0 and _is_word_char(find_text[left - 1]):
                left -= 1
            prefix = find_text[left:span_start]
            span_start = left
            span_length = span_end - span_start
            span_end = span_start + span_length
            new_middle = prefix + new_middle

        if (
            span_end > 0
            and span_end < len(find_text)
            and _is_word_char(find_text[span_end - 1])
            and _is_word_char(find_text[span_end])
        ):
            right = span_end
            while right < len(find_text) and _is_word_char(find_text[right]):
                right += 1
            suffix = find_text[span_end:right]
            span_length = right - span_start
            new_middle = new_middle + suffix

    if (
        old_middle
        and new_middle
        and any(ch.isalnum() for ch in (old_middle + new_middle))
        and " " not in old_middle
        and "\t" not in old_middle
        and " " not in new_middle
        and "\t" not in new_middle
    ):
        token_start = span_start
        token_end = span_start + span_length
        while token_start > 0 and _is_word_char(find_text[token_start - 1]):
            token_start -= 1
        while token_end < len(find_text) and _is_word_char(find_text[token_end]):
            token_end += 1

        if token_start != span_start or token_end != span_start + span_length:
            token_prefix = find_text[token_start:span_start]
            token_suffix = find_text[span_start + span_length : token_end]
            span_start = token_start
            span_length = token_end - token_start
            new_middle = token_prefix + new_middle + token_suffix

    rewritten = dict(op)
    rewritten["type"] = "replace_span_once"
    rewritten["find"] = find_text
    rewritten["occurrence"] = occurrence
    rewritten["span_start"] = span_start
    rewritten["span_length"] = span_length
    rewritten["replacement"] = new_middle

    if not old_middle and new_middle:
        strategy = "insert_span"
    elif old_middle and not new_middle:
        strategy = "delete_span"
    else:
        strategy = "replace_span"

    return rewritten, {
        "index": op_index,
        "type": str(op.get("type")),
        "status": "rewritten",
        "strategy": strategy,
        "original_find": find_text,
        "original_replace": replace_text,
        "original_occurrence": occurrence,
        "span_start": span_start,
        "span_length": span_length,
        "span_replacement": new_middle,
    }


def _token_change_islands(old_text: str, new_text: str) -> list[tuple[int, int, str]]:
    old_tokens = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"\s+|\w+|[^\w\s]", old_text)]
    new_tokens = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"\s+|\w+|[^\w\s]", new_text)]

    matcher = SequenceMatcher(
        a=[token for token, _, _ in old_tokens],
        b=[token for token, _, _ in new_tokens],
        autojunk=False,
    )
    islands: list[tuple[int, int, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        old_start = old_tokens[i1][1] if i1 < len(old_tokens) else len(old_text)
        old_end = old_tokens[i2 - 1][2] if i2 > i1 else old_start
        new_start = new_tokens[j1][1] if j1 < len(new_tokens) else len(new_text)
        new_end = new_tokens[j2 - 1][2] if j2 > j1 else new_start
        islands.append((old_start, old_end, new_text[new_start:new_end]))
    return islands


def _build_split_uno_replace_sequence(
    *,
    op: dict[str, Any],
    op_index: int,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    find_text = op.get("find")
    replace_text = op.get("replace")

    if not isinstance(find_text, str) or not isinstance(replace_text, str):
        return None, None

    try:
        occurrence = int(op.get("occurrence", 1))
    except (TypeError, ValueError):
        occurrence = 1

    # Guardrail: split-sequence rewrite is currently only safe/deterministic
    # for the default single targeted occurrence path.
    if occurrence != 1 or find_text == replace_text:
        return None, None

    islands = _token_change_islands(find_text, replace_text)
    if len(islands) < 2 or len(islands) > 3:
        return None, None

    sequence_ops: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    current_find = find_text
    offset = 0

    for idx, (i1, i2, replacement) in enumerate(islands):
        if idx > 0:
            prior_end = islands[idx - 1][1]
            if i1 - prior_end < 2:
                return None, None

        span_start = i1 + offset
        span_end = i2 + offset
        if span_start < 0 or span_end < span_start or span_end > len(current_find):
            return None, None

        next_find = current_find[:span_start] + replacement + current_find[span_end:]
        step_op = {
            "type": "replace_text_once",
            "find": current_find,
            "replace": next_find,
            "occurrence": 1,
        }
        rewritten_step, step_info = _build_minimal_uno_replace_once(op=step_op, op_index=op_index)
        if step_info.get("status") != "rewritten":
            return None, None

        sequence_ops.append(rewritten_step)
        steps.append(
            {
                "span_start": int(step_info.get("span_start", 0)),
                "span_length": int(step_info.get("span_length", 0)),
                "span_replacement": str(step_info.get("span_replacement", "")),
            }
        )
        current_find = next_find
        offset += len(replacement) - (i2 - i1)

    if len(sequence_ops) < 2:
        return None, None

    return sequence_ops, {
        "index": op_index,
        "type": str(op.get("type")),
        "status": "rewritten_split",
        "strategy": "split_span_sequence",
        "original_find": find_text,
        "original_replace": replace_text,
        "original_occurrence": occurrence,
        "split_operations": len(sequence_ops),
        "steps": steps,
    }


def _prepare_uno_precision_patch(docx: Path, patch_data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    operations = patch_data.get("operations")
    if not isinstance(operations, list) or not operations:
        return patch_data, None

    rewritten_ops: list[dict[str, Any]] = []
    op_results: list[dict[str, Any]] = []
    rewritten_count = 0

    for index, op in enumerate(operations):
        if not isinstance(op, dict):
            rewritten_ops.append(op)
            op_results.append(
                {
                    "index": index,
                    "type": "unknown",
                    "status": "passthrough",
                    "reason": "non_object_operation",
                }
            )
            continue

        op_type = str(op.get("type"))
        prepared_op = op
        info: dict[str, Any] = {
            "index": index,
            "type": op_type,
            "status": "passthrough",
            "reason": "non_replace_text_once_operation",
        }

        if op_type == "replace_text_once":
            split_ops, split_info = _build_split_uno_replace_sequence(op=op, op_index=index)
            if split_ops is not None and split_info is not None:
                rewritten_ops.extend(split_ops)
                op_results.append(split_info)
                rewritten_count += 1
                continue

            prepared_op, info = _build_minimal_uno_replace_once(op=op, op_index=index)
            if info.get("status") == "rewritten":
                rewritten_count += 1

        rewritten_ops.append(prepared_op)
        op_results.append(info)

    if rewritten_count == 0:
        return patch_data, {
            "attempted": True,
            "rewritten_operations": 0,
            "total_operations": len(operations),
            "status": "no_rewrites",
            "operation_results": op_results,
        }

    rewritten_patch = dict(patch_data)
    rewritten_patch["operations"] = rewritten_ops
    return rewritten_patch, {
        "attempted": True,
        "rewritten_operations": rewritten_count,
        "total_operations": len(operations),
        "status": "rewritten",
        "operation_results": op_results,
    }


def _build_uno_low_hit_retry_patch(uno_payload: dict[str, Any]) -> dict[str, Any] | None:
    op_results = uno_payload.get("operation_results")
    if not isinstance(op_results, list):
        return None

    retry_ops: list[dict[str, Any]] = []
    for item in op_results:
        if not isinstance(item, dict):
            continue
        op_type = str(item.get("type"))
        status = str(item.get("status"))
        requested = item.get("requested")
        if not isinstance(requested, dict):
            continue

        # Deterministic retry policy:
        # If a literal global replace had no hit, retry that operation once.
        if op_type == "replace_text_global" and status == "not_found":
            retry_op = dict(requested)
            retry_op["type"] = "replace_text_once"
            retry_op["occurrence"] = int(retry_op.get("occurrence", 1))
            retry_ops.append(retry_op)

    if not retry_ops:
        return None
    return {"operations": retry_ops}


def _should_retry_uno_low_hit(uno_payload: dict[str, Any]) -> bool:
    summary = uno_payload.get("summary")
    if not isinstance(summary, dict):
        return False
    return int(summary.get("operations_without_hits", 0)) > 0


def _count_risky_preflight_ops(preflight: dict[str, Any]) -> int:
    operations = preflight.get("operations")
    if not isinstance(operations, list):
        return 0
    risky = 0
    for op in operations:
        if not isinstance(op, dict):
            continue
        classification = str(op.get("classification"))
        reason_code = str(op.get("reason_code"))
        if classification == "unsupported_high_risk" or reason_code == "risky_markup_detected":
            risky += 1
    return risky


def _used_uno_fallback(attempts: list[dict[str, Any]]) -> bool:
    for attempt in attempts:
        engine = str(attempt.get("engine"))
        status = str(attempt.get("status"))
        if engine == "uno" and status in {"applied", "retry_applied"}:
            return True
    return False


def _precision_rewrite_count(result: OperationResult) -> int:
    rewrite = result.details.get("uno_precision_rewrite")
    if not isinstance(rewrite, dict):
        return 0
    try:
        return int(rewrite.get("rewritten_operations", 0))
    except (TypeError, ValueError):
        return 0


def _analyze_interop_drift(
    *,
    docx: Path,
    before_text: str | None,
    threshold: str,
    dry_run: bool,
) -> dict[str, Any]:
    if dry_run:
        return {
            "detected": False,
            "warning": False,
            "warning_threshold": threshold,
            "severity": "none",
            "signals": [],
            "changed_families": [],
            "change_magnitude": 0,
            "before_counts": {},
            "after_counts": {},
            "recommended_action": "Skipped drift analysis for dry-run.",
            "analysis_skipped": True,
            "analysis_reason": "dry_run",
        }

    if before_text is None:
        return {
            "detected": False,
            "warning": False,
            "warning_threshold": threshold,
            "severity": "none",
            "signals": [],
            "changed_families": [],
            "change_magnitude": 0,
            "before_counts": {},
            "after_counts": {},
            "recommended_action": "Could not compute drift due missing baseline text snapshot.",
            "analysis_failed": True,
            "analysis_reason": "before_snapshot_missing",
        }

    try:
        after_text = ooxml_engine.inspect(docx, text_mode="review-visible").text_value
    except Exception as exc:  # pragma: no cover - defensive path
        return {
            "detected": False,
            "warning": False,
            "warning_threshold": threshold,
            "severity": "none",
            "signals": [],
            "changed_families": [],
            "change_magnitude": 0,
            "before_counts": {},
            "after_counts": {},
            "recommended_action": "Could not compute drift; inspect after-snapshot failed.",
            "analysis_failed": True,
            "analysis_reason": "after_snapshot_failed",
            "error": str(exc),
        }

    return interop_drift.analyze_reference_drift(
        before_text,
        after_text,
        warning_threshold=threshold,
    )


def _build_risk_summary(
    *,
    preflight: dict[str, Any],
    attempts: list[dict[str, Any]],
    policy: dict[str, Any],
    result: OperationResult,
    drift_check_enabled: bool,
    drift_threshold: str,
) -> dict[str, Any]:
    drift = result.details.get("interop_drift")
    drift_detected = bool(isinstance(drift, dict) and drift.get("detected", False))
    drift_warning = bool(isinstance(drift, dict) and drift.get("warning", False))
    drift_severity = str(drift.get("severity", "none")) if isinstance(drift, dict) else "none"

    return {
        "used_uno_fallback": _used_uno_fallback(attempts),
        "risky_operations_count": _count_risky_preflight_ops(preflight),
        "precision_rewrite_count": _precision_rewrite_count(result),
        "drift_check_enabled": drift_check_enabled,
        "drift_warning_threshold": drift_threshold if drift_check_enabled else None,
        "drift_detected": drift_detected,
        "drift_warning": drift_warning,
        "drift_severity": drift_severity,
        "mode": str(policy.get("fidelity_mode", "")),
    }


def _write_review_sidecars(config: AppConfig, docx_path: Path, review_data: dict[str, Any]) -> dict[str, str]:
    if not config.sidecar.enabled:
        return {}
    sidecars = render_sidecar_paths(config, docx_path)
    comments = review_data.get("comments", [])
    revisions = review_data.get("revisions", [])
    text_value = str(review_data.get("text_value", ""))

    write_json(sidecars["comments"], comments)
    write_json(sidecars["revisions"], revisions)
    write_text(sidecars["text"], text_value + ("\n" if text_value else ""))
    return {"comments": str(sidecars["comments"]), "revisions": str(sidecars["revisions"]), "text": str(sidecars["text"])}


def _collect_artifact_files(
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


def _prune_empty_dirs(root: Path) -> list[Path]:
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


def _safe_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _to_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _date_suffix(now: datetime | None = None) -> str:
    current = now or datetime.now(tz=timezone.utc)
    return current.strftime("%a%d%b%Y").lower()


@contextmanager
def _docx_operation_lock(docx_path: Path):
    lock_path = docx_path.with_suffix(docx_path.suffix + ".wordmark.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield lock_path
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    try:
        lock_path.unlink()
    except OSError:
        pass


@app.command("version")
def version() -> None:
    """Print tool version."""
    typer.echo(__version__)


@app.command("inspect")
def inspect_cmd(
    docx: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    text_mode: str = typer.Option("review-visible", "--text-mode", help="review-visible|raw"),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
    write_sidecar: bool = typer.Option(True, "--write-sidecar/--no-write-sidecar", help="Write sidecar artifacts."),
) -> None:
    """Inspect paragraphs, comments, and revision state."""
    config = _load_app_config(config_path)
    resolved_text_mode = _resolve_choice("text_mode", text_mode, {"review-visible", "raw"})
    report = ooxml_engine.inspect(docx, text_mode=resolved_text_mode)

    payload: dict[str, Any] = {
        "schema_version": 2,
        "report": _payload(report),
        "sidecars": {},
    }

    if write_sidecar:
        review_data = ooxml_engine.list_review(docx, text_mode=resolved_text_mode)
        payload["sidecars"] = _write_review_sidecars(config, docx, review_data)

    _echo(payload, json_output=json_output)


@comment_app.command("add")
def comment_add(
    docx: Path = typer.Argument(..., exists=True, readable=True, writable=True, resolve_path=True),
    anchor: str | None = typer.Option(None, "--anchor", help="Anchor selector: p:<index> or text:<snippet>"),
    anchor_json: str | None = typer.Option(
        None,
        "--anchor-json",
        help="Anchor object JSON (paragraph_index/expected_text/context_before/context_after/occurrence).",
    ),
    text: str = typer.Option(..., "--text", help="Comment text."),
    author: str | None = typer.Option(None, "--author", help="Comment author label."),
    initials: str | None = typer.Option(None, "--initials", help="Comment initials."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Emit intended mutation without writing."),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Add a DOCX comment anchored to a paragraph or text snippet."""
    if not anchor and not anchor_json:
        raise ValueError("Provide either --anchor or --anchor-json")

    anchor_payload: dict[str, Any] | None = None
    if anchor_json:
        parsed = json.loads(anchor_json)
        if not isinstance(parsed, dict):
            raise ValueError("--anchor-json must be a JSON object")
        anchor_payload = parsed

    config = _load_app_config(config_path)
    resolved_author = _resolve_author(author, config)
    resolved_initials = _resolve_initials(initials, config)

    with _docx_operation_lock(docx):
        result = ooxml_engine.add_comment(
            docx,
            selector=anchor,
            anchor=anchor_payload,
            text=text,
            author=resolved_author,
            initials=resolved_initials,
            dry_run=dry_run,
        )
    transcript_path = append_transcript(config, result)

    payload = {
        "operation": _payload(result),
        "transcript": str(transcript_path),
    }
    _echo(payload, json_output=json_output)


@edit_app.command("apply")
def edit_apply(
    docx: Path = typer.Argument(..., exists=True, readable=True, writable=True, resolve_path=True),
    patch: Path = typer.Option(..., "--patch", exists=True, readable=True, resolve_path=True, help="Patch JSON file."),
    author: str | None = typer.Option(None, "--author", help="Tracked changes author label."),
    initials: str | None = typer.Option(None, "--initials", help="Fallback comment initials."),
    track_changes: str = typer.Option("default", "--track-changes", help="default|on|off"),
    fidelity_mode: str | None = typer.Option(None, "--fidelity-mode", help="strict|balanced|aggressive"),
    on_unsupported: str | None = typer.Option(None, "--on-unsupported", help="fail|comment|uno"),
    on_uno_fail: str | None = typer.Option(None, "--on-uno-fail", help="fail|comment"),
    allow_paragraph_rewrite: bool | None = typer.Option(
        None,
        "--allow-paragraph-rewrite/--no-allow-paragraph-rewrite",
        help="Allow paragraph-level rewrite fallback in tracked mode.",
    ),
    preflight_only: bool = typer.Option(False, "--preflight-only", help="Classify operation strategy without writing."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Emit intended mutation without writing."),
    drift_check: bool = typer.Option(
        True,
        "--drift-check/--no-drift-check",
        help="Check cross-reference drift (Figure/Table/Eq/Appendix) after mutation.",
    ),
    drift_warning_threshold: str = typer.Option(
        "low",
        "--drift-warning-threshold",
        help="low|moderate|high threshold for emitting drift warnings.",
    ),
    emit_risk_summary: bool = typer.Option(
        True,
        "--emit-risk-summary/--no-emit-risk-summary",
        help="Emit risk summary metadata in operation details.",
    ),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Apply a patch with policy-driven OOXML/UNO/comment fallback ordering."""
    config = _load_app_config(config_path)
    resolved_author = _resolve_author(author, config)
    resolved_initials = _resolve_initials(initials, config)
    track = _resolve_track_changes(track_changes, config)
    resolved_drift_threshold = _resolve_choice(
        "drift_warning_threshold",
        drift_warning_threshold,
        {"low", "moderate", "high"},
    )
    patch_data = json.loads(patch.read_text(encoding="utf-8"))
    policy = _resolve_edit_policy(
        config,
        fidelity_mode=fidelity_mode,
        on_unsupported=on_unsupported,
        on_uno_fail=on_uno_fail,
        allow_paragraph_rewrite=allow_paragraph_rewrite,
    )
    preflight = ooxml_engine.preflight_patch(
        docx,
        patch_data=patch_data,
        track_changes=track,
        allow_paragraph_rewrite_tracked=bool(policy["allow_paragraph_rewrite_tracked"]),
    )

    if preflight_only:
        _echo(
            {
                "policy": policy,
                "preflight": preflight,
                "preflight_only": True,
            },
            json_output=json_output,
        )
        return

    result: OperationResult | None = None
    errors: list[str] = []
    attempts: list[dict[str, Any]] = []
    fallback_reason = ""
    uno_enabled = "uno" in config.engine_order
    before_text_snapshot: str | None = None

    with _docx_operation_lock(docx):
        if drift_check:
            try:
                before_text_snapshot = ooxml_engine.inspect(docx, text_mode="review-visible").text_value
            except Exception:  # pragma: no cover - defensive diagnostics path
                before_text_snapshot = None

        try:
            result = ooxml_engine.apply_patch(
                docx,
                patch_data=patch_data,
                author=resolved_author,
                track_changes=track,
                dry_run=dry_run,
                allow_paragraph_rewrite_tracked=bool(policy["allow_paragraph_rewrite_tracked"]),
            )
            attempts.append({"engine": "ooxml", "status": "applied"})
        except ooxml_engine.OoxmlUnsupportedOperation as exc:
            fallback_reason = str(exc)
            attempts.append({"engine": "ooxml", "status": "unsupported", "reason": fallback_reason})
            errors.append(f"ooxml: {exc}")
        except Exception as exc:  # pragma: no cover - surfaced to user
            fallback_reason = str(exc)
            attempts.append({"engine": "ooxml", "status": "error", "reason": fallback_reason})
            errors.append(f"ooxml: {exc}")

        if result is None:
            if policy["on_unsupported"] == "comment":
                try:
                    result = _apply_comment_fallback(
                        docx=docx,
                        patch_data=patch_data,
                        preflight=preflight,
                        reason=fallback_reason or "ooxml unsupported",
                        author=resolved_author,
                        initials=resolved_initials,
                        config=config,
                        dry_run=dry_run,
                    )
                    attempts.append({"engine": "comment_fallback", "status": "applied"})
                except Exception as exc:  # pragma: no cover - surfaced to user
                    attempts.append({"engine": "comment_fallback", "status": "error", "reason": str(exc)})
                    errors.append(f"comment_fallback: {exc}")

            elif policy["on_unsupported"] == "uno":
                if not uno_enabled:
                    attempts.append({"engine": "uno", "status": "skipped", "reason": "uno_not_enabled"})
                    errors.append("uno: engine not enabled in config.engine_order")
                else:
                    try:
                        uno_patch_data = patch_data
                        precision_rewrite: dict[str, Any] | None = None
                        if not dry_run:
                            uno_patch_data, precision_rewrite = _prepare_uno_precision_patch(docx, patch_data)

                        result = uno_engine.apply_patch(
                            docx,
                            patch_data=uno_patch_data,
                            author=resolved_author,
                            track_changes=track,
                            dry_run=dry_run,
                            fallback_reason=fallback_reason or "ooxml unsupported",
                        )
                        attempts.append({"engine": "uno", "status": "applied"})
                        if precision_rewrite is not None:
                            result.details["uno_precision_rewrite"] = precision_rewrite

                        uno_payload = result.details.get("uno", {})
                        if isinstance(uno_payload, dict) and _should_retry_uno_low_hit(uno_payload) and not dry_run:
                            retry_patch = _build_uno_low_hit_retry_patch(uno_payload)
                            if retry_patch is not None:
                                try:
                                    retry_result = uno_engine.apply_patch(
                                        docx,
                                        patch_data=retry_patch,
                                        author=resolved_author,
                                        track_changes=track,
                                        dry_run=False,
                                        fallback_reason="uno low-hit retry after initial global pass",
                                    )
                                    result.details["uno_retry"] = {
                                        "attempted": True,
                                        "patch": retry_patch,
                                        "result": retry_result.details.get("uno", {}),
                                        "author_binding_postprocess": retry_result.details.get("author_binding_postprocess"),
                                    }
                                    result.changed = bool(result.changed or retry_result.changed)
                                    attempts.append(
                                        {
                                            "engine": "uno",
                                            "status": "retry_applied",
                                            "requested_operations": len(retry_patch.get("operations", [])),
                                            "changed": retry_result.changed,
                                        }
                                    )
                                except Exception as retry_exc:  # pragma: no cover - surfaced to user
                                    result.details["uno_retry"] = {
                                        "attempted": True,
                                        "patch": retry_patch,
                                        "error": str(retry_exc),
                                    }
                                    attempts.append(
                                        {
                                            "engine": "uno",
                                            "status": "retry_error",
                                            "reason": str(retry_exc),
                                        }
                                    )
                                    errors.append(f"uno_retry: {retry_exc}")
                    except Exception as exc:  # pragma: no cover - surfaced to user
                        attempts.append({"engine": "uno", "status": "error", "reason": str(exc)})
                        errors.append(f"uno: {exc}")
                        if policy["on_uno_fail"] == "comment":
                            try:
                                result = _apply_comment_fallback(
                                    docx=docx,
                                    patch_data=patch_data,
                                    preflight=preflight,
                                    reason=f"uno failed after ooxml unsupported: {exc}",
                                    author=resolved_author,
                                    initials=resolved_initials,
                                    config=config,
                                    dry_run=dry_run,
                                )
                                attempts.append({"engine": "comment_fallback", "status": "applied", "after": "uno"})
                            except Exception as comment_exc:  # pragma: no cover - surfaced to user
                                attempts.append(
                                    {
                                        "engine": "comment_fallback",
                                        "status": "error",
                                        "reason": str(comment_exc),
                                        "after": "uno",
                                    }
                                )
                                errors.append(f"comment_fallback: {comment_exc}")

        if result is not None and drift_check:
            result.details["interop_drift"] = _analyze_interop_drift(
                docx=docx,
                before_text=before_text_snapshot,
                threshold=resolved_drift_threshold,
                dry_run=dry_run,
            )

    if result is None:
        _echo(
            {
                "error": "No configured engine could apply this patch",
                "engine_attempt_errors": errors,
                "attempts": attempts,
                "policy": policy,
                "preflight": preflight,
            },
            json_output=True,
        )
        raise typer.Exit(code=1)

    if emit_risk_summary:
        result.details["risk_summary"] = _build_risk_summary(
            preflight=preflight,
            attempts=attempts,
            policy=policy,
            result=result,
            drift_check_enabled=drift_check,
            drift_threshold=resolved_drift_threshold,
        )

    transcript_path = append_transcript(config, result)
    payload = {
        "operation": _payload(result),
        "transcript": str(transcript_path),
        "engine_attempt_errors": errors,
        "attempts": attempts,
        "policy": policy,
        "preflight": preflight,
    }
    _echo(payload, json_output=json_output)


@review_app.command("list")
def review_list(
    docx: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    text_mode: str = typer.Option("review-visible", "--text-mode", help="review-visible|raw"),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
    write_sidecar: bool = typer.Option(True, "--write-sidecar/--no-write-sidecar", help="Write sidecar artifacts."),
) -> None:
    """List comments and revisions in review-friendly format."""
    config = _load_app_config(config_path)
    resolved_text_mode = _resolve_choice("text_mode", text_mode, {"review-visible", "raw"})
    review_data = ooxml_engine.list_review(docx, text_mode=resolved_text_mode)
    sidecars: dict[str, str] = {}

    if write_sidecar:
        sidecars = _write_review_sidecars(config, docx, review_data)

    payload = {
        "schema_version": 2,
        "review": review_data,
        "sidecars": sidecars,
    }
    _echo(payload, json_output=json_output)


@review_app.command("accept")
def review_accept(
    docx: Path = typer.Argument(..., exists=True, readable=True, writable=True, resolve_path=True),
    author: str | None = typer.Option(None, "--author", help="Accept revisions by author only."),
    all_authors: bool = typer.Option(False, "--all", help="Accept revisions from all authors."),
    actor: str | None = typer.Option(None, "--actor", help="Operator label for transcript metadata."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Emit intended mutation without writing."),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Accept tracked revisions by author or globally."""
    config = _load_app_config(config_path)
    resolved_actor = _resolve_author(actor, config)
    filter_author = None if all_authors else author

    with _docx_operation_lock(docx):
        result = ooxml_engine.review_action(
            docx,
            mode="accept",
            author=filter_author,
            actor=resolved_actor,
            dry_run=dry_run,
        )
    transcript_path = append_transcript(config, result)

    payload = {
        "operation": _payload(result),
        "transcript": str(transcript_path),
    }
    _echo(payload, json_output=json_output)


@review_app.command("reject")
def review_reject(
    docx: Path = typer.Argument(..., exists=True, readable=True, writable=True, resolve_path=True),
    author: str | None = typer.Option(None, "--author", help="Reject revisions by author only."),
    all_authors: bool = typer.Option(False, "--all", help="Reject revisions from all authors."),
    actor: str | None = typer.Option(None, "--actor", help="Operator label for transcript metadata."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Emit intended mutation without writing."),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Reject tracked revisions by author or globally."""
    config = _load_app_config(config_path)
    resolved_actor = _resolve_author(actor, config)
    filter_author = None if all_authors else author

    with _docx_operation_lock(docx):
        result = ooxml_engine.review_action(
            docx,
            mode="reject",
            author=filter_author,
            actor=resolved_actor,
            dry_run=dry_run,
        )
    transcript_path = append_transcript(config, result)

    payload = {
        "operation": _payload(result),
        "transcript": str(transcript_path),
    }
    _echo(payload, json_output=json_output)


@review_app.command("prepare-merge")
def review_prepare_merge(
    baseline: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    edited: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    out: Path | None = typer.Option(None, "--out", help="Optional JSON checklist/report output path."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Prepare a Word desktop compare/combine handoff checklist."""
    extension = baseline.suffix if baseline.suffix else ".docx"
    suggested_name = f"{baseline.stem}_merged_{_date_suffix()}{extension}"

    checklist = [
        "Open baseline and edited documents in Microsoft Word desktop.",
        "Use Review > Compare (or Review > Compare > Combine) with baseline as original and edited as revised.",
        "Review tracked changes and comments in the comparison output document.",
        "Accept or reject revisions in the GUI until the document reflects approved content.",
        "Save the merged document with a versioned filename and then upload/replace in shared storage.",
    ]

    payload: dict[str, Any] = {
        "baseline": str(baseline),
        "edited": str(edited),
        "word_desktop_required": True,
        "suggested_merged_filename": suggested_name,
        "suggested_output_path": str(baseline.with_name(suggested_name)),
        "checklist": checklist,
        "notes": [
            "This helper does not modify either source document.",
            "Use Word desktop, not Word for the web, for Compare/Combine.",
        ],
    }

    if out is not None:
        write_json(out, payload)
        payload["report"] = str(out)

    _echo(payload, json_output=json_output)


@artifacts_app.command("clean")
def artifacts_clean(
    path: Path = typer.Option(Path("artifacts"), "--path", help="Artifact directory to clean."),
    older_than_days: int | None = typer.Option(
        None,
        "--older-than-days",
        min=0,
        help="Only target files modified more than this many days ago.",
    ),
    keep_transcripts: bool = typer.Option(False, "--keep-transcripts", help="Do not delete files under transcripts/."),
    apply: bool = typer.Option(False, "--apply", help="Delete matched files. Default is preview-only."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Preview or remove sidecar artifacts and transcripts."""
    root = path.resolve()
    keep_names = {".gitkeep", "README.md"}

    if root.exists() and not root.is_dir():
        _echo({"error": "--path must point to a directory", "path": str(root)}, json_output=json_output)
        raise typer.Exit(code=2)

    matches = _collect_artifact_files(
        root,
        older_than_days=older_than_days,
        keep_names=keep_names,
        keep_transcripts=keep_transcripts,
    )
    matched_paths = [_to_relative(item, root) for item in matches]
    matched_bytes = sum(_safe_size(item) for item in matches)

    deleted_paths: list[str] = []
    deleted_dirs: list[str] = []
    deleted_bytes = 0
    errors: list[str] = []

    if apply:
        for file_path in matches:
            size = _safe_size(file_path)
            try:
                file_path.unlink()
            except OSError as exc:
                errors.append(f"{file_path}: {exc}")
                continue
            deleted_bytes += size
            deleted_paths.append(_to_relative(file_path, root))
        deleted_dirs = [_to_relative(item, root) for item in _prune_empty_dirs(root)]

    payload = {
        "path": str(root),
        "exists": root.exists(),
        "apply": apply,
        "older_than_days": older_than_days,
        "keep_transcripts": keep_transcripts,
        "preserved_names": sorted(keep_names),
        "matched_count": len(matches),
        "matched_bytes": matched_bytes,
        "matched_files": matched_paths,
        "deleted_count": len(deleted_paths),
        "deleted_bytes": deleted_bytes,
        "deleted_files": deleted_paths,
        "deleted_dirs": deleted_dirs,
        "errors": errors,
    }
    _echo(payload, json_output=json_output)

    if errors:
        raise typer.Exit(code=1)


@manuscript_app.command("prepare")
def manuscript_prepare(
    source: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    build_cmd: str | None = typer.Option(
        None,
        "--build-cmd",
        help="Optional builder template. Placeholders: {input}, {outdir}, {docx_out}, {pdf_out}.",
    ),
    formats: str = typer.Option("docx,pdf", "--formats", help="Comma-separated formats: docx,pdf"),
    out: Path = typer.Option(
        Path("artifacts/manuscript_rounds"),
        "--out",
        help="Root directory for manuscript review rounds.",
    ),
    round_id: str | None = typer.Option(None, "--round-id", help="Optional stable round identifier."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Create a review round bundle from a Markdown/Quarto source."""
    payload = manuscript_rounds.prepare_round(
        source,
        build_cmd=build_cmd,
        formats=formats,
        out_root=out,
        round_id=round_id,
    )
    _echo(payload, json_output=json_output)


@manuscript_app.command("collect")
def manuscript_collect(
    round_dir: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    from_pr: str | None = typer.Option(
        None,
        "--from-pr",
        help="PR number or URL to ingest GitHub review comments/suggestions via gh.",
    ),
    notes: Path | None = typer.Option(
        None,
        "--notes",
        exists=True,
        readable=True,
        resolve_path=True,
        help="Local markdown notes file to ingest.",
    ),
    docx_reviewed: Path | None = typer.Option(
        None,
        "--docx-reviewed",
        exists=True,
        readable=True,
        resolve_path=True,
        help="Reviewed DOCX copy to ingest comment/revision feedback from.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Collect multi-channel feedback into a normalized bundle."""
    payload = manuscript_ingest.collect_feedback(
        round_dir,
        from_pr=from_pr,
        notes_path=notes,
        reviewed_docx=docx_reviewed,
    )
    _echo(payload, json_output=json_output)


@manuscript_app.command("synthesize")
def manuscript_synthesize(
    round_dir: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    source: Path = typer.Option(..., "--source", exists=True, readable=True, resolve_path=True, help="Source .md/.qmd file."),
    apply_safe: bool = typer.Option(
        False,
        "--apply-safe",
        help="Apply deterministic safe edits directly to source.",
    ),
    export_critic: bool = typer.Option(
        False,
        "--export-critic",
        help="Export optional CriticMarkup review copy.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Create patch proposals and reports from collected feedback."""
    payload = manuscript_synthesis.synthesize_feedback(
        round_dir,
        source=source,
        apply_safe=apply_safe,
        export_critic=export_critic,
    )
    _echo(payload, json_output=json_output)


@manuscript_app.command("status")
def manuscript_status(
    round_dir: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Report round completion status and unresolved items."""
    payload = manuscript_rounds.manuscript_status(round_dir)
    _echo(payload, json_output=json_output)


@app.command("verify")
def verify_cmd(
    before: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    after: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    profile: str = typer.Option("business-docs", "--profile", help="Fidelity profile"),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
    write_sidecar: bool = typer.Option(True, "--write-sidecar/--no-write-sidecar", help="Write report sidecars."),
) -> None:
    """Run integrity and render diff verification gates."""
    config = _load_app_config(config_path)
    persist_render_dir = None
    if write_sidecar and config.sidecar.enabled:
        persist_render_dir = render_sidecar_paths(config, after)["render_diff"]
    result = verify_mod.verify_docx(
        before,
        after,
        profile=profile,
        config=config,
        persist_render_dir=persist_render_dir,
    )

    payload = {
        "schema_version": 2,
        "verify": {
            "passed": result.passed,
            "profile": result.profile,
            "checks": result.checks,
        },
        "sidecars": {},
    }

    if write_sidecar and config.sidecar.enabled:
        sidecars = render_sidecar_paths(config, after)
        write_json(
            sidecars["report"],
            {
                "schema_version": 2,
                "verify": payload["verify"],
            },
        )
        write_json(sidecars["xml_manifest"], result.checks["manifest"])
        write_json(sidecars["revisions"], result.checks["revisions"])
        write_json(sidecars["comments"], result.checks["comment_integrity"])
        payload["sidecars"] = {
            "report": str(sidecars["report"]),
            "xml_manifest": str(sidecars["xml_manifest"]),
            "revisions": str(sidecars["revisions"]),
            "comments": str(sidecars["comments"]),
            "render_diff": str(sidecars["render_diff"]),
        }

    _echo(payload, json_output=json_output)
    if not result.passed:
        raise typer.Exit(code=2)


@app.command("render")
def render_cmd(
    docx: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    out: Path = typer.Option(..., "--out", help="Output directory for PDF and page PNGs."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Render DOCX to PDF and PNG pages for visual inspection."""
    output = render_docx(docx, out)
    payload = {
        "docx": str(output.docx_path),
        "pdf": str(output.pdf_path),
        "png_pages": [str(p) for p in output.png_paths],
    }
    _echo(payload, json_output=json_output)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
