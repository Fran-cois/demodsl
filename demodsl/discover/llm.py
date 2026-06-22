"""LLM provider abstraction for the discovery agent.

Mirrors the project's existing provider-factory pattern (see
:class:`~demodsl.providers.base.VoiceProviderFactory`).  Three providers ship:

* ``openai`` / ``anthropic`` — cloud chat models, used for real runs.  Vision
  is supported by passing screenshot paths (Set-of-Marks grounding).
* ``heuristic`` — a deterministic, dependency-free, **offline** provider.  It
  lets the whole harness (and the benchmark) run without any API key, which is
  what makes the reported numbers reproducible.

Every call returns token-usage so the harness can enforce a compute budget and
report cost as a first-class metric.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, other: TokenUsage) -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.calls += other.calls


@dataclass
class LLMResponse:
    text: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw: Any = None

    def json(self) -> dict[str, Any]:
        """Parse the first JSON object found in the response text."""
        return _extract_json(self.text)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort extraction of a single JSON object from model output."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


class LLMProvider(ABC):
    """Abstract chat-completion provider."""

    name: str = "abstract"

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        *,
        images: list[Path] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> LLMResponse:
        """Return a completion for the (system, user) prompt."""


class LLMProviderFactory:
    _registry: dict[str, type[LLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[LLMProvider]) -> None:
        cls._registry[name] = provider_cls

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> LLMProvider:
        if name not in cls._registry:
            raise ValueError(f"Unknown LLM provider '{name}'. Available: {sorted(cls._registry)}")
        return cls._registry[name](**kwargs)

    @classmethod
    def available(cls) -> list[str]:
        return sorted(cls._registry)


# ── OpenAI ──────────────────────────────────────────────────────────────────


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None) -> None:
        self.model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dep
                raise RuntimeError(
                    "openai package not installed. `pip install openai` or use "
                    "the 'heuristic' provider."
                ) from exc
            if not self._api_key:
                raise RuntimeError("OPENAI_API_KEY is not set.")
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def complete(
        self,
        system: str,
        user: str,
        *,
        images: list[Path] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> LLMResponse:  # pragma: no cover - requires network/key
        import base64

        client = self._ensure_client()
        content: list[dict[str, Any]] = [{"type": "text", "text": user}]
        for img in images or []:
            data = base64.b64encode(Path(img).read_bytes()).decode()
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{data}"},
                }
            )
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        usage = TokenUsage(
            prompt_tokens=getattr(resp.usage, "prompt_tokens", 0),
            completion_tokens=getattr(resp.usage, "completion_tokens", 0),
            calls=1,
        )
        return LLMResponse(text=resp.choices[0].message.content or "", usage=usage, raw=resp)


# ── Anthropic ────────────────────────────────────────────────────────────────


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str = "claude-3-5-sonnet-latest", api_key: str | None = None) -> None:
        self.model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dep
                raise RuntimeError(
                    "anthropic package not installed. `pip install anthropic` or "
                    "use the 'heuristic' provider."
                ) from exc
            if not self._api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not set.")
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete(
        self,
        system: str,
        user: str,
        *,
        images: list[Path] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> LLMResponse:  # pragma: no cover - requires network/key
        import base64

        client = self._ensure_client()
        content: list[dict[str, Any]] = [{"type": "text", "text": user}]
        for img in images or []:
            data = base64.b64encode(Path(img).read_bytes()).decode()
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": data,
                    },
                }
            )
        resp = client.messages.create(
            model=self.model,
            system=system,
            messages=[{"role": "user", "content": content}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = "".join(getattr(b, "text", "") for b in resp.content)
        usage = TokenUsage(
            prompt_tokens=getattr(resp.usage, "input_tokens", 0),
            completion_tokens=getattr(resp.usage, "output_tokens", 0),
            calls=1,
        )
        return LLMResponse(text=text, usage=usage, raw=resp)


# ── Heuristic (offline, deterministic) ───────────────────────────────────────


class HeuristicLLMProvider(LLMProvider):
    """A deterministic stand-in used for offline runs, tests and the benchmark.

    It does **not** parse natural language.  Instead the policy talks to it
    through a private side-channel: the structured decision is computed by
    :class:`~demodsl.discover.policy.HeuristicPolicy` and merely *accounted*
    here so token-budget bookkeeping stays realistic.  When called directly it
    echoes an empty-but-valid JSON action.
    """

    name = "heuristic"

    def complete(
        self,
        system: str,
        user: str,
        *,
        images: list[Path] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> LLMResponse:
        usage = TokenUsage(
            prompt_tokens=_estimate_tokens(system) + _estimate_tokens(user),
            completion_tokens=24,
            calls=1,
        )
        # A harmless default; the heuristic policy never relies on this text.
        return LLMResponse(text='{"action": "scroll", "direction": "down"}', usage=usage)


LLMProviderFactory.register("openai", OpenAIProvider)
LLMProviderFactory.register("anthropic", AnthropicProvider)
LLMProviderFactory.register("heuristic", HeuristicLLMProvider)
