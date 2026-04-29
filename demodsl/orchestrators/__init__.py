"""Orchestrator sub-modules extracted from DemoEngine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RecordingResult:
    """Immutable result of scenario recording, replaces mutable state."""

    raw_videos: list[Path] = field(default_factory=list)
    step_timestamps: list[float] = field(default_factory=list)
    step_post_effects: list[list[tuple[str, dict[str, Any]]]] = field(default_factory=list)
    scroll_positions: list[tuple[float, int]] = field(default_factory=list)
