"""Deterministic rewrite helpers for precision-preserving UNO fallback patches."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Any


def _replacement_delta(old_text: str, new_text: str) -> tuple[str, str, str, str]:
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


def build_minimal_uno_replace_once(
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

    common_prefix, old_middle, _common_suffix, new_middle = _replacement_delta(find_text, replace_text)
    if not old_middle and not new_middle:  # pragma: no cover - defensive
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


def build_split_uno_replace_sequence(
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
        rewritten_step, step_info = build_minimal_uno_replace_once(op=step_op, op_index=op_index)
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


def prepare_uno_precision_patch(_docx: Path, patch_data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
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
            split_ops, split_info = build_split_uno_replace_sequence(op=op, op_index=index)
            if split_ops is not None and split_info is not None:
                rewritten_ops.extend(split_ops)
                op_results.append(split_info)
                rewritten_count += 1
                continue

            prepared_op, info = build_minimal_uno_replace_once(op=op, op_index=index)
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


def build_uno_low_hit_retry_patch(uno_payload: dict[str, Any]) -> dict[str, Any] | None:
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

        if op_type == "replace_text_global" and status == "not_found":
            retry_op = dict(requested)
            retry_op["type"] = "replace_text_once"
            retry_op["occurrence"] = int(retry_op.get("occurrence", 1))
            retry_ops.append(retry_op)

    if not retry_ops:
        return None
    return {"operations": retry_ops}


def should_retry_uno_low_hit(uno_payload: dict[str, Any]) -> bool:
    summary = uno_payload.get("summary")
    if not isinstance(summary, dict):
        return False
    return int(summary.get("operations_without_hits", 0)) > 0
