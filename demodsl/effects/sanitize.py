"""Input sanitization for browser effect parameters injected into JS/CSS/HTML."""

from __future__ import annotations

import re

# CSS color names (subset — most common)
_CSS_COLOR_NAMES = frozenset({
    "aliceblue", "antiquewhite", "aqua", "aquamarine", "azure", "beige",
    "bisque", "black", "blanchedalmond", "blue", "blueviolet", "brown",
    "burlywood", "cadetblue", "chartreuse", "chocolate", "coral",
    "cornflowerblue", "cornsilk", "crimson", "cyan", "darkblue", "darkcyan",
    "darkgoldenrod", "darkgray", "darkgreen", "darkkhaki", "darkmagenta",
    "darkolivegreen", "darkorange", "darkorchid", "darkred", "darksalmon",
    "darkseagreen", "darkslateblue", "darkslategray", "darkturquoise",
    "darkviolet", "deeppink", "deepskyblue", "dimgray", "dodgerblue",
    "firebrick", "floralwhite", "forestgreen", "fuchsia", "gainsboro",
    "ghostwhite", "gold", "goldenrod", "gray", "green", "greenyellow",
    "honeydew", "hotpink", "indianred", "indigo", "ivory", "khaki",
    "lavender", "lavenderblush", "lawngreen", "lemonchiffon", "lightblue",
    "lightcoral", "lightcyan", "lightgoldenrodyellow", "lightgray",
    "lightgreen", "lightpink", "lightsalmon", "lightseagreen",
    "lightskyblue", "lightslategray", "lightsteelblue", "lightyellow",
    "lime", "limegreen", "linen", "magenta", "maroon", "mediumaquamarine",
    "mediumblue", "mediumorchid", "mediumpurple", "mediumseagreen",
    "mediumslateblue", "mediumspringgreen", "mediumturquoise",
    "mediumvioletred", "midnightblue", "mintcream", "mistyrose",
    "moccasin", "navajowhite", "navy", "oldlace", "olive", "olivedrab",
    "orange", "orangered", "orchid", "palegoldenrod", "palegreen",
    "paleturquoise", "palevioletred", "papayawhip", "peachpuff", "peru",
    "pink", "plum", "powderblue", "purple", "rebeccapurple", "red",
    "rosybrown", "royalblue", "saddlebrown", "salmon", "sandybrown",
    "seagreen", "seashell", "sienna", "silver", "skyblue", "slateblue",
    "slategray", "snow", "springgreen", "steelblue", "tan", "teal",
    "thistle", "tomato", "turquoise", "violet", "wheat", "white",
    "whitesmoke", "yellow", "yellowgreen", "transparent", "inherit",
    "currentcolor",
})

# Patterns for valid CSS color values
_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_RGB_RGBA = re.compile(
    r"^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*[\d.]+\s*)?\)$"
)
_HSL_HSLA = re.compile(
    r"^hsla?\(\s*\d{1,3}\s*,\s*\d{1,3}%\s*,\s*\d{1,3}%\s*(?:,\s*[\d.]+\s*)?\)$"
)


def sanitize_css_color(value: str) -> str:
    """Validate and return a safe CSS color value.

    Accepts: hex (#fff, #aabbcc, #aabbccdd), rgb/rgba, hsl/hsla, named colors.
    Rejects anything else and falls back to a safe default.
    """
    stripped = value.strip()
    if stripped.lower() in _CSS_COLOR_NAMES:
        return stripped
    if _HEX_COLOR.match(stripped):
        return stripped
    if _RGB_RGBA.match(stripped):
        return stripped
    if _HSL_HSLA.match(stripped):
        return stripped
    # Reject — return safe fallback
    return "#888888"


def sanitize_number(value: float | int | str, *, default: float = 0.0,
                    min_val: float | None = None, max_val: float | None = None) -> float:
    """Ensure a value is a safe number within optional bounds."""
    try:
        num = float(value)
    except (ValueError, TypeError):
        return default
    if min_val is not None:
        num = max(min_val, num)
    if max_val is not None:
        num = min(max_val, num)
    return num


def sanitize_html_text(value: str) -> str:
    """Escape text for safe insertion into HTML/SVG content."""
    return (
        value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def sanitize_js_string(value: str) -> str:
    """Escape text for safe insertion into a JS single-quoted string literal."""
    return (
        value
        .replace("\0", "")             # strip null bytes
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("`", "\\`")
        .replace("${", "\\${")
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")  # JS line separator
        .replace("\u2029", "\\u2029")  # JS paragraph separator
    )


def sanitize_css_position(value: str, *, allowed: frozenset[str] | None = None) -> str:
    """Validate a CSS position keyword against an allowed set."""
    default_positions = frozenset({
        "top", "bottom", "left", "right", "center",
        "top-left", "top-right", "bottom-left", "bottom-right",
        "top-center", "bottom-center",
    })
    valid = allowed or default_positions
    if value in valid:
        return value
    return next(iter(valid))


def sanitize_css_colors_list(values: list[str]) -> list[str]:
    """Sanitize a list of CSS colors."""
    return [sanitize_css_color(c) for c in values]
