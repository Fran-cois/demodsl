"""Metadata model."""

from __future__ import annotations

from demodsl.models._base import _StrictBase


class Metadata(_StrictBase):
    title: str
    description: str | None = None
    author: str | None = None
    version: str | None = None
