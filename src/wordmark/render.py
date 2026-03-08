"""DOCX rendering helpers for visual validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile

from wordmark.external_tools import missing_binaries


class RenderError(RuntimeError):
    """Raised when rendering commands fail."""


@dataclass(slots=True)
class RenderOutput:
    docx_path: Path
    pdf_path: Path
    png_paths: list[Path]


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RenderError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")


def convert_docx_to_pdf(docx_path: Path, out_dir: Path) -> Path:
    missing = missing_binaries("soffice")
    if missing:
        raise RenderError(f"Missing required render tool(s): {', '.join(missing)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wordmark_lo_profile_") as profile_dir:
        profile_uri = Path(profile_dir).as_uri()
        cmd = [
            "soffice",
            f"-env:UserInstallation={profile_uri}",
            "--headless",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(docx_path),
        ]
        _run(cmd)
    pdf_path = out_dir / f"{docx_path.stem}.pdf"
    if not pdf_path.exists():
        raise RenderError(f"Expected PDF not found after conversion: {pdf_path}")
    return pdf_path


def convert_pdf_to_png(pdf_path: Path, out_prefix: Path) -> list[Path]:
    missing = missing_binaries("pdftoppm")
    if missing:
        raise RenderError(f"Missing required render tool(s): {', '.join(missing)}")
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["pdftoppm", "-png", str(pdf_path), str(out_prefix)]
    _run(cmd)
    png_paths = sorted(out_prefix.parent.glob(f"{out_prefix.name}-*.png"))
    if not png_paths:
        raise RenderError(f"No PNG pages produced from PDF: {pdf_path}")
    return png_paths


def render_docx(docx_path: Path, out_dir: Path) -> RenderOutput:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = convert_docx_to_pdf(docx_path, out_dir)
    out_prefix = out_dir / docx_path.stem
    png_paths = convert_pdf_to_png(pdf_path, out_prefix)
    return RenderOutput(docx_path=docx_path, pdf_path=pdf_path, png_paths=png_paths)
