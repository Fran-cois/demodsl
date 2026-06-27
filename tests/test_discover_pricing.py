"""Tests for the discovery cost estimator (``demodsl.discover.pricing``)."""

from __future__ import annotations

import pytest

from demodsl.discover.pricing import MODEL_PRICING, estimate_cost, lookup_price


def test_known_model_cost() -> None:
    # gpt-4o = $2.50 / $10.00 per 1M tokens.
    cost = estimate_cost("gpt-4o", 1_000_000, 1_000_000)
    assert cost == pytest.approx(12.50)


def test_openrouter_slug_and_version_normalization() -> None:
    # vendor/ prefix stripped; dotted version unified to dashed.
    assert lookup_price("openai/gpt-4o") is MODEL_PRICING["gpt-4o"]
    assert lookup_price("anthropic/claude-3.5-sonnet") is MODEL_PRICING["claude-3-5-sonnet"]


def test_dated_variant_prefix_match() -> None:
    # A dated snapshot resolves to its base model.
    assert lookup_price("openai/gpt-4o-2024-08-06") is MODEL_PRICING["gpt-4o"]


def test_mini_variant_not_shadowed_by_base() -> None:
    assert lookup_price("gpt-4o-mini") is MODEL_PRICING["gpt-4o-mini"]


def test_unknown_model_returns_none() -> None:
    assert lookup_price("sim-1") is None
    assert estimate_cost("sim-1", 1000, 1000) is None
    assert estimate_cost(None, 1000, 1000) is None


def test_env_override_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMODSL_LLM_PRICE_INPUT", "1.0")
    monkeypatch.setenv("DEMODSL_LLM_PRICE_OUTPUT", "2.0")
    # Even an unknown model is now priced, and known models are overridden.
    assert estimate_cost("sim-1", 1_000_000, 1_000_000) == pytest.approx(3.0)
    assert estimate_cost("gpt-4o", 1_000_000, 0) == pytest.approx(1.0)
