"""Environment probes for optional external command-line integrations."""

from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import subprocess


def _existing(paths: list[Path]) -> list[Path]:
    return [path for path in paths if path.exists() and path.is_file()]


def _candidate_paths(name: str) -> list[Path]:
    candidates: list[Path] = []
    system = platform.system()

    if system == "Darwin":
        if name == "soffice":
            candidates.extend(
                [
                    Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
                ]
            )
            candidates.extend(sorted(Path("/opt/homebrew/Caskroom").glob("libreoffice/*/soffice.wrapper.sh"), reverse=True))
            candidates.extend(
                sorted(
                    Path("/opt/homebrew/Caskroom").glob("libreoffice/*/LibreOffice.app/Contents/MacOS/soffice"),
                    reverse=True,
                )
            )
        elif name == "quarto":
            candidates.extend(
                [
                    Path("/Applications/quarto/bin/quarto"),
                ]
            )
            candidates.extend(sorted(Path("/opt/homebrew/Caskroom").glob("quarto/*/quarto"), reverse=True))
        elif name == "libreoffice_python":
            candidates.extend(
                [
                    Path("/Applications/LibreOffice.app/Contents/Resources/python"),
                ]
            )
            candidates.extend(
                sorted(
                    Path("/opt/homebrew/Caskroom").glob("libreoffice/*/LibreOffice.app/Contents/Resources/python"),
                    reverse=True,
                )
            )

    return _existing(candidates)


def binary_path(name: str) -> str | None:
    resolved = shutil.which(name)
    if resolved is not None:
        return resolved

    for candidate in _candidate_paths(name):
        return str(candidate)
    return None


def binary_available(name: str) -> bool:
    return binary_path(name) is not None


def missing_binaries(*names: str) -> list[str]:
    return [name for name in names if not binary_available(name)]


def render_tools_available() -> bool:
    return not missing_binaries("soffice", "pdftoppm")


def quarto_available() -> bool:
    return binary_available("quarto")


def gh_available() -> bool:
    return binary_available("gh")


def gh_auth_available(*, cwd: Path | None = None) -> bool:
    if not gh_available():
        return False
    try:
        proc = subprocess.run(
            ["gh", "auth", "status", "-h", "github.com"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False
    return proc.returncode == 0


def system_uno_available() -> bool:
    if platform.system() == "Darwin" and os.getenv("WORDMARK_ENABLE_MACOS_UNO") != "1":
        # LibreOffice's embedded Python wrapper currently hangs on this host for a
        # simple `import uno` probe, so macOS UNO remains explicit opt-in until a
        # stable non-interactive invocation path is proven.
        return False

    python_bin = binary_path("libreoffice_python")
    if python_bin is None:
        python_path = Path("/usr/bin/python3")
        if not python_path.exists():
            return False
        python_bin = str(python_path)
    try:
        proc = subprocess.run(
            [str(python_bin), "-c", "import uno"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return False
    return proc.returncode == 0
