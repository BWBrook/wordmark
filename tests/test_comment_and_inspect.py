from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from wordmark.cli import app
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
    assert "sidecars" in result.stdout
