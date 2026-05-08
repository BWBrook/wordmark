from __future__ import annotations

from pathlib import Path
import subprocess

from wordmark import external_tools
from wordmark import manuscript_ingest
from wordmark import manuscript_rounds


def test_manuscript_run_shell_reports_timeout(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    def fake_run(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise subprocess.TimeoutExpired(cmd="bash", timeout=3, output="out", stderr="err")

    monkeypatch.setattr("subprocess.run", fake_run)

    result = manuscript_rounds._run_shell("sleep 999", cwd=tmp_path, timeout_s=3)  # noqa: SLF001

    assert result["exit_code"] == 124
    assert result["timed_out"] is True
    assert result["timeout_s"] == 3
    assert "timed out after 3s" in result["stderr"]


def test_manuscript_git_value_returns_none_on_timeout(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    def fake_run(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise subprocess.TimeoutExpired(cmd="git", timeout=15)

    monkeypatch.setattr("subprocess.run", fake_run)

    assert manuscript_rounds._git_value(["rev-parse", "HEAD"], cwd=tmp_path) is None  # noqa: SLF001


def test_gh_json_reports_timeout(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    def fake_run(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise subprocess.TimeoutExpired(cmd="gh", timeout=60)

    monkeypatch.setattr("subprocess.run", fake_run)

    payload, error = manuscript_ingest._gh_json(["api", "repos/x/y"], cwd=tmp_path)  # noqa: SLF001

    assert payload is None
    assert error == "gh command timed out after 60s"


def test_gh_auth_available_returns_false_on_timeout(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    def fake_run(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise subprocess.TimeoutExpired(cmd="gh", timeout=30)

    monkeypatch.setattr(external_tools, "gh_available", lambda: True)
    monkeypatch.setattr("subprocess.run", fake_run)

    assert external_tools.gh_auth_available(cwd=tmp_path) is False

