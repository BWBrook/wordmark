from __future__ import annotations

import json
from pathlib import Path
import shutil

from docx import Document
import pytest
from typer.testing import CliRunner

from wordmark.cli import app
from wordmark import manuscript_ingest, manuscript_rounds
from wordmark import ooxml_engine


def _write_docx(path: Path, text: str) -> Path:
    doc = Document()
    doc.add_paragraph(text)
    doc.save(path)
    return path


def _prepare_round_with_docx(tmp_path: Path, *, round_id: str = "round1") -> tuple[dict, Path, Path]:
    source = tmp_path / "chapter.md"
    source.write_text("# Title\n\nAlpha example sentence.\n", encoding="utf-8")

    seed_docx = _write_docx(tmp_path / "seed.docx", "Alpha example sentence.")
    rounds_root = tmp_path / "rounds"

    runner = CliRunner()
    build_cmd = f"cp {seed_docx} {{docx_out}}"
    result = runner.invoke(
        app,
        [
            "manuscript",
            "prepare",
            str(source),
            "--build-cmd",
            build_cmd,
            "--formats",
            "docx",
            "--out",
            str(rounds_root),
            "--round-id",
            round_id,
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    return payload, source, rounds_root / round_id


def test_manuscript_prepare_creates_round_bundle(tmp_path: Path) -> None:
    payload, source, round_dir = _prepare_round_with_docx(tmp_path)
    assert payload["schema_version"] == 1
    assert payload["round_id"] == "round1"
    assert round_dir.exists()
    assert Path(payload["manifest"]).exists()
    assert Path(payload["report"]).exists()

    manifest = json.loads((round_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_path"] == str(source.resolve())
    assert "docx" in manifest["artifacts"]
    assert (round_dir / manifest["artifacts"]["docx"]["path"]).exists()


def test_manuscript_collect_ingests_notes_and_docx_feedback(tmp_path: Path) -> None:
    _, _, round_dir = _prepare_round_with_docx(tmp_path, round_id="collect1")
    baseline = round_dir / "rendered.docx"
    reviewed = tmp_path / "reviewed.docx"
    shutil.copy2(baseline, reviewed)

    ooxml_engine.add_comment(
        reviewed,
        selector="p:0",
        text="Please tighten this sentence.",
        author="Barry Brook",
        initials="BB",
        dry_run=False,
    )
    ooxml_engine.apply_patch(
        reviewed,
        patch_data={"operations": [{"type": "replace_text_once", "find": "Alpha", "replace": "Beta"}]},
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
    )

    notes = tmp_path / "feedback.md"
    notes.write_text(
        "# Notes\n\n- replace 'example' with 'sample'\n- Consider clarifying rationale.\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "manuscript",
            "collect",
            str(round_dir),
            "--notes",
            str(notes),
            "--docx-reviewed",
            str(reviewed),
            "--json",
        ],
    )
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["counts"]["total"] >= 3
    channels = payload["counts"]["by_channel"]
    assert channels["notes_md"] >= 1
    assert channels["docx_comment"] >= 1
    assert channels["docx_revision"] >= 1
    assert Path(payload["bundle"]).exists()
    assert Path(payload["timeline"]).exists()


@pytest.mark.github_integration
def test_manuscript_collect_warns_when_gh_auth_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, round_dir = _prepare_round_with_docx(tmp_path, round_id="collect-gh-missing")

    monkeypatch.setattr(manuscript_ingest, "gh_available", lambda: True)
    monkeypatch.setattr(manuscript_ingest, "gh_auth_available", lambda *, cwd=None: False)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "manuscript",
            "collect",
            str(round_dir),
            "--from-pr",
            "123",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "gh auth is not available" in payload["warnings"][0]
    assert payload["counts"]["total"] == 0


@pytest.mark.github_integration
def test_manuscript_collect_ingests_github_review_feedback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, round_dir = _prepare_round_with_docx(tmp_path, round_id="collect-gh-success")

    monkeypatch.setattr(manuscript_ingest, "gh_available", lambda: True)
    monkeypatch.setattr(manuscript_ingest, "gh_auth_available", lambda *, cwd=None: True)
    monkeypatch.setattr(manuscript_ingest, "_origin_repo_slug", lambda cwd: "owner/repo")

    def fake_gh_json(args: list[str], *, cwd: Path):
        endpoint = args[1]
        if endpoint.endswith("/pulls/123/comments"):
            return (
                [
                    {
                        "id": 10,
                        "body": "```suggestion\nImproved manuscript line.\n```",
                        "line": 4,
                        "start_line": 4,
                        "path": "chapter.md",
                        "created_at": "2026-03-01T10:00:00Z",
                        "html_url": "https://example/pull/123#discussion_r10",
                        "user": {"login": "reviewer1"},
                    }
                ],
                None,
            )
        if endpoint.endswith("/issues/123/comments"):
            return (
                [
                    {
                        "id": 11,
                        "body": "Please clarify the framing in the introduction.",
                        "created_at": "2026-03-01T10:05:00Z",
                        "html_url": "https://example/pull/123#issuecomment-11",
                        "user": {"login": "reviewer2"},
                    }
                ],
                None,
            )
        return [], None

    monkeypatch.setattr(manuscript_ingest, "_gh_json", fake_gh_json)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "manuscript",
            "collect",
            str(round_dir),
            "--from-pr",
            "123",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["counts"]["by_channel"]["github_pr"] == 2
    assert payload["counts"]["by_kind"]["suggestion"] == 1
    assert payload["counts"]["by_kind"]["comment"] == 1


@pytest.mark.manuscript_build
def test_manuscript_prepare_qmd_default_build_requires_quarto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "chapter.qmd"
    source.write_text("# Title\n\nBody.\n", encoding="utf-8")

    monkeypatch.setattr(manuscript_rounds, "quarto_available", lambda: False)

    with pytest.raises(RuntimeError, match="quarto CLI is required"):
        manuscript_rounds.prepare_round(
            source,
            build_cmd=None,
            formats="docx",
            out_root=tmp_path / "rounds",
            round_id="missing-quarto",
        )


@pytest.mark.manuscript_build
def test_manuscript_prepare_qmd_default_build_invokes_expected_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "chapter.qmd"
    source.write_text("# Title\n\nBody.\n", encoding="utf-8")
    commands: list[str] = []

    monkeypatch.setattr(manuscript_rounds, "quarto_available", lambda: True)

    def fake_run_shell(command: str, *, cwd: Path):
        commands.append(command)
        if "--output rendered.docx" in command:
            (tmp_path / "rounds" / "qmd-build" / "rendered.docx").parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / "rounds" / "qmd-build" / "rendered.docx").write_bytes(b"docx")
        if "--output rendered.pdf" in command:
            (tmp_path / "rounds" / "qmd-build" / "rendered.pdf").write_bytes(b"pdf")
        return {"command": command, "cwd": str(cwd), "exit_code": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(manuscript_rounds, "_run_shell", fake_run_shell)

    payload = manuscript_rounds.prepare_round(
        source,
        build_cmd=None,
        formats="docx,pdf",
        out_root=tmp_path / "rounds",
        round_id="qmd-build",
    )

    assert payload["round_id"] == "qmd-build"
    assert len(commands) == 2
    assert any("quarto render" in command and "--to docx" in command for command in commands)
    assert any("quarto render" in command and "--to pdf" in command for command in commands)


def test_manuscript_prepare_reports_build_command_failure(tmp_path: Path) -> None:
    source = tmp_path / "chapter.md"
    source.write_text("# Title\n\nBody.\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "manuscript",
            "prepare",
            str(source),
            "--build-cmd",
            "false",
            "--formats",
            "docx",
            "--out",
            str(tmp_path / "rounds"),
            "--round-id",
            "build-fail",
            "--json",
        ],
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, RuntimeError)
    assert "Build command failed" in str(result.exception)


def test_manuscript_synthesize_generates_patch_and_critic_without_mutating_source(tmp_path: Path) -> None:
    _, source, round_dir = _prepare_round_with_docx(tmp_path, round_id="synth1")

    notes = tmp_path / "feedback.md"
    notes.write_text("- replace 'example' with 'sample'\n", encoding="utf-8")
    runner = CliRunner()
    collect = runner.invoke(
        app,
        ["manuscript", "collect", str(round_dir), "--notes", str(notes), "--json"],
    )
    assert collect.exit_code == 0

    before = source.read_text(encoding="utf-8")
    synth = runner.invoke(
        app,
        [
            "manuscript",
            "synthesize",
            str(round_dir),
            "--source",
            str(source),
            "--export-critic",
            "--json",
        ],
    )
    assert synth.exit_code == 0
    payload = json.loads(synth.stdout)

    assert Path(payload["outputs"]["patch"]).exists()
    assert Path(payload["outputs"]["safe_edits"]).exists()
    assert Path(payload["outputs"]["summary"]).exists()
    assert Path(payload["outputs"]["open_issues"]).exists()
    assert Path(payload["outputs"]["critic"]).exists()

    safe = json.loads(Path(payload["outputs"]["safe_edits"]).read_text(encoding="utf-8"))
    assert safe["proposals"]
    assert any(item["status"] in {"proposed_safe", "applied"} for item in safe["proposals"])

    critic_text = Path(payload["outputs"]["critic"]).read_text(encoding="utf-8")
    assert "{--example--}{++sample++}" in critic_text
    assert source.read_text(encoding="utf-8") == before


def test_manuscript_synthesize_marks_repeated_text_replace_as_ambiguous(tmp_path: Path) -> None:
    source = tmp_path / "chapter.md"
    source.write_text("# Title\n\nexample one\n\nexample two\n", encoding="utf-8")
    round_dir = tmp_path / "rounds" / "ambiguous"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "manifest.json").write_text(
        json.dumps({"round_id": "ambiguous", "artifacts": {}}, ensure_ascii=True),
        encoding="utf-8",
    )

    notes = tmp_path / "feedback.md"
    notes.write_text("- replace 'example' with 'sample'\n", encoding="utf-8")
    runner = CliRunner()
    collect = runner.invoke(app, ["manuscript", "collect", str(round_dir), "--notes", str(notes), "--json"])
    assert collect.exit_code == 0

    before = source.read_text(encoding="utf-8")
    synth = runner.invoke(
        app,
        ["manuscript", "synthesize", str(round_dir), "--source", str(source), "--json"],
    )
    assert synth.exit_code == 0
    payload = json.loads(synth.stdout)
    safe = json.loads(Path(payload["outputs"]["safe_edits"]).read_text(encoding="utf-8"))
    assert any(item["status"] == "ambiguous" for item in safe["proposals"])
    assert source.read_text(encoding="utf-8") == before


def test_manuscript_synthesize_apply_safe_updates_source(tmp_path: Path) -> None:
    _, source, round_dir = _prepare_round_with_docx(tmp_path, round_id="synth2")

    notes = tmp_path / "feedback.md"
    notes.write_text("- replace 'Alpha example sentence.' with 'Alpha sample sentence.'\n", encoding="utf-8")
    runner = CliRunner()
    collect = runner.invoke(
        app,
        ["manuscript", "collect", str(round_dir), "--notes", str(notes), "--json"],
    )
    assert collect.exit_code == 0

    synth = runner.invoke(
        app,
        [
            "manuscript",
            "synthesize",
            str(round_dir),
            "--source",
            str(source),
            "--apply-safe",
            "--json",
        ],
    )
    assert synth.exit_code == 0
    payload = json.loads(synth.stdout)
    updated = source.read_text(encoding="utf-8")
    assert "Alpha sample sentence." in updated

    safe = json.loads(Path(payload["outputs"]["safe_edits"]).read_text(encoding="utf-8"))
    assert any(item["status"] == "applied" for item in safe["proposals"])


def test_manuscript_status_tracks_stage_progression(tmp_path: Path) -> None:
    _, source, round_dir = _prepare_round_with_docx(tmp_path, round_id="status1")
    runner = CliRunner()

    status_prepare = runner.invoke(app, ["manuscript", "status", str(round_dir), "--json"])
    assert status_prepare.exit_code == 0
    payload_prepare = json.loads(status_prepare.stdout)
    assert payload_prepare["stages"] == {"prepare": True, "collect": False, "synthesize": False}

    notes = tmp_path / "feedback.md"
    notes.write_text("- replace 'example' with 'sample'\n", encoding="utf-8")
    collect = runner.invoke(
        app,
        ["manuscript", "collect", str(round_dir), "--notes", str(notes), "--json"],
    )
    assert collect.exit_code == 0

    synth = runner.invoke(
        app,
        ["manuscript", "synthesize", str(round_dir), "--source", str(source), "--json"],
    )
    assert synth.exit_code == 0

    status_complete = runner.invoke(app, ["manuscript", "status", str(round_dir), "--json"])
    assert status_complete.exit_code == 0
    payload_complete = json.loads(status_complete.stdout)
    assert payload_complete["stages"] == {"prepare": True, "collect": True, "synthesize": True}
    assert payload_complete["complete"] is True


def test_manuscript_status_requires_both_safe_edits_and_summary_for_synthesize_stage(tmp_path: Path) -> None:
    round_dir = tmp_path / "rounds" / "partial-status"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "manifest.json").write_text(json.dumps({"round_id": "partial-status"}, ensure_ascii=True), encoding="utf-8")
    (round_dir / "feedback.bundle.json").write_text(
        json.dumps({"events": [], "ingestion_warnings": []}, ensure_ascii=True),
        encoding="utf-8",
    )
    (round_dir / "proposed.safe_edits.json").write_text(json.dumps({"proposals": []}, ensure_ascii=True), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["manuscript", "status", str(round_dir), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["stages"] == {"prepare": True, "collect": True, "synthesize": False}
