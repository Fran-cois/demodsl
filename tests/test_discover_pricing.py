"""Tests for the discovery cost estimator (``demodsl.discover.pricing``)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from demodsl.discover.pricing import (
    MODEL_PRICING,
    clear_openrouter_cache,
    estimate_cost,
    fetch_openrouter_prices,
    lookup_price,
)


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


# ── live OpenRouter pricing ──────────────────────────────────────────────────


_FAKE_MODELS = {
    "data": [
        # OpenRouter prices are USD per token.
        {"id": "openai/gpt-4o", "pricing": {"prompt": "0.000003", "completion": "0.000012"}},
        {"id": "x-ai/grok-9", "pricing": {"prompt": "0.000001", "completion": "0.000002"}},
    ]
}


def _mock_get(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    return resp


def test_fetch_openrouter_prices_parses_per_token_to_per_1m() -> None:
    clear_openrouter_cache()
    with patch("httpx.get", return_value=_mock_get(_FAKE_MODELS)) as mget:
        prices = fetch_openrouter_prices(refresh=True)
    assert mget.call_args.args[0].endswith("/models")
    # per-token → per-1M scaling.
    assert prices["openai/gpt-4o"].input_per_1m == pytest.approx(3.0)
    assert prices["openai/gpt-4o"].output_per_1m == pytest.approx(12.0)
    clear_openrouter_cache()


def test_live_lookup_prefers_openrouter_over_table() -> None:
    clear_openrouter_cache()
    with patch("httpx.get", return_value=_mock_get(_FAKE_MODELS)):
        # gpt-4o exists in the static table (2.50/10.00) but live wins (3.0/12.0).
        price = lookup_price("openai/gpt-4o", live=True)
    assert price is not None
    assert price.input_per_1m == pytest.approx(3.0)
    # A model absent from the static table is still priced live.
    with patch("httpx.get", return_value=_mock_get(_FAKE_MODELS)):
        assert lookup_price("x-ai/grok-9", live=True) is not None
    clear_openrouter_cache()


def test_live_failure_falls_back_to_table() -> None:
    clear_openrouter_cache()
    with patch("httpx.get", side_effect=RuntimeError("network down")):
        price = lookup_price("openai/gpt-4o", live=True)
    # Network error → silent fallback to the built-in table.
    assert price is MODEL_PRICING["gpt-4o"]
    clear_openrouter_cache()


def test_no_live_does_not_hit_network() -> None:
    clear_openrouter_cache()
    with patch("httpx.get", side_effect=AssertionError("must not be called")):
        price = lookup_price("openai/gpt-4o", live=False)
    assert price is MODEL_PRICING["gpt-4o"]
