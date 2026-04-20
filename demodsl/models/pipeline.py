"""Pipeline stage model."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field, model_validator

from demodsl.models._base import _StrictBase


class PipelineStage(_StrictBase):
    """A single pipeline stage parsed from a one-key dict in the YAML list."""

    model_config = ConfigDict(extra="allow")  # params are free-form by design

    stage_type: str
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _parse_from_dict(cls, data: Any) -> Any:
        """Accept ``{"restore_audio": {"denoise": true}}`` shorthand."""
        if isinstance(data, dict) and "stage_type" not in data:
            if len(data) != 1:
                raise ValueError(
                    f"Pipeline stage dict must have exactly 1 key, got {list(data.keys())}"
                )
            key, value = next(iter(data.items()))
            return {
                "stage_type": key,
                "params": value if isinstance(value, dict) else {},
            }
        return data
