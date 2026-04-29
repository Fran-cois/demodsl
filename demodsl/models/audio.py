"""Audio configuration models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from demodsl.models._base import _StrictBase
from demodsl.validators import _validate_safe_path


class BackgroundMusic(_StrictBase):
    file: str
    volume: float = Field(default=0.3, ge=0.0, le=1.0)
    ducking_mode: Literal["none", "light", "moderate", "heavy"] = "moderate"
    loop: bool = True

    @field_validator("file")
    @classmethod
    def _safe_file(cls, v: str) -> str:
        return _validate_safe_path(v)


class VoiceProcessing(_StrictBase):
    normalize: bool = True
    target_dbfs: int = -20
    remove_silence: bool = True
    silence_threshold: int = -40
    min_silence_duration: float = Field(
        default=0.5,
        ge=0.1,
        le=10.0,
        description="Minimum silence duration (seconds) to remove.",
    )
    enhance_clarity: bool = False
    enhance_warmth: bool = False
    noise_reduction: bool = False
    noise_reduction_strength: Literal["light", "moderate", "heavy", "auto"] = "moderate"
    de_ess: bool = False
    de_ess_intensity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="De-esser intensity (0=subtle, 1=aggressive).",
    )


class Compression(_StrictBase):
    threshold: int = -20
    ratio: float = Field(default=3.0, gt=0)
    attack: int = Field(default=5, ge=0)
    release: int = Field(default=50, ge=0)
    preset: Literal["voice", "podcast", "broadcast", "gentle", "custom"] | None = None


class EQBand(_StrictBase):
    """Parametric EQ band for custom equalization."""

    frequency: int = Field(gt=20, le=20000, description="Center frequency in Hz")
    gain: float = Field(ge=-24.0, le=24.0, description="Gain in dB")
    q: float = Field(default=1.0, gt=0, le=10.0, description="Q factor (bandwidth)")


class AudioEffects(_StrictBase):
    eq_preset: (
        Literal["podcast", "warm", "bright", "telephone", "radio", "deep", "custom"] | None
    ) = None
    eq_bands: list[EQBand] | None = Field(
        default=None,
        description="Custom EQ bands (only used when eq_preset='custom').",
    )
    reverb_preset: (
        Literal["none", "small_room", "large_room", "hall", "cathedral", "plate"] | None
    ) = None
    compression: Compression | None = None


class AudioConfig(_StrictBase):
    background_music: BackgroundMusic | None = None
    voice_processing: VoiceProcessing | None = None
    effects: AudioEffects | None = None
