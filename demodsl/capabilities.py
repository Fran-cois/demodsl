"""Machine-readable capability manifest (issue #15).

The authoring grammar used to exist only in Python source: the ``EffectType``
literal, :data:`EFFECT_VALID_PARAMS`, the per-action required fields, the
numeric bounds on every effect param. An agent writing a config had to be
*told* all of it in a hand-maintained prompt that silently drifted from the
code — the biggest single source of invalid or degraded output.

This module derives the same information **from the models themselves**, so
``demodsl capabilities --json`` can never drift:

* ``build_manifest()`` — actions, effects (typed params + bounds), locator
  types, beat roles, failure policies;
* ``json_schema()`` — the full JSON Schema of :class:`~demodsl.models.DemoConfig`.
"""

from __future__ import annotations

import types
import typing
from typing import Any, Literal, Union, get_args, get_origin

from demodsl import __version__

__all__ = ["build_manifest", "json_schema", "AUTO_ANCHORED_EFFECTS"]

#: Pointing effects whose ``target_x``/``target_y`` (and ``radius``) are filled
#: from the step's locator at runtime when omitted — see
#: ``ScenarioOrchestrator._ANCHORABLE_EFFECTS`` (issue #11).
AUTO_ANCHORED_EFFECTS: frozenset[str] = frozenset(
    {"animated_annotation", "callout_arrow", "magnifier", "marker_underline", "hand_mark"}
)

#: Recommended on-screen duration per effect family, in seconds. Below the
#: floor a canvas animation barely renders; above the ceiling it overstays.
_DURATION_HINTS: dict[str, tuple[float, float]] = {
    "confetti": (2.0, 6.0),
    "fireworks": (2.0, 6.0),
    "emoji_rain": (2.0, 8.0),
    "snow": (3.0, 12.0),
    "bubbles": (2.0, 8.0),
    "star_burst": (1.5, 5.0),
    "party_popper": (1.5, 5.0),
    "matrix_rain": (3.0, 10.0),
    "animated_annotation": (2.0, 10.0),
    "marker_underline": (1.5, 10.0),
    "callout_arrow": (2.0, 10.0),
    "hand_mark": (1.5, 10.0),
    "verdict_stamp": (1.5, 10.0),
    "typewriter": (2.0, 10.0),
    "countdown_timer": (2.0, 15.0),
}

#: Params that are CSS colors rather than plain strings.
_COLOR_PARAMS = frozenset({"color", "colors"})

#: Which subsystem resolves which locator strategy.
_LOCATOR_SUPPORT: dict[str, list[str]] = {
    "css": ["browser"],
    "id": ["browser", "mobile"],
    "xpath": ["browser", "mobile"],
    "text": ["browser", "mobile"],
    "accessibility_id": ["mobile"],
    "class_name": ["mobile"],
    "android_uiautomator": ["mobile"],
    "ios_predicate": ["mobile"],
    "ios_class_chain": ["mobile"],
}


def _literal_values(annotation: Any) -> list[str] | None:
    """Return the string options of a (possibly optional) ``Literal`` annotation."""
    if get_origin(annotation) is Literal:
        return [str(v) for v in get_args(annotation)]
    if get_origin(annotation) in (Union, types.UnionType):
        for arg in get_args(annotation):
            values = _literal_values(arg)
            if values:
                return values
    return None


def _base_type(annotation: Any) -> str:
    """Collapse an annotation to a coarse JSON-ish type name."""
    if get_origin(annotation) in (Union, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        return _base_type(args[0]) if args else "any"
    origin = get_origin(annotation)
    if origin in (list, typing.List):  # noqa: UP006 - runtime check
        return "array"
    if origin in (dict, typing.Dict):  # noqa: UP006 - runtime check
        return "object"
    if annotation is bool:
        return "boolean"
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is str:
        return "string"
    return "any"


def _param_spec(name: str, field: Any) -> dict[str, Any]:
    """Describe one effect/step field: type, bounds, enum values."""
    spec: dict[str, Any] = {
        "type": "css_color" if name in _COLOR_PARAMS else _base_type(field.annotation)
    }
    if name == "colors":
        spec["type"] = "array"
        spec["items"] = "css_color"
    options = _literal_values(field.annotation)
    if options:
        spec["type"] = "enum"
        spec["values"] = options
    for constraint in field.metadata or ():
        for attr, key in (
            ("ge", "min"),
            ("gt", "exclusive_min"),
            ("le", "max"),
            ("lt", "exclusive_max"),
            ("max_length", "max_len"),
        ):
            value = getattr(constraint, attr, None)
            if value is not None:
                spec[key] = value
    if field.description:
        spec["description"] = field.description
    return spec


def build_manifest() -> dict[str, Any]:
    """Build the capability manifest from the live models."""
    from demodsl.models.effects import EFFECT_VALID_PARAMS, Effect, EffectType
    from demodsl.models.scenario import (
        STEP_COMMON_FIELDS,
        STEP_RELEVANT_FIELDS,
        STEP_REQUIRED_FIELDS,
        BeatSpec,
        Locator,
        Step,
    )

    step_fields = Step.model_fields
    effect_fields = Effect.model_fields

    actions: list[dict[str, Any]] = []
    for action in get_args(step_fields["action"].annotation):
        required = list(STEP_REQUIRED_FIELDS.get(action, ()))
        relevant = STEP_RELEVANT_FIELDS.get(action, set())
        optional = sorted(((relevant | STEP_COMMON_FIELDS) - {"action"}) - set(required))
        actions.append(
            {
                "name": action,
                "requires": required,
                "optional": optional,
                "fields": {
                    name: _param_spec(name, step_fields[name])
                    for name in sorted(relevant)
                    if name in step_fields
                },
            }
        )

    effects: list[dict[str, Any]] = []
    for name in sorted(set(get_args(EffectType)) | set(EFFECT_VALID_PARAMS)):
        params = sorted(EFFECT_VALID_PARAMS.get(name, set()))
        entry: dict[str, Any] = {
            "name": name,
            "params": {p: _param_spec(p, effect_fields[p]) for p in params if p in effect_fields},
            "auto_anchored": name in AUTO_ANCHORED_EFFECTS,
        }
        hint = _DURATION_HINTS.get(name)
        if hint:
            entry["recommended_duration"] = list(hint)
        effects.append(entry)

    return {
        "version": __version__,
        "actions": actions,
        "effects": effects,
        "locator_types": _LOCATOR_SUPPORT,
        "beat_roles": _literal_values(BeatSpec.model_fields["role"].annotation) or [],
        "beat_sentiments": _literal_values(BeatSpec.model_fields["sentiment"].annotation) or [],
        "on_error_policies": _literal_values(step_fields["on_error"].annotation) or [],
        "locator_fields": sorted(Locator.model_fields),
        "diagnostic_codes": _diagnostic_codes(),
    }


def _diagnostic_codes() -> list[str]:
    """Stable diagnostic codes an agent can branch on (issue #18)."""
    from demodsl.diagnostics import DIAGNOSTIC_CODES

    return sorted(DIAGNOSTIC_CODES)


def json_schema() -> dict[str, Any]:
    """JSON Schema of a complete demo config."""
    from demodsl.models import DemoConfig

    return DemoConfig.model_json_schema()
