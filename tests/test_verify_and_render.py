from __future__ import annotations

import shutil
from pathlib import Path

from wordmark.config import load_config
from wordmark.render import render_docx
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
