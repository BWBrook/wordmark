"""Input validation helpers for CLI JSON payloads."""

from __future__ import annotations

import json
from typing import Any


class ValidationError(ValueError):
    """Raised when a user-supplied JSON payload is structurally invalid."""


def parse_json_object(raw: str, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{label} must be valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValidationError(f"{label} must be a JSON object")
    return parsed


def _require_string(op: dict[str, Any], key: str, *, index: int, allow_empty: bool = True) -> str:
    value = op.get(key)
    if not isinstance(value, str):
        raise ValidationError(f"operations[{index}].{key} must be a string")
    if not allow_empty and value == "":
        raise ValidationError(f"operations[{index}].{key} must be a non-empty string")
    return value


def _optional_int(value: Any, *, label: str, min_value: int | None = None) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{label} must be an integer")
    if min_value is not None and value < min_value:
        raise ValidationError(f"{label} must be >= {min_value}")


def validate_anchor_payload(anchor: dict[str, Any]) -> dict[str, Any]:
    allowed = {"paragraph_index", "expected_text", "context_before", "context_after", "occurrence"}
    unknown = sorted(set(anchor) - allowed)
    if unknown:
        raise ValidationError(f"anchor contains unsupported field(s): {', '.join(unknown)}")

    _optional_int(anchor.get("paragraph_index"), label="anchor.paragraph_index", min_value=0)
    _optional_int(anchor.get("occurrence"), label="anchor.occurrence", min_value=1)
    for key in ("expected_text", "context_before", "context_after"):
        value = anchor.get(key)
        if value is not None and not isinstance(value, str):
            raise ValidationError(f"anchor.{key} must be a string")
    return anchor


def validate_anchor_selector(selector: str) -> str:
    if selector.startswith("p:"):
        raw_index = selector.split(":", 1)[1]
        try:
            index = int(raw_index)
        except ValueError as exc:
            raise ValidationError("--anchor p:<index> requires an integer paragraph index") from exc
        if index < 0:
            raise ValidationError("--anchor p:<index> requires a non-negative paragraph index")
        return selector
    if selector.startswith("text:"):
        if selector.split(":", 1)[1] == "":
            raise ValidationError("--anchor text:<snippet> requires a non-empty snippet")
        return selector
    raise ValidationError("Unsupported --anchor selector. Use 'p:<index>' or 'text:<snippet>'")


def validate_patch_payload(patch_data: dict[str, Any]) -> dict[str, Any]:
    operations = patch_data.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValidationError("Patch must include a non-empty 'operations' list")

    allowed_types = {
        "replace_paragraph_text",
        "replace_text_once",
        "replace_text_global",
        "replace_span_once",
    }
    for index, op in enumerate(operations):
        if not isinstance(op, dict):
            raise ValidationError(f"operations[{index}] must be an object")
        op_type = op.get("type")
        if not isinstance(op_type, str) or op_type == "":
            raise ValidationError(f"operations[{index}].type must be a non-empty string")
        if op_type not in allowed_types:
            raise ValidationError(f"operations[{index}].type is unsupported: {op_type}")

        raw_anchor = op.get("anchor")
        if raw_anchor is not None:
            if not isinstance(raw_anchor, dict):
                raise ValidationError(f"operations[{index}].anchor must be an object")
            validate_anchor_payload(raw_anchor)

        _optional_int(op.get("paragraph_index"), label=f"operations[{index}].paragraph_index", min_value=0)
        _optional_int(op.get("occurrence"), label=f"operations[{index}].occurrence", min_value=1)

        if op_type in {"replace_text_once", "replace_text_global"}:
            _require_string(op, "find", index=index, allow_empty=False)
            _require_string(op, "replace", index=index)
        elif op_type == "replace_paragraph_text":
            _require_string(op, "new_text", index=index)
            expected = op.get("expected_text")
            if expected is not None and not isinstance(expected, str):
                raise ValidationError(f"operations[{index}].expected_text must be a string")
        elif op_type == "replace_span_once":
            _require_string(op, "find", index=index, allow_empty=False)
            _require_string(op, "replacement", index=index)
            _optional_int(op.get("span_start"), label=f"operations[{index}].span_start", min_value=0)
            _optional_int(op.get("span_length"), label=f"operations[{index}].span_length", min_value=0)
            if "span_start" not in op or "span_length" not in op:
                raise ValidationError(f"operations[{index}] replace_span_once requires span_start and span_length")

    return patch_data

