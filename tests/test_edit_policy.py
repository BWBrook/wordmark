from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from wordmark.cli import _prepare_uno_precision_patch, app
from wordmark.models import OperationResult
from wordmark import ooxml_engine
from wordmark import uno_engine


def _write_patch(path: Path, payload: dict) -> Path:
    patch_path = path.parent / "policy_patch.json"
    patch_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    return patch_path


def test_preflight_only_does_not_mutate(sample_docx: Path) -> None:
    runner = CliRunner()
    patch = {
        "operations": [
            {
                "type": "replace_paragraph_text",
                "paragraph_index": 2,
                "new_text": "Policy preflight paragraph",
            }
        ]
    }
    patch_path = _write_patch(sample_docx, patch)

    result = runner.invoke(app, ["edit", "apply", str(sample_docx), "--patch", str(patch_path), "--preflight-only", "--json"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["preflight_only"] is True
    assert payload["policy"]["fidelity_mode"] == "strict"
    op = payload["preflight"]["operations"][0]
    assert op["classification"] == "requires_uno"

    review = ooxml_engine.list_review(sample_docx)
    assert review["revisions"] == []
    assert review["comments"] == []


def test_strict_mode_comment_fallback_after_uno_failure(sample_docx: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    patch = {
        "operations": [
            {
                "type": "replace_text_global",
                "find": "Second paragraph",
                "replace": "Fallback via comment",
            }
        ]
    }
    patch_path = _write_patch(sample_docx, patch)

    def fake_uno_apply_patch(*args, **kwargs):  # noqa: ANN002, ANN003
        raise uno_engine.UnoEngineError("simulated uno failure")

    monkeypatch.setattr(uno_engine, "apply_patch", fake_uno_apply_patch)

    result = runner.invoke(app, ["edit", "apply", str(sample_docx), "--patch", str(patch_path), "--json"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["operation"]["engine"] == "comment_fallback"

    review = ooxml_engine.list_review(sample_docx)
    assert review["revisions"] == []
    assert len(review["comments"]) == 1
    assert "Suggested edit" in review["comments"][0]["text"]


def test_strict_mode_fail_policy_exits_nonzero(sample_docx: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    patch = {
        "operations": [
            {
                "type": "replace_text_global",
                "find": "Second paragraph",
                "replace": "Fail policy",
            }
        ]
    }
    patch_path = _write_patch(sample_docx, patch)

    def fake_uno_apply_patch(*args, **kwargs):  # noqa: ANN002, ANN003
        raise uno_engine.UnoEngineError("simulated uno failure")

    monkeypatch.setattr(uno_engine, "apply_patch", fake_uno_apply_patch)

    result = runner.invoke(
        app,
        [
            "edit",
            "apply",
            str(sample_docx),
            "--patch",
            str(patch_path),
            "--on-uno-fail",
            "fail",
            "--json",
        ],
    )
    assert result.exit_code == 1

    review = ooxml_engine.list_review(sample_docx)
    assert review["revisions"] == []
    assert review["comments"] == []


def test_uno_low_hit_retry_is_reported(sample_docx: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    patch = {
        "operations": [
            {
                "type": "replace_text_global",
                "find": "not-present-long-form",
                "replace": "present-short-form",
            }
        ]
    }
    patch_path = _write_patch(sample_docx, patch)

    calls: list[dict[str, object]] = []

    def fake_uno_apply_patch(*args, **kwargs):  # noqa: ANN002, ANN003
        patch_data = kwargs["patch_data"]
        calls.append(patch_data)
        if len(calls) == 1:
            return OperationResult.now(
                command="edit apply",
                path=sample_docx,
                engine="uno",
                changed=False,
                author="Barry Brook",
                details={
                    "uno": {
                        "summary": {"requested_operations": 1, "operations_with_hits": 0, "operations_without_hits": 1},
                        "operation_results": [
                            {
                                "index": 0,
                                "type": "replace_text_global",
                                "status": "not_found",
                                "replaced_count": 0,
                                "requested": patch["operations"][0],
                            }
                        ],
                    }
                },
            )

        assert patch_data["operations"][0]["type"] == "replace_text_once"
        assert patch_data["operations"][0]["occurrence"] == 1
        return OperationResult.now(
            command="edit apply",
            path=sample_docx,
            engine="uno",
            changed=True,
            author="Barry Brook",
            details={
                "uno": {
                    "summary": {"requested_operations": 1, "operations_with_hits": 1, "operations_without_hits": 0},
                    "operation_results": [
                        {
                            "index": 0,
                            "type": "replace_text_once",
                            "status": "applied",
                            "replaced_count": 1,
                            "requested": patch_data["operations"][0],
                        }
                    ],
                }
            },
        )

    monkeypatch.setattr(uno_engine, "apply_patch", fake_uno_apply_patch)

    result = runner.invoke(app, ["edit", "apply", str(sample_docx), "--patch", str(patch_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["operation"]["details"]["uno_retry"]["attempted"] is True
    assert payload["operation"]["details"]["uno_retry"]["patch"]["operations"][0]["type"] == "replace_text_once"
    assert any(item["status"] == "retry_applied" for item in payload["attempts"])


def test_prepare_uno_precision_patch_rewrites_insertion_to_suffix_anchor(sample_docx: Path) -> None:
    patch = {
        "operations": [
            {
                "type": "replace_text_once",
                "find": "Second paragraph for tracked replacement operations.",
                "replace": "Second paragraph for carefully tracked replacement operations.",
            }
        ]
    }

    prepared, info = _prepare_uno_precision_patch(sample_docx, patch)
    assert info is not None
    assert info["status"] == "rewritten"
    assert info["rewritten_operations"] == 1

    op = prepared["operations"][0]
    assert op["type"] == "replace_span_once"
    assert op["find"] == "Second paragraph for tracked replacement operations."
    assert op["occurrence"] == 1
    assert op["span_start"] == len("Second paragraph for ")
    assert op["span_length"] == 0
    assert op["replacement"] == "carefully "


def test_edit_apply_records_uno_precision_rewrite(sample_docx: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    patch = {
        "operations": [
            {
                "type": "replace_text_once",
                "find": "Second paragraph for tracked replacement operations.",
                "replace": "Second paragraph for carefully tracked replacement operations.",
            }
        ]
    }
    patch_path = _write_patch(sample_docx, patch)

    def fake_ooxml_apply_patch(*args, **kwargs):  # noqa: ANN002, ANN003
        raise ooxml_engine.OoxmlUnsupportedOperation("risky ooxml markup")

    captured_uno_patch: dict[str, object] = {}

    def fake_uno_apply_patch(*args, **kwargs):  # noqa: ANN002, ANN003
        patch_data = kwargs["patch_data"]
        captured_uno_patch["patch_data"] = patch_data
        return OperationResult.now(
            command="edit apply",
            path=sample_docx,
            engine="uno",
            changed=True,
            author="Barry Brook",
            details={
                "uno": {
                    "summary": {"requested_operations": 1, "operations_with_hits": 1, "operations_without_hits": 0},
                    "operation_results": [
                        {
                            "index": 0,
                            "type": patch_data["operations"][0]["type"],
                            "status": "applied",
                            "replaced_count": 1,
                            "requested": patch_data["operations"][0],
                        }
                    ],
                }
            },
        )

    monkeypatch.setattr(ooxml_engine, "apply_patch", fake_ooxml_apply_patch)
    monkeypatch.setattr(uno_engine, "apply_patch", fake_uno_apply_patch)

    result = runner.invoke(app, ["edit", "apply", str(sample_docx), "--patch", str(patch_path), "--json"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    rewrite = payload["operation"]["details"]["uno_precision_rewrite"]
    assert rewrite["attempted"] is True
    assert rewrite["rewritten_operations"] == 1

    prepared = captured_uno_patch["patch_data"]
    assert isinstance(prepared, dict)
    op = prepared["operations"][0]
    assert op["type"] == "replace_span_once"
    assert op["find"] == "Second paragraph for tracked replacement operations."
    assert op["span_length"] == 0
    assert op["replacement"] == "carefully "


def test_prepare_uno_precision_patch_widens_punctuation_delta_with_context(tmp_path: Path) -> None:
    from docx import Document

    doc_path = tmp_path / "punctuation.docx"
    doc = Document()
    doc.add_paragraph(
        "In terms of habitat, forest ecosystems dominated the literature; temperate and tropical forests were common."
    )
    doc.save(doc_path)

    patch = {
        "operations": [
            {
                "type": "replace_text_once",
                "find": "forest ecosystems dominated the literature;",
                "replace": "forest ecosystems dominated the literature,",
            }
        ]
    }

    prepared, info = _prepare_uno_precision_patch(doc_path, patch)
    assert info is not None
    assert info["rewritten_operations"] == 1

    op = prepared["operations"][0]
    assert op["type"] == "replace_span_once"
    assert op["find"] == "forest ecosystems dominated the literature;"
    assert op["span_start"] == len("forest ecosystems dominated the literature")
    assert op["span_length"] == 1
    assert op["replacement"] == ","


def test_prepare_uno_precision_patch_rewrites_tail_append_without_suffix(sample_docx: Path) -> None:
    patch = {
        "operations": [
            {
                "type": "replace_text_once",
                "find": "Second paragraph for tracked replacement operations.",
                "replace": "Second paragraph for tracked replacement operations. Please confirm.",
            }
        ]
    }

    prepared, info = _prepare_uno_precision_patch(sample_docx, patch)
    assert info is not None
    assert info["rewritten_operations"] == 1

    op = prepared["operations"][0]
    assert op["type"] == "replace_span_once"
    assert op["find"] == "Second paragraph for tracked replacement operations."
    assert op["span_start"] == len("Second paragraph for tracked replacement operations.")
    assert op["span_length"] == 0
    assert op["replacement"] == " Please confirm."


def test_prepare_uno_precision_patch_rewrites_sentence_to_internal_span(tmp_path: Path) -> None:
    from docx import Document

    doc_path = tmp_path / "word-token.docx"
    doc = Document()
    doc.add_paragraph("Median absolute deviations are provided in the appendix.")
    doc.save(doc_path)

    patch = {
        "operations": [
            {
                "type": "replace_text_once",
                "find": "Median absolute deviations are provided in the appendix.",
                "replace": "Median absolute deviations are reported in the appendix.",
            }
        ]
    }

    prepared, info = _prepare_uno_precision_patch(doc_path, patch)
    assert info is not None
    assert info["rewritten_operations"] == 1

    op = prepared["operations"][0]
    assert op["type"] == "replace_span_once"
    assert op["find"] == "Median absolute deviations are provided in the appendix."
    assert op["span_start"] == len("Median absolute deviations are ")
    assert op["span_length"] == len("provided")
    assert op["replacement"] == "reported"


def test_prepare_uno_precision_patch_expands_single_token_boundaries(sample_docx: Path) -> None:
    patch = {
        "operations": [
            {
                "type": "replace_text_once",
                "find": "The field displays a strong terrestrial filter:",
                "replace": "The field shows a strong terrestrial filter:",
            }
        ]
    }

    prepared, info = _prepare_uno_precision_patch(sample_docx, patch)
    assert info is not None
    assert info["rewritten_operations"] == 1

    op = prepared["operations"][0]
    assert op["type"] == "replace_span_once"
    assert op["find"] == "The field displays a strong terrestrial filter:"
    assert op["span_start"] == len("The field ")
    assert op["span_length"] == len("displays")
    assert op["replacement"] == "shows"


def test_prepare_uno_precision_patch_avoids_partial_word_boundary(tmp_path: Path) -> None:
    from docx import Document

    doc_path = tmp_path / "boundary.docx"
    doc = Document()
    doc.add_paragraph("Models were fitted using Non-linear Least-square Regression.")
    doc.save(doc_path)

    patch = {
        "operations": [
            {
                "type": "replace_text_once",
                "find": "Models were fitted using Non-linear Least-square Regression.",
                "replace": "Models were fitted using non-linear least-squares regression.",
            }
        ]
    }

    prepared, info = _prepare_uno_precision_patch(doc_path, patch)
    assert info is not None
    assert info["rewritten_operations"] == 1

    op = prepared["operations"][0]
    assert op["type"] == "replace_span_once"
    assert "regression" in op["replacement"]
    assert not op["replacement"].endswith(" r")


def test_edit_apply_emits_interop_drift_and_risk_summary(sample_docx: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    patch = {
        "operations": [
            {
                "type": "replace_text_once",
                "find": "Second paragraph",
                "replace": "Updated paragraph",
            }
        ]
    }
    patch_path = _write_patch(sample_docx, patch)

    inspect_calls = {"count": 0}

    def fake_preflight_patch(*args, **kwargs):  # noqa: ANN002, ANN003
        return {
            "operations": [
                {
                    "classification": "unsupported_high_risk",
                    "reason_code": "risky_markup_detected",
                }
            ]
        }

    def fake_inspect(*args, **kwargs):  # noqa: ANN002, ANN003
        inspect_calls["count"] += 1
        if inspect_calls["count"] == 1:
            return SimpleNamespace(text="Figure 2 shows accumulation.")
        return SimpleNamespace(text="Figure 1 shows accumulation.")

    def fake_ooxml_apply_patch(*args, **kwargs):  # noqa: ANN002, ANN003
        return OperationResult.now(
            command="edit apply",
            path=sample_docx,
            engine="ooxml",
            changed=True,
            author="Barry Brook",
            details={
                "uno_precision_rewrite": {
                    "rewritten_operations": 2,
                }
            },
        )

    monkeypatch.setattr(ooxml_engine, "preflight_patch", fake_preflight_patch)
    monkeypatch.setattr(ooxml_engine, "inspect", fake_inspect)
    monkeypatch.setattr(ooxml_engine, "apply_patch", fake_ooxml_apply_patch)

    result = runner.invoke(app, ["edit", "apply", str(sample_docx), "--patch", str(patch_path), "--json"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    details = payload["operation"]["details"]
    drift = details["interop_drift"]
    summary = details["risk_summary"]

    assert drift["detected"] is True
    assert "figure_ref_shift" in drift["signals"]
    assert drift["warning"] is True

    assert summary["used_uno_fallback"] is False
    assert summary["risky_operations_count"] == 1
    assert summary["precision_rewrite_count"] == 2
    assert summary["drift_check_enabled"] is True
    assert summary["drift_warning_threshold"] == "low"
    assert summary["drift_detected"] is True
    assert summary["drift_warning"] is True
    assert summary["drift_severity"] == "low"


def test_edit_apply_can_disable_drift_and_risk_summary(sample_docx: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    patch = {
        "operations": [
            {
                "type": "replace_text_once",
                "find": "Second paragraph",
                "replace": "Updated paragraph",
            }
        ]
    }
    patch_path = _write_patch(sample_docx, patch)

    def fake_inspect(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("inspect should not be called when --no-drift-check is active")

    def fake_ooxml_apply_patch(*args, **kwargs):  # noqa: ANN002, ANN003
        return OperationResult.now(
            command="edit apply",
            path=sample_docx,
            engine="ooxml",
            changed=True,
            author="Barry Brook",
            details={},
        )

    monkeypatch.setattr(ooxml_engine, "inspect", fake_inspect)
    monkeypatch.setattr(ooxml_engine, "apply_patch", fake_ooxml_apply_patch)

    result = runner.invoke(
        app,
        [
            "edit",
            "apply",
            str(sample_docx),
            "--patch",
            str(patch_path),
            "--no-drift-check",
            "--no-emit-risk-summary",
            "--json",
        ],
    )
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    details = payload["operation"]["details"]
    assert "interop_drift" not in details
    assert "risk_summary" not in details
