"""Structured, machine-applicable diagnostics (issue #18).

Validation used to speak human: pydantic tracebacks, ``ValueError`` strings,
``UserWarning``s. An agent in a repair loop had to regex-parse prose to know
*what* to fix and *where* — so it often fixed the wrong thing, or regenerated
the whole config and lost the good parts.

:func:`diagnose` returns a list of :class:`Diagnostic` with three properties
that matter:

* **stable ``code``** — the agent branches on it (and users suppress classes
  of warnings by code);
* **``path``** — ``scenarios[0].steps[6].effects[0]``, so the repair is
  surgical instead of a rewrite;
* optional **``fix``** — a machine-applicable edit
  (``insert_before`` / ``set`` / ``remove``) the agent can apply blind.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from demodsl.models import DemoConfig

__all__ = [
    "Diagnostic",
    "diagnose",
    "diagnose_raw",
    "voice_dependency_diagnostics",
    "DIAGNOSTIC_CODES",
]

ERROR = "error"
WARN = "warn"

#: Every code this module can emit — published through
#: ``demodsl capabilities --json`` so agents can enumerate them.
DIAGNOSTIC_CODES: frozenset[str] = frozenset(
    {
        "config.parse_error",
        "camera.move_on_navigate",
        "camera.scroll_while_zoomed",
        "camera.zoom_too_high",
        "camera.zoom_too_low",
        "camera.retarget_while_zoomed",
        "camera.hold_exceeds_wait",
        "camera.target_mismatch",
        "camera.ends_zoomed",
        "camera.incoherent",
        "effect.duration_below_threshold",
        "effect.unknown_param",
        "effect.budget_exceeded",
        "narration.collision",
        "narration.missing",
        "scenario.no_navigate",
        "step.locator_fragile",
        "step.locator_unsupported",
        "voice.missing_dependency",
    }
)

#: Canvas/particle effects that need time on screen to read as an animation.
_SLOW_EFFECTS: dict[str, float] = {
    "confetti": 2.0,
    "fireworks": 2.0,
    "emoji_rain": 2.0,
    "snow": 3.0,
    "bubbles": 2.0,
    "matrix_rain": 3.0,
    "typewriter": 2.0,
    "animated_annotation": 1.5,
    "callout_arrow": 1.5,
}

#: More than this many effects on one step is noise, not emphasis.
_EFFECT_BUDGET = 3


@dataclass
class Diagnostic:
    severity: str
    code: str
    path: str
    message: str
    hint: str | None = None
    fix: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if not data["meta"]:
            data.pop("meta")
        if data["fix"] is None:
            data.pop("fix")
        if data["hint"] is None:
            data.pop("hint")
        return data


def _wpm() -> int:
    try:
        return max(60, int(os.environ.get("DEMODSL_VALIDATE_WPM", "150")))
    except ValueError:
        return 150


def voice_dependency_diagnostics(config: DemoConfig) -> list[Diagnostic]:
    """Flag voice engines whose package is not installed (issue #35).

    A ``WARN``, not an ``ERROR``: the config itself is correct, it is *this*
    machine that cannot render it — authoring on a laptop and rendering on a
    worker is a normal split.
    """
    from demodsl.providers.base import missing_voice_dependency

    out: list[Diagnostic] = []
    configured: list[tuple[str, str]] = []
    if config.voice is not None:
        configured.append(("voice.engine", config.voice.engine))
    languages = getattr(config, "languages", None)
    for lang, voice in ((languages.voices if languages else None) or {}).items():
        configured.append((f"languages.voices.{lang}.engine", voice.engine))

    for path, engine in configured:
        missing = missing_voice_dependency(engine)
        if missing is None:
            continue
        module, install = missing
        out.append(
            Diagnostic(
                severity=WARN,
                code="voice.missing_dependency",
                path=path,
                message=(
                    f"voice engine {engine!r} needs the {module.split('.')[0]!r} package, "
                    f"which is not importable in this environment — the run will fail "
                    f"once narration starts."
                ),
                hint=install,
                meta={"engine": engine, "module": module, "install": install},
            )
        )
    return out


def diagnose(config: DemoConfig) -> list[Diagnostic]:
    """Collect structured diagnostics for an already-parsed *config*."""
    from demodsl.camera_check import ERROR as CAM_ERROR
    from demodsl.camera_check import check_camera_flow
    from demodsl.models.effects import EFFECT_VALID_PARAMS

    out: list[Diagnostic] = []
    gap = config.voice.narration_gap if config.voice else 0.3
    words_per_second = _wpm() / 60.0

    out.extend(voice_dependency_diagnostics(config))

    for s_idx, scenario in enumerate(config.scenarios):
        base = f"scenarios[{s_idx}]"
        steps = scenario.steps or []

        # ── camera choreography ──────────────────────────────────────────
        for issue in check_camera_flow(scenario):
            step_path = f"{base}.steps[{issue.step}]"
            fix = None
            if issue.code == "camera.scroll_while_zoomed":
                fix = {
                    "op": "insert_before",
                    "path": step_path,
                    "value": {"action": "camera_reset", "camera": {"reset": True}},
                }
            elif issue.code == "camera.ends_zoomed":
                fix = {
                    "op": "insert_after",
                    "path": step_path,
                    "value": {"action": "camera_reset", "camera": {"reset": True}},
                }
            out.append(
                Diagnostic(
                    severity=ERROR if issue.severity == CAM_ERROR else WARN,
                    code=issue.code,
                    path=step_path,
                    message=issue.message,
                    hint="insert a camera_reset" if fix else None,
                    fix=fix,
                )
            )

        # ── steps ────────────────────────────────────────────────────────
        if steps and not any(st.action == "navigate" for st in steps) and not scenario.mobile:
            out.append(
                Diagnostic(
                    severity=WARN,
                    code="scenario.no_navigate",
                    path=f"{base}.steps",
                    message="no explicit 'navigate' step — an SPA may render blank",
                    hint="make the first step an explicit navigate to scenario.url",
                )
            )

        narrated: list[tuple[int, float, float]] = []
        for i, step in enumerate(steps):
            step_path = f"{base}.steps[{i}]"

            for e_idx, effect in enumerate(step.effects or []):
                effect_path = f"{step_path}.effects[{e_idx}]"
                floor = _SLOW_EFFECTS.get(effect.type)
                if floor is not None and effect.duration is not None and effect.duration < floor:
                    out.append(
                        Diagnostic(
                            severity=WARN,
                            code="effect.duration_below_threshold",
                            path=effect_path,
                            message=(
                                f"effect '{effect.type}' with duration "
                                f"{effect.duration:.1f}s may not render visibly"
                            ),
                            hint=f"use duration >= {floor}",
                            fix={"op": "set", "path": f"{effect_path}.duration", "value": floor},
                        )
                    )
                valid = EFFECT_VALID_PARAMS.get(effect.type)
                if valid is not None:
                    extra = {
                        name
                        for name, value in effect.model_dump(exclude_none=True).items()
                        if name not in ("type", "duration") and value is not None
                    } - set(valid)
                    for name in sorted(extra):
                        out.append(
                            Diagnostic(
                                severity=WARN,
                                code="effect.unknown_param",
                                path=f"{effect_path}.{name}",
                                message=f"'{effect.type}' ignores the parameter '{name}'",
                                hint=f"valid params: {sorted(valid) or 'none'}",
                                fix={"op": "remove", "path": f"{effect_path}.{name}"},
                            )
                        )

            if step.effects and len(step.effects) > _EFFECT_BUDGET:
                out.append(
                    Diagnostic(
                        severity=WARN,
                        code="effect.budget_exceeded",
                        path=f"{step_path}.effects",
                        message=(
                            f"{len(step.effects)} effects on one step — "
                            "emphasis stops being emphasis"
                        ),
                        hint=f"keep at most {_EFFECT_BUDGET} effects per step",
                    )
                )

            if step.locator is not None and step.locator.type == "text":
                value = step.locator.value
                if len(value) > 40 or any(ch in value for ch in "—–…"):
                    out.append(
                        Diagnostic(
                            severity=WARN,
                            code="step.locator_fragile",
                            path=f"{step_path}.locator",
                            message=(
                                "long or punctuation-heavy 'text' locator is brittle "
                                "(whitespace and dash variants break exact matching)"
                            ),
                            hint="use a short distinctive substring, or a css locator",
                        )
                    )

            if step.narration:
                words = len(step.narration.split())
                narrated.append((i, max(1.0, words / words_per_second), step.wait or 0.0))
            elif step.action in ("hover", "click") and step.wait and step.wait >= 4.0:
                out.append(
                    Diagnostic(
                        severity=WARN,
                        code="narration.missing",
                        path=step_path,
                        message=f"{step.wait:.1f}s of silence on a '{step.action}' step",
                        hint="add a narration or shorten the wait",
                    )
                )

        for pos in range(len(narrated) - 1):
            idx_a, dur_a, wait_a = narrated[pos]
            if not wait_a or dur_a + gap <= wait_a:
                continue
            suggested = round(dur_a + gap, 1)
            path = f"{base}.steps[{idx_a}]"
            out.append(
                Diagnostic(
                    severity=WARN,
                    code="narration.collision",
                    path=path,
                    message=(
                        f"narration (~{dur_a:.1f}s) outlasts wait ({wait_a:.1f}s) — "
                        "it will overlap step "
                        f"{narrated[pos + 1][0]}"
                    ),
                    hint=f"raise wait to ~{suggested}s",
                    fix={"op": "set", "path": f"{path}.wait", "value": suggested},
                    meta={"spoken_seconds": round(dur_a, 2), "wait": wait_a},
                )
            )

    return out


def diagnose_raw(raw: dict[str, Any]) -> tuple[list[Diagnostic], DemoConfig | None]:
    """Parse *raw* then diagnose it, turning parse errors into diagnostics."""
    from pydantic import ValidationError

    from demodsl.models import DemoConfig

    try:
        config = DemoConfig(**raw)
    except ValidationError as exc:
        return ([_parse_diagnostic(err) for err in exc.errors()], None)
    except Exception as exc:  # pragma: no cover - defensive
        return (
            [Diagnostic(severity=ERROR, code="config.parse_error", path="", message=str(exc))],
            None,
        )
    return diagnose(config), config


def _parse_diagnostic(err: dict[str, Any]) -> Diagnostic:
    """Turn one pydantic error into a diagnostic with the most specific code.

    A rejected locator strategy (issue #28) carries its own exception type in
    ``ctx['error']``, so the code is derived from the type rather than by
    regex-parsing the message.
    """
    from demodsl.models.scenario import LocatorNotSupportedError

    original = (err.get("ctx") or {}).get("error")
    code = "config.parse_error"
    hint: str | None = str(err.get("type", "")) or None
    if isinstance(original, LocatorNotSupportedError):
        code = "step.locator_unsupported"
        hint = f"use one of: {', '.join(original.supported)}"
    return Diagnostic(
        severity=ERROR,
        code=code,
        path=_pointer(err.get("loc", ())),
        message=str(err.get("msg", "invalid value")),
        hint=hint,
    )


def _pointer(loc: tuple[Any, ...]) -> str:
    """Render a pydantic error location as ``scenarios[0].steps[6].wait``."""
    parts: list[str] = []
    for item in loc:
        if isinstance(item, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{item}]"
            else:
                parts.append(f"[{item}]")
        else:
            parts.append(str(item))
    return ".".join(parts)
