#!/usr/bin/env python3
"""Regenerate skill reference docs from demodsl source code.

Usage:
    python scripts/sync_skill_refs.py

Reads models.py, effects/, examples/ and regenerates:
  .github/skills/demodsl-generate/references/schema-reference.md
  .github/skills/demodsl-generate/references/effects-catalog.md
  .github/skills/demodsl-generate/references/examples.md
"""

from __future__ import annotations

import inspect
import re
import textwrap
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

ROOT = Path(__file__).resolve().parent.parent
REFS_DIR = ROOT / ".github" / "skills" / "demodsl-generate" / "references"
EXAMPLES_DIR = ROOT / "examples"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _type_str(annotation: Any) -> str:
    """Convert a type annotation to a readable string."""
    if annotation is type(None):
        return "null"
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Literal:
        return " \\| ".join(f"`{a}`" for a in args)
    if origin is list:
        inner = _type_str(args[0]) if args else "Any"
        return f"list[{inner}]"
    if origin is dict:
        return "dict"
    # Union / Optional (X | None)
    if origin is type(None):
        return "null"
    if hasattr(annotation, "__origin__") and str(annotation).startswith("typing.Union"):
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _type_str(non_none[0])
        return " | ".join(_type_str(a) for a in non_none)
    # X | None  (Python 3.10+ union)
    if str(origin) == "typing.Union" or (args and type(None) in args):
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _type_str(non_none[0])
        return " | ".join(_type_str(a) for a in non_none)
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def _default_str(field_info: Any) -> str:
    """Extract default value from a Pydantic FieldInfo."""
    from pydantic.fields import FieldInfo
    from pydantic_core import PydanticUndefined

    if not isinstance(field_info, FieldInfo):
        return "—"
    if field_info.default is not PydanticUndefined:
        val = field_info.default
        if val is None:
            return "null"
        if isinstance(val, str):
            return f'`"{val}"`'
        if isinstance(val, bool):
            return f"`{str(val).lower()}`"
        if isinstance(val, (int, float)):
            return f"`{val}`"
        return f"`{val}`"
    if field_info.default_factory is not None:
        try:
            val = field_info.default_factory()
            if isinstance(val, list) and len(val) <= 6:
                return f"`{val}`"
            return f"*(factory)*"
        except Exception:
            return "*(factory)*"
    return "**required**"


def _model_table(model_cls: type) -> str:
    """Generate a markdown table for a Pydantic model."""
    lines = ["| Field | Type | Default |", "|-------|------|---------|"]
    for name, field in model_cls.model_fields.items():
        type_s = _type_str(field.annotation)
        default_s = _default_str(field)
        lines.append(f"| `{name}` | {type_s} | {default_s} |")
    return "\n".join(lines)


# ── Schema Reference ─────────────────────────────────────────────────────────


def generate_schema_reference() -> str:
    """Generate schema-reference.md from models.py."""
    from demodsl import models as m

    sections: list[str] = ["# DemoDSL Schema Reference\n"]
    sections.append("Complete field reference — auto-generated from `demodsl/models.py`.\n")

    # Collect models in logical order
    model_groups: list[tuple[str, list[tuple[str, type]]]] = [
        ("Root: `DemoConfig`", [("DemoConfig", m.DemoConfig)]),
        ("Metadata", [("Metadata", m.Metadata)]),
        ("VoiceConfig", [("VoiceConfig", m.VoiceConfig)]),
        ("AudioConfig", [
            ("AudioConfig", m.AudioConfig),
            ("BackgroundMusic", m.BackgroundMusic),
            ("VoiceProcessing", m.VoiceProcessing),
            ("Compression", m.Compression),
            ("AudioEffects", m.AudioEffects),
        ]),
        ("DeviceRendering", [("DeviceRendering", m.DeviceRendering)]),
        ("VideoConfig", [
            ("VideoConfig", m.VideoConfig),
            ("Intro", m.Intro),
            ("Transitions", m.Transitions),
            ("Watermark", m.Watermark),
            ("Outro", m.Outro),
            ("VideoOptimization", m.VideoOptimization),
        ]),
        ("Scenario", [
            ("Scenario", m.Scenario),
            ("Viewport", m.Viewport),
            ("CursorConfig", m.CursorConfig),
            ("GlowSelectConfig", m.GlowSelectConfig),
            ("AvatarConfig", m.AvatarConfig),
            ("SubtitleConfig", m.SubtitleConfig),
            ("PopupCardConfig", m.PopupCardConfig),
        ]),
        ("Step", [
            ("Step", m.Step),
            ("Locator", m.Locator),
            ("Effect", m.Effect),
            ("CardContent", m.CardContent),
        ]),
        ("Pipeline & Output", [
            ("PipelineStage", m.PipelineStage),
            ("OutputConfig", m.OutputConfig),
            ("SocialExport", m.SocialExport),
            ("Analytics", m.Analytics),
        ]),
    ]

    for group_title, models in model_groups:
        sections.append(f"## {group_title}\n")
        for model_name, model_cls in models:
            if model_name != group_title.strip("`").split(":")[-1].strip():
                sections.append(f"### {model_name}\n")
            sections.append(_model_table(model_cls))
            sections.append("")

    # Avatar styles list
    avatar_styles = sorted(m.AVATAR_STYLES)
    sections.append("### Avatar Styles\n")
    sections.append(", ".join(f"`{s}`" for s in avatar_styles))
    sections.append("")

    # EffectType list
    effect_types = get_args(m.EffectType)
    sections.append("### All Effect Types\n")
    sections.append(", ".join(f"`{e}`" for e in effect_types))
    sections.append("")

    return "\n".join(sections)


# ── Effects Catalog ──────────────────────────────────────────────────────────


def generate_effects_catalog() -> str:
    """Generate effects-catalog.md from effects/ source."""
    from demodsl.effects import browser_effects, post_effects
    from demodsl.effects.registry import EffectRegistry

    registry = EffectRegistry()
    browser_effects.register_all_browser_effects(registry)
    post_effects.register_all_post_effects(registry)

    lines: list[str] = ["# DemoDSL Effects Catalog\n"]
    lines.append("Auto-generated from `demodsl/effects/`. All effects with their parameters.\n")

    # Browser effects
    lines.append("## Browser Effects (JS-injected during capture)\n")
    lines.append("| Effect | Class |")
    lines.append("|--------|-------|")
    for name in sorted(registry.browser_effects):
        cls = registry.get_browser_effect(name)
        lines.append(f"| `{name}` | `{cls.__class__.__name__}` |")
    lines.append("")

    # Post effects
    lines.append("## Post-Processing Effects (applied to video clips)\n")
    lines.append("| Effect | Class |")
    lines.append("|--------|-------|")
    for name in sorted(registry.post_effects):
        cls = registry.get_post_effect(name)
        lines.append(f"| `{name}` | `{cls.__class__.__name__}` |")
    lines.append("")

    # Common params
    lines.append("## Common Effect Parameters\n")
    lines.append("| Param | Type | Description |")
    lines.append("|-------|------|-------------|")
    lines.append("| `duration` | float | Effect duration in seconds |")
    lines.append("| `intensity` | float | Effect strength (0.0–1.0) |")
    lines.append("| `color` | str | CSS color (hex, rgba) |")
    lines.append("| `speed` | float | Animation speed multiplier |")
    lines.append("| `scale` | float | Zoom/scale factor |")
    lines.append("| `depth` | int | Parallax depth |")
    lines.append("| `direction` | str | Direction (up/down/left/right, in/out) |")
    lines.append("| `target_x` | float | Normalized X position (0.0–1.0) |")
    lines.append("| `target_y` | float | Normalized Y position (0.0–1.0) |")
    lines.append("| `angle` | float | Rotation angle in degrees |")
    lines.append("| `ratio` | float | Aspect ratio |")
    lines.append("| `preset` | str | Named preset |")
    lines.append("| `focus_position` | float | Focus point (0.0–1.0) |")
    lines.append("")

    return "\n".join(lines)


# ── Examples ─────────────────────────────────────────────────────────────────


def generate_examples() -> str:
    """Generate examples.md from examples/ directory."""
    lines: list[str] = ["# DemoDSL YAML Examples\n"]
    lines.append("Auto-generated from `examples/` directory.\n")

    # Pick representative examples
    picks = [
        ("Minimal — Navigate & Scroll", "demo_navigate_scroll.yaml"),
        ("Browser Effects", "demo_browser_effects.yaml"),
        ("Multi-Scenario", "demo_multi_scenario.yaml"),
        ("Voice Narration", "demo_voice_narration.yaml"),
        ("Avatar", "demo_avatar.yaml"),
        ("Popup Cards", "demo_popup_card.yaml"),
        ("Cursor Trails", "demo_cursor_trails.yaml"),
        ("Subtitles", "demo_subtitle.yaml"),
    ]

    for title, filename in picks:
        path = EXAMPLES_DIR / filename
        if not path.exists():
            continue
        content = path.read_text().strip()
        lines.append(f"---\n\n## {title}\n")
        lines.append(f"Source: `examples/{filename}`\n")
        lines.append(f"```yaml\n{content}\n```\n")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    import sys
    sys.path.insert(0, str(ROOT))

    REFS_DIR.mkdir(parents=True, exist_ok=True)

    schema = generate_schema_reference()
    (REFS_DIR / "schema-reference.md").write_text(schema)
    print(f"✓ schema-reference.md ({len(schema.splitlines())} lines)")

    catalog = generate_effects_catalog()
    (REFS_DIR / "effects-catalog.md").write_text(catalog)
    print(f"✓ effects-catalog.md ({len(catalog.splitlines())} lines)")

    examples = generate_examples()
    (REFS_DIR / "examples.md").write_text(examples)
    print(f"✓ examples.md ({len(examples.splitlines())} lines)")

    print("Done — skill references synced.")


if __name__ == "__main__":
    main()
