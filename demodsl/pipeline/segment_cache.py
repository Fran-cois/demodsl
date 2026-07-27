"""Content-addressed per-step segments for incremental re-render (issue #25).

Fixing one word of narration currently costs a full re-record + full TTS
+ full composite. This module makes the unit of caching the **step**, not
the config: each step gets a key derived from everything that can change
its pixels (its own config, the resolved locator, the page URL it runs
on, the effect params, the engine version). On the next run, every step
whose key is unchanged reuses its recorded segment and only the dirty
ones are re-recorded.

The old run-cache is keyed by *config section*, which is why a single
edited word invalidated the whole recording and why ``--force-record``
had to exist. A content hash fixes both problems at once — and
``--explain-cache`` makes the reuse auditable, because a silently reused
stale segment is worse than no cache at all.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from demodsl import __version__ as _ENGINE_VERSION

logger = logging.getLogger(__name__)

__all__ = [
    "SegmentKeyInputs",
    "SegmentPlanEntry",
    "SegmentPlan",
    "step_key",
    "narration_key",
    "plan_segments",
    "parse_only_steps",
    "SegmentStore",
]


def _hash(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:32]


@dataclass(frozen=True)
class SegmentKeyInputs:
    """Everything that affects a step's recorded segment."""

    step: dict[str, Any]
    page_url: str | None
    scenario: dict[str, Any]
    engine_version: str = _ENGINE_VERSION
    resolved_locator: str | None = None


def step_key(inputs: SegmentKeyInputs) -> str:
    """Content hash of a single step's recording."""
    return _hash(
        {
            "step": inputs.step,
            "page_url": inputs.page_url,
            "scenario": inputs.scenario,
            "engine": inputs.engine_version,
            "locator": inputs.resolved_locator,
        }
    )


def narration_key(text: str, engine: str, voice: str | None, speed: float | None) -> str:
    """Content hash of a narration clip — the shape the TTS cache already has."""
    return _hash({"text": text, "engine": engine, "voice": voice, "speed": speed})


#: Scenario fields that change how *every* step of it renders. Anything not
#: listed here (the scenario name, its narration text…) must not invalidate a
#: recorded segment.
_SCENARIO_RECORDING_FIELDS = (
    "browser",
    "provider",
    "viewport",
    "color_scheme",
    "locale",
    "cursor",
    "glow_select",
    "popup_card",
    "background",
    "natural",
    "mobile",
    "terminal",
    "auth",
)

#: Step fields that only affect audio/composition, never the recorded pixels.
_NON_RECORDING_STEP_FIELDS = frozenset({"narration", "narrations", "audio_offset"})


def _scenario_context(scenario: Any) -> dict[str, Any]:
    dump = scenario.model_dump(exclude_none=True)
    return {k: dump[k] for k in _SCENARIO_RECORDING_FIELDS if k in dump}


def _step_payload(step: Any) -> dict[str, Any]:
    dump = step.model_dump(exclude_none=True)
    return {k: v for k, v in dump.items() if k not in _NON_RECORDING_STEP_FIELDS}


@dataclass
class SegmentPlanEntry:
    index: int
    scenario: str
    action: str
    key: str
    hit: bool
    reason: str
    narration: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SegmentPlan:
    entries: list[SegmentPlanEntry] = field(default_factory=list)
    engine_version: str = _ENGINE_VERSION

    @property
    def dirty(self) -> list[int]:
        return [e.index for e in self.entries if not e.hit]

    @property
    def reused(self) -> list[int]:
        return [e.index for e in self.entries if e.hit]

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_version": self.engine_version,
            "reused": self.reused,
            "dirty": self.dirty,
            "steps": [e.to_dict() for e in self.entries],
        }

    def explain(self) -> str:
        """Human-readable ``--explain-cache`` table."""
        lines = [
            f"{'step':>5}  {'status':<6} {'action':<14} {'key':<12} reason",
            "-" * 72,
        ]
        for e in self.entries:
            status = "HIT" if e.hit else "MISS"
            lines.append(
                f"{e.index + 1:>5}  {status:<6} {e.action:<14} {e.key[:10]:<12} {e.reason}"
            )
        lines.append(
            f"\n{len(self.reused)} reused, {len(self.dirty)} to re-record "
            f"(engine {self.engine_version})"
        )
        return "\n".join(lines)


def parse_only_steps(spec: str | None) -> set[int] | None:
    """Parse ``--only-steps 6,7,10-12`` into a set of 0-based indexes."""
    if not spec:
        return None
    out: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, _, end = chunk.partition("-")
            try:
                lo, hi = int(start), int(end)
            except ValueError as exc:
                raise ValueError(f"Invalid --only-steps range: {chunk!r}") from exc
            if lo > hi:
                raise ValueError(f"Invalid --only-steps range: {chunk!r}")
            out.update(range(lo - 1, hi))
        else:
            try:
                out.add(int(chunk) - 1)
            except ValueError as exc:
                raise ValueError(f"Invalid --only-steps value: {chunk!r}") from exc
    if any(i < 0 for i in out):
        raise ValueError("--only-steps is 1-based; step numbers must be >= 1")
    return out


def plan_segments(
    config: Any,
    *,
    cached_keys: dict[str, Any] | None = None,
    only_steps: set[int] | None = None,
    available: set[str] | None = None,
) -> SegmentPlan:
    """Decide, per step, whether its recorded segment can be reused.

    *cached_keys* maps ``str(step_index) -> key`` from the previous run's
    manifest; *available* is the set of keys whose segment file actually
    exists (a manifest entry without its artefact is a miss, not a
    silent reuse).
    """
    cached_keys = cached_keys or {}
    plan = SegmentPlan()
    index = 0
    for scenario in getattr(config, "scenarios", []) or []:
        context = _scenario_context(scenario)
        page_url = getattr(scenario, "url", None)
        for step in getattr(scenario, "steps", []) or []:
            if step.action == "navigate" and step.url:
                page_url = step.url
            key = step_key(
                SegmentKeyInputs(
                    step=_step_payload(step),
                    page_url=page_url,
                    scenario=context,
                )
            )
            previous = cached_keys.get(str(index))
            if only_steps is not None and index in only_steps:
                hit, reason = False, "forced by --only-steps"
            elif previous is None:
                hit, reason = False, "no cached segment"
            elif previous != key:
                hit, reason = False, "step content changed"
            elif available is not None and key not in available:
                hit, reason = False, "cached segment artefact missing"
            else:
                hit, reason = True, "unchanged"
            plan.entries.append(
                SegmentPlanEntry(
                    index=index,
                    scenario=scenario.name,
                    action=step.action,
                    key=key,
                    hit=hit,
                    reason=reason,
                    narration=(step.narration or None),
                )
            )
            index += 1
    return plan


class SegmentStore:
    """Filesystem store of per-step segments, addressed by content key."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, key: str, suffix: str = ".mp4") -> Path:
        return self._root / f"{key}{suffix}"

    def available(self, suffix: str = ".mp4") -> set[str]:
        return {p.stem for p in self._root.glob(f"*{suffix}")}

    def load_keys(self) -> dict[str, Any]:
        index = self._root / "segments.json"
        if not index.exists():
            return {}
        try:
            return json.loads(index.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Corrupt segment index at %s — treating cache as empty", index)
            return {}

    def save_keys(self, keys: dict[str, Any]) -> None:
        (self._root / "segments.json").write_text(
            json.dumps(keys, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
