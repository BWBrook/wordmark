"""Edit-policy and risk-summary helpers used by CLI orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wordmark import interop_drift
from wordmark.config import AppConfig
from wordmark.models import OperationResult
from wordmark import ooxml_engine


def resolve_choice(name: str, value: str, allowed: set[str]) -> str:
    token = value.strip().lower()
    if token not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {allowed_list}")
    return token


def resolve_edit_policy(
    config: AppConfig,
    *,
    fidelity_mode: str | None,
    on_unsupported: str | None,
    on_uno_fail: str | None,
    allow_paragraph_rewrite: bool | None,
) -> dict[str, Any]:
    mode = resolve_choice("fidelity_mode", fidelity_mode or config.fidelity_mode, {"strict", "balanced", "aggressive"})
    unsupported_policy = resolve_choice(
        "on_unsupported",
        on_unsupported or config.fallback_policy.on_ooxml_unsupported,
        {"fail", "comment", "uno"},
    )
    uno_fail_policy = resolve_choice(
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


def count_risky_preflight_ops(preflight: dict[str, Any]) -> int:
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


def used_uno_fallback(attempts: list[dict[str, Any]]) -> bool:
    for attempt in attempts:
        engine = str(attempt.get("engine"))
        status = str(attempt.get("status"))
        if engine == "uno" and status in {"applied", "retry_applied"}:
            return True
    return False


def precision_rewrite_count(result: OperationResult) -> int:
    rewrite = result.details.get("uno_precision_rewrite")
    if not isinstance(rewrite, dict):
        return 0
    try:
        return int(rewrite.get("rewritten_operations", 0))
    except (TypeError, ValueError):
        return 0


def analyze_interop_drift(
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


def build_risk_summary(
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
        "used_uno_fallback": used_uno_fallback(attempts),
        "risky_operations_count": count_risky_preflight_ops(preflight),
        "precision_rewrite_count": precision_rewrite_count(result),
        "drift_check_enabled": drift_check_enabled,
        "drift_warning_threshold": drift_threshold if drift_check_enabled else None,
        "drift_detected": drift_detected,
        "drift_warning": drift_warning,
        "drift_severity": drift_severity,
        "mode": str(policy.get("fidelity_mode", "")),
    }
