from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

from PIL import Image
import pytest

from wordmark import render
from wordmark import verify as verify_mod


def test_render_command_timeout_is_reported(monkeypatch) -> None:  # noqa: ANN001
    def fake_run(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise subprocess.TimeoutExpired(cmd="soffice", timeout=180, output="out", stderr="err")

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(render.RenderError, match="Command timed out"):
        render._run(["soffice", "--headless"])  # noqa: SLF001


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

    pages = render.convert_pdf_to_png(pdf_path, out_prefix)
    assert [path.name for path in pages] == ["sample-1.png"]
    assert stale.exists() is False


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

    result = verify_mod._render_diff(before, after, threshold=1.0, max_page_growth=0)  # noqa: SLF001
    assert result["ok"] is False
    assert result["per_page"][0]["dimensions_match"] is False


def test_render_diff_cleans_stale_persisted_pages(monkeypatch, sample_docx: Path, tmp_path: Path) -> None:  # noqa: ANN001
    before = tmp_path / "before.docx"
    after = tmp_path / "after.docx"
    shutil.copy2(sample_docx, before)
    shutil.copy2(sample_docx, after)

    before_page = tmp_path / "before.png"
    after_page = tmp_path / "after.png"
    Image.new("RGB", (16, 16), color=(255, 255, 255)).save(before_page)
    Image.new("RGB", (16, 16), color=(255, 255, 255)).save(after_page)

    persist_dir = tmp_path / "persist"
    persist_dir.mkdir()
    stale = persist_dir / "diff-page-99.png"
    Image.new("RGB", (4, 4), color=(255, 0, 0)).save(stale)

    def fake_render(docx: Path, _out: Path):  # noqa: ANN001
        if docx == before:
            return SimpleNamespace(png_paths=[before_page])
        return SimpleNamespace(png_paths=[after_page])

    monkeypatch.setattr(verify_mod, "render_docx", fake_render)

    result = verify_mod._render_diff(  # noqa: SLF001
        before,
        after,
        threshold=0.02,
        max_page_growth=0,
        persist_dir=persist_dir,
    )

    assert result["ok"] is True
    assert stale.exists() is False
    assert (persist_dir / "diff-page-1.png").exists()

