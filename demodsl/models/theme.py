"""First-class theme tokens (issue #27).

One place for the visual identity of a demo — accent, ink, surface, mark
colours, font, subtitle style and presenter persona — instead of a dozen
scattered colour fields spread across cursor / glow / subtitle / popup /
intro / progress-bar configs.

Contrast is a *validated property* of the theme: a theme whose ink is
unreadable on its own surface is rejected at parse time, and softer
problems (a low-contrast accent) are reported by
:meth:`ThemeConfig.contrast_issues`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from demodsl.color_utils import contrast_ratio, is_light
from demodsl.models._base import _StrictBase, _validate_css_color

__all__ = [
    "SubtitleTheme",
    "PresenterTheme",
    "ThemeConfig",
    "THEME_PRESETS",
    "MIN_INK_CONTRAST",
    "MIN_ACCENT_CONTRAST",
]

#: Below this, body text on the theme surface is simply unreadable — a hard error.
MIN_INK_CONTRAST = 3.0
#: WCAG AA for large text / UI components — a warning, not an error.
MIN_ACCENT_CONTRAST = 3.0


class SubtitleTheme(_StrictBase):
    style: Literal["classic", "karaoke", "boxed", "minimal"] = "classic"
    size: Literal["sm", "md", "lg", "xl"] = "md"


class PresenterTheme(_StrictBase):
    """Who the viewer is listening to."""

    name: str | None = None
    title: str | None = None
    tone: str | None = Field(
        default=None,
        description="Narration register, e.g. 'analytical', 'warm', 'punchy'.",
    )


class ThemeConfig(_StrictBase):
    """Visual identity tokens referenced by every overlay."""

    accent: str = "#6366F1"
    ink: str = "#101418"
    surface: str = "#FFFFFFEE"
    mark_positive: str = "#16A34A"
    mark_negative: str = "#DC2626"
    font: str = "Inter"
    subtitle: SubtitleTheme = Field(default_factory=SubtitleTheme)
    presenter: PresenterTheme = Field(default_factory=PresenterTheme)

    @field_validator("accent", "ink", "surface", "mark_positive", "mark_negative")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        return _validate_css_color(v)

    @model_validator(mode="after")
    def _ink_must_be_readable(self) -> ThemeConfig:
        ratio = contrast_ratio(self.ink, self.surface)
        if ratio is not None and ratio < MIN_INK_CONTRAST:
            raise ValueError(
                f"theme.ink {self.ink!r} is unreadable on theme.surface "
                f"{self.surface!r} (contrast {ratio:.1f}:1, minimum "
                f"{MIN_INK_CONTRAST}:1). Pick a darker ink or a lighter surface."
            )
        return self

    # ── Introspection ─────────────────────────────────────────────────────

    def contrast_issues(self, background: str | None = None) -> list[dict[str, Any]]:
        """Report tokens that read poorly against *background* (default: surface).

        Returns a list of ``{token, against, ratio, minimum}`` dicts —
        empty when the theme is clean. Fed into the QA report (issue #24)
        and into ``demodsl theme`` so extraction never proposes an accent
        that fails on the page it was extracted from.
        """
        bg = background or self.surface
        issues: list[dict[str, Any]] = []
        for token in ("accent", "mark_positive", "mark_negative", "ink"):
            value = getattr(self, token)
            ratio = contrast_ratio(value, bg)
            if ratio is None:
                continue
            minimum = MIN_INK_CONTRAST if token == "ink" else MIN_ACCENT_CONTRAST
            if ratio < minimum:
                issues.append(
                    {
                        "token": token,
                        "color": value,
                        "against": bg,
                        "ratio": round(ratio, 2),
                        "minimum": minimum,
                    }
                )
        return issues

    @property
    def is_light(self) -> bool:
        """Whether the theme surface reads as light."""
        return bool(is_light(self.surface))


#: Named presets so a batch can pick a look per site (``theme: dark-dev``).
THEME_PRESETS: dict[str, dict[str, Any]] = {
    "dark-dev": {
        "accent": "#6366F1",
        "ink": "#E6E8EB",
        "surface": "#0B0E14",
        "mark_positive": "#4ADE80",
        "mark_negative": "#F87171",
        "font": "Inter",
        "subtitle": {"style": "minimal", "size": "md"},
    },
    "light-consumer": {
        "accent": "#FF5A1F",
        "ink": "#101418",
        "surface": "#FFFFFF",
        "mark_positive": "#15803D",
        "mark_negative": "#B91C1C",
        "font": "Inter",
        "subtitle": {"style": "classic", "size": "lg"},
    },
    "neutral": {
        "accent": "#2563EB",
        "ink": "#111827",
        "surface": "#F8FAFC",
        "mark_positive": "#16A34A",
        "mark_negative": "#DC2626",
        "font": "Inter",
        "subtitle": {"style": "classic", "size": "md"},
    },
}
