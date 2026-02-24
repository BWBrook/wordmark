"""Configuration loading for Wordmark."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class SidecarPaths:
    text: str = "artifacts/{stem}.text.md"
    comments: str = "artifacts/{stem}.comments.json"
    revisions: str = "artifacts/{stem}.revisions.json"
    xml_manifest: str = "artifacts/{stem}.xml-manifest.json"
    report: str = "artifacts/{stem}.report.json"
    render_diff: str = "artifacts/{stem}.render"


@dataclass(slots=True)
class SidecarConfig:
    enabled: bool = True
    paths: SidecarPaths = field(default_factory=SidecarPaths)


@dataclass(slots=True)
class FallbackPolicy:
    on_ooxml_unsupported: str = "uno"
    on_uno_fail: str = "comment"


@dataclass(slots=True)
class CommentFallbackConfig:
    enabled: bool = True
    template: str = (
        "Suggested edit: replace '{find}' with '{replace}'. "
        "Reason: {reason}. Classification: {classification}."
    )
    anchor_strategy: str = "best-effort-match"


@dataclass(slots=True)
class FidelityProfileConfig:
    render_diff_threshold: float = 0.02
    max_page_growth: int = 0


@dataclass(slots=True)
class AppConfig:
    default_author: str = "Barry Brook"
    default_initials: str = "BB"
    track_changes_default: bool = True
    engine_order: tuple[str, ...] = ("ooxml", "uno")
    fidelity_mode: str = "strict"
    allow_paragraph_rewrite_tracked: bool = False
    fallback_policy: FallbackPolicy = field(default_factory=FallbackPolicy)
    comment_fallback: CommentFallbackConfig = field(default_factory=CommentFallbackConfig)
    fidelity_profiles: tuple[str, ...] = ("business-docs",)
    fidelity_profile_settings: dict[str, FidelityProfileConfig] = field(
        default_factory=lambda: {
            "business-docs": FidelityProfileConfig(render_diff_threshold=0.02, max_page_growth=0),
            "review-edit": FidelityProfileConfig(render_diff_threshold=0.12, max_page_growth=2),
        }
    )
    sidecar: SidecarConfig = field(default_factory=SidecarConfig)
    transcript_path: str = "artifacts/transcripts/operations.jsonl"
    edited_output_dir: str = "examples/edited"


DEFAULT_CONFIG_PATH = Path("wordmark.yaml")


def _merge_dict(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge_dict(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path | None = None) -> AppConfig:
    cfg_path = path or DEFAULT_CONFIG_PATH
    raw = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    defaults = {
        "default_author": "Barry Brook",
        "default_initials": "BB",
        "track_changes_default": True,
        "engine_order": ["ooxml", "uno"],
        "fidelity_mode": "strict",
        "allow_paragraph_rewrite_tracked": False,
        "fallback_policy": {
            "on_ooxml_unsupported": "uno",
            "on_uno_fail": "comment",
        },
        "comment_fallback": {
            "enabled": True,
            "template": (
                "Suggested edit: replace '{find}' with '{replace}'. "
                "Reason: {reason}. Classification: {classification}."
            ),
            "anchor_strategy": "best-effort-match",
        },
        "fidelity_profiles": ["business-docs", "review-edit"],
        "fidelity_profile_settings": {
            "business-docs": {
                "render_diff_threshold": 0.02,
                "max_page_growth": 0,
            },
            "review-edit": {
                "render_diff_threshold": 0.12,
                "max_page_growth": 2,
            },
        },
        "sidecar": {
            "enabled": True,
            "paths": {
                "text": "artifacts/{stem}.text.md",
                "comments": "artifacts/{stem}.comments.json",
                "revisions": "artifacts/{stem}.revisions.json",
                "xml_manifest": "artifacts/{stem}.xml-manifest.json",
                "report": "artifacts/{stem}.report.json",
                "render_diff": "artifacts/{stem}.render",
            },
        },
        "transcript_path": "artifacts/transcripts/operations.jsonl",
        "edited_output_dir": "examples/edited",
    }
    merged = _merge_dict(defaults, raw)
    paths = SidecarPaths(**merged["sidecar"]["paths"])
    sidecar = SidecarConfig(enabled=bool(merged["sidecar"]["enabled"]), paths=paths)
    fallback_policy = FallbackPolicy(
        on_ooxml_unsupported=str(merged["fallback_policy"]["on_ooxml_unsupported"]),
        on_uno_fail=str(merged["fallback_policy"]["on_uno_fail"]),
    )
    comment_fallback = CommentFallbackConfig(
        enabled=bool(merged["comment_fallback"]["enabled"]),
        template=str(merged["comment_fallback"]["template"]),
        anchor_strategy=str(merged["comment_fallback"]["anchor_strategy"]),
    )
    profile_names = tuple(str(x) for x in merged["fidelity_profiles"])
    raw_profile_settings = merged.get("fidelity_profile_settings", {})
    if not isinstance(raw_profile_settings, dict):
        raise ValueError("fidelity_profile_settings must be an object mapping profile names to config")

    profile_settings: dict[str, FidelityProfileConfig] = {}
    for profile_name in profile_names:
        raw_settings = raw_profile_settings.get(profile_name, {})
        if not isinstance(raw_settings, dict):
            raise ValueError(f"fidelity_profile_settings.{profile_name} must be an object")
        profile_settings[profile_name] = FidelityProfileConfig(
            render_diff_threshold=float(raw_settings.get("render_diff_threshold", 0.02)),
            max_page_growth=int(raw_settings.get("max_page_growth", 0)),
        )

    return AppConfig(
        default_author=str(merged["default_author"]),
        default_initials=str(merged["default_initials"]),
        track_changes_default=bool(merged["track_changes_default"]),
        engine_order=tuple(str(x) for x in merged["engine_order"]),
        fidelity_mode=str(merged["fidelity_mode"]),
        allow_paragraph_rewrite_tracked=bool(merged["allow_paragraph_rewrite_tracked"]),
        fallback_policy=fallback_policy,
        comment_fallback=comment_fallback,
        fidelity_profiles=profile_names,
        fidelity_profile_settings=profile_settings,
        sidecar=sidecar,
        transcript_path=str(merged["transcript_path"]),
        edited_output_dir=str(merged["edited_output_dir"]),
    )
