from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from wordmark.cli import app
from wordmark import ooxml_engine


def _write_patch(path: Path, payload: dict) -> Path:
    patch_path = path.parent / "patch.json"
    patch_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    return patch_path


def test_tracked_edit_defaults_to_barry_brook(sample_docx: Path) -> None:
    runner = CliRunner()
    patch = {
        "operations": [
            {
                "type": "replace_paragraph_text",
                "paragraph_index": 2,
                "new_text": "Second paragraph updated by default author.",
            }
        ]
    }
    patch_path = _write_patch(sample_docx, patch)

    result = runner.invoke(
        app,
        ["edit", "apply", str(sample_docx), "--patch", str(patch_path), "--fidelity-mode", "aggressive", "--json"],
    )
    assert result.exit_code == 0

    review = ooxml_engine.list_review(sample_docx)
    assert any(r["type"] == "ins" and r["author"] == "Barry Brook" for r in review["revisions"])
    assert any(r["type"] == "del" and r["author"] == "Barry Brook" for r in review["revisions"])


def test_override_author_for_tracked_edit(sample_docx: Path) -> None:
    runner = CliRunner()
    patch = {
        "operations": [
            {
                "type": "replace_paragraph_text",
                "paragraph_index": 2,
                "new_text": "Second paragraph updated by custom author.",
            }
        ]
    }
    patch_path = _write_patch(sample_docx, patch)

    result = runner.invoke(
        app,
        [
            "edit",
            "apply",
            str(sample_docx),
            "--patch",
            str(patch_path),
            "--author",
            "Agent Smith",
            "--fidelity-mode",
            "aggressive",
            "--json",
        ],
    )
    assert result.exit_code == 0

    review = ooxml_engine.list_review(sample_docx)
    assert any(r["author"] == "Agent Smith" for r in review["revisions"])


def test_accept_and_reject_by_author(sample_docx: Path) -> None:
    runner = CliRunner()

    patch_a = {
        "operations": [
            {
                "type": "replace_paragraph_text",
                "paragraph_index": 2,
                "new_text": "Edit by Barry",
            }
        ]
    }
    patch_b = {
        "operations": [
            {
                "type": "replace_text_once",
                "find": "Alpha",
                "replace": "Omega",
            }
        ]
    }

    runner.invoke(
        app,
        [
            "edit",
            "apply",
            str(sample_docx),
            "--patch",
            str(_write_patch(sample_docx, patch_a)),
            "--author",
            "Barry Brook",
            "--fidelity-mode",
            "aggressive",
        ],
    )
    runner.invoke(app, ["edit", "apply", str(sample_docx), "--patch", str(_write_patch(sample_docx, patch_b)), "--author", "Other Author"])

    result = runner.invoke(app, ["review", "accept", str(sample_docx), "--author", "Barry Brook", "--json"])
    assert result.exit_code == 0

    review_after_accept = ooxml_engine.list_review(sample_docx)
    assert any(r["author"] == "Other Author" for r in review_after_accept["revisions"])
    assert not any(r["author"] == "Barry Brook" for r in review_after_accept["revisions"])

    result2 = runner.invoke(app, ["review", "reject", str(sample_docx), "--all", "--json"])
    assert result2.exit_code == 0

    review_after_reject = ooxml_engine.list_review(sample_docx)
    assert review_after_reject["revisions"] == []


def test_mixed_content_doc_survives_comment_and_revision(sample_docx: Path) -> None:
    ooxml_engine.add_comment(
        sample_docx,
        selector="p:1",
        text="Looks good, maybe shorten.",
        author="Reviewer",
        initials="RV",
        dry_run=False,
    )

    ooxml_engine.apply_patch(
        sample_docx,
        patch_data={
            "operations": [
                {
                    "type": "replace_text_once",
                    "find": "Second paragraph",
                    "replace": "Revised paragraph",
                }
            ]
        },
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
    )

    report = ooxml_engine.inspect(sample_docx)
    assert report.paragraph_count >= 4
    assert len(report.comments) >= 1
    assert len(report.revisions) >= 2
