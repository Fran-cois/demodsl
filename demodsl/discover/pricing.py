"""Best-effort cost estimation for the discovery harness.

Turns a model name + token usage into an estimated USD price, using a small,
overridable table of published per-million-token prices. Prices drift, so this
is an **estimate**: callers can always override with the environment variables
``DEMODSL_LLM_PRICE_INPUT`` / ``DEMODSL_LLM_PRICE_OUTPUT`` (USD per 1M tokens),
which take precedence over the table for any model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

__all__ = ["ModelPrice", "MODEL_PRICING", "estimate_cost", "lookup_price"]


@dataclass(frozen=True)
class ModelPrice:
    """USD price per 1,000,000 tokens."""

    input_per_1m: float
    output_per_1m: float


#: Published prices (USD per 1M tokens), keyed by a normalised model id.
#: Approximate and provider-list based — override via env for accuracy.
MODEL_PRICING: dict[str, ModelPrice] = {
    # OpenAI
    "gpt-4o": ModelPrice(2.50, 10.00),
    "gpt-4o-mini": ModelPrice(0.15, 0.60),
    "gpt-4.1": ModelPrice(2.00, 8.00),
    "gpt-4.1-mini": ModelPrice(0.40, 1.60),
    "gpt-4.1-nano": ModelPrice(0.10, 0.40),
    "gpt-4-turbo": ModelPrice(10.00, 30.00),
    "gpt-3.5-turbo": ModelPrice(0.50, 1.50),
    "o1": ModelPrice(15.00, 60.00),
    "o1-mini": ModelPrice(1.10, 4.40),
    "o3-mini": ModelPrice(1.10, 4.40),
    # Anthropic
    "claude-3-5-sonnet": ModelPrice(3.00, 15.00),
    "claude-3-5-haiku": ModelPrice(0.80, 4.00),
    "claude-3-opus": ModelPrice(15.00, 75.00),
    "claude-3-sonnet": ModelPrice(3.00, 15.00),
    "claude-3-haiku": ModelPrice(0.25, 1.25),
    # Google
    "gemini-1.5-pro": ModelPrice(1.25, 5.00),
    "gemini-1.5-flash": ModelPrice(0.075, 0.30),
    "gemini-2.0-flash": ModelPrice(0.10, 0.40),
    # Meta / Mistral (commonly routed via OpenRouter)
    "llama-3.1-70b": ModelPrice(0.40, 0.40),
    "llama-3.1-8b": ModelPrice(0.05, 0.05),
    "mistral-large": ModelPrice(2.00, 6.00),
    "mistral-small": ModelPrice(0.20, 0.60),
}


def _normalize_model(model: str) -> str:
    """Canonicalise a model id for table lookup.

    Strips an OpenRouter ``vendor/`` prefix, lower-cases, and unifies ``3.5``
    style versions to ``3-5`` so ``anthropic/claude-3.5-sonnet`` matches the
    ``claude-3-5-sonnet`` key.
    """
    name = (model or "").strip().lower()
    if "/" in name:
        name = name.rsplit("/", 1)[1]
    return name.replace(".", "-")


def lookup_price(model: str | None) -> ModelPrice | None:
    """Resolve a :class:`ModelPrice` for *model*.

    Environment overrides win; otherwise the longest matching table key that is
    a prefix of the (normalised) model id is used, so dated snapshots like
    ``gpt-4o-2024-08-06`` still resolve to ``gpt-4o``.
    """
    env_in = os.environ.get("DEMODSL_LLM_PRICE_INPUT")
    env_out = os.environ.get("DEMODSL_LLM_PRICE_OUTPUT")
    if env_in is not None and env_out is not None:
        try:
            return ModelPrice(float(env_in), float(env_out))
        except ValueError:
            pass

    if not model:
        return None
    norm = _normalize_model(model)
    if norm in MODEL_PRICING:
        return MODEL_PRICING[norm]
    # Longest-prefix match (handles dated/sized variants).
    for key in sorted(MODEL_PRICING, key=len, reverse=True):
        if norm.startswith(key):
            return MODEL_PRICING[key]
    return None


def estimate_cost(model: str | None, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Estimated USD cost for the given token counts, or ``None`` if unknown."""
    price = lookup_price(model)
    if price is None:
        return None
    return (
        prompt_tokens / 1_000_000 * price.input_per_1m
        + completion_tokens / 1_000_000 * price.output_per_1m
    )
