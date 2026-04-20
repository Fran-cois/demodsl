"""Voice (TTS) configuration model."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from demodsl.models._base import _StrictBase
from demodsl.validators import _validate_safe_path


class VoiceConfig(_StrictBase):
    engine: Literal[
        "elevenlabs",
        "google",
        "azure",
        "aws_polly",
        "openai",
        "cosyvoice",
        "coqui",
        "piper",
        "local_openai",
        "espeak",
        "gtts",
        "voxtral",
        "custom",
    ] = "elevenlabs"
    voice_id: str = Field(default="josh", description="ElevenLabs voice preset name")
    speed: float = Field(default=1.0, gt=0, le=10.0)
    pitch: int = Field(default=0, ge=-100, le=100)
    reference_audio: str | None = None  # path to .wav/.mp3 for voice cloning
    narration_gap: float = Field(
        default=0.3,
        ge=0.0,
        le=10.0,
        description="Minimum gap in seconds between narration clips to prevent overlap.",
    )
    collision_strategy: Literal["warn", "shift", "truncate"] = Field(
        default="warn",
        description=(
            "How to handle narration collisions: "
            "'warn' logs only, 'shift' delays the next clip, "
            "'truncate' fades out the previous clip."
        ),
    )

    @field_validator("reference_audio")
    @classmethod
    def _safe_reference_audio(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_safe_path(v)
        return v
