from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from docx import Document
import pytest
from typer.testing import CliRunner

from wordmark.cli import app
from wordmark.external_tools import quarto_available
from wordmark import manuscript_ingest, manuscript_rounds
from wordmark import ooxml_engine


def _write_docx(path: Path, text: str) -> Path:
    doc = Document()
    doc.add_paragraph(text)
    doc.save(path)
    return path


def _append_paragraphs(path: Path, *texts: str) -> None:
    doc = Document(path)
    for text in texts:
        doc.add_paragraph(text)
    doc.save(path)


def _sha256_text(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    _append_paragraphs(reviewed, "Separate review target.")

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
        patch_data={
            "operations": [
                {
                    "type": "replace_text_once",
                    "find": "review target",
                    "replace": "reviewed target",
                }
            ]
        },
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


def test_manuscript_collect_docx_import_reports_only_new_review_state(tmp_path: Path) -> None:
    _, _, round_dir = _prepare_round_with_docx(tmp_path, round_id="collect-docx-delta")
    baseline = round_dir / "rendered.docx"
    _append_paragraphs(
        baseline,
        "Separate baseline target.",
        "Separate new-comment paragraph.",
        "Separate reviewed target.",
    )

    ooxml_engine.add_comment(
        baseline,
        selector="p:0",
        text="Existing baseline comment.",
        author="Barry Brook",
        initials="BB",
        dry_run=False,
    )
    ooxml_engine.apply_patch(
        baseline,
        patch_data={
            "operations": [
                {
                    "type": "replace_text_once",
                    "find": "baseline target",
                    "replace": "baseline revision",
                }
            ]
        },
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
    )

    reviewed = tmp_path / "reviewed-delta.docx"
    shutil.copy2(baseline, reviewed)
    ooxml_engine.add_comment(
        reviewed,
        selector="p:2",
        text="New reviewed comment.",
        author="Barry Brook",
        initials="BB",
        dry_run=False,
    )
    ooxml_engine.apply_patch(
        reviewed,
        patch_data={
            "operations": [
                {
                    "type": "replace_text_once",
                    "find": "reviewed target",
                    "replace": "reviewed revision",
                }
            ]
        },
        author="Barry Brook",
        track_changes=True,
        dry_run=False,
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "manuscript",
            "collect",
            str(round_dir),
            "--docx-reviewed",
            str(reviewed),
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["counts"]["by_channel"]["docx_comment"] == 1
    assert payload["counts"]["by_channel"]["docx_revision"] >= 1

    bundle = json.loads(Path(payload["bundle"]).read_text(encoding="utf-8"))
    comment_events = [event for event in bundle["events"] if event["channel"] == "docx_comment"]
    assert [event["content"]["summary"] for event in comment_events] == ["New reviewed comment."]


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


@pytest.mark.github_integration
def test_manuscript_collect_github_variant_uses_original_line_and_stable_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, round_dir = _prepare_round_with_docx(tmp_path, round_id="collect-gh-variant")

    monkeypatch.setattr(manuscript_ingest, "gh_available", lambda: True)
    monkeypatch.setattr(manuscript_ingest, "gh_auth_available", lambda *, cwd=None: True)
    monkeypatch.setattr(manuscript_ingest, "_origin_repo_slug", lambda cwd: "owner/repo")

    def fake_gh_json(args: list[str], *, cwd: Path):
        endpoint = args[1]
        if endpoint.endswith("/pulls/123/comments"):
            return (
                [
                    {
                        "id": 21,
                        "body": "Minor wording suggestion.",
                        "original_line": 12,
                        "path": "chapter.md",
                        "created_at": "2026-03-02T09:00:00Z",
                        "html_url": "https://example/pull/123#discussion_r21",
                        "user": {"login": "reviewer1"},
                    }
                ],
                None,
            )
        if endpoint.endswith("/issues/123/comments"):
            return (
                [
                    {
                        "id": 22,
                        "body": "Please expand the methods note.",
                        "created_at": "2026-03-02T09:05:00Z",
                        "html_url": "https://example/pull/123#issuecomment-22",
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
        ["manuscript", "collect", str(round_dir), "--from-pr", "123", "--json"],
    )
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    bundle = json.loads(Path(payload["bundle"]).read_text(encoding="utf-8"))
    assert [event["event_id"] for event in bundle["events"]] == ["evt-00001", "evt-00002"]
    pr_event = bundle["events"][0]
    assert pr_event["anchor"]["line_start"] == 12
    assert pr_event["anchor"]["line_end"] == 12


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


@pytest.mark.external_tools
@pytest.mark.manuscript_build
@pytest.mark.skipif(not quarto_available(), reason="quarto CLI unavailable")
def test_manuscript_prepare_real_qmd_smoke_build(tmp_path: Path) -> None:
    source = tmp_path / "chapter.qmd"
    source.write_text(
        "---\ntitle: Test Chapter\nformat:\n  docx: default\n---\n\nAlpha example sentence.\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "manuscript",
            "prepare",
            str(source),
            "--formats",
            "docx",
            "--out",
            str(tmp_path / "rounds"),
            "--round-id",
            "qmd-real-smoke",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    manifest = json.loads(Path(payload["manifest"]).read_text(encoding="utf-8"))
    assert "docx" in manifest["artifacts"]
    assert (tmp_path / "rounds" / "qmd-real-smoke" / manifest["artifacts"]["docx"]["path"]).exists()


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
    before_hash = _sha256_text(source)
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
    assert _sha256_text(source) == before_hash


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


def test_manuscript_synthesize_marks_excerpt_based_duplicate_as_ambiguous(tmp_path: Path) -> None:
    source = tmp_path / "chapter.md"
    source.write_text("# Title\n\nshared excerpt one\n\nshared excerpt two\n", encoding="utf-8")
    round_dir = tmp_path / "rounds" / "excerpt-ambiguous"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "feedback.bundle.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "round_id": "excerpt-ambiguous",
                "events": [
                    {
                        "event_id": "evt-00001",
                        "channel": "github_pr",
                        "kind": "suggestion",
                        "severity": "medium",
                        "author": "reviewer",
                        "created_at": "2026-03-02T10:00:00Z",
                        "anchor": {"excerpt": "shared excerpt"},
                        "content": {
                            "summary": "Replace shared excerpt",
                            "proposed_text": "refined excerpt",
                        },
                        "trace": {"source_ref": "pull_comment:1"},
                    }
                ],
                "counts": {"total": 1},
                "ingestion_warnings": [],
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["manuscript", "synthesize", str(round_dir), "--source", str(source), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    safe = json.loads(Path(payload["outputs"]["safe_edits"]).read_text(encoding="utf-8"))
    assert any(item["status"] == "ambiguous" for item in safe["proposals"])


def test_manuscript_synthesize_anchored_note_rewrites_only_targeted_line(tmp_path: Path) -> None:
    source = tmp_path / "chapter.md"
    source.write_text("# Title\n\nexample one\n\nexample two\n", encoding="utf-8")
    round_dir = tmp_path / "rounds" / "anchored-note"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "manifest.json").write_text(json.dumps({"round_id": "anchored-note", "artifacts": {}}, ensure_ascii=True), encoding="utf-8")

    notes = tmp_path / "feedback.md"
    notes.write_text("chapter.md:3: replace 'example' with 'sample'\n", encoding="utf-8")
    runner = CliRunner()
    collect = runner.invoke(app, ["manuscript", "collect", str(round_dir), "--notes", str(notes), "--json"])
    assert collect.exit_code == 0

    synth = runner.invoke(
        app,
        ["manuscript", "synthesize", str(round_dir), "--source", str(source), "--apply-safe", "--json"],
    )
    assert synth.exit_code == 0
    updated = source.read_text(encoding="utf-8")
    assert "sample one" in updated
    assert "example two" in updated


def test_manuscript_synthesize_anchored_suggestion_uses_target_span_for_repeated_lines(tmp_path: Path) -> None:
    source = tmp_path / "chapter.md"
    source.write_text("# Title\n\nSame line.\nMiddle.\nSame line.\n", encoding="utf-8")
    round_dir = tmp_path / "rounds" / "anchored-repeat"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "feedback.bundle.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "round_id": "anchored-repeat",
                "events": [
                    {
                        "event_id": "evt-00001",
                        "channel": "github_pr",
                        "kind": "suggestion",
                        "severity": "medium",
                        "author": "reviewer",
                        "created_at": "2026-05-08T00:00:00Z",
                        "anchor": {"file": "chapter.md", "line_start": 5, "line_end": 5},
                        "content": {"summary": "Update second repeated line", "proposed_text": "Changed second line.\n"},
                        "trace": {"source_ref": "pull_comment:1"},
                    }
                ],
                "counts": {"total": 1},
                "ingestion_warnings": [],
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    synth = runner.invoke(
        app,
        ["manuscript", "synthesize", str(round_dir), "--source", str(source), "--apply-safe", "--json"],
    )

    assert synth.exit_code == 0
    assert source.read_text(encoding="utf-8") == "# Title\n\nSame line.\nMiddle.\nChanged second line.\n"
    safe = json.loads((round_dir / "proposed.safe_edits.json").read_text(encoding="utf-8"))
    proposal = safe["proposals"][0]
    assert proposal["status"] == "applied"
    assert proposal["details"]["occurrences"] == 2
    assert proposal["details"]["span_start"] > source.read_text(encoding="utf-8").index("Same line.")


def test_manuscript_synthesize_preserves_distinct_identical_anchored_proposals(tmp_path: Path) -> None:
    source = tmp_path / "chapter.md"
    source.write_text("# Title\n\nSame line.\nSame line.\n", encoding="utf-8")
    round_dir = tmp_path / "rounds" / "anchored-repeat-two"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "feedback.bundle.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "round_id": "anchored-repeat-two",
                "events": [
                    {
                        "event_id": "evt-00001",
                        "channel": "github_pr",
                        "kind": "suggestion",
                        "severity": "medium",
                        "author": "reviewer",
                        "created_at": "2026-05-08T00:00:00Z",
                        "anchor": {"file": "chapter.md", "line_start": 3, "line_end": 3},
                        "content": {"summary": "Update first repeated line", "proposed_text": "First changed.\n"},
                        "trace": {"source_ref": "pull_comment:1"},
                    },
                    {
                        "event_id": "evt-00002",
                        "channel": "github_pr",
                        "kind": "suggestion",
                        "severity": "medium",
                        "author": "reviewer",
                        "created_at": "2026-05-08T00:01:00Z",
                        "anchor": {"file": "chapter.md", "line_start": 4, "line_end": 4},
                        "content": {"summary": "Update second repeated line", "proposed_text": "Second changed.\n"},
                        "trace": {"source_ref": "pull_comment:2"},
                    },
                ],
                "counts": {"total": 2},
                "ingestion_warnings": [],
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    synth = runner.invoke(
        app,
        ["manuscript", "synthesize", str(round_dir), "--source", str(source), "--apply-safe", "--json"],
    )

    assert synth.exit_code == 0
    assert source.read_text(encoding="utf-8") == "# Title\n\nFirst changed.\nSecond changed.\n"
    safe = json.loads((round_dir / "proposed.safe_edits.json").read_text(encoding="utf-8"))
    assert len(safe["proposals"]) == 2
    assert {item["status"] for item in safe["proposals"]} == {"applied"}


def test_manuscript_synthesize_guards_markdown_structural_contexts(tmp_path: Path) -> None:
    source = tmp_path / "chapter.md"
    before = "---\ntitle: Old title\n---\n\nBody text.\n\n```r\nold <- 1\n```\n\nSee [old link](https://example.com) and [@old2024].\n"
    source.write_text(before, encoding="utf-8")
    round_dir = tmp_path / "rounds" / "markdown-guards"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "feedback.bundle.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "round_id": "markdown-guards",
                "events": [
                    {
                        "event_id": "evt-00001",
                        "channel": "github_pr",
                        "kind": "suggestion",
                        "severity": "medium",
                        "author": "reviewer",
                        "created_at": "2026-05-08T00:00:00Z",
                        "anchor": {"file": "chapter.md", "line_start": 2, "line_end": 2},
                        "content": {"summary": "Change title", "proposed_text": "title: New title\n"},
                        "trace": {"source_ref": "pull_comment:1"},
                    },
                    {
                        "event_id": "evt-00002",
                        "channel": "github_pr",
                        "kind": "suggestion",
                        "severity": "medium",
                        "author": "reviewer",
                        "created_at": "2026-05-08T00:01:00Z",
                        "anchor": {"file": "chapter.md", "line_start": 8, "line_end": 8},
                        "content": {"summary": "Change code", "proposed_text": "new <- 2\n"},
                        "trace": {"source_ref": "pull_comment:2"},
                    },
                    {
                        "event_id": "evt-00003",
                        "channel": "github_pr",
                        "kind": "suggestion",
                        "severity": "medium",
                        "author": "reviewer",
                        "created_at": "2026-05-08T00:02:00Z",
                        "anchor": {"file": "chapter.md", "line_start": 11, "line_end": 11},
                        "content": {"summary": "Change markdown inline syntax", "proposed_text": "See revised link and old2024.\n"},
                        "trace": {"source_ref": "pull_comment:3"},
                    },
                ],
                "counts": {"total": 3},
                "ingestion_warnings": [],
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    synth = runner.invoke(
        app,
        ["manuscript", "synthesize", str(round_dir), "--source", str(source), "--apply-safe", "--json"],
    )

    assert synth.exit_code == 0
    assert source.read_text(encoding="utf-8") == before
    payload = json.loads(synth.stdout)
    assert payload["counts"]["guarded_markdown"] == 3
    safe = json.loads((round_dir / "proposed.safe_edits.json").read_text(encoding="utf-8"))
    assert {item["status"] for item in safe["proposals"]} == {"guarded_markdown"}
    issues = {issue for item in safe["proposals"] for issue in item["details"]["markdown_guard_issues"]}
    assert {"yaml_front_matter", "fenced_code_block", "link_or_image", "bracketed_citation"}.issubset(issues)


def test_manuscript_critic_markup_is_span_based_and_escapes_nested_tokens(tmp_path: Path) -> None:
    source = tmp_path / "chapter.md"
    source.write_text("# Title\n\nSame line.\nMiddle.\nSame line.\n", encoding="utf-8")
    round_dir = tmp_path / "rounds" / "critic-span"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "feedback.bundle.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "round_id": "critic-span",
                "events": [
                    {
                        "event_id": "evt-00001",
                        "channel": "github_pr",
                        "kind": "suggestion",
                        "severity": "medium",
                        "author": "reviewer",
                        "created_at": "2026-05-08T00:00:00Z",
                        "anchor": {"file": "chapter.md", "line_start": 5, "line_end": 5},
                        "content": {"summary": "Update second repeated line", "proposed_text": "Changed {-- second --} line.\n"},
                        "trace": {"source_ref": "pull_comment:1"},
                    }
                ],
                "counts": {"total": 1},
                "ingestion_warnings": [],
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    synth = runner.invoke(
        app,
        ["manuscript", "synthesize", str(round_dir), "--source", str(source), "--export-critic", "--json"],
    )

    assert synth.exit_code == 0
    critic_text = (round_dir / "source_review.critic.md").read_text(encoding="utf-8")
    assert "prop-00001" in critic_text
    assert critic_text.index("Middle.") < critic_text.index("{>> prop-00001 <<}{--Same line.")
    assert r"Changed {\-- second --\} line." in critic_text


def test_manuscript_decide_and_apply_accepted_safe_proposal(tmp_path: Path) -> None:
    _, source, round_dir = _prepare_round_with_docx(tmp_path, round_id="decision-apply")

    notes = tmp_path / "feedback.md"
    notes.write_text("- replace 'Alpha example sentence.' with 'Alpha sample sentence.'\n", encoding="utf-8")
    runner = CliRunner()
    collect = runner.invoke(app, ["manuscript", "collect", str(round_dir), "--notes", str(notes), "--json"])
    assert collect.exit_code == 0

    synth = runner.invoke(app, ["manuscript", "synthesize", str(round_dir), "--source", str(source), "--json"])
    assert synth.exit_code == 0
    safe = json.loads((round_dir / "proposed.safe_edits.json").read_text(encoding="utf-8"))
    proposal_id = safe["proposals"][0]["proposal_id"]
    assert safe["proposals"][0]["status"] == "proposed_safe"

    decide = runner.invoke(
        app,
        [
            "manuscript",
            "decide",
            str(round_dir),
            "--proposal-id",
            proposal_id,
            "--decision",
            "accept",
            "--note",
            "Looks good.",
            "--json",
        ],
    )
    assert decide.exit_code == 0

    apply = runner.invoke(
        app,
        ["manuscript", "apply-proposals", str(round_dir), "--source", str(source), "--accepted", "--json"],
    )

    assert apply.exit_code == 0
    payload = json.loads(apply.stdout)
    assert payload["applied_proposal_ids"] == [proposal_id]
    assert "Alpha sample sentence." in source.read_text(encoding="utf-8")
    log_text = (round_dir / "proposal.decisions.jsonl").read_text(encoding="utf-8")
    assert '"decision": "accept"' in log_text
    assert '"decision": "applied"' in log_text


def test_manuscript_synthesize_skips_suggestion_for_different_source_file(tmp_path: Path) -> None:
    source = tmp_path / "chapter.md"
    source.write_text("# Title\n\nAlpha line.\n", encoding="utf-8")
    round_dir = tmp_path / "rounds" / "wrong-file"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "feedback.bundle.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "round_id": "wrong-file",
                "events": [
                    {
                        "event_id": "evt-00001",
                        "channel": "github_pr",
                        "kind": "suggestion",
                        "severity": "medium",
                        "author": "reviewer",
                        "created_at": "2026-03-02T10:00:00Z",
                        "anchor": {"file": "other.md", "line_start": 3, "line_end": 3},
                        "content": {"summary": "Wrong file", "proposed_text": "Updated line.\n"},
                        "trace": {"source_ref": "pull_comment:1"},
                    }
                ],
                "counts": {"total": 1},
                "ingestion_warnings": [],
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["manuscript", "synthesize", str(round_dir), "--source", str(source), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    safe = json.loads(Path(payload["outputs"]["safe_edits"]).read_text(encoding="utf-8"))
    assert safe["proposals"] == []


def test_manuscript_collect_missing_manifest_fails(tmp_path: Path) -> None:
    round_dir = tmp_path / "rounds" / "missing-manifest"
    round_dir.mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(app, ["manuscript", "collect", str(round_dir), "--json"])
    assert result.exit_code != 0
    assert isinstance(result.exception, FileNotFoundError)


def test_manuscript_synthesize_invalid_bundle_fails(tmp_path: Path) -> None:
    source = tmp_path / "chapter.md"
    source.write_text("# Title\n\nBody.\n", encoding="utf-8")
    round_dir = tmp_path / "rounds" / "invalid-bundle"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "feedback.bundle.json").write_text(
        json.dumps({"schema_version": 1, "round_id": "invalid-bundle", "events": {}}, ensure_ascii=True),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["manuscript", "synthesize", str(round_dir), "--source", str(source), "--json"],
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)


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


def test_manuscript_synthesize_apply_safe_refuses_stale_source(tmp_path: Path) -> None:
    _, source, round_dir = _prepare_round_with_docx(tmp_path, round_id="stale-source")

    notes = tmp_path / "feedback.md"
    notes.write_text("- replace 'Alpha example sentence.' with 'Alpha sample sentence.'\n", encoding="utf-8")
    runner = CliRunner()
    collect = runner.invoke(app, ["manuscript", "collect", str(round_dir), "--notes", str(notes), "--json"])
    assert collect.exit_code == 0

    source.write_text("# Title\n\nAlpha example sentence.\n\nNew author-side paragraph.\n", encoding="utf-8")

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

    assert synth.exit_code != 0
    assert isinstance(synth.exception, ValueError)
    assert "Source has changed since manuscript prepare" in str(synth.exception)
    assert "Alpha sample sentence." not in source.read_text(encoding="utf-8")


def test_manuscript_synthesize_apply_safe_can_override_source_drift(tmp_path: Path) -> None:
    _, source, round_dir = _prepare_round_with_docx(tmp_path, round_id="source-drift-override")

    notes = tmp_path / "feedback.md"
    notes.write_text("- replace 'Alpha example sentence.' with 'Alpha sample sentence.'\n", encoding="utf-8")
    runner = CliRunner()
    collect = runner.invoke(app, ["manuscript", "collect", str(round_dir), "--notes", str(notes), "--json"])
    assert collect.exit_code == 0

    source.write_text("# Title\n\nAlpha example sentence.\n\nNew author-side paragraph.\n", encoding="utf-8")

    synth = runner.invoke(
        app,
        [
            "manuscript",
            "synthesize",
            str(round_dir),
            "--source",
            str(source),
            "--apply-safe",
            "--allow-source-drift",
            "--json",
        ],
    )

    assert synth.exit_code == 0
    payload = json.loads(synth.stdout)
    assert payload["source_drift"]["drifted"] is True
    assert "Alpha sample sentence." in source.read_text(encoding="utf-8")


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
