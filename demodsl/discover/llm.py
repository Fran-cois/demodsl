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
import re
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


# ── OpenRouter (OpenAI-compatible gateway to many models) ────────────────────


class OpenRouterProvider(OpenAIProvider):
    """Chat completions via `OpenRouter <https://openrouter.ai>`_.

    OpenRouter exposes an OpenAI-compatible ``/chat/completions`` endpoint, so we
    reuse :class:`OpenAIProvider` wholesale and only swap the base URL, the API
    key (``OPENROUTER_API_KEY``) and the optional ranking headers. Models use the
    ``vendor/model`` slug form, e.g. ``openai/gpt-4o``, ``anthropic/claude-3.5-sonnet``,
    ``google/gemini-flash-1.5``. Vision works for any multimodal model since the
    image payload format is identical to OpenAI's.
    """

    name = "openrouter"
    API_BASE = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        model: str = "openai/gpt-4o",
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        site_url: str | None = None,
        app_name: str | None = None,
    ) -> None:
        super().__init__(model=model, api_key=api_key or os.environ.get("OPENROUTER_API_KEY"))
        self._base_url = base_url or os.environ.get("OPENROUTER_BASE_URL", self.API_BASE)
        # Optional headers OpenRouter uses for app ranking/attribution.
        self._site_url = site_url or os.environ.get("OPENROUTER_SITE_URL")
        self._app_name = app_name or os.environ.get("OPENROUTER_APP_NAME", "demodsl")

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
                raise RuntimeError("OPENROUTER_API_KEY is not set.")
            headers: dict[str, str] = {}
            if self._site_url:
                headers["HTTP-Referer"] = self._site_url
            if self._app_name:
                headers["X-Title"] = self._app_name
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                default_headers=headers or None,
            )
        return self._client


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


# ── Simulated (offline, reads the prompt, returns a real JSON decision) ───────


_QUERY_RE = re.compile(r"QUERY:\s*(.+)")
_ELEMENT_RE = re.compile(r"^\s*\[(\d+)\]\s+([^:]+):\s*(.*)$")
# Strip the trailing decorations element serialisation can append:
# " (input)", " @(x,y)" (Set-of-Marks), " <tag>" (DOM tier).
_SUFFIX_RE = re.compile(r"\s*(?:\(input\)|@\(-?\d+\s*,\s*-?\d+\)|<[^>]+>)\s*$")
_MARK_REF_RE = re.compile(r"#(\d+)")
_ACTED_RE = re.compile(r"(?:click|type|hover)\s+#(\d+)")

#: A real model holds out for a *confident* match instead of grabbing the first
#: weakly-relevant control — below this grounded score it keeps looking.
_ACT_THRESHOLD = 0.2
#: Roles that are plausible "affordances" for a goal (clickable / typable).
_AFFORDANCE_ROLES = frozenset(
    {"button", "link", "tab", "menuitem", "searchbox", "textbox", "combobox"}
)


@dataclass
class _PageItem:
    mark: int
    role: str
    name: str
    editable: bool


def _concision(name: str) -> float:
    """Down-weight verbose, banner-like labels.

    A precise control ("Pricing", "Tarifs", "Itinéraires") is far likelier to be
    the right target than a 100-character marketing blob, and a real model reads
    it that way. Returns a multiplier in ``[0.45, 1.0]`` by word count.
    """
    words = len(name.split())
    if words > 10:
        return 0.45
    if words > 6:
        return 0.75
    return 1.0


def _ground(name: str, role: str, keywords: list[str]) -> float:
    """Model-like grounding score: lexical/fuzzy relevance, made *selective*.

    Reuses the page's own relevance signal, then applies a concision penalty and
    a small affordance bonus — so the simulated model prefers a crisp matching
    link/button over a long promotional heading, the way a real one does.
    """
    from demodsl.discover.observation import _relevance

    rel = _relevance(name, role, keywords, fuzzy=True) * _concision(name)
    if role in _AFFORDANCE_ROLES:
        rel = min(1.0, rel * 1.05)
    return rel


def _parse_page_items(page_text: str) -> list[_PageItem]:
    """Recover the ``[mark] role: name`` rows from the serialised page block."""
    items: list[_PageItem] = []
    in_elements = False
    for line in page_text.splitlines():
        if line.strip() == "ELEMENTS:":
            in_elements = True
            continue
        if not in_elements:
            continue
        m = _ELEMENT_RE.match(line)
        if not m:
            continue
        rest = m.group(3).strip()
        editable = "(input)" in rest
        name = rest
        while True:  # peel any stack of trailing decorations
            stripped = _SUFFIX_RE.sub("", name)
            if stripped == name:
                break
            name = stripped
        items.append(
            _PageItem(
                mark=int(m.group(1)),
                role=m.group(2).strip(),
                name=name.strip() or "—",
                editable=editable,
            )
        )
    return items


def _is_strong_match(name: str, keywords: list[str]) -> bool:
    if not keywords:
        return False
    low = name.lower()
    hits = sum(1 for k in keywords if re.search(rf"\b{re.escape(k)}\b", low))
    return hits >= max(1, len(keywords) - 1)


def _simulate_decision(
    user: str, *, has_image: bool, max_scrolls: int, type_text: str
) -> dict[str, Any]:
    """Decide the next action *from the prompt text alone*, like a real model.

    Grounds on the same ``[mark] role: name`` surface the cloud model receives:
    pick the best query match in view (click it, or type if it is an input);
    otherwise scroll to reveal more, escalating to a visual request after the
    first miss; give up only once the scroll budget is spent. Deterministic.
    """
    # Lazy import keeps llm.py free of an observation dependency at module load.
    from demodsl.discover.observation import _keywords

    qm = _QUERY_RE.search(user)
    query = qm.group(1).strip() if qm else ""
    keywords = _keywords(query)

    if "\n\nCURRENT PAGE:\n" in user:
        head, _, tail = user.partition("\n\nCURRENT PAGE:\n")
        page_text = tail.split("\n\nReturn the JSON", 1)[0]
    else:
        head, page_text = user, ""

    avoid: set[int] = set()
    refl = re.search(r"PREVIOUS FAILURE TO AVOID:\s*(.+)", head)
    if refl:
        avoid |= {int(x) for x in _MARK_REF_RE.findall(refl.group(1))}
    scrolls = 0
    for line in head.splitlines():
        s = line.strip()
        if not s.startswith("- "):
            continue
        entry = s[2:].strip()
        if entry.startswith("scroll"):
            scrolls += 1
        acted = _ACTED_RE.match(entry)
        if acted:  # don't re-act on a control we already consumed
            avoid.add(int(acted.group(1)))

    best: _PageItem | None = None
    best_rel = 0.0
    for it in _parse_page_items(page_text):
        if it.mark in avoid:
            continue
        rel = _ground(it.name, it.role, keywords)
        if rel > best_rel:
            best, best_rel = it, rel

    if best is not None and best_rel >= _ACT_THRESHOLD:
        strong = best_rel >= 0.9 or _is_strong_match(best.name, keywords)
        conf = round(min(0.97, 0.5 + best_rel), 3)
        if best.editable:
            return {
                "thought": f"The {best.role} '{best.name}' fits the goal; I'll type into it.",
                "action": "type",
                "mark": best.mark,
                "value": type_text,
                "narration": f"I type into '{best.name}'.",
                "confidence": conf,
                "feature_reached": strong,
                "needs_visual": False,
                "effect_hint": "highlight",
            }
        return {
            "thought": f"'{best.name}' is the closest match to the goal; I'll open it.",
            "action": "click",
            "mark": best.mark,
            "narration": f"I open '{best.name}'.",
            "confidence": conf,
            "feature_reached": strong,
            "needs_visual": False,
            "effect_hint": "spotlight",
        }

    if scrolls >= max_scrolls:
        return {
            "thought": "I scanned the page without spotting the target; I'll stop here.",
            "action": "done",
            "narration": "That is as far as this feature seems to go.",
            "confidence": 0.3,
            "feature_reached": False,
            "needs_visual": False,
            "effect_hint": None,
        }
    return {
        "thought": "Nothing on screen matches yet; I'll scroll to reveal more.",
        "action": "scroll",
        "direction": "down",
        "pixels": 720,
        "narration": "I scroll down to reveal more of the page.",
        "confidence": 0.4,
        "needs_visual": scrolls >= 1,
        "feature_reached": False,
        "effect_hint": None,
    }


class SimulatedLLMProvider(LLMProvider):
    """A deterministic, offline **stand-in for a real chat model**.

    Unlike :class:`HeuristicLLMProvider` (which only does token accounting while
    the separate :class:`~demodsl.discover.policy.HeuristicPolicy` decides), this
    provider *parses the very prompt the cloud model would receive* and returns a
    schema-valid JSON action grounded in the serialised page. That exercises the
    full LLM code path — :class:`~demodsl.discover.policy.LLMPolicy` prompt
    construction, JSON parsing, vision-flag handling and token budgeting — with
    no API key, so ``--policy llm --llm simulated`` is fully runnable, testable
    and reproducible. It behaves like a *competent* agent (semantic/fuzzy
    grounding, mild persistence), which is what lets an LLM-policy panel run
    explore deeper than the bare offline rule engine.
    """

    name = "simulated"

    def __init__(
        self, model: str = "sim-1", *, max_scrolls: int = 6, type_text: str = "demo"
    ) -> None:
        self.model = model
        self.max_scrolls = max_scrolls
        self.type_text = type_text

    def complete(
        self,
        system: str,
        user: str,
        *,
        images: list[Path] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> LLMResponse:
        decision = _simulate_decision(
            user,
            has_image=bool(images),
            max_scrolls=self.max_scrolls,
            type_text=self.type_text,
        )
        text = json.dumps(decision, ensure_ascii=False)
        usage = TokenUsage(
            prompt_tokens=_estimate_tokens(system) + _estimate_tokens(user),
            completion_tokens=_estimate_tokens(text),
            calls=1,
        )
        return LLMResponse(text=text, usage=usage)


LLMProviderFactory.register("openai", OpenAIProvider)
LLMProviderFactory.register("openrouter", OpenRouterProvider)
LLMProviderFactory.register("anthropic", AnthropicProvider)
LLMProviderFactory.register("heuristic", HeuristicLLMProvider)
LLMProviderFactory.register("simulated", SimulatedLLMProvider)
