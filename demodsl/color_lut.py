"""Parser and validator for Adobe/DaVinci Resolve-style ``.cube`` 3D LUT files.

ffmpeg's own ``lut3d`` filter already applies a ``.cube`` file correctly
(trilinear interpolation, no resampling needed on our side) — this module
only parses and validates the file up front so a malformed LUT fails with a
clear ``demodsl``-native error instead of an opaque ffmpeg stderr dump.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class CubeLutError(ValueError):
    """Raised when a ``.cube`` LUT file is malformed or unsupported."""


@dataclass(frozen=True)
class CubeLut:
    """A parsed 3D LUT: a ``size``x``size``x``size`` cube of RGB -> RGB triples."""

    size: int
    domain_min: tuple[float, float, float]
    domain_max: tuple[float, float, float]
    title: str | None
    entries: tuple[tuple[float, float, float], ...]


def _parse_domain_line(line: str, lineno: int) -> tuple[float, float, float]:
    parts = line.split()
    if len(parts) != 4:
        raise CubeLutError(f"Malformed domain line {lineno}: {line!r}")
    try:
        return (float(parts[1]), float(parts[2]), float(parts[3]))
    except ValueError as exc:
        raise CubeLutError(f"Non-numeric domain line {lineno}: {line!r}") from exc


def parse_cube_lut(text: str) -> CubeLut:
    """Parse the text contents of a ``.cube`` file.

    Raises :class:`CubeLutError` on anything that would make ffmpeg's
    ``lut3d`` filter either reject the file or silently misbehave.
    """
    size: int | None = None
    domain_min = (0.0, 0.0, 0.0)
    domain_max = (1.0, 1.0, 1.0)
    title: str | None = None
    entries: list[tuple[float, float, float]] = []

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        upper = line.upper()

        if upper.startswith("TITLE"):
            rest = line.split(None, 1)
            title = rest[1].strip().strip('"') if len(rest) > 1 else None
            continue
        if upper.startswith("LUT_1D_SIZE"):
            raise CubeLutError(
                "1D LUTs (LUT_1D_SIZE) are not supported — only 3D .cube LUTs "
                "(LUT_3D_SIZE) can be applied via ffmpeg's lut3d filter."
            )
        if upper.startswith("LUT_3D_SIZE"):
            parts = line.split()
            if len(parts) != 2:
                raise CubeLutError(f"Malformed LUT_3D_SIZE on line {lineno}: {line!r}")
            try:
                size = int(parts[1])
            except ValueError as exc:
                raise CubeLutError(f"Malformed LUT_3D_SIZE on line {lineno}: {line!r}") from exc
            if not (2 <= size <= 256):
                raise CubeLutError(f"LUT_3D_SIZE must be between 2 and 256, got {size}.")
            continue
        if upper.startswith("DOMAIN_MIN"):
            domain_min = _parse_domain_line(line, lineno)
            continue
        if upper.startswith("DOMAIN_MAX"):
            domain_max = _parse_domain_line(line, lineno)
            continue

        # Anything else must be a data row: three floats (R G B).
        parts = line.split()
        if len(parts) != 3:
            raise CubeLutError(f"Malformed data row on line {lineno}: {line!r}")
        try:
            r, g, b = (float(p) for p in parts)
        except ValueError as exc:
            raise CubeLutError(f"Non-numeric data row on line {lineno}: {line!r}") from exc
        entries.append((r, g, b))

    if size is None:
        raise CubeLutError("Missing LUT_3D_SIZE header — not a valid 3D .cube LUT.")
    expected = size**3
    if len(entries) != expected:
        raise CubeLutError(
            f"Expected {expected} data rows for a {size}x{size}x{size} LUT, got {len(entries)}."
        )
    return CubeLut(
        size=size,
        domain_min=domain_min,
        domain_max=domain_max,
        title=title,
        entries=tuple(entries),
    )


def load_cube_lut(path: str | Path) -> CubeLut:
    """Parse a ``.cube`` file from disk. Raises :class:`CubeLutError`."""
    p = Path(path)
    if not p.exists():
        raise CubeLutError(f"LUT file not found: {p}")
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise CubeLutError(f"Could not read LUT file {p}: {exc}") from exc
    return parse_cube_lut(text)


def escape_ffmpeg_filter_path(path: str) -> str:
    """Escape a filesystem path for embedding inside an ffmpeg filtergraph string.

    The result is meant to be wrapped in single quotes, e.g.
    ``f"lut3d=file='{escape_ffmpeg_filter_path(path)}'"``.
    """
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
