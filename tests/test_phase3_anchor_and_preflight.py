from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from typer.testing import CliRunner

from wordmark.cli import app
from wordmark import ooxml_engine


def test_preflight_reports_reason_code_and_engine(sample_docx: Path) -> None:
    patch = {
        "operations": [
            {
                "type": "replace_paragraph_text",
                "paragraph_index": 2,
                "new_text": "Phase 3 preflight detail test",
            }
        ]
    }
    report = ooxml_engine.preflight_patch(
        sample_docx,
        patch_data=patch,
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    op = report["operations"][0]
    assert op["classification"] == "requires_uno"
    assert op["reason_code"] == "tracked_paragraph_rewrite_disallowed"
    assert op["recommended_engine"] == "uno"
    assert isinstance(op["detected_patterns"], list)


def test_replace_text_once_anchor_context_disambiguates(tmp_path: Path) -> None:
    doc_path = tmp_path / "anchor_context.docx"
    doc = Document()
    doc.add_paragraph("Section A")
    doc.add_paragraph("Draft appears in the first target paragraph.")
    doc.add_paragraph("Divider Context")
    doc.add_paragraph("Draft appears in the second target paragraph.")
    doc.save(doc_path)

    result = ooxml_engine.apply_patch(
        doc_path,
        patch_data={
            "operations": [
                {
                    "type": "replace_text_once",
                    "find": "Draft",
                    "replace": "Final",
                    "anchor": {
                        "expected_text": "Draft appears",
                        "context_before": "Divider Context",
                    },
                }
            ]
        },
        author="Barry Brook",
        track_changes=False,
        dry_run=False,
    )

    op = result.details["operations"][0]
    assert op["paragraph_index"] == 3

    report = ooxml_engine.inspect(doc_path)
    lines = report.text_value.splitlines()
    assert "Draft appears in the first target paragraph." in lines
    assert "Final appears in the second target paragraph." in lines


def test_preflight_reports_anchor_ambiguity(tmp_path: Path) -> None:
    doc_path = tmp_path / "anchor_ambiguous.docx"
    doc = Document()
    doc.add_paragraph("Draft token appears here.")
    doc.add_paragraph("Draft token appears here as well.")
    doc.save(doc_path)

    report = ooxml_engine.preflight_patch(
        doc_path,
        patch_data={
            "operations": [
                {
                    "type": "replace_text_once",
                    "find": "Draft",
                    "replace": "Final",
                    "anchor": {"expected_text": "Draft token"},
                }
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    op = report["operations"][0]
    assert op["classification"] == "unsupported_high_risk"
    assert op["reason_code"] == "anchor_ambiguous"
    assert op["recommended_engine"] == "comment_fallback"


def test_preflight_reports_anchor_not_found(tmp_path: Path) -> None:
    doc_path = tmp_path / "anchor_not_found.docx"
    doc = Document()
    doc.add_paragraph("Paragraph one.")
    doc.add_paragraph("Paragraph two.")
    doc.save(doc_path)

    report = ooxml_engine.preflight_patch(
        doc_path,
        patch_data={
            "operations": [
                {
                    "type": "replace_text_once",
                    "find": "Missing",
                    "replace": "Present",
                    "anchor": {"expected_text": "Missing"},
                }
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    op = report["operations"][0]
    assert op["classification"] == "unsupported_high_risk"
    assert op["reason_code"] == "anchor_not_found"


def test_preflight_reports_anchor_context_mismatch(tmp_path: Path) -> None:
    doc_path = tmp_path / "anchor_context_mismatch.docx"
    doc = Document()
    doc.add_paragraph("Heading")
    doc.add_paragraph("Draft token appears in this paragraph.")
    doc.add_paragraph("Trailing note")
    doc.save(doc_path)

    report = ooxml_engine.preflight_patch(
        doc_path,
        patch_data={
            "operations": [
                {
                    "type": "replace_text_once",
                    "find": "Draft",
                    "replace": "Final",
                    "anchor": {
                        "expected_text": "Draft token",
                        "context_before": "Wrong heading",
                    },
                }
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    op = report["operations"][0]
    assert op["classification"] == "unsupported_high_risk"
    assert op["reason_code"] == "anchor_context_mismatch"


def test_replace_text_once_anchor_occurrence_selects_second_match(tmp_path: Path) -> None:
    doc_path = tmp_path / "anchor_occurrence.docx"
    doc = Document()
    doc.add_paragraph("Shared target sentence.")
    doc.add_paragraph("Spacer")
    doc.add_paragraph("Shared target sentence.")
    doc.save(doc_path)

    result = ooxml_engine.apply_patch(
        doc_path,
        patch_data={
            "operations": [
                {
                    "type": "replace_text_once",
                    "find": "Shared",
                    "replace": "Updated",
                    "anchor": {
                        "expected_text": "Shared target sentence.",
                        "occurrence": 2,
                    },
                }
            ]
        },
        author="Barry Brook",
        track_changes=False,
        dry_run=False,
    )

    op = result.details["operations"][0]
    assert op["paragraph_index"] == 2

    report = ooxml_engine.inspect(doc_path)
    lines = report.text_value.splitlines()
    assert "Shared target sentence." in lines
    assert "Updated target sentence." in lines


def test_cli_comment_add_supports_anchor_json(tmp_path: Path) -> None:
    doc_path = tmp_path / "comment_anchor_json.docx"
    doc = Document()
    doc.add_paragraph("Context A")
    doc.add_paragraph("Please reviewword this paragraph.")
    doc.add_paragraph("Context B")
    doc.add_paragraph("Please reviewword this paragraph.")
    doc.save(doc_path)

    runner = CliRunner()
    anchor_json = json.dumps({"expected_text": "reviewword", "context_before": "Context B"})
    result = runner.invoke(
        app,
        [
            "comment",
            "add",
            str(doc_path),
            "--anchor-json",
            anchor_json,
            "--text",
            "Comment via anchor JSON",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["operation"]["details"]["paragraph_index"] == 3


def test_cli_comment_add_supports_anchor_occurrence(tmp_path: Path) -> None:
    doc_path = tmp_path / "comment_anchor_occurrence.docx"
    doc = Document()
    doc.add_paragraph("Repeated paragraph.")
    doc.add_paragraph("Divider")
    doc.add_paragraph("Repeated paragraph.")
    doc.save(doc_path)

    runner = CliRunner()
    anchor_json = json.dumps({"expected_text": "Repeated paragraph.", "occurrence": 2})
    result = runner.invoke(
        app,
        [
            "comment",
            "add",
            str(doc_path),
            "--anchor-json",
            anchor_json,
            "--text",
            "Comment via anchor occurrence",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["operation"]["details"]["paragraph_index"] == 2


def test_preflight_routes_risky_markup_to_uno(tmp_path: Path) -> None:
    doc_path = tmp_path / "risky_markup.docx"
    doc = Document()
    paragraph = doc.add_paragraph()
    paragraph.add_run("Alpha ")
    risky_run = paragraph.add_run()
    risky_run.add_break()
    risky_run.add_text("target")
    doc.save(doc_path)

    report = ooxml_engine.preflight_patch(
        doc_path,
        patch_data={
            "operations": [
                {
                    "type": "replace_text_once",
                    "find": "target",
                    "replace": "replacement",
                }
            ]
        },
        track_changes=True,
        allow_paragraph_rewrite_tracked=False,
    )
    op = report["operations"][0]
    assert op["classification"] == "unsupported_high_risk"
    assert op["reason_code"] == "risky_markup_detected"
    assert op["recommended_engine"] == "uno"


def test_review_prepare_merge_emits_checklist(sample_docx: Path, tmp_path: Path) -> None:
    out_path = tmp_path / "merge_report.json"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "review",
            "prepare-merge",
            str(sample_docx),
            str(sample_docx),
            "--out",
            str(out_path),
            "--json",
        ],
    )
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["word_desktop_required"] is True
    assert payload["suggested_merged_filename"].endswith(".docx")
    assert "_merged_" in payload["suggested_merged_filename"]
    assert len(payload["checklist"]) >= 4
    assert out_path.exists()
