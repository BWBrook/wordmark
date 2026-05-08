from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from wordmark.cli import app


def _write_patch(path: Path, payload: object | str) -> Path:
    patch_path = path.parent / "patch.json"
    if isinstance(payload, str):
        patch_path.write_text(payload, encoding="utf-8")
    else:
        patch_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    return patch_path


def test_edit_apply_rejects_non_object_patch(sample_docx: Path) -> None:
    runner = CliRunner()
    patch = _write_patch(sample_docx, [])

    result = runner.invoke(app, ["edit", "apply", str(sample_docx), "--patch", str(patch), "--json"])

    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "--patch must be a JSON object" in str(result.exception)


def test_edit_apply_rejects_empty_find(sample_docx: Path) -> None:
    runner = CliRunner()
    patch = _write_patch(sample_docx, {"operations": [{"type": "replace_text_once", "find": "", "replace": "x"}]})

    result = runner.invoke(app, ["edit", "apply", str(sample_docx), "--patch", str(patch), "--json"])

    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "operations[0].find must be a non-empty string" in str(result.exception)


def test_edit_apply_rejects_unknown_operation_type(sample_docx: Path) -> None:
    runner = CliRunner()
    patch = _write_patch(sample_docx, {"operations": [{"type": "typo_replace", "find": "a", "replace": "b"}]})

    result = runner.invoke(app, ["edit", "apply", str(sample_docx), "--patch", str(patch), "--json"])

    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "operations[0].type is unsupported" in str(result.exception)


def test_comment_add_requires_one_anchor_mode(sample_docx: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "comment",
            "add",
            str(sample_docx),
            "--anchor",
            "p:1",
            "--anchor-json",
            '{"paragraph_index": 1}',
            "--text",
            "Comment text",
            "--json",
        ],
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "exactly one" in str(result.exception)


def test_comment_add_rejects_bad_anchor_json(sample_docx: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "comment",
            "add",
            str(sample_docx),
            "--anchor-json",
            '{"occurrence": 0}',
            "--text",
            "Comment text",
            "--json",
        ],
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "anchor.occurrence must be >= 1" in str(result.exception)


def test_comment_add_rejects_bad_anchor_selector(sample_docx: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "comment",
            "add",
            str(sample_docx),
            "--anchor",
            "p:not-an-int",
            "--text",
            "Comment text",
            "--json",
        ],
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "integer paragraph index" in str(result.exception)

