"""CLI entrypoint for wordmark."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any

import typer

from wordmark import __version__
from wordmark.config import AppConfig, load_config
from wordmark.jsonio import dumps
from wordmark import ooxml_engine
from wordmark import uno_engine
from wordmark import verify as verify_mod
from wordmark.render import render_docx
from wordmark.sidecar import render_sidecar_paths, write_json, write_text
from wordmark.transcript import append_transcript

app = typer.Typer(help="CLI-first DOCX review tooling", no_args_is_help=True)
comment_app = typer.Typer(help="Comment operations")
edit_app = typer.Typer(help="Document edit operations")
review_app = typer.Typer(help="Review operations")

app.add_typer(comment_app, name="comment")
app.add_typer(edit_app, name="edit")
app.add_typer(review_app, name="review")


def _payload(value: Any) -> Any:
    if is_dataclass(value):
        out = asdict(value)
        if "path" in out:
            out["path"] = str(out["path"])
        return out
    return value


def _echo(value: Any, *, json_output: bool) -> None:
    if json_output:
        typer.echo(dumps(value))
    else:
        if isinstance(value, str):
            typer.echo(value)
        else:
            typer.echo(json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True))


def _load_app_config(config_path: Path | None) -> AppConfig:
    return load_config(config_path)


def _resolve_author(author: str | None, config: AppConfig) -> str:
    return author or config.default_author


def _resolve_initials(initials: str | None, config: AppConfig) -> str:
    return initials or config.default_initials


def _resolve_track_changes(raw: str, config: AppConfig) -> bool:
    token = raw.strip().lower()
    if token == "default":
        return config.track_changes_default
    if token in {"on", "true", "1", "yes"}:
        return True
    if token in {"off", "false", "0", "no"}:
        return False
    raise ValueError("--track-changes must be one of: default, on, off")


def _write_review_sidecars(config: AppConfig, docx_path: Path, review_data: dict[str, Any]) -> dict[str, str]:
    if not config.sidecar.enabled:
        return {}
    sidecars = render_sidecar_paths(config, docx_path)
    comments = review_data.get("comments", [])
    revisions = review_data.get("revisions", [])
    text_lines = [item.get("text", "") for item in revisions]

    write_json(sidecars["comments"], comments)
    write_json(sidecars["revisions"], revisions)
    write_text(sidecars["text"], "\n".join(text_lines) + ("\n" if text_lines else ""))
    return {"comments": str(sidecars["comments"]), "revisions": str(sidecars["revisions"]), "text": str(sidecars["text"])}


@app.command("version")
def version() -> None:
    """Print tool version."""
    typer.echo(__version__)


@app.command("inspect")
def inspect_cmd(
    docx: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
    write_sidecar: bool = typer.Option(True, "--write-sidecar/--no-write-sidecar", help="Write sidecar artifacts."),
) -> None:
    """Inspect paragraphs, comments, and revision state."""
    config = _load_app_config(config_path)
    report = ooxml_engine.inspect(docx)

    payload: dict[str, Any] = {
        "report": _payload(report),
        "sidecars": {},
    }

    if write_sidecar:
        review_data = ooxml_engine.list_review(docx)
        payload["sidecars"] = _write_review_sidecars(config, docx, review_data)

    _echo(payload, json_output=json_output)


@comment_app.command("add")
def comment_add(
    docx: Path = typer.Argument(..., exists=True, readable=True, writable=True, resolve_path=True),
    anchor: str = typer.Option(..., "--anchor", help="Anchor selector: p:<index> or text:<snippet>"),
    text: str = typer.Option(..., "--text", help="Comment text."),
    author: str | None = typer.Option(None, "--author", help="Comment author label."),
    initials: str | None = typer.Option(None, "--initials", help="Comment initials."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Emit intended mutation without writing."),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Add a DOCX comment anchored to a paragraph or text snippet."""
    config = _load_app_config(config_path)
    resolved_author = _resolve_author(author, config)
    resolved_initials = _resolve_initials(initials, config)

    result = ooxml_engine.add_comment(
        docx,
        selector=anchor,
        text=text,
        author=resolved_author,
        initials=resolved_initials,
        dry_run=dry_run,
    )
    transcript_path = append_transcript(config, result)

    payload = {
        "operation": _payload(result),
        "transcript": str(transcript_path),
    }
    _echo(payload, json_output=json_output)


@edit_app.command("apply")
def edit_apply(
    docx: Path = typer.Argument(..., exists=True, readable=True, writable=True, resolve_path=True),
    patch: Path = typer.Option(..., "--patch", exists=True, readable=True, resolve_path=True, help="Patch JSON file."),
    author: str | None = typer.Option(None, "--author", help="Tracked changes author label."),
    track_changes: str = typer.Option("default", "--track-changes", help="default|on|off"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Emit intended mutation without writing."),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Apply a patch with OOXML-first and UNO fallback engine ordering."""
    config = _load_app_config(config_path)
    resolved_author = _resolve_author(author, config)
    track = _resolve_track_changes(track_changes, config)
    patch_data = json.loads(patch.read_text(encoding="utf-8"))

    result = None
    fallback_reason = ""
    errors: list[str] = []

    for engine_name in config.engine_order:
        if engine_name == "ooxml":
            try:
                result = ooxml_engine.apply_patch(
                    docx,
                    patch_data=patch_data,
                    author=resolved_author,
                    track_changes=track,
                    dry_run=dry_run,
                )
                break
            except ooxml_engine.OoxmlUnsupportedOperation as exc:
                fallback_reason = str(exc)
                errors.append(f"ooxml: {exc}")
                continue
            except Exception as exc:  # pragma: no cover - surfaced to user
                errors.append(f"ooxml: {exc}")
                continue

        if engine_name == "uno":
            try:
                result = uno_engine.apply_patch(
                    docx,
                    patch_data=patch_data,
                    author=resolved_author,
                    track_changes=track,
                    dry_run=dry_run,
                    fallback_reason=fallback_reason or "configured engine order",
                )
                break
            except Exception as exc:  # pragma: no cover - surfaced to user
                errors.append(f"uno: {exc}")
                continue

    if result is None:
        _echo(
            {
                "error": "No configured engine could apply this patch",
                "engine_attempt_errors": errors,
            },
            json_output=True,
        )
        raise typer.Exit(code=1)

    transcript_path = append_transcript(config, result)
    payload = {
        "operation": _payload(result),
        "transcript": str(transcript_path),
        "engine_attempt_errors": errors,
    }
    _echo(payload, json_output=json_output)


@review_app.command("list")
def review_list(
    docx: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
    write_sidecar: bool = typer.Option(True, "--write-sidecar/--no-write-sidecar", help="Write sidecar artifacts."),
) -> None:
    """List comments and revisions in review-friendly format."""
    config = _load_app_config(config_path)
    review_data = ooxml_engine.list_review(docx)
    sidecars: dict[str, str] = {}

    if write_sidecar:
        sidecars = _write_review_sidecars(config, docx, review_data)

    payload = {
        "review": review_data,
        "sidecars": sidecars,
    }
    _echo(payload, json_output=json_output)


@review_app.command("accept")
def review_accept(
    docx: Path = typer.Argument(..., exists=True, readable=True, writable=True, resolve_path=True),
    author: str | None = typer.Option(None, "--author", help="Accept revisions by author only."),
    all_authors: bool = typer.Option(False, "--all", help="Accept revisions from all authors."),
    actor: str | None = typer.Option(None, "--actor", help="Operator label for transcript metadata."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Emit intended mutation without writing."),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Accept tracked revisions by author or globally."""
    config = _load_app_config(config_path)
    resolved_actor = _resolve_author(actor, config)
    filter_author = None if all_authors else author

    result = ooxml_engine.review_action(
        docx,
        mode="accept",
        author=filter_author,
        actor=resolved_actor,
        dry_run=dry_run,
    )
    transcript_path = append_transcript(config, result)

    payload = {
        "operation": _payload(result),
        "transcript": str(transcript_path),
    }
    _echo(payload, json_output=json_output)


@review_app.command("reject")
def review_reject(
    docx: Path = typer.Argument(..., exists=True, readable=True, writable=True, resolve_path=True),
    author: str | None = typer.Option(None, "--author", help="Reject revisions by author only."),
    all_authors: bool = typer.Option(False, "--all", help="Reject revisions from all authors."),
    actor: str | None = typer.Option(None, "--actor", help="Operator label for transcript metadata."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Emit intended mutation without writing."),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Reject tracked revisions by author or globally."""
    config = _load_app_config(config_path)
    resolved_actor = _resolve_author(actor, config)
    filter_author = None if all_authors else author

    result = ooxml_engine.review_action(
        docx,
        mode="reject",
        author=filter_author,
        actor=resolved_actor,
        dry_run=dry_run,
    )
    transcript_path = append_transcript(config, result)

    payload = {
        "operation": _payload(result),
        "transcript": str(transcript_path),
    }
    _echo(payload, json_output=json_output)


@app.command("verify")
def verify_cmd(
    before: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    after: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    profile: str = typer.Option("business-docs", "--profile", help="Fidelity profile"),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
    write_sidecar: bool = typer.Option(True, "--write-sidecar/--no-write-sidecar", help="Write report sidecars."),
) -> None:
    """Run integrity and render diff verification gates."""
    config = _load_app_config(config_path)
    persist_render_dir = None
    if write_sidecar and config.sidecar.enabled:
        persist_render_dir = render_sidecar_paths(config, after)["render_diff"]
    result = verify_mod.verify_docx(
        before,
        after,
        profile=profile,
        config=config,
        persist_render_dir=persist_render_dir,
    )

    payload = {
        "verify": {
            "passed": result.passed,
            "profile": result.profile,
            "checks": result.checks,
        },
        "sidecars": {},
    }

    if write_sidecar and config.sidecar.enabled:
        sidecars = render_sidecar_paths(config, after)
        write_json(sidecars["report"], payload["verify"])
        write_json(sidecars["xml_manifest"], result.checks["manifest"])
        write_json(sidecars["revisions"], result.checks["revisions"])
        write_json(sidecars["comments"], result.checks["comment_integrity"])
        payload["sidecars"] = {
            "report": str(sidecars["report"]),
            "xml_manifest": str(sidecars["xml_manifest"]),
            "revisions": str(sidecars["revisions"]),
            "comments": str(sidecars["comments"]),
            "render_diff": str(sidecars["render_diff"]),
        }

    _echo(payload, json_output=json_output)
    if not result.passed:
        raise typer.Exit(code=2)


@app.command("render")
def render_cmd(
    docx: Path = typer.Argument(..., exists=True, readable=True, resolve_path=True),
    out: Path = typer.Option(..., "--out", help="Output directory for PDF and page PNGs."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Render DOCX to PDF and PNG pages for visual inspection."""
    output = render_docx(docx, out)
    payload = {
        "docx": str(output.docx_path),
        "pdf": str(output.pdf_path),
        "png_pages": [str(p) for p in output.png_paths],
    }
    _echo(payload, json_output=json_output)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
