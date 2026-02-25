"""Cross-reference drift analysis for edited DOCX text snapshots."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

_REF_PATTERNS: dict[str, re.Pattern[str]] = {
    "figure": re.compile(r"\b(?:Figure|Fig\.?)\s+([0-9]+[A-Za-z]?)\b", flags=re.IGNORECASE),
    "table": re.compile(r"\bTable\s+([0-9]+[A-Za-z]?)\b", flags=re.IGNORECASE),
    "equation": re.compile(r"\b(?:Equation|Eq\.?)\s+([0-9]+[A-Za-z]?)\b", flags=re.IGNORECASE),
    "appendix": re.compile(r"\bAppendix\s+([A-Za-z0-9]+)\b", flags=re.IGNORECASE),
}

_SEVERITY_ORDER = {"none": 0, "low": 1, "moderate": 2, "high": 3}


def _normalize_threshold(value: str) -> str:
    token = value.strip().lower()
    if token not in {"low", "moderate", "high"}:
        raise ValueError("drift_warning_threshold must be one of: low, moderate, high")
    return token


def _extract_mentions(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for family, pattern in _REF_PATTERNS.items():
        out[family] = [match.group(1) for match in pattern.finditer(text)]
    return out


def _mentions_to_counts(mentions: dict[str, list[str]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for family, values in mentions.items():
        counter = Counter(values)
        out[family] = {token: int(counter[token]) for token in sorted(counter)}
    return out


def _parse_numeric_prefix(token: str) -> int | None:
    match = re.match(r"^([0-9]+)", token)
    if match is None:
        return None
    return int(match.group(1))


def _constant_numeric_shift(before: list[str], after: list[str]) -> int | None:
    if len(before) != len(after) or not before:
        return None

    before_nums: list[int] = []
    after_nums: list[int] = []
    for b_token, a_token in zip(before, after):
        b_num = _parse_numeric_prefix(b_token)
        a_num = _parse_numeric_prefix(a_token)
        if b_num is None or a_num is None:
            return None
        before_nums.append(b_num)
        after_nums.append(a_num)

    deltas = {a - b for b, a in zip(before_nums, after_nums)}
    if len(deltas) != 1:
        return None
    delta = next(iter(deltas))
    if delta == 0:
        return None
    return delta


def _family_delta(family: str, before: list[str], after: list[str]) -> dict[str, Any] | None:
    before_counter = Counter(before)
    after_counter = Counter(after)
    if before_counter == after_counter:
        return None

    removed = before_counter - after_counter
    added = after_counter - before_counter
    magnitude = int(sum(removed.values()) + sum(added.values()))

    signal_kind = "count_change"
    signal = f"{family}_ref_count_change"
    details: dict[str, Any] = {}

    if len(before) == len(after):
        shift = _constant_numeric_shift(before, after)
        if shift is not None:
            signal_kind = "shift"
            signal = f"{family}_ref_shift"
            details["delta"] = shift
        else:
            signal_kind = "redistribution"
            signal = f"{family}_ref_redistribution"

    return {
        "family": family,
        "signal": signal,
        "kind": signal_kind,
        "magnitude": magnitude,
        "before_total": len(before),
        "after_total": len(after),
        "details": details,
    }


def _severity(changed_family_count: int, magnitude: int) -> str:
    if changed_family_count == 0:
        return "none"
    if changed_family_count == 1 and magnitude <= 4:
        return "low"
    if changed_family_count <= 2 and magnitude <= 8:
        return "moderate"
    return "high"


def analyze_reference_drift(
    before_text: str,
    after_text: str,
    *,
    warning_threshold: str = "low",
) -> dict[str, Any]:
    """Analyze likely cross-reference drift between text snapshots."""
    threshold = _normalize_threshold(warning_threshold)
    before_mentions = _extract_mentions(before_text)
    after_mentions = _extract_mentions(after_text)

    deltas: list[dict[str, Any]] = []
    for family in sorted(_REF_PATTERNS):
        family_delta = _family_delta(family, before_mentions[family], after_mentions[family])
        if family_delta is not None:
            deltas.append(family_delta)

    detected = bool(deltas)
    changed_families = [item["family"] for item in deltas]
    magnitude = int(sum(int(item["magnitude"]) for item in deltas))
    severity = _severity(len(changed_families), magnitude)
    warning = bool(detected and _SEVERITY_ORDER[severity] >= _SEVERITY_ORDER[threshold])

    recommended_action = "No cross-reference drift detected."
    if severity == "low":
        recommended_action = "Review changed references in Word desktop before merge."
    elif severity in {"moderate", "high"}:
        recommended_action = "Run Word desktop compare/combine and verify all cross-references before merge."

    return {
        "detected": detected,
        "warning": warning,
        "warning_threshold": threshold,
        "severity": severity,
        "signals": [item["signal"] for item in deltas],
        "changed_families": changed_families,
        "change_magnitude": magnitude,
        "family_deltas": deltas,
        "before_counts": _mentions_to_counts(before_mentions),
        "after_counts": _mentions_to_counts(after_mentions),
        "recommended_action": recommended_action,
    }
