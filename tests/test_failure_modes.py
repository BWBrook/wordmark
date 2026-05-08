from __future__ import annotations

from pathlib import Path

import pytest

from wordmark import ooxml_engine
from wordmark import uno_engine
from wordmark.docx_package import DocxPackage


def test_broken_anchor_raises(sample_docx: Path) -> None:
    with pytest.raises(ValueError, match="Anchor"):
        ooxml_engine.add_comment(
            sample_docx,
            selector="text:__missing_anchor__",
            text="This should fail",
            author="Reviewer",
            initials="RV",
            dry_run=False,
        )


def test_conflicting_expected_text_raises(sample_docx: Path) -> None:
    with pytest.raises(ValueError, match="Expected paragraph text mismatch"):
        ooxml_engine.apply_patch(
            sample_docx,
            patch_data={
                "operations": [
                    {
                        "type": "replace_paragraph_text",
                        "paragraph_index": 2,
                        "expected_text": "Not the actual paragraph",
                        "new_text": "Replacement",
                    }
                ]
            },
            author="Barry Brook",
            track_changes=True,
            dry_run=False,
        )


def test_unsupported_operation_requires_fallback(sample_docx: Path) -> None:
    with pytest.raises(ooxml_engine.OoxmlUnsupportedOperation):
        ooxml_engine.apply_patch(
            sample_docx,
            patch_data={
                "operations": [
                    {
                        "type": "replace_text_global",
                        "find": "alpha",
                        "replace": "beta",
                    }
                ]
            },
            author="Barry Brook",
            track_changes=True,
            dry_run=False,
        )


def test_uno_failure_path_surfaces_error(monkeypatch: pytest.MonkeyPatch, sample_docx: Path) -> None:
    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "boom"

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return FakeProc()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setenv("WORDMARK_ENABLE_MACOS_UNO", "1")

    with pytest.raises(uno_engine.UnoEngineError, match="UNO fallback failed"):
        uno_engine.apply_patch(
            sample_docx,
            patch_data={"operations": [{"type": "replace_text_global", "find": "A", "replace": "B"}]},
            author="Barry Brook",
            track_changes=True,
            dry_run=False,
            fallback_reason="test",
        )


def test_docx_package_save_preserves_target_when_zip_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.docx"
    original = b"original payload"
    target.write_bytes(original)
    pkg = DocxPackage(parts={"word/document.xml": b"<root/>"})

    class FailingZipFile:
        def __init__(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("zip write failed")

    monkeypatch.setattr("wordmark.docx_package.zipfile.ZipFile", FailingZipFile)

    with pytest.raises(RuntimeError, match="zip write failed"):
        pkg.save(target)

    assert target.read_bytes() == original
    assert list(tmp_path.glob(".target.docx.*.tmp")) == []
