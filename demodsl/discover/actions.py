"""Agent action space for the discovery harness.

The action space is a deliberately small, DemoDSL-aligned subset so that a
discovered trajectory maps one-to-one onto :class:`~demodsl.models.Step`
objects during synthesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from demodsl.models import Locator

ActionKind = Literal[
    "navigate",
    "click",
    "type",
    "scroll",
    "wait_for",
    "hover",
    "press_key",
    "done",
]

#: Human-readable description of every action, injected into the policy prompt.
ACTION_SPACE: dict[str, str] = {
    "navigate": "navigate{url}: go to an absolute URL.",
    "click": "click{mark}: click the element with the given mark id.",
    "type": "type{mark, value}: type text into the input with the given mark id.",
    "scroll": "scroll{direction, pixels}: scroll the page (down/up/left/right).",
    "wait_for": "wait_for{mark}: wait until the element with the mark id appears.",
    "hover": "hover{mark}: move the cursor over the element with the mark id.",
    "press_key": "press_key{key}: press a single key (e.g. 'Enter', 'Escape').",
    "done": "done: the queried feature is now visible / exercised — stop.",
}


@dataclass
class AgentAction:
    """A single structured action proposed by the policy.

    ``mark`` references an element in the current
    :class:`~demodsl.discover.observation.PageObservation`; the search loop
    resolves it to a concrete :class:`~demodsl.models.Locator` before acting.
    """

    kind: ActionKind
    mark: int | None = None
    locator: Locator | None = None
    url: str | None = None
    value: str | None = None
    direction: Literal["up", "down", "left", "right"] | None = None
    pixels: int | None = None
    key: str | None = None

    # Narration the policy suggests for this step (used by the synthesizer).
    narration: str | None = None
    # Free-text chain-of-thought rationale (ReAct "thought").
    rationale: str = ""
    # Policy self-confidence in [0, 1]; low confidence triggers SoM escalation.
    confidence: float = 0.5
    # Whether the policy believes the queried feature has now been reached.
    feature_reached: bool = False
    # Whether the policy needs a richer (visual / Set-of-Marks) representation.
    needs_visual: bool = False
    # Effect hint for the synthesizer (e.g. "spotlight" on a click).
    effect_hint: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def is_terminal(self) -> bool:
        return self.kind == "done" or self.feature_reached

    def to_summary(self) -> str:
        bits = [self.kind]
        if self.mark is not None:
            bits.append(f"#{self.mark}")
        if self.url:
            bits.append(self.url)
        if self.value:
            bits.append(f"{self.value!r}")
        if self.direction:
            bits.append(self.direction)
        return " ".join(bits)


@dataclass
class StepResult:
    """Outcome of executing an :class:`AgentAction` against the environment."""

    ok: bool
    action: AgentAction
    error: str | None = None
    url_before: str | None = None
    url_after: str | None = None
    # True when a navigation/DOM change was observed after the action.
    page_changed: bool = False

    def to_summary(self) -> str:
        status = "ok" if self.ok else f"FAIL({self.error})"
        return f"{self.action.to_summary()} -> {status}"
