"""Terminal scenario configuration model."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from demodsl.models._base import _StrictBase


class TerminalConfig(_StrictBase):
    """Configuration for terminal recording scenarios.

    Terminal scenarios render a realistic terminal emulator in the browser
    (via Playwright) and execute typed commands with animated output,
    reusing the existing video-recording pipeline.
    """

    shell: str = Field(
        default="bash",
        description="Shell name shown in the title bar (cosmetic only).",
    )
    prompt: str = Field(
        default="$ ",
        description="Prompt string displayed before each command.",
    )
    theme: Literal["dark", "light", "dracula", "monokai", "solarized"] = Field(
        default="dark",
        description="Terminal colour theme.",
    )
    font_family: str = Field(
        default="'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace",
        description="CSS font-family for the terminal.",
    )
    font_size: int = Field(default=18, ge=10, le=48)
    line_height: float = Field(default=1.5, ge=1.0, le=3.0)
    cols: int = Field(default=100, ge=40, le=300)
    rows: int = Field(default=28, ge=10, le=80)
    title: str | None = Field(
        default=None,
        description="Window title. Defaults to shell name if not set.",
    )
    window_chrome: bool = Field(
        default=True,
        description="Show macOS-style window chrome (traffic lights + title bar).",
    )
    typing_speed: float = Field(
        default=12.0,
        gt=0,
        le=200,
        description="Characters per second for typing commands.",
    )
    output_delay: float = Field(
        default=0.3,
        ge=0,
        le=5.0,
        description="Seconds to wait after typing before showing output.",
    )
