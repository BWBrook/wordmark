from __future__ import annotations

import json
import re
import shutil
from types import SimpleNamespace
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image
import pytest
from typer.testing import CliRunner

from wordmark.config import load_config
from wordmark.cli import app
from wordmark.external_tools import render_tools_available
from wordmark.render import RenderError, convert_docx_to_pdf, convert_pdf_to_png, render_docx
from wordmark import verify as verify_mod
from wordmark.verify import verify_docx


pytestmark = [pytest.mark.external_tools, pytest.mark.rendering]
requires_render_tools = pytest.mark.skipif(not render_tools_available(), reason="Render tools unavailable: soffice/pdftoppm")


def _inject_ignorable_prefix_mismatch(path: Path) -> None:
    with ZipFile(path, "r") as zin:
        parts = {name: zin.read(name) for name in zin.namelist()}

    xml = parts["word/document.xml"].decode("utf-8")
    root_match = re.search(r"<w:document\b[^>]*>", xml)
    assert root_match is not None
    root_tag = root_match.group(0)

    if 'xmlns:mc="' not in root_tag:
        root_tag = root_tag[:-1] + ' xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'

    root_tag = re.sub(r'\s+xmlns:w14="[^"]*"', "", root_tag)
    root_tag = re.sub(r'\s+xmlns:wp14="[^"]*"', "", root_tag)

    if re.search(r'\b(?:mc|ns\d+):Ignorable="[^"]*"', root_tag):
        root_tag = re.sub(r'\b(?:mc|ns\d+):Ignorable="[^"]*"', 'mc:Ignorable="w14 wp14"', root_tag, count=1)
    else:
        root_tag = root_tag[:-1] + ' mc:Ignorable="w14 wp14">'

    xml = xml[: root_match.start()] + root_tag + xml[root_match.end() :]
    parts["word/document.xml"] = xml.encode("utf-8")

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zout:
        for name in sorted(parts.keys()):
            zout.writestr(name, parts[name])


def _remove_comments_part(path: Path) -> None:
    with ZipFile(path, "r") as zin:
        parts = {name: zin.read(name) for name in zin.namelist() if name != "word/comments.xml"}

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zout:
        for name in sorted(parts.keys()):
            zout.writestr(name, parts[name])


@requires_render_tools
def test_render_produces_pdf_and_pngs(sample_docx: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "render"
    output = render_docx(sample_docx, out_dir)
    assert output.pdf_path.exists()
    assert len(output.png_paths) >= 1


@requires_render_tools
def test_verify_identical_documents_pass(sample_docx: Path, tmp_path: Path) -> None:
    before = tmp_path / "before.docx"
    after = tmp_path / "after.docx"
    shutil.copy2(sample_docx, before)
    shutil.copy2(sample_docx, after)

    cfg = load_config(Path("wordmark.yaml"))
    result = verify_docx(before, after, profile="business-docs", config=cfg)
    assert result.passed
    assert result.checks["comment_integrity"]["ok"]
    assert result.checks["render_diff"]["ok"]


@requires_render_tools
def test_verify_can_persist_render_artifacts(sample_docx: Path, tmp_path: Path) -> None:
    before = tmp_path / "before.docx"
    after = tmp_path / "after.docx"
    render_dir = tmp_path / "render-artifacts"
    shutil.copy2(sample_docx, before)
    shutil.copy2(sample_docx, after)

    cfg = load_config(Path("wordmark.yaml"))
    result = verify_docx(
        before,
        after,
        profile="business-docs",
        config=cfg,
        persist_render_dir=render_dir,
    )
    assert result.passed
    assert any(render_dir.glob("before-page-*.png"))
    assert any(render_dir.glob("after-page-*.png"))
    assert any(render_dir.glob("diff-page-*.png"))


def test_render_diff_page_growth_tolerance(monkeypatch, sample_docx: Path, tmp_path: Path) -> None:  # noqa: ANN001
    before = tmp_path / "before.docx"
    after = tmp_path / "after.docx"
    shutil.copy2(sample_docx, before)
    shutil.copy2(sample_docx, after)

    render_root = tmp_path / "fake-render"
    before_pages = [render_root / "before-1.png", render_root / "before-2.png"]
    after_pages = [render_root / "after-1.png", render_root / "after-2.png", render_root / "after-3.png"]
    for page in before_pages + after_pages:
        page.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (16, 16), color=(255, 255, 255))
        img.save(page)

    def fake_render(docx: Path, _out: Path):  # noqa: ANN001
        if docx == before:
            return SimpleNamespace(png_paths=before_pages)
        return SimpleNamespace(png_paths=after_pages)

    monkeypatch.setattr(verify_mod, "render_docx", fake_render)

    strict = verify_mod._render_diff(before, after, threshold=0.02, max_page_growth=0)
    assert strict["ok"] is False
    assert strict["page_growth"] == 1
    assert strict["page_growth_ok"] is False

    tolerant = verify_mod._render_diff(before, after, threshold=0.02, max_page_growth=2)
    assert tolerant["ok"] is True
    assert tolerant["page_growth"] == 1
    assert tolerant["page_growth_ok"] is True


def test_render_diff_fails_on_page_dimension_mismatch(monkeypatch, sample_docx: Path, tmp_path: Path) -> None:  # noqa: ANN001
    before = tmp_path / "before.docx"
    after = tmp_path / "after.docx"
    shutil.copy2(sample_docx, before)
    shutil.copy2(sample_docx, after)

    before_page = tmp_path / "before.png"
    after_page = tmp_path / "after.png"
    Image.new("RGB", (16, 16), color=(255, 255, 255)).save(before_page)
    Image.new("RGB", (20, 16), color=(255, 255, 255)).save(after_page)

    def fake_render(docx: Path, _out: Path):  # noqa: ANN001
        if docx == before:
            return SimpleNamespace(png_paths=[before_page])
        return SimpleNamespace(png_paths=[after_page])

    monkeypatch.setattr(verify_mod, "render_docx", fake_render)

    result = verify_mod._render_diff(before, after, threshold=1.0, max_page_growth=0)
    assert result["ok"] is False
    assert result["per_page"][0]["dimensions_match"] is False
    assert result["per_page"][0]["before_size"] == (16, 16)
    assert result["per_page"][0]["after_size"] == (20, 16)


def test_convert_pdf_to_png_removes_stale_prefix_pages(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    out_prefix = tmp_path / "pages" / "sample"
    out_prefix.parent.mkdir(parents=True)
    stale = out_prefix.parent / "sample-2.png"
    Image.new("RGB", (4, 4), color=(255, 255, 255)).save(stale)

    monkeypatch.setattr("wordmark.render.missing_binaries", lambda *names: [])

    def fake_run(_cmd: list[str]) -> None:
        Image.new("RGB", (4, 4), color=(0, 0, 0)).save(out_prefix.parent / "sample-1.png")

    monkeypatch.setattr("wordmark.render._run", fake_run)

    pages = convert_pdf_to_png(pdf_path, out_prefix)
    assert [path.name for path in pages] == ["sample-1.png"]
    assert stale.exists() is False


@requires_render_tools
def test_verify_review_edit_profile_reasoning(sample_docx: Path, tmp_path: Path) -> None:
    before = tmp_path / "before.docx"
    after = tmp_path / "after.docx"
    shutil.copy2(sample_docx, before)
    shutil.copy2(sample_docx, after)

    cfg = load_config(Path("wordmark.yaml"))
    result = verify_docx(before, after, profile="review-edit", config=cfg)
    assert result.passed
    reasoning = result.checks["profile_reasoning"]
    assert reasoning["profile"] == "review-edit"
    assert reasoning["render_diff_threshold"] == 0.12
    assert reasoning["max_page_growth"] == 2
    assert (
        reasoning["pass_rule"]
        == "comment_integrity.ok and compatibility_namespace_integrity.ok and render_diff.ok"
    )
    assert result.checks["compatibility_namespace_integrity"]["ok"] is True
    revisions = result.checks["revisions"]
    assert set(revisions["before"].keys()) == {"insert", "delete", "move_to", "move_from", "total"}
    assert set(revisions["after"].keys()) == {"insert", "delete", "move_to", "move_from", "total"}
    assert set(revisions["delta"].keys()) == {"insert", "delete", "move_to", "move_from", "total"}


@requires_render_tools
def test_cli_verify_emits_schema_v2(sample_docx: Path, tmp_path: Path) -> None:
    before = tmp_path / "before.docx"
    after = tmp_path / "after.docx"
    shutil.copy2(sample_docx, before)
    shutil.copy2(sample_docx, after)

    runner = CliRunner()
    result = runner.invoke(app, ["verify", str(before), str(after), "--json"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 2
    assert payload["verify"]["passed"] is True
    assert set(payload["verify"]["checks"]["revisions"]["delta"].keys()) == {
        "insert",
        "delete",
        "move_to",
        "move_from",
        "total",
    }


@requires_render_tools
def test_verify_fails_on_ignorable_prefix_mismatch(sample_docx: Path, tmp_path: Path) -> None:
    before = tmp_path / "before.docx"
    after = tmp_path / "after.docx"
    shutil.copy2(sample_docx, before)
    shutil.copy2(sample_docx, after)

    _inject_ignorable_prefix_mismatch(after)

    cfg = load_config(Path("wordmark.yaml"))
    result = verify_docx(before, after, profile="business-docs", config=cfg)

    assert result.passed is False
    compat = result.checks["compatibility_namespace_integrity"]
    assert compat["ok"] is False
    assert compat["missing_prefixes"] == ["w14", "wp14"]


@requires_render_tools
def test_verify_fails_on_comment_integrity_mismatch(monkeypatch, sample_docx: Path, tmp_path: Path) -> None:  # noqa: ANN001
    before = tmp_path / "before.docx"
    after = tmp_path / "after.docx"
    shutil.copy2(sample_docx, before)
    shutil.copy2(sample_docx, after)

    from wordmark import ooxml_engine

    ooxml_engine.add_comment(
        after,
        selector="p:1",
        text="Break comment integrity",
        author="Barry Brook",
        initials="BB",
        dry_run=False,
    )
    _remove_comments_part(after)

    monkeypatch.setattr(verify_mod, "_render_diff", lambda *args, **kwargs: {"ok": True})

    cfg = load_config(Path("wordmark.yaml"))
    result = verify_docx(before, after, profile="business-docs", config=cfg)

    assert result.passed is False
    assert result.checks["comment_integrity"]["ok"] is False
    assert result.checks["comment_integrity"]["orphan_doc_refs"] != []


def test_convert_docx_to_pdf_reports_missing_soffice(monkeypatch, sample_docx: Path, tmp_path: Path) -> None:  # noqa: ANN001
    monkeypatch.setattr("wordmark.render.missing_binaries", lambda *names: ["soffice"])

    with pytest.raises(RenderError, match="Missing required render tool"):
        convert_docx_to_pdf(sample_docx, tmp_path / "render")
