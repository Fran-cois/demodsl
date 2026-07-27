"""Color parsing and WCAG contrast helpers.

Shared by the theme system (issue #27) and the post-render QA report
(issue #24), which both need to answer the same question: *is this
overlay colour readable on that background?*

Everything here is pure and dependency-free so it can be unit-tested
without a browser or a render.
"""

from __future__ import annotations

import re

__all__ = [
    "RGBA",
    "parse_css_color",
    "blend_over",
    "relative_luminance",
    "contrast_ratio",
    "is_light",
    "readable_ink",
    "adjust_for_contrast",
    "mix",
    "to_hex",
]

RGBA = tuple[float, float, float, float]

_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3,8})$")
_FUNC_RE = re.compile(r"^(rgba?|hsla?)\(([^)]*)\)$")

# Minimal named-colour table: the ones that realistically show up in a
# theme or in an extracted page palette. Unknown names return None rather
# than guessing.
_NAMED: dict[str, tuple[int, int, int]] = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "lime": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "aqua": (0, 255, 255),
    "magenta": (255, 0, 255),
    "fuchsia": (255, 0, 255),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "silver": (192, 192, 192),
    "maroon": (128, 0, 0),
    "olive": (128, 128, 0),
    "navy": (0, 0, 128),
    "teal": (0, 128, 128),
    "purple": (128, 0, 128),
    "orange": (255, 165, 0),
    "pink": (255, 192, 203),
    "indigo": (75, 0, 130),
    "transparent": (0, 0, 0),
}


def _hsl_to_rgb(h: float, s: float, lightness: float) -> tuple[float, float, float]:
    """Convert HSL (h in degrees, s/l in 0..1) to RGB in 0..255."""
    c = (1 - abs(2 * lightness - 1)) * s
    hp = (h % 360) / 60.0
    x = c * (1 - abs(hp % 2 - 1))
    if hp < 1:
        rgb = (c, x, 0.0)
    elif hp < 2:
        rgb = (x, c, 0.0)
    elif hp < 3:
        rgb = (0.0, c, x)
    elif hp < 4:
        rgb = (0.0, x, c)
    elif hp < 5:
        rgb = (x, 0.0, c)
    else:
        rgb = (c, 0.0, x)
    m = lightness - c / 2
    return tuple((v + m) * 255 for v in rgb)  # type: ignore[return-value]


def parse_css_color(value: str | None) -> RGBA | None:
    """Parse a CSS colour into ``(r, g, b, a)`` with r/g/b in 0..255.

    Returns ``None`` for anything that cannot be resolved to a concrete
    colour (``inherit``, ``currentColor``, gradients, unknown names).
    """
    if not value or not isinstance(value, str):
        return None
    raw = value.strip().lower()
    if raw in ("inherit", "currentcolor", "none", "unset", "initial"):
        return None
    if raw == "transparent":
        return (0.0, 0.0, 0.0, 0.0)

    named = _NAMED.get(raw)
    if named is not None:
        return (float(named[0]), float(named[1]), float(named[2]), 1.0)

    hex_match = _HEX_RE.match(raw)
    if hex_match:
        digits = hex_match.group(1)
        if len(digits) in (3, 4):
            digits = "".join(ch * 2 for ch in digits)
        if len(digits) not in (6, 8):
            return None
        r = int(digits[0:2], 16)
        g = int(digits[2:4], 16)
        b = int(digits[4:6], 16)
        a = int(digits[6:8], 16) / 255.0 if len(digits) == 8 else 1.0
        return (float(r), float(g), float(b), a)

    func = _FUNC_RE.match(raw)
    if func:
        kind = func.group(1)
        parts = [p.strip() for p in re.split(r"[,\s/]+", func.group(2)) if p.strip()]
        if len(parts) < 3:
            return None
        try:
            alpha = 1.0
            if len(parts) >= 4:
                alpha = float(parts[3].rstrip("%"))
                if parts[3].endswith("%"):
                    alpha /= 100.0
            if kind.startswith("rgb"):
                channels = []
                for p in parts[:3]:
                    channels.append(
                        float(p.rstrip("%")) * 255 / 100 if p.endswith("%") else float(p)
                    )
                return (channels[0], channels[1], channels[2], max(0.0, min(1.0, alpha)))
            h = float(parts[0].rstrip("deg"))
            s = float(parts[1].rstrip("%")) / 100.0
            lightness = float(parts[2].rstrip("%")) / 100.0
            r, g, b = _hsl_to_rgb(h, s, lightness)
            return (r, g, b, max(0.0, min(1.0, alpha)))
        except ValueError:
            return None
    return None


def blend_over(fg: RGBA, bg: RGBA) -> RGBA:
    """Alpha-composite *fg* over an opaque-ish *bg*."""
    a = fg[3]
    if a >= 1.0:
        return fg
    return (
        fg[0] * a + bg[0] * (1 - a),
        fg[1] * a + bg[1] * (1 - a),
        fg[2] * a + bg[2] * (1 - a),
        1.0,
    )


def relative_luminance(color: RGBA) -> float:
    """WCAG 2.1 relative luminance of an opaque colour."""

    def channel(v: float) -> float:
        c = max(0.0, min(1.0, v / 255.0))
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = channel(color[0]), channel(color[1]), channel(color[2])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground: str | RGBA, background: str | RGBA) -> float | None:
    """WCAG contrast ratio between two colours (1.0 … 21.0).

    Semi-transparent foregrounds are composited over the background
    first, which is what actually happens on screen. Returns ``None``
    when either colour cannot be parsed.
    """
    fg = parse_css_color(foreground) if isinstance(foreground, str) else foreground
    bg = parse_css_color(background) if isinstance(background, str) else background
    if fg is None or bg is None:
        return None
    bg_opaque = blend_over(bg, (255.0, 255.0, 255.0, 1.0)) if bg[3] < 1.0 else bg
    fg_opaque = blend_over(fg, bg_opaque)
    l1 = relative_luminance(fg_opaque)
    l2 = relative_luminance(bg_opaque)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def is_light(color: str | RGBA) -> bool | None:
    """Whether *color* reads as a light surface (luminance > 0.5)."""
    parsed = parse_css_color(color) if isinstance(color, str) else color
    if parsed is None:
        return None
    return relative_luminance(blend_over(parsed, (255.0, 255.0, 255.0, 1.0))) > 0.5


def readable_ink(background: str | RGBA, *, dark: str = "#101418", light: str = "#FFFFFF") -> str:
    """Pick the ink colour with the better contrast against *background*."""
    dark_ratio = contrast_ratio(dark, background) or 0.0
    light_ratio = contrast_ratio(light, background) or 0.0
    return dark if dark_ratio >= light_ratio else light


def adjust_for_contrast(
    color: str,
    background: str,
    *,
    minimum: float = 4.5,
    steps: int = 24,
) -> str:
    """Darken or lighten *color* until it clears *minimum* against *background*.

    Returns a ``#rrggbb`` string. The hue is preserved (channels are
    scaled towards black or white), so an extracted brand colour stays
    recognisable instead of being replaced by a generic accent.
    """
    fg = parse_css_color(color)
    bg = parse_css_color(background)
    if fg is None or bg is None:
        return color
    current = contrast_ratio(fg, bg)
    if current is not None and current >= minimum:
        return _to_hex(fg)

    bg_opaque = blend_over(bg, (255.0, 255.0, 255.0, 1.0))
    towards_white = relative_luminance(bg_opaque) <= 0.5
    best = fg
    for i in range(1, steps + 1):
        t = i / steps
        if towards_white:
            candidate = (
                fg[0] + (255 - fg[0]) * t,
                fg[1] + (255 - fg[1]) * t,
                fg[2] + (255 - fg[2]) * t,
                1.0,
            )
        else:
            candidate = (fg[0] * (1 - t), fg[1] * (1 - t), fg[2] * (1 - t), 1.0)
        best = candidate
        ratio = contrast_ratio(candidate, bg)
        if ratio is not None and ratio >= minimum:
            break
    return _to_hex(best)


def _to_hex(color: RGBA) -> str:
    r, g, b = (int(round(max(0.0, min(255.0, c)))) for c in color[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


def to_hex(color: str | RGBA) -> str | None:
    """Normalise any parsable colour to ``#RRGGBB``."""
    parsed = parse_css_color(color) if isinstance(color, str) else color
    return None if parsed is None else _to_hex(parsed)


def mix(color_a: str, color_b: str, t: float = 0.5) -> str:
    """Linear blend of two colours; ``t=0`` returns *color_a*, ``t=1`` *color_b*."""
    a = parse_css_color(color_a)
    b = parse_css_color(color_b)
    if a is None or b is None:
        return color_a
    t = max(0.0, min(1.0, t))
    return _to_hex(
        (
            a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t,
            1.0,
        )
    )
