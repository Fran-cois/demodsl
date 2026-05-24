"""Reusable effect library models.

A *library effect* is a named, parametrised template that expands into
one or more timeline layers (and/or step-level effects) at config-load time.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from demodsl.models._base import _StrictBase

# ── Parameter schema ─────────────────────────────────────────────────────────

ParamType = Literal["string", "number", "color", "boolean", "list"]


class LibraryParam(_StrictBase):
    """Schema for a single parameter exposed by a library effect."""

    type: ParamType = Field(description="Expected value type.")
    default: Any = Field(default=None, description="Default value (None = required).")
    description: str = Field(default="", description="Human-readable description.")

    @property
    def required(self) -> bool:
        return self.default is None


# ── Library Effect ───────────────────────────────────────────────────────────


class LibraryEffect(_StrictBase):
    """A reusable effect template stored in the library.

    Each library effect declares its parameters, and its body is a list of
    raw layer dicts (and/or step-level effect dicts) that will be interpolated
    with the resolved parameter values and injected into the user's config.
    """

    name: str = Field(description="Unique identifier (e.g. 'lower_thirds/tech').")
    description: str = Field(default="", description="What this effect does.")
    tags: list[str] = Field(default_factory=list, description="Searchable tags.")
    parameters: dict[str, LibraryParam] = Field(
        default_factory=dict,
        description="Named parameters exposed to the user via $params.",
    )
    layers: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Raw layer dicts (timeline layer format). "
        "May contain {{ param }} template expressions.",
    )
    effects: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Raw step-level effect dicts. May contain {{ param }} template expressions.",
    )
    extends: str | None = Field(
        default=None,
        description="Name of a parent library effect to inherit from.",
    )

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not v or not v.replace("/", "").replace("_", "").replace("-", "").isalnum():
            msg = f"Library effect name must be alphanumeric with / _ - separators, got: {v!r}"
            raise ValueError(msg)
        return v
