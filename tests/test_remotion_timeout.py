"""Tests for the configurable Remotion render timeout."""

from __future__ import annotations

import pytest

from demodsl.providers.remotion_bridge import (
    REMOTION_RENDER_TIMEOUT_DEFAULT,
    _remotion_render_timeout,
)


def test_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMODSL_REMOTION_TIMEOUT", raising=False)
    assert _remotion_render_timeout() == REMOTION_RENDER_TIMEOUT_DEFAULT


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMODSL_REMOTION_TIMEOUT", "3000")
    assert _remotion_render_timeout() == 3000


@pytest.mark.parametrize("valeur", ["", "   ", "abc", "0", "-1"])
def test_invalid_values_fall_back(monkeypatch: pytest.MonkeyPatch, valeur: str) -> None:
    """A bad value must not cancel the timeout: a hung render would never end."""
    monkeypatch.setenv("DEMODSL_REMOTION_TIMEOUT", valeur)
    assert _remotion_render_timeout() == REMOTION_RENDER_TIMEOUT_DEFAULT
