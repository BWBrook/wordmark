"""CLI entrypoint for wordmark."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import typer

from wordmark import __version__
from wordmark.config import AppConfig, load_config
from wordmark.jsonio import dumps
from wordmark.models import OperationResult
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
artifacts_app = typer.Typer(help="Artifact housekeeping")

app.add_typer(comment_app, name="comment")
app.add_typer(edit_app, name="edit")
app.add_typer(review_app, name="review")
app.add_typer(artifacts_app, name="artifacts")


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


def _resolve_choice(name: str, value: str, allowed: set[str]) -> str:
    token = value.strip().lower()
    if token not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {allowed_list}")
    return token


def _resolve_edit_policy(
    config: AppConfig,
    *,
    fidelity_mode: str | None,
    on_unsupported: str | None,
    on_uno_fail: str | None,
    allow_paragraph_rewrite: bool | None,
) -> dict[str, Any]:
    mode = _resolve_choice("fidelity_mode", fidelity_mode or config.fidelity_mode, {"strict", "balanced", "aggressive"})
    unsupported_policy = _resolve_choice(
        "on_unsupported",
        on_unsupported or config.fallback_policy.on_ooxml_unsupported,
        {"fail", "comment", "uno"},
    )
    uno_fail_policy = _resolve_choice(
        "on_uno_fail",
        on_uno_fail or config.fallback_policy.on_uno_fail,
        {"fail", "comment"},
    )

    if allow_paragraph_rewrite is not None:
        allow_rewrite = bool(allow_paragraph_rewrite)
    elif mode == "strict":
        allow_rewrite = False
    elif mode == "aggressive":
        allow_rewrite = True
    else:
        allow_rewrite = bool(config.allow_paragraph_rewrite_tracked)

    return {
        "fidelity_mode": mode,
        "on_unsupported": unsupported_policy,
        "on_uno_fail": uno_fail_policy,
        "allow_paragraph_rewrite_tracked": allow_rewrite,
    }


def _safe_template(template: str, values: dict[str, Any]) -> str:
    text = template
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def _shorten(value: Any, limit: int = 140) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _apply_comment_fallback(
    *,
    docx: Path,
    patch_data: dict[str, Any],
    preflight: dict[str, Any],
    reason: str,
    author: str,
    initials: str,
    config: AppConfig,
    dry_run: bool,
) -> OperationResult:
    ops = patch_data.get("operations", [])
    preflight_ops = preflight.get("operations", [])
    created: list[dict[str, Any]] = []

    if not config.comment_fallback.enabled:
        raise RuntimeError("Comment fallback is disabled by config")

    reason_short = _shorten(str(reason).splitlines()[0] if str(reason) else "fallback requested")

    for i, op in enumerate(ops):
        pinfo = preflight_ops[i] if i < len(preflight_ops) else {}
        paragraph_index = pinfo.get("paragraph_index")
        selector = f"p:{paragraph_index}" if isinstance(paragraph_index, int) and paragraph_index >= 0 else "p:0"

        values = {
            "find": _shorten(op.get("find", op.get("expected_text", "<paragraph text>"))),
            "replace": _shorten(op.get("replace", op.get("new_text", "<new value>"))),
            "type": op.get("type", ""),
            "reason": reason_short,
            "classification": pinfo.get("classification", "unknown"),
        }
        comment_text = _safe_template(config.comment_fallback.template, values)

        if dry_run:
            created.append(
                {
                    "selector": selector,
                    "text": comment_text,
                    "dry_run": True,
                }
            )
            continue

        result = ooxml_engine.add_comment(
            docx,
            selector=selector,
            text=comment_text,
            author=author,
            initials=initials,
            dry_run=False,
        )
        created.append(
            {
                "selector": selector,
                "comment_id": result.details.get("comment_id"),
                "paragraph_index": result.details.get("paragraph_index"),
                "classification": pinfo.get("classification"),
            }
        )

    return OperationResult.now(
        command="edit apply",
        path=docx,
        engine="comment_fallback",
        changed=bool(created) and not dry_run,
        author=author,
        details={
            "fallback_reason": reason,
            "dry_run": dry_run,
            "comments_created": created,
            "operations_count": len(ops),
        },
    )


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


def _collect_artifact_files(
    root: Path,
    *,
    older_than_days: int | None,
    keep_names: set[str],
    keep_transcripts: bool,
) -> list[Path]:
    if not root.exists():
        return []

    cutoff_ts: float | None = None
    if older_than_days is not None:
        cutoff_ts = datetime.now(tz=timezone.utc).timestamp() - float(older_than_days * 86400)

    selected: list[Path] = []
    for candidate in sorted(root.rglob("*")):
        if candidate.is_dir():
            continue

        if candidate.name in keep_names:
            continue

        relative = candidate.relative_to(root)
        if keep_transcripts and relative.parts and relative.parts[0] == "transcripts":
            continue

        if cutoff_ts is not None:
            try:
                modified_ts = candidate.stat().st_mtime
            except OSError:
                continue
            if modified_ts > cutoff_ts:
                continue

        selected.append(candidate)
    return selected


def _prune_empty_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []

    removed: list[Path] = []
    directories = sorted((item for item in root.rglob("*") if item.is_dir()), key=lambda item: len(item.parts), reverse=True)
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            continue
        removed.append(directory)
    return removed


def _safe_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _to_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


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
    initials: str | None = typer.Option(None, "--initials", help="Fallback comment initials."),
    track_changes: str = typer.Option("default", "--track-changes", help="default|on|off"),
    fidelity_mode: str | None = typer.Option(None, "--fidelity-mode", help="strict|balanced|aggressive"),
    on_unsupported: str | None = typer.Option(None, "--on-unsupported", help="fail|comment|uno"),
    on_uno_fail: str | None = typer.Option(None, "--on-uno-fail", help="fail|comment"),
    allow_paragraph_rewrite: bool | None = typer.Option(
        None,
        "--allow-paragraph-rewrite/--no-allow-paragraph-rewrite",
        help="Allow paragraph-level rewrite fallback in tracked mode.",
    ),
    preflight_only: bool = typer.Option(False, "--preflight-only", help="Classify operation strategy without writing."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Emit intended mutation without writing."),
    config_path: Path | None = typer.Option(None, "--config", help="Path to wordmark config file."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Apply a patch with policy-driven OOXML/UNO/comment fallback ordering."""
    config = _load_app_config(config_path)
    resolved_author = _resolve_author(author, config)
    resolved_initials = _resolve_initials(initials, config)
    track = _resolve_track_changes(track_changes, config)
    patch_data = json.loads(patch.read_text(encoding="utf-8"))
    policy = _resolve_edit_policy(
        config,
        fidelity_mode=fidelity_mode,
        on_unsupported=on_unsupported,
        on_uno_fail=on_uno_fail,
        allow_paragraph_rewrite=allow_paragraph_rewrite,
    )
    preflight = ooxml_engine.preflight_patch(
        docx,
        patch_data=patch_data,
        track_changes=track,
        allow_paragraph_rewrite_tracked=bool(policy["allow_paragraph_rewrite_tracked"]),
    )

    if preflight_only:
        _echo(
            {
                "policy": policy,
                "preflight": preflight,
                "preflight_only": True,
            },
            json_output=json_output,
        )
        return

    result: OperationResult | None = None
    errors: list[str] = []
    attempts: list[dict[str, Any]] = []
    fallback_reason = ""
    uno_enabled = "uno" in config.engine_order

    try:
        result = ooxml_engine.apply_patch(
            docx,
            patch_data=patch_data,
            author=resolved_author,
            track_changes=track,
            dry_run=dry_run,
            allow_paragraph_rewrite_tracked=bool(policy["allow_paragraph_rewrite_tracked"]),
        )
        attempts.append({"engine": "ooxml", "status": "applied"})
    except ooxml_engine.OoxmlUnsupportedOperation as exc:
        fallback_reason = str(exc)
        attempts.append({"engine": "ooxml", "status": "unsupported", "reason": fallback_reason})
        errors.append(f"ooxml: {exc}")
    except Exception as exc:  # pragma: no cover - surfaced to user
        fallback_reason = str(exc)
        attempts.append({"engine": "ooxml", "status": "error", "reason": fallback_reason})
        errors.append(f"ooxml: {exc}")

    if result is None:
        if policy["on_unsupported"] == "comment":
            try:
                result = _apply_comment_fallback(
                    docx=docx,
                    patch_data=patch_data,
                    preflight=preflight,
                    reason=fallback_reason or "ooxml unsupported",
                    author=resolved_author,
                    initials=resolved_initials,
                    config=config,
                    dry_run=dry_run,
                )
                attempts.append({"engine": "comment_fallback", "status": "applied"})
            except Exception as exc:  # pragma: no cover - surfaced to user
                attempts.append({"engine": "comment_fallback", "status": "error", "reason": str(exc)})
                errors.append(f"comment_fallback: {exc}")

        elif policy["on_unsupported"] == "uno":
            if not uno_enabled:
                attempts.append({"engine": "uno", "status": "skipped", "reason": "uno_not_enabled"})
                errors.append("uno: engine not enabled in config.engine_order")
            else:
                try:
                    result = uno_engine.apply_patch(
                        docx,
                        patch_data=patch_data,
                        author=resolved_author,
                        track_changes=track,
                        dry_run=dry_run,
                        fallback_reason=fallback_reason or "ooxml unsupported",
                    )
                    attempts.append({"engine": "uno", "status": "applied"})
                except Exception as exc:  # pragma: no cover - surfaced to user
                    attempts.append({"engine": "uno", "status": "error", "reason": str(exc)})
                    errors.append(f"uno: {exc}")
                    if policy["on_uno_fail"] == "comment":
                        try:
                            result = _apply_comment_fallback(
                                docx=docx,
                                patch_data=patch_data,
                                preflight=preflight,
                                reason=f"uno failed after ooxml unsupported: {exc}",
                                author=resolved_author,
                                initials=resolved_initials,
                                config=config,
                                dry_run=dry_run,
                            )
                            attempts.append({"engine": "comment_fallback", "status": "applied", "after": "uno"})
                        except Exception as comment_exc:  # pragma: no cover - surfaced to user
                            attempts.append(
                                {
                                    "engine": "comment_fallback",
                                    "status": "error",
                                    "reason": str(comment_exc),
                                    "after": "uno",
                                }
                            )
                            errors.append(f"comment_fallback: {comment_exc}")

    if result is None:
        _echo(
            {
                "error": "No configured engine could apply this patch",
                "engine_attempt_errors": errors,
                "attempts": attempts,
                "policy": policy,
                "preflight": preflight,
            },
            json_output=True,
        )
        raise typer.Exit(code=1)

    transcript_path = append_transcript(config, result)
    payload = {
        "operation": _payload(result),
        "transcript": str(transcript_path),
        "engine_attempt_errors": errors,
        "attempts": attempts,
        "policy": policy,
        "preflight": preflight,
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


@artifacts_app.command("clean")
def artifacts_clean(
    path: Path = typer.Option(Path("artifacts"), "--path", help="Artifact directory to clean."),
    older_than_days: int | None = typer.Option(
        None,
        "--older-than-days",
        min=0,
        help="Only target files modified more than this many days ago.",
    ),
    keep_transcripts: bool = typer.Option(False, "--keep-transcripts", help="Do not delete files under transcripts/."),
    apply: bool = typer.Option(False, "--apply", help="Delete matched files. Default is preview-only."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output."),
) -> None:
    """Preview or remove sidecar artifacts and transcripts."""
    root = path.resolve()
    keep_names = {".gitkeep", "README.md"}

    if root.exists() and not root.is_dir():
        _echo({"error": "--path must point to a directory", "path": str(root)}, json_output=json_output)
        raise typer.Exit(code=2)

    matches = _collect_artifact_files(
        root,
        older_than_days=older_than_days,
        keep_names=keep_names,
        keep_transcripts=keep_transcripts,
    )
    matched_paths = [_to_relative(item, root) for item in matches]
    matched_bytes = sum(_safe_size(item) for item in matches)

    deleted_paths: list[str] = []
    deleted_dirs: list[str] = []
    deleted_bytes = 0
    errors: list[str] = []

    if apply:
        for file_path in matches:
            size = _safe_size(file_path)
            try:
                file_path.unlink()
            except OSError as exc:
                errors.append(f"{file_path}: {exc}")
                continue
            deleted_bytes += size
            deleted_paths.append(_to_relative(file_path, root))
        deleted_dirs = [_to_relative(item, root) for item in _prune_empty_dirs(root)]

    payload = {
        "path": str(root),
        "exists": root.exists(),
        "apply": apply,
        "older_than_days": older_than_days,
        "keep_transcripts": keep_transcripts,
        "preserved_names": sorted(keep_names),
        "matched_count": len(matches),
        "matched_bytes": matched_bytes,
        "matched_files": matched_paths,
        "deleted_count": len(deleted_paths),
        "deleted_bytes": deleted_bytes,
        "deleted_files": deleted_paths,
        "deleted_dirs": deleted_dirs,
        "errors": errors,
    }
    _echo(payload, json_output=json_output)

    if errors:
        raise typer.Exit(code=1)


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
