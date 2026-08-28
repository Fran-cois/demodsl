"""Theme resolution, application and brand extraction (issue #27).

Three pieces:

* :func:`resolve_theme` — turn ``theme: dark-dev`` (a preset name) or an
  inline mapping into a validated :class:`~demodsl.models.theme.ThemeConfig`.
* :func:`apply_theme` — push the theme tokens down into every overlay that
  currently hard-codes a colour, *without* clobbering explicit per-field
  overrides.
* :func:`extract_theme` — derive a contrast-checked theme proposal from a
  sample of the target page's computed styles.

Only :func:`extract_theme`'s browser-side collection needs Playwright; the
logic itself is pure so it can be unit-tested from a JSON fixture.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from demodsl.color_utils import (
    adjust_for_contrast,
    contrast_ratio,
    is_light,
    mix,
    parse_css_color,
    readable_ink,
    to_hex,
)
from demodsl.models.theme import MIN_ACCENT_CONTRAST, ThemeConfig, discover_theme_presets

logger = logging.getLogger(__name__)

__all__ = [
    "resolve_theme",
    "apply_theme",
    "extract_theme",
    "theme_palette",
    "PAGE_SAMPLE_JS",
]


def resolve_theme(theme: ThemeConfig | str | dict[str, Any] | None) -> ThemeConfig | None:
    """Resolve a preset name / mapping / instance into a ``ThemeConfig``."""
    if theme is None:
        return None
    if isinstance(theme, ThemeConfig):
        return theme
    if isinstance(theme, str):
        presets = discover_theme_presets()
        preset = presets.get(theme)
        if preset is None:
            raise ValueError(f"Unknown theme preset {theme!r}. Available: {sorted(presets)}")
        return ThemeConfig(**preset)
    return ThemeConfig(**theme)


def theme_palette(theme: ThemeConfig | str | dict[str, Any] | None) -> dict[str, Any]:
    """Flatten a theme into the tokens a renderer actually needs.

    Plugins draw with Pillow, ffmpeg, Blender or raw CSS rather than with the
    engine's overlay models, so they need the derived values too — a muted
    accent for fills, an ink that stays readable on the accent, a four-stop
    glow ramp. Computing those in each plugin is how palettes drift apart.

    Returns an empty dict when there is no theme, so a caller can write
    ``palette.get("accent", MY_DEFAULT)`` and stay themeless-safe.
    """
    resolved = resolve_theme(theme)
    if resolved is None:
        return {}
    accent = resolved.accent
    surface = resolved.surface
    return {
        "accent": accent,
        "accent_soft": mix(accent, surface, 0.65),
        "accent_strong": mix(accent, resolved.ink, 0.25),
        "on_accent": readable_ink(accent),
        "ink": resolved.ink,
        "ink_muted": mix(resolved.ink, surface, 0.45),
        "surface": surface,
        "surface_raised": mix(surface, resolved.ink, 0.06),
        "border": mix(surface, resolved.ink, 0.18),
        "mark_positive": resolved.mark_positive,
        "mark_negative": resolved.mark_negative,
        "font": resolved.font,
        "is_light": resolved.is_light,
        "glow": _glow_palette(resolved),
    }


def _glow_palette(theme: ThemeConfig) -> list[str]:
    return [
        theme.accent,
        mix(theme.accent, theme.ink, 0.35),
        mix(theme.accent, theme.surface, 0.35),
        theme.accent,
    ]


def _set_default(model: Any, field: str, value: Any) -> str | None:
    """Set ``model.field`` to *value* unless the author set it explicitly.

    Pydantic's ``model_fields_set`` is what distinguishes "the author wrote
    this colour" from "this is the library default", which is exactly the
    rule the issue asks for: per-field overrides keep winning.
    """
    if model is None or field in model.model_fields_set:
        return None
    setattr(model, field, value)
    model.model_fields_set.add(field)
    return field


def _theme_effect(effect: Any, theme: ThemeConfig, glow_palette: list[str]) -> list[str]:
    """Push theme tokens into one browser/post effect, returning themed fields.

    ``EFFECT_VALID_PARAMS`` is the source of truth for what each effect
    understands, so a token is only written when that effect declares it —
    an effect that takes no colour is left alone. This is also how a plugin
    effect opts in: declare ``accent`` / ``font`` (or any of the others) in
    the params it passes to ``register_plugin_effect_type``.
    """
    from demodsl.models.effects import EFFECT_VALID_PARAMS

    valid = EFFECT_VALID_PARAMS.get(getattr(effect, "type", ""))
    if not valid:
        return []
    tokens = {
        "color": theme.accent,
        "accent": theme.accent,
        "colors": glow_palette,
        "surface": theme.surface,
        "ink": theme.ink,
        "font": theme.font,
    }
    return [
        field
        for name, value in tokens.items()
        if name in valid and (field := _set_default(effect, name, value))
    ]


def apply_theme(config: Any) -> list[str]:
    """Propagate ``config.theme`` into every overlay that carries a colour.

    Returns the list of ``dotted.paths`` that were themed, so callers (and
    tests) can see exactly what changed. Fields the author set explicitly
    are left untouched.
    """
    theme = resolve_theme(getattr(config, "theme", None))
    if theme is None:
        return []

    applied: list[str] = []

    def record(prefix: str, field: str | None) -> None:
        if field:
            applied.append(f"{prefix}.{field}")

    glow_palette = _glow_palette(theme)

    for idx, scenario in enumerate(getattr(config, "scenarios", []) or []):
        prefix = f"scenarios[{idx}]"
        record(f"{prefix}.cursor", _set_default(scenario.cursor, "color", theme.accent))
        record(
            f"{prefix}.glow_select",
            _set_default(scenario.glow_select, "colors", glow_palette),
        )
        record(
            f"{prefix}.popup_card",
            _set_default(scenario.popup_card, "accent_color", theme.accent),
        )
        if scenario.subtitle is not None:
            record(
                f"{prefix}.subtitle",
                _set_default(scenario.subtitle, "highlight_color", theme.accent),
            )
            record(f"{prefix}.subtitle", _set_default(scenario.subtitle, "font_family", theme.font))

        for step_idx, step in enumerate(getattr(scenario, "steps", []) or []):
            for fx_idx, effect in enumerate(getattr(step, "effects", []) or []):
                fx_prefix = f"{prefix}.steps[{step_idx}].effects[{fx_idx}]"
                for field in _theme_effect(effect, theme, glow_palette):
                    record(fx_prefix, field)

    subtitle = getattr(config, "subtitle", None)
    if subtitle is not None:
        record("subtitle", _set_default(subtitle, "highlight_color", theme.accent))
        record("subtitle", _set_default(subtitle, "font_family", theme.font))

    # The 3D device backdrop (demodsl-blender) is a core model, so it themes
    # here rather than in the plugin.
    device = getattr(config, "device_rendering", None)
    if device is not None:
        record("device_rendering", _set_default(device, "background_color", theme.surface))
        record(
            "device_rendering",
            _set_default(device, "background_gradient_color", theme.accent),
        )

    video = getattr(config, "video", None)
    if video is not None:
        for name in ("reviewer", "live_avatar", "progress_bar"):
            record(
                f"video.{name}", _set_default(getattr(video, name, None), "accent", theme.accent)
            )
        intro = getattr(video, "intro", None)
        if intro is not None:
            record("video.intro", _set_default(intro, "background_color", theme.surface))
            record(
                "video.intro",
                _set_default(intro, "font_color", readable_ink(theme.surface)),
            )
        reviewer = getattr(video, "reviewer", None)
        if reviewer is not None and theme.presenter.name:
            record("video.reviewer", _set_default(reviewer, "name", theme.presenter.name))
            if theme.presenter.title:
                record("video.reviewer", _set_default(reviewer, "title", theme.presenter.title))

    if applied:
        logger.debug("Theme applied to %d overlay field(s): %s", len(applied), applied)
    return applied


# ── Brand extraction ─────────────────────────────────────────────────────────

#: Collected in the page; returns the raw material :func:`extract_theme` needs.
PAGE_SAMPLE_JS = r"""
(() => {
  const body = getComputedStyle(document.body);
  const html = getComputedStyle(document.documentElement);
  const bg = (c) => (c && c !== 'rgba(0, 0, 0, 0)' ? c : null);
  const heading = document.querySelector('h1, h2');
  const buttons = Array.from(
    document.querySelectorAll('a[class*=btn], a[class*=button], button, [role=button]')
  ).slice(0, 40);
  const palette = {};
  for (const el of buttons) {
    const cs = getComputedStyle(el);
    const c = bg(cs.backgroundColor);
    if (!c) continue;
    const r = el.getBoundingClientRect();
    palette[c] = (palette[c] || 0) + Math.max(1, r.width * r.height);
  }
  const primary = buttons.find((el) => bg(getComputedStyle(el).backgroundColor));
  return {
    background: bg(body.backgroundColor) || bg(html.backgroundColor) || '#ffffff',
    text_color: body.color,
    heading_font: heading ? getComputedStyle(heading).fontFamily : body.fontFamily,
    cta: primary
      ? {
          background: getComputedStyle(primary).backgroundColor,
          color: getComputedStyle(primary).color,
          text: (primary.textContent || '').trim().slice(0, 60),
        }
      : null,
    palette: Object.entries(palette).map(([color, weight]) => ({ color, weight })),
  };
})()
"""


def _first_font(font_family: str | None) -> str | None:
    if not font_family:
        return None
    first = font_family.split(",")[0].strip().strip("'\"")
    return first or None


def extract_theme(sample: dict[str, Any]) -> dict[str, Any]:
    """Build a contrast-checked theme proposal from a page style *sample*.

    The proposal is never allowed to emit an accent that fails against the
    page background — the exact defect class the issue calls out. When the
    dominant brand colour is too weak, it is darkened/lightened towards a
    readable variant (hue preserved) and the adjustment is reported.
    """
    background = to_hex(sample.get("background") or "#FFFFFF") or "#FFFFFF"
    light = bool(is_light(background))

    candidates: Counter[str] = Counter()
    cta = sample.get("cta") or {}
    cta_bg = to_hex(cta.get("background")) if cta.get("background") else None
    for entry in sample.get("palette") or []:
        color = to_hex(entry.get("color"))
        parsed = parse_css_color(entry.get("color"))
        if not color or parsed is None or parsed[3] == 0:
            continue
        # Ignore neutrals: a grey button is chrome, not a brand colour.
        if _is_neutral(color):
            continue
        candidates[color] += int(entry.get("weight") or 1)

    accent_source = "cta"
    accent = cta_bg if cta_bg and not _is_neutral(cta_bg) else None
    if accent is None:
        accent_source = "palette"
        accent = candidates.most_common(1)[0][0] if candidates else None
    if accent is None:
        accent_source = "fallback"
        accent = "#6366F1"

    adjusted = adjust_for_contrast(accent, background, minimum=MIN_ACCENT_CONTRAST)
    accent_adjusted = adjusted.upper() != accent.upper()

    ink = to_hex(sample.get("text_color") or "") or readable_ink(background)
    if (contrast_ratio(ink, background) or 0) < 4.5:
        ink = readable_ink(background)

    theme = ThemeConfig(
        accent=adjusted,
        ink=ink,
        surface=background,
        mark_positive="#4ADE80" if not light else "#15803D",
        mark_negative="#F87171" if not light else "#B91C1C",
        font=_first_font(sample.get("heading_font")) or "Inter",
        subtitle={"style": "classic", "size": "lg" if light else "md"},
    )

    return {
        "theme": theme,
        "mode": "light" if light else "dark",
        "accent_source": accent_source,
        "accent_raw": accent,
        "accent_adjusted": accent_adjusted,
        "accent_contrast": round(contrast_ratio(adjusted, background) or 0.0, 2),
        "issues": theme.contrast_issues(background),
        "closest_preset": "light-consumer" if light else "dark-dev",
    }


def _is_neutral(color: str, *, saturation_threshold: float = 0.12) -> bool:
    """A near-grey/black/white colour carries no brand signal."""
    parsed = parse_css_color(color)
    if parsed is None:
        return True
    r, g, b = parsed[0], parsed[1], parsed[2]
    high, low = max(r, g, b), min(r, g, b)
    if high == 0:
        return True
    return (high - low) / high < saturation_threshold
