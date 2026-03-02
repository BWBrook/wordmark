from __future__ import annotations

import json
from pathlib import Path
import shutil

from docx import Document
from typer.testing import CliRunner

from wordmark.cli import app
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
