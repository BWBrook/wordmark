from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from wordmark.cli import app
from wordmark.docx_package import DocxPackage
from wordmark import ooxml_engine


def test_add_comment_with_explicit_author_metadata(sample_docx: Path) -> None:
    result = ooxml_engine.add_comment(
        sample_docx,
        selector="p:1",
        text="Please tighten this sentence.",
        author="Reviewer A",
        initials="RA",
        dry_run=False,
    )
    assert result.changed

    report = ooxml_engine.inspect(sample_docx)
    assert len(report.comments) == 1
    assert report.comments[0].author == "Reviewer A"
    assert report.comments[0].initials == "RA"
    assert "tighten" in report.comments[0].text


def test_add_comment_creates_comments_infrastructure(sample_docx: Path) -> None:
    result = ooxml_engine.add_comment(
        sample_docx,
        selector="p:1",
        text="Infrastructure creation check.",
        author="Reviewer A",
        initials="RA",
        dry_run=False,
    )
    assert result.changed

    pkg = DocxPackage.open(sample_docx)
    assert pkg.has_part("word/comments.xml")
    assert pkg.has_part("word/_rels/document.xml.rels")

    rels_root = pkg.read_xml("word/_rels/document.xml.rels")
    rel_types = [rel.get("Type") for rel in rels_root]
    assert "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" in rel_types

    content_types = pkg.read_xml("[Content_Types].xml")
    override_types = [item.get("ContentType") for item in content_types]
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml" in override_types


def test_cli_inspect_writes_sidecars(sample_docx: Path) -> None:
    cfg_path = sample_docx.parent / "wordmark.test.yaml"
    cfg_payload = {
        "sidecar": {
            "enabled": True,
            "paths": {
                "text": str(sample_docx.parent / "{stem}.text.md"),
                "comments": str(sample_docx.parent / "{stem}.comments.json"),
                "revisions": str(sample_docx.parent / "{stem}.revisions.json"),
                "xml_manifest": str(sample_docx.parent / "{stem}.xml-manifest.json"),
                "report": str(sample_docx.parent / "{stem}.report.json"),
                "render_diff": str(sample_docx.parent / "{stem}.render"),
            },
        },
    }
    cfg_path.write_text(yaml.safe_dump(cfg_payload), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["inspect", str(sample_docx), "--config", str(cfg_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 2
    assert payload["report"]["text_mode"] == "review-visible"
    assert "text_value" in payload["report"]
    assert "sidecars" in payload

    sidecar_path = sample_docx.parent / f"{sample_docx.stem}.text.md"
    assert sidecar_path.exists()
    assert sidecar_path.read_text(encoding="utf-8").strip() == payload["report"]["text_value"].strip()


def test_cli_inspect_supports_raw_text_mode(sample_docx: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["inspect", str(sample_docx), "--text-mode", "raw", "--json"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 2
    assert payload["report"]["text_mode"] == "raw"


def test_cli_review_list_schema_v2(sample_docx: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["review", "list", str(sample_docx), "--json"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 2
    assert payload["review"]["text_mode"] == "review-visible"
    assert "text_value" in payload["review"]
