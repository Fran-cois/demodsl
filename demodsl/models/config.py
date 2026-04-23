"""Root DemoConfig, Analytics, and LanguagesConfig models."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from demodsl.models._base import _StrictBase
from demodsl.models.audio import AudioConfig
from demodsl.models.edit import EditConfig
from demodsl.models.metadata import Metadata
from demodsl.models.output import OutputConfig
from demodsl.models.overlays import SubtitleConfig
from demodsl.models.pipeline import PipelineStage
from demodsl.models.rendering import DeviceRendering
from demodsl.models.scenario import Scenario
from demodsl.models.video import VideoConfig
from demodsl.models.voice import VoiceConfig


class Analytics(_StrictBase):
    track_engagement: bool = False
    heatmap: bool = False
    click_tracking: bool = False


class LanguagesConfig(_StrictBase):
    """Multi-language configuration for separate-audio rendering."""

    default: str = Field(
        default="fr",
        min_length=2,
        max_length=5,
        description="ISO 639-1 language code of the narrations in the YAML.",
    )
    targets: list[str] = Field(
        default_factory=list,
        description="Additional target languages (handled by backend, not demodsl).",
    )


class DemoConfig(_StrictBase):
    metadata: Metadata
    voice: VoiceConfig | None = None
    audio: AudioConfig | None = None
    device_rendering: DeviceRendering | None = None
    video: VideoConfig | None = None
    languages: LanguagesConfig | None = None
    # Root-level subtitle config. Takes priority over per-scenario subtitle.
    # Resolution order: root (if enabled) > first scenario (if enabled) > disabled.
    # See orchestrators/post_processing.py get_subtitle_config().
    subtitle: SubtitleConfig | None = None
    scenarios: list[Scenario] = Field(default_factory=list)
    pipeline: list[PipelineStage] = Field(default_factory=list)
    output: OutputConfig | None = None
    edit: EditConfig | None = None
    analytics: Analytics | None = None
    webinar: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Raw webinar configuration passed through to the demodsl_webinar "
            "plugin. Validation is delegated to the plugin's own WebinarConfig "
            "model — the core engine treats this as an opaque dict."
        ),
    )
    chrome_extensions: dict[str, Any] | list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Raw Chrome extensions configuration passed through to the "
            "demodsl-chrome-extensions plugin. Validation is delegated to "
            "the plugin's own ChromeExtConfig model."
        ),
    )
    appless: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Raw AppLess configuration passed through to the demodsl-appless "
            "plugin. Validation is delegated to the plugin's own AppLessConfig "
            "model — the core engine treats this as an opaque dict."
        ),
    )
