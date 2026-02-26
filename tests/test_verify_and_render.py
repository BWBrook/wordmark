from __future__ import annotations

import json
import shutil
from types import SimpleNamespace
from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from wordmark.config import load_config
from wordmark.cli import app
from wordmark.render import render_docx
from wordmark import verify as verify_mod
from wordmark.verify import verify_docx


def test_render_produces_pdf_and_pngs(sample_docx: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "render"
    output = render_docx(sample_docx, out_dir)
    assert output.pdf_path.exists()
    assert len(output.png_paths) >= 1


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
    revisions = result.checks["revisions"]
    assert set(revisions["before"].keys()) == {"insert", "delete", "move_to", "move_from", "total"}
    assert set(revisions["after"].keys()) == {"insert", "delete", "move_to", "move_from", "total"}
    assert set(revisions["delta"].keys()) == {"insert", "delete", "move_to", "move_from", "total"}


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
