"""Font resolution + colour helpers (pure, LRU-cached)."""

from __future__ import annotations

import re
from functools import lru_cache

from PIL import ImageFont

# Color-emoji font candidates (macOS / Linux).
# Apple Color Emoji only renders at a fixed set of pixel sizes — we always
# rasterize at the largest available size and let the caller scale down.
_EMOJI_FONT_CANDIDATES: tuple[str, ...] = (
    "/System/Library/Fonts/Apple Color Emoji.ttc",
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
    "NotoColorEmoji.ttf",
    "seguiemj.ttf",  # Windows
)
# Sizes Apple Color Emoji accepts via Pillow's FreeType binding.
EMOJI_RENDER_SIZE: int = 160

# Match any character outside the BMP (most emojis live in U+1F000+) plus a
# few BMP symbols commonly treated as emoji (♥ ★ ✨ ✦ ✓ ▲ …) that *do* render
# in regular sans-serif fonts — we only want to switch fonts when the glyph
# is genuinely missing, so this regex targets only the high-range codepoints.
_EMOJI_RE = re.compile(r"[\U0001F000-\U0001FFFF\U0001E000-\U0001EFFF\U00002600-\U000027BF\uFE0F]")


def contains_emoji(text: str) -> bool:
    """Return True if ``text`` contains at least one likely-emoji codepoint."""
    if not text:
        return False
    return bool(_EMOJI_RE.search(text))


@lru_cache(maxsize=8)
def load_emoji_font() -> ImageFont.FreeTypeFont | None:
    """Load a color-emoji-capable font, or ``None`` if none are available."""
    for cand in _EMOJI_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(cand, size=EMOJI_RENDER_SIZE)
        except OSError:
            continue
    return None


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
