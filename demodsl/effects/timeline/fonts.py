"""Font resolution + colour helpers (pure, LRU-cached)."""

from __future__ import annotations

from functools import lru_cache

from PIL import ImageFont


def _font_candidates(family: str, weight: str) -> list[str]:
    is_bold = weight in ("bold", "black")
    # macOS / Linux common system fonts. Pillow accepts both file paths and
    # PostScript names on macOS when freetype is available.
    bold_suffix = "-Bold" if is_bold else "-Regular"
    return [
        # User-requested family first
        f"{family}{bold_suffix}.ttf",
        f"{family}.ttf",
        # Common inter-platform fallbacks
        "Inter-Bold.ttf" if is_bold else "Inter-Regular.ttf",
        "Helvetica.ttc",
        "Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]


def _load_font(family: str, weight: str, size: int) -> ImageFont.FreeTypeFont:
    return _load_font_cached(family, weight, size)


@lru_cache(maxsize=128)
def _load_font_cached(family: str, weight: str, size: int) -> ImageFont.FreeTypeFont:
    for cand in _font_candidates(family, weight):
        try:
            return ImageFont.truetype(cand, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _hex_to_rgba(hex_color: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(255 * opacity)
        return r, g, b, a
    if len(h) == 8:
        r, g, b, a = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
        return r, g, b, int(a * opacity)
    # Fallback: white
    return 255, 255, 255, int(255 * opacity)
