"""Best-effort cost estimation for the discovery harness.

Turns a model name + token usage into an estimated USD price. Three sources, in
precedence order:

1. **Environment override** — ``DEMODSL_LLM_PRICE_INPUT`` / ``DEMODSL_LLM_PRICE_OUTPUT``
   (USD per 1M tokens) always win, for any model.
2. **Live OpenRouter prices** — when enabled, the public ``GET /models`` endpoint
   is queried (no auth required) for the exact, up-to-date price of the slug.
   Cached for the process; network failures fall through silently.
3. **Static table** — a small, built-in list of published prices as an offline
   fallback.

Prices drift, so this remains an **estimate** unless the live source is used.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = [
    "ModelPrice",
    "MODEL_PRICING",
    "estimate_cost",
    "lookup_price",
    "fetch_openrouter_prices",
    "fetch_openrouter_models",
    "clear_openrouter_cache",
]


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


# ── live OpenRouter pricing (public /models endpoint, cached) ────────────────

#: Process-wide cache of the OpenRouter price map (None = not fetched yet).
_OPENROUTER_CACHE: dict[str, ModelPrice] | None = None
#: Process-wide cache of the raw OpenRouter model list (None = not fetched yet).
_OPENROUTER_MODELS: list[str] | None = None


def clear_openrouter_cache() -> None:
    """Forget any cached OpenRouter data (mainly for tests)."""
    global _OPENROUTER_CACHE, _OPENROUTER_MODELS
    _OPENROUTER_CACHE = None
    _OPENROUTER_MODELS = None


def _fetch_openrouter_models_raw(
    *, base_url: str | None, api_key: str | None, timeout: float
) -> list[dict]:
    """GET the raw ``data`` list from OpenRouter's public ``/models`` endpoint.

    Best-effort: returns ``[]`` on any network/parse error (never raises).
    """
    base = (
        base_url or os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    ).rstrip("/")
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    try:
        import httpx

        headers = {"Authorization": f"Bearer {key}"} if key else {}
        resp = httpx.get(f"{base}/models", headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return data if isinstance(data, list) else []
    except Exception as exc:  # network down, httpx missing, bad payload, …
        logger.debug("OpenRouter /models fetch failed: %s", exc)
        return []


def fetch_openrouter_prices(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float = 10.0,
    refresh: bool = False,
) -> dict[str, ModelPrice]:
    """Fetch per-model prices from OpenRouter's public ``/models`` endpoint.

    Returns a map keyed by the OpenRouter model id (e.g. ``"openai/gpt-4o"``).
    Best-effort: any network/parse error returns an empty map (never raises).
    The result is cached for the process unless *refresh* is set.
    """
    global _OPENROUTER_CACHE
    if _OPENROUTER_CACHE is not None and not refresh:
        return _OPENROUTER_CACHE

    prices: dict[str, ModelPrice] = {}
    for entry in _fetch_openrouter_models_raw(base_url=base_url, api_key=api_key, timeout=timeout):
        mid = entry.get("id")
        pricing = entry.get("pricing") or {}
        try:
            # OpenRouter prices are USD *per token*; scale to per-1M.
            in_per_1m = float(pricing.get("prompt", 0)) * 1_000_000
            out_per_1m = float(pricing.get("completion", 0)) * 1_000_000
        except (TypeError, ValueError):
            continue
        if mid and (in_per_1m or out_per_1m):
            prices[mid.lower()] = ModelPrice(in_per_1m, out_per_1m)

    _OPENROUTER_CACHE = prices
    return prices


def fetch_openrouter_models(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float = 10.0,
    refresh: bool = False,
) -> list[str]:
    """Fetch the list of available OpenRouter model ids (e.g. ``"openai/gpt-4o"``).

    Sorted, de-duplicated. Best-effort: empty list on any failure. Cached for the
    process unless *refresh* is set.
    """
    global _OPENROUTER_MODELS
    if _OPENROUTER_MODELS is not None and not refresh:
        return _OPENROUTER_MODELS

    ids = {
        str(entry["id"])
        for entry in _fetch_openrouter_models_raw(
            base_url=base_url, api_key=api_key, timeout=timeout
        )
        if entry.get("id")
    }
    _OPENROUTER_MODELS = sorted(ids)
    return _OPENROUTER_MODELS


def _openrouter_price(model: str) -> ModelPrice | None:
    """Resolve *model* against the cached OpenRouter price map."""
    prices = fetch_openrouter_prices()
    if not prices:
        return None
    mid = (model or "").strip().lower()
    if mid in prices:
        return prices[mid]
    # Match by slug suffix (e.g. "gpt-4o" against "openai/gpt-4o").
    suffix = _normalize_model(model)
    for key, price in prices.items():
        if _normalize_model(key) == suffix:
            return price
    return None


def lookup_price(model: str | None, *, live: bool = False) -> ModelPrice | None:
    """Resolve a :class:`ModelPrice` for *model*.

    Precedence: environment override → live OpenRouter price (when *live*) →
    static table (longest matching key prefix, so dated snapshots like
    ``gpt-4o-2024-08-06`` still resolve to ``gpt-4o``).
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

    if live:
        live_price = _openrouter_price(model)
        if live_price is not None:
            return live_price

    norm = _normalize_model(model)
    if norm in MODEL_PRICING:
        return MODEL_PRICING[norm]
    # Longest-prefix match (handles dated/sized variants).
    for key in sorted(MODEL_PRICING, key=len, reverse=True):
        if norm.startswith(key):
            return MODEL_PRICING[key]
    return None


def estimate_cost(
    model: str | None, prompt_tokens: int, completion_tokens: int, *, live: bool = False
) -> float | None:
    """Estimated USD cost for the given token counts, or ``None`` if unknown."""
    price = lookup_price(model, live=live)
    if price is None:
        return None
    return (
        prompt_tokens / 1_000_000 * price.input_per_1m
        + completion_tokens / 1_000_000 * price.output_per_1m
    )
