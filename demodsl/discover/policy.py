"""ReAct policy: propose the next action from the current observation.

Two interchangeable implementations:

* :class:`LLMPolicy` — prompts an :class:`~demodsl.discover.llm.LLMProvider`
  (OpenAI / Anthropic) with the budgeted observation and parses a structured
  JSON action.  This is the default for real runs.
* :class:`HeuristicPolicy` — a deterministic, query-grounded rule engine used
  for offline runs, tests and the benchmark.  It implements the same
  reason→act contract without any model call, so the harness is fully runnable
  with zero API keys.

Both follow the ReAct pattern (a short "thought" precedes the action) and
accept a Reflexion note describing the previous failure so the next proposal can
adapt instead of repeating a dead end.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from demodsl.discover.actions import ACTION_SPACE, AgentAction
from demodsl.discover.llm import LLMProvider, TokenUsage
from demodsl.discover.observation import PageObservation, _keywords

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a web-demo discovery agent. Given a user QUERY describing a website
feature to show or test, and a budgeted representation of the current page,
choose the single best next action to make that feature visible or exercised.

Respond with ONLY a JSON object:
{
  "thought": "<one short sentence of reasoning>",
  "action": "navigate|click|type|scroll|wait_for|hover|press_key|done",
  "mark": <integer element id or null>,
  "url": "<url or null>",
  "value": "<text to type or null>",
  "direction": "down|up|left|right|null",
  "pixels": <integer or null>,
  "key": "<single key or null>",
  "narration": "<a friendly one-sentence narration for this step>",
  "confidence": <float 0..1>,
  "feature_reached": <true|false>,
  "needs_visual": <true|false>,
  "effect_hint": "spotlight|highlight|glow|null"
}
Prefer clicking elements whose name matches the query. Use "done" with
feature_reached=true when the feature is on screen. Set needs_visual=true if the
text representation is ambiguous and you need element coordinates.
ACTIONS:
""" + "\n".join(f"- {v}" for v in ACTION_SPACE.values())


@dataclass
class PolicyDecision:
    action: AgentAction
    usage: TokenUsage = field(default_factory=TokenUsage)


class Policy(ABC):
    @abstractmethod
    def propose(
        self,
        query: str,
        observation: PageObservation,
        history: list[str],
        *,
        reflection: str | None = None,
    ) -> PolicyDecision:
        """Return the next action for *observation* given *query* and history."""


class LLMPolicy(Policy):
    def __init__(self, llm: LLMProvider, *, temperature: float = 0.0) -> None:
        self.llm = llm
        self.temperature = temperature

    def propose(
        self,
        query: str,
        observation: PageObservation,
        history: list[str],
        *,
        reflection: str | None = None,
    ) -> PolicyDecision:
        hist = "\n".join(f"- {h}" for h in history[-8:]) or "(none yet)"
        reflect = f"\nPREVIOUS FAILURE TO AVOID: {reflection}" if reflection else ""
        images = [observation.screenshot] if observation.screenshot else None
        user = (
            f"QUERY: {query}\n\nHISTORY:\n{hist}{reflect}\n\n"
            f"CURRENT PAGE:\n{observation.text}\n\nReturn the JSON action."
        )
        resp = self.llm.complete(
            _SYSTEM_PROMPT,
            user,
            images=images,
            temperature=self.temperature,
        )
        action = _parse_action(resp.json(), observation)
        return PolicyDecision(action=action, usage=resp.usage)


def _parse_action(data: dict, observation: PageObservation) -> AgentAction:
    kind = str(data.get("action", "scroll")).strip().lower()
    if kind not in ACTION_SPACE:
        kind = "scroll"
    mark = data.get("mark")
    mark = int(mark) if isinstance(mark, (int, float)) else None
    locator = None
    editable = False
    if mark is not None:
        el = observation.by_mark(mark)
        if el is not None:
            locator = el.locator
            editable = el.editable
    direction = data.get("direction")
    if direction not in ("up", "down", "left", "right"):
        direction = "down" if kind == "scroll" else None
    if kind == "type" and not editable and mark is not None:
        # Model picked a non-input; degrade to click so we still make progress.
        kind = "click"
    return AgentAction(
        kind=kind,  # type: ignore[arg-type]
        mark=mark,
        locator=locator,
        url=data.get("url") or None,
        value=data.get("value") or None,
        direction=direction,  # type: ignore[arg-type]
        pixels=int(data["pixels"]) if isinstance(data.get("pixels"), (int, float)) else None,
        key=data.get("key") or None,
        narration=data.get("narration") or None,
        rationale=str(data.get("thought", "")),
        confidence=float(data.get("confidence", 0.5) or 0.5),
        feature_reached=bool(data.get("feature_reached", False)),
        needs_visual=bool(data.get("needs_visual", False)),
        effect_hint=data.get("effect_hint") or None,
    )


class HeuristicPolicy(Policy):
    """Deterministic query-grounded policy (no LLM call).

    Strategy: find the highest-relevance element for the query; click it (or
    type into it if it is an input); if nothing relevant is on screen, scroll to
    reveal more, up to a bounded number of scrolls before giving up.
    """

    def __init__(self, *, max_scrolls: int = 4, type_text: str = "demo") -> None:
        self.max_scrolls = max_scrolls
        self.type_text = type_text

    def propose(
        self,
        query: str,
        observation: PageObservation,
        history: list[str],
        *,
        reflection: str | None = None,
    ) -> PolicyDecision:
        usage = TokenUsage(
            prompt_tokens=observation.token_estimate + 60,
            completion_tokens=24,
            calls=1,
        )
        kws = _keywords(query)
        scrolls = sum(1 for h in history if h.startswith("scroll"))
        avoid = _avoided_marks(reflection)
        # Don't loop on a control we already acted on: a logo/link that never
        # navigates would otherwise stay the top match and get re-clicked every
        # step. Skipping already-acted marks makes exploration advance in
        # breadth across the page instead.
        avoid |= _acted_marks(history)

        best = None
        best_rel = 0.0
        for el in observation.elements:
            if el.mark in avoid:
                continue
            if el.relevance > best_rel:
                best, best_rel = el, el.relevance

        if best is not None and best_rel > 0:
            reached = best_rel >= 0.9 or _strong_match(best.name, kws)
            if best.editable:
                action = AgentAction(
                    kind="type",
                    mark=best.mark,
                    locator=best.locator,
                    value=self.type_text,
                    narration=f"I type into the {best.role} '{best.name}'.",
                    rationale=f"'{best.name}' matches the query; it is an input.",
                    confidence=min(1.0, 0.5 + best_rel),
                    feature_reached=reached,
                    effect_hint="highlight",
                )
            else:
                action = AgentAction(
                    kind="click",
                    mark=best.mark,
                    locator=best.locator,
                    narration=f"I open '{best.name}'.",
                    rationale=f"'{best.name}' is the best match for the query.",
                    confidence=min(1.0, 0.5 + best_rel),
                    feature_reached=reached,
                    effect_hint="spotlight",
                )
            return PolicyDecision(action=action, usage=usage)

        # Nothing relevant in view.
        if scrolls >= self.max_scrolls:
            action = AgentAction(
                kind="done",
                narration="That covers the requested feature.",
                rationale="No further relevant elements found after scrolling.",
                confidence=0.3,
                feature_reached=False,
            )
        else:
            action = AgentAction(
                kind="scroll",
                direction="down",
                pixels=720,
                narration="I scroll down to reveal more of the page.",
                rationale="No relevant element on screen; reveal more content.",
                confidence=0.4,
                needs_visual=scrolls >= 1,  # escalate representation after 1 miss
            )
        return PolicyDecision(action=action, usage=usage)


def _strong_match(name: str, keywords: list[str]) -> bool:
    if not keywords:
        return False
    low = name.lower()
    return sum(1 for k in keywords if re.search(rf"\b{re.escape(k)}\b", low)) >= max(
        1, len(keywords) - 1
    )


def _avoided_marks(reflection: str | None) -> set[int]:
    if not reflection:
        return set()
    return {int(m) for m in re.findall(r"#(\d+)", reflection)}


def _acted_marks(history: list[str]) -> set[int]:
    """Marks already consumed by a click/type/hover action in the trajectory.

    The history holds :meth:`AgentAction.to_summary` strings such as
    ``"click #5"``. Re-acting on the same mark is almost always a dead loop
    (e.g. a logo that stays the top relevance match), so we let the policy skip
    them and explore new elements. Scroll/navigate/wait actions don't consume a
    mark and never appear here.
    """
    marks: set[int] = set()
    for entry in history:
        match = re.match(r"(?:click|type|hover)\s+#(\d+)", entry)
        if match:
            marks.add(int(match.group(1)))
    return marks
