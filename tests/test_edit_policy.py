from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from wordmark.cli import app
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
                "type": "replace_paragraph_text",
                "paragraph_index": 2,
                "new_text": "Fallback via comment",
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
                "type": "replace_paragraph_text",
                "paragraph_index": 2,
                "new_text": "Fail policy",
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
