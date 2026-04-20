"""Edit / pause models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from demodsl.models._base import _StrictBase


class PauseEdit(_StrictBase):
    """A pause inserted after a given step."""

    after_step: int = Field(..., ge=0, description="Global step index (0-based).")
    duration: float = Field(
        ..., gt=0, le=30.0, description="Pause duration in seconds."
    )
    type: Literal["audio", "freeze"] = Field(
        default="audio",
        description=(
            "'audio' inserts silence in the narration track; "
            "'freeze' also holds the last video frame."
        ),
    )


class EditConfig(_StrictBase):
    """Post-recording edit directives (pauses, timing adjustments)."""

    pauses: list[PauseEdit] = Field(default_factory=list)
