"""Keyboard geometry — which key a finger actually hits when it misses.

A random letter substitution reads as data corruption; a *neighbouring* key
reads as a human hand. The tables below are physical adjacency (same row ±1,
row above/below), which is what makes the correction that follows believable.
"""

from __future__ import annotations

from typing import Any

__all__ = ["neighbour_key", "bigram_factor", "hand_and_finger", "LAYOUTS"]

_QWERTY_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
_AZERTY_ROWS = ("azertyuiop", "qsdfghjklm", "wxcvbn")


def _build(rows: tuple[str, ...]) -> dict[str, str]:
    table: dict[str, str] = {}
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            near: list[str] = []
            if c > 0:
                near.append(row[c - 1])
            if c + 1 < len(row):
                near.append(row[c + 1])
            for other in (r - 1, r + 1):
                if 0 <= other < len(rows):
                    orow = rows[other]
                    for oc in (c - 1, c, c + 1):
                        if 0 <= oc < len(orow):
                            near.append(orow[oc])
            table[ch] = "".join(dict.fromkeys(near))
    return table


LAYOUTS: dict[str, dict[str, str]] = {
    "qwerty": _build(_QWERTY_ROWS),
    "azerty": _build(_AZERTY_ROWS),
}

_ROWS: dict[str, tuple[str, ...]] = {"qwerty": _QWERTY_ROWS, "azerty": _AZERTY_ROWS}

#: Column index (within its row) at which the right hand takes over.
_HAND_SPLIT = {"qwerty": (5, 4, 3), "azerty": (5, 4, 2)}


def _key_position(char: str, layout: str) -> tuple[int, int] | None:
    for r, row in enumerate(_ROWS.get(layout, _QWERTY_ROWS)):
        c = row.find(char.lower())
        if c >= 0:
            return r, c
    return None


def hand_and_finger(char: str, layout: str = "qwerty") -> tuple[str, int] | None:
    """Which hand types *char*, and roughly which finger. ``None`` if unknown."""
    pos = _key_position(char, layout)
    if pos is None:
        return None
    row, col = pos
    split = _HAND_SPLIT.get(layout, _HAND_SPLIT["qwerty"])[row]
    hand = "L" if col < split else "R"
    # Index fingers cover two columns; beyond that one column each.
    offset = col if hand == "L" else col - split
    return hand, min(3, offset if hand == "L" else 3 - min(offset, 3))


def bigram_factor(prev: str, char: str, layout: str = "qwerty") -> float:
    """Relative cost of typing *char* right after *prev*.

    Alternating hands is the fast case; repeating the same finger is the slow
    one. This is what gives typed text an uneven pulse instead of a metronome.
    """
    a = hand_and_finger(prev, layout)
    b = hand_and_finger(char, layout)
    if a is None or b is None:
        return 1.0
    if a[0] != b[0]:
        return 0.82
    if a[1] == b[1]:
        return 1.5
    return 1.0


def neighbour_key(char: str, rng: Any, *, layout: str = "qwerty") -> str | None:
    """A physically adjacent key to *char*, preserving case. ``None`` if unknown."""
    table = LAYOUTS.get(layout, LAYOUTS["qwerty"])
    near = table.get(char.lower())
    if not near:
        return None
    pick = rng.choice(near)
    return pick.upper() if char.isupper() else pick
