"""Emotion signal + self-contained avatar for persona discovery runs.

A persona run already reports *effort*, *frustration* and designer findings.
This module adds the fast, human-readable layer on top: a single predicted
**emotion** (with emoji, valence and a mood colour) and a small **SVG avatar**
that draws that emotion as an expressive face.

The point is to give a web dev / designer an at-a-glance UX sentiment indicator:
a green smiling face next to a flow means "this profile sailed through"; a red
scowl means "this profile rage-quit here". The avatar is pure inline SVG (no
asset files, no API), so it drops straight into a report, a dashboard cell, or a
PR comment.

This module is deliberately free of any :mod:`demodsl.discover.persona`
dependency so it can be reused on its own; :func:`predict_emotion` (which needs
the persona/state types) lives in ``persona.py`` and maps a run onto one of the
:data:`EMOTIONS` below.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Emotion",
    "EMOTIONS",
    "emotion_avatar_svg",
]


@dataclass(frozen=True)
class Emotion:
    """A predicted affective state plus its visual identity.

    * ``key``      — stable identifier (e.g. ``"frustrated"``).
    * ``emoji``    — one-glyph summary, handy for plain-text logs.
    * ``valence``  — ``"positive" | "neutral" | "negative"`` (the coarse signal).
    * ``color``    — mood hex, for badges, borders or the avatar background.
    * ``labels``   — localised human label (``fr`` / ``en``).
    """

    key: str
    emoji: str
    valence: str
    color: str
    labels: dict[str, str]

    def label(self, lang: str = "en") -> str:
        return self.labels.get(lang, self.labels["en"])

    def avatar_svg(self, *, size: int = 96) -> str:
        """Return an inline SVG avatar drawing this emotion as a face."""
        return emotion_avatar_svg(self, size=size)


# Ordered roughly best → worst; each carries its own colour + emoji + labels.
EMOTIONS: dict[str, Emotion] = {
    "delighted": Emotion(
        "delighted",
        "😄",
        "positive",
        "#16a34a",
        {"fr": "ravie", "en": "delighted"},
    ),
    "satisfied": Emotion(
        "satisfied",
        "🙂",
        "positive",
        "#65a30d",
        {"fr": "satisfaite", "en": "satisfied"},
    ),
    "relieved": Emotion(
        "relieved",
        "😅",
        "positive",
        "#0891b2",
        {"fr": "soulagée (mais ça a coûté)", "en": "relieved (it was work)"},
    ),
    "curious": Emotion(
        "curious",
        "🤔",
        "neutral",
        "#2563eb",
        {"fr": "curieuse / intriguée", "en": "curious"},
    ),
    "bored": Emotion(
        "bored",
        "😐",
        "neutral",
        "#9ca3af",
        {"fr": "lassée", "en": "bored"},
    ),
    "confused": Emotion(
        "confused",
        "😕",
        "negative",
        "#d97706",
        {"fr": "perdue", "en": "confused"},
    ),
    "frustrated": Emotion(
        "frustrated",
        "😣",
        "negative",
        "#ea580c",
        {"fr": "frustrée", "en": "frustrated"},
    ),
    "disappointed": Emotion(
        "disappointed",
        "😞",
        "negative",
        "#7c3aed",
        {"fr": "déçue (a vraiment essayé)", "en": "disappointed (really tried)"},
    ),
    "angry": Emotion(
        "angry",
        "😠",
        "negative",
        "#dc2626",
        {"fr": "remontée / excédée", "en": "angry"},
    ),
}


# Per-emotion face geometry. ``mouth`` curvature: + smile / − frown. ``brow``
# inner-end vertical shift: + lowers the inner brow (anger) / − raises it (worry).
_FACE: dict[str, dict[str, object]] = {
    "delighted": {"mouth": 13, "open": True, "brow": -2, "eye": "happy"},
    "satisfied": {"mouth": 8, "open": False, "brow": -1, "eye": "open"},
    "relieved": {"mouth": 6, "open": False, "brow": -3, "eye": "squint", "sweat": True},
    "curious": {"mouth": 3, "open": False, "brow": -5, "eye": "open", "qmark": True},
    "bored": {"mouth": 0, "open": False, "brow": 1, "eye": "squint"},
    "confused": {"mouth": -3, "open": False, "brow": -4, "eye": "open", "qmark": True},
    "frustrated": {"mouth": -7, "open": False, "brow": 6, "eye": "squint", "teeth": True},
    "disappointed": {"mouth": -9, "open": False, "brow": -6, "eye": "open"},
    "angry": {"mouth": -8, "open": True, "brow": 8, "eye": "narrow", "teeth": True},
}

_INK = "#1f2937"
_SKIN = "#ffe0bd"


def _eyes(style: str, lx: int, rx: int, ey: int) -> list[str]:
    out: list[str] = []
    if style == "happy":
        for ex in (lx, rx):
            out.append(
                f'<path d="M{ex - 6},{ey + 1} Q{ex},{ey - 7} {ex + 6},{ey + 1}" '
                f'fill="none" stroke="{_INK}" stroke-width="3" stroke-linecap="round"/>'
            )
    elif style == "squint":
        for ex in (lx, rx):
            out.append(
                f'<line x1="{ex - 6}" y1="{ey}" x2="{ex + 6}" y2="{ey}" '
                f'stroke="{_INK}" stroke-width="3.2" stroke-linecap="round"/>'
            )
    elif style == "narrow":
        for ex in (lx, rx):
            out.append(
                f'<ellipse cx="{ex}" cy="{ey}" rx="6.5" ry="3" fill="#fff" '
                f'stroke="{_INK}" stroke-width="1.5"/>'
            )
            out.append(f'<circle cx="{ex}" cy="{ey}" r="2.6" fill="{_INK}"/>')
    else:  # "open"
        for ex in (lx, rx):
            out.append(
                f'<circle cx="{ex}" cy="{ey}" r="6" fill="#fff" '
                f'stroke="{_INK}" stroke-width="1.5"/>'
            )
            out.append(f'<circle cx="{ex}" cy="{ey + 1}" r="3.1" fill="{_INK}"/>')
    return out


def _mouth(face: dict[str, object], cx: int, my: int) -> list[str]:
    out: list[str] = []
    mouth = float(face["mouth"])  # type: ignore[arg-type]
    if face.get("open") and mouth >= 0:  # open grin
        out.append(
            f'<path d="M{cx - 12},{my - 1} Q{cx},{my + 13} {cx + 12},{my - 1} Z" fill="#7a2b34"/>'
        )
        out.append(
            f'<path d="M{cx - 9},{my} Q{cx},{my + 2} {cx + 9},{my} '
            f'L{cx + 8},{my - 2} Q{cx},{my - 1} {cx - 8},{my - 2} Z" fill="#fff"/>'
        )
    elif face.get("open"):  # open shout
        out.append(f'<ellipse cx="{cx}" cy="{my + 1}" rx="9" ry="7" fill="#7a2b34"/>')
    else:  # closed curve
        out.append(
            f'<path d="M{cx - 12},{my} Q{cx},{my + mouth} {cx + 12},{my}" '
            f'fill="none" stroke="{_INK}" stroke-width="3.4" stroke-linecap="round"/>'
        )
    if face.get("teeth"):
        for tx in (cx - 6, cx, cx + 6):
            out.append(
                f'<line x1="{tx}" y1="{my - 3}" x2="{tx}" y2="{my + 3}" '
                f'stroke="{_INK}" stroke-width="1.4"/>'
            )
    return out


def emotion_avatar_svg(emotion: Emotion, *, size: int = 96) -> str:
    """Render *emotion* as a small, self-contained SVG face (inline string).

    The face is parametric (brows, eyes and mouth driven by :data:`_FACE`) and
    tinted with the emotion's mood colour, so each emotion is visually distinct
    at a glance — a drop-in UX sentiment badge.
    """
    face = _FACE.get(emotion.key, _FACE["satisfied"])
    mood = emotion.color
    cx, cy, r = 50, 52, 33
    lx, rx, ey = 39, 61, 47
    by = ey - 12  # brow baseline
    my = 68  # mouth centre
    brow = float(face["brow"])  # type: ignore[arg-type]
    parts: list[str] = [
        f'<rect x="2" y="2" width="96" height="96" rx="18" fill="{mood}" fill-opacity="0.12"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{_SKIN}" stroke="{mood}" stroke-width="3"/>',
    ]
    parts += _eyes(str(face["eye"]), lx, rx, ey)
    # eyebrows: outer ends fixed, inner ends shifted by ``brow``.
    parts.append(
        f'<line x1="{lx - 7}" y1="{by}" x2="{lx + 6}" y2="{by + brow}" '
        f'stroke="{_INK}" stroke-width="3" stroke-linecap="round"/>'
    )
    parts.append(
        f'<line x1="{rx - 6}" y1="{by + brow}" x2="{rx + 7}" y2="{by}" '
        f'stroke="{_INK}" stroke-width="3" stroke-linecap="round"/>'
    )
    parts += _mouth(face, cx, my)
    if face.get("sweat"):
        parts.append(
            f'<path d="M{rx + 12},{ey - 7} q4.5,7 0,9.5 q-4.5,-2.5 0,-9.5 Z" '
            f'fill="#38bdf8" stroke="#0284c7" stroke-width="0.8"/>'
        )
    if face.get("qmark"):
        parts.append(
            f'<text x="{rx + 11}" y="{by + 4}" font-size="15" font-family="sans-serif" '
            f'font-weight="700" fill="{mood}">?</text>'
        )
    label = emotion.label("en")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 100 100" role="img" aria-label="{label}">' + "".join(parts) + "</svg>"
    )
