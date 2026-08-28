"""Root DemoConfig, Analytics, and LanguagesConfig models."""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from demodsl.models._base import _StrictBase
from demodsl.models.audio import AudioConfig
from demodsl.models.edit import EditConfig
from demodsl.models.metadata import Metadata
from demodsl.models.output import OutputConfig
from demodsl.models.overlays import SubtitleConfig
from demodsl.models.pipeline import PipelineStage
from demodsl.models.rendering import DeviceRendering
from demodsl.models.scenario import HumanizeConfig, Scenario
from demodsl.models.theme import THEME_PRESETS, ThemeConfig, discover_theme_presets
from demodsl.models.video import VideoConfig
from demodsl.models.voice import VoiceConfig

_LANG_RE = r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})?$"


class Analytics(_StrictBase):
    track_engagement: bool = False
    heatmap: bool = False
    click_tracking: bool = False


class LanguagesConfig(_StrictBase):
    """Multi-language configuration.

    When ``targets`` is non-empty, the engine produces a single MP4 with
    multiple audio tracks (one per language) and multiple soft subtitle
    tracks. Each step may carry per-language translations via
    ``Step.narrations`` ; missing translations fall back to the source
    ``narration`` text (the default language).
    """

    default: str = Field(
        default="fr",
        min_length=2,
        max_length=8,
        pattern=_LANG_RE,
        description="BCP-47 / ISO 639-1 code of the source narrations in the YAML.",
    )
    targets: list[str] = Field(
        default_factory=list,
        description=(
            "Additional target languages. Each entry triggers a dedicated "
            "narration audio track and subtitle track in the final MP4."
        ),
    )
    voices: dict[str, VoiceConfig] | None = Field(
        default=None,
        description=(
            "Per-language voice overrides: {lang: VoiceConfig}. "
            "When a target language is missing here, the root 'voice' "
            "config is reused with its 'voice_id' tweaked when possible."
        ),
    )
    embed: bool = Field(
        default=True,
        description=(
            "When True, all language audio + subtitle tracks are muxed into "
            "a single MP4. When False, sidecar files are written next to "
            "the video (narration_<lang>.mp3 + subtitles_<lang>.ass)."
        ),
    )
    burn_default: bool = Field(
        default=False,
        description=(
            "Burn the default-language subtitle into the video as hard subs "
            "in addition to embedding all languages as soft subtitle tracks."
        ),
    )
    audio_only: list[str] = Field(
        default_factory=list,
        description="Languages to include as audio tracks only (no subtitle track).",
    )
    subtitle_only: list[str] = Field(
        default_factory=list,
        description="Languages to include as subtitle tracks only (no audio/TTS).",
    )


class DemoConfig(_StrictBase):
    metadata: Metadata
    seed: int | None = Field(
        default=None,
        ge=0,
        le=2**31 - 1,
        description=(
            "Determinism contract (issue #26): every stochastic subsystem "
            "(hand-drawn wobble, avatar blink/saccade schedules, natural "
            "timing jitter, particle emitters) derives its RNG from this "
            "seed, so the same config + seed + page snapshot renders the "
            "same frames. Leave unset for the legacy random behaviour."
        ),
    )
    theme: ThemeConfig | None = Field(
        default=None,
        description=(
            "Visual identity tokens (issue #27) referenced by every overlay: "
            "accent / ink / surface / mark colours, font, subtitle style and "
            "presenter persona. Accepts an inline object or the name of a "
            f"built-in preset ({', '.join(sorted(THEME_PRESETS))}), or one contributed "
            "by a plugin. Per-field overlay "
            "overrides keep winning over the theme."
        ),
    )
    voice: VoiceConfig | None = None
    audio: AudioConfig | None = None
    humanize: bool | HumanizeConfig | None = Field(
        default=None,
        description="Simulated human operator applied to every scenario that "
        "does not define its own 'humanize' block. True uses the 'presenter' "
        "defaults.",
    )
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
    fake_chat: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Raw fake-chat configuration passed through to the demodsl-fake-chat "
            "plugin. Controls the built-in chat simulator server (port, "
            "conversations directory, inline conversations)."
        ),
    )

    @field_validator("theme", mode="before")
    @classmethod
    def _resolve_theme_preset(cls, v: Any) -> Any:
        """Accept ``theme: dark-dev`` (a preset name) as well as an object."""
        if isinstance(v, str):
            presets = discover_theme_presets()
            preset = presets.get(v)
            if preset is None:
                raise ValueError(f"Unknown theme preset {v!r}. Available: {sorted(presets)}")
            return dict(preset)
        return v
