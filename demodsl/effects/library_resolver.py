"""Resolve ``$use`` references in raw config dicts before Pydantic validation.

The resolver walks the config tree looking for dicts containing ``$use``.
It expands them by:

1. Looking up the named library effect.
2. Resolving ``extends`` if present.
3. Interpolating ``$params`` into the template layers/effects.
4. Returning the expanded structure in-place.

Usage::

    from demodsl.effects.library_resolver import resolve_library_refs

    raw_config = yaml.safe_load(...)
    resolve_library_refs(raw_config, library)
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

from demodsl.effects.library_registry import EffectLibrary, LibraryLoadError
from demodsl.models.library import LibraryEffect

logger = logging.getLogger(__name__)

# Template pattern: {{ expr }}
_TEMPLATE_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}")

# Allowed names in template expressions (no builtins, no imports)
_SAFE_NAMES = frozenset(
    {"True", "False", "None", "int", "float", "str", "abs", "min", "max", "round"}
)

MAX_RESOLVE_DEPTH = 10


class LibraryResolveError(Exception):
    """Raised when $use resolution fails."""


# ── Public API ───────────────────────────────────────────────────────────────


def resolve_library_refs(config: dict[str, Any], library: EffectLibrary) -> dict[str, Any]:
    """Resolve all ``$use`` references in a raw config dict (in-place).

    Walks:
    - ``config["steps"][*]["effects"]`` — step-level effects
    - ``config["timeline"]["layers"]`` — timeline layers
    - ``config["scenarios"][*]["steps"][*]["effects"]`` — multi-scenario

    Returns the mutated config.
    """
    # Step-level effects
    if "steps" in config and isinstance(config["steps"], list):
        for step in config["steps"]:
            if isinstance(step, dict) and "effects" in step:
                step["effects"] = _resolve_effects_list(step["effects"], library)

    # Multi-scenario
    if "scenarios" in config and isinstance(config["scenarios"], list):
        for scenario in config["scenarios"]:
            if isinstance(scenario, dict) and "steps" in scenario:
                for step in scenario["steps"]:
                    if isinstance(step, dict) and "effects" in step:
                        step["effects"] = _resolve_effects_list(step["effects"], library)
            # Scenario-level timeline layers
            if isinstance(scenario, dict) and "timeline" in scenario:
                stl = scenario["timeline"]
                if isinstance(stl, dict) and "layers" in stl:
                    stl["layers"] = _resolve_layers_list(stl["layers"], library)

    # Timeline layers
    if "timeline" in config and isinstance(config["timeline"], dict):
        tl = config["timeline"]
        if "layers" in tl and isinstance(tl["layers"], list):
            tl["layers"] = _resolve_layers_list(tl["layers"], library)

    return config


# ── Internal ─────────────────────────────────────────────────────────────────


def _resolve_effects_list(effects: list[Any], library: EffectLibrary) -> list[dict[str, Any]]:
    """Expand $use in a list of effect dicts."""
    result: list[dict[str, Any]] = []
    for item in effects:
        if not isinstance(item, dict):
            result.append(item)
            continue
        if "$use" not in item:
            result.append(item)
            continue
        expanded = _expand_use(item, library, context="effects")
        result.extend(expanded)
    return result


def _resolve_layers_list(layers: list[Any], library: EffectLibrary) -> list[dict[str, Any]]:
    """Expand $use in a list of layer dicts."""
    result: list[dict[str, Any]] = []
    use_counter = 0
    for item in layers:
        if not isinstance(item, dict):
            result.append(item)
            continue
        if "$use" not in item:
            result.append(item)
            continue
        expanded = _expand_use(item, library, context="layers")
        # Auto-prefix layer IDs to avoid collisions when same preset used multiple times
        use_counter += 1
        for layer in expanded:
            if "id" in layer:
                layer["id"] = f"{layer['id']}_{use_counter}"
            if "parent" in layer and layer["parent"]:
                layer["parent"] = f"{layer['parent']}_{use_counter}"
        result.extend(expanded)
    return result


def _expand_use(
    ref: dict[str, Any],
    library: EffectLibrary,
    context: str,
    _depth: int = 0,
) -> list[dict[str, Any]]:
    """Expand a single $use reference into a list of dicts."""
    if _depth > MAX_RESOLVE_DEPTH:
        msg = f"$use resolution exceeded max depth ({MAX_RESOLVE_DEPTH})"
        raise LibraryResolveError(msg)

    name = ref["$use"]
    params = ref.get("$params", {})

    # Look up in library
    effect = library.get(name)
    if effect is None:
        msg = f"Unknown library effect: {name!r}"
        raise LibraryResolveError(msg)

    # Resolve inheritance
    effect = library.resolve_extends(effect)

    # Validate and merge params with defaults
    resolved_params = _resolve_params(effect, params)

    # Pick the right template based on context
    if context == "layers" and effect.layers:
        template = copy.deepcopy(effect.layers)
    elif context == "effects" and effect.effects:
        template = copy.deepcopy(effect.effects)
    elif context == "layers" and effect.effects:
        # $use in layers context but effect only has step-level effects
        msg = (
            f"Library effect {name!r} only defines step-level effects, "
            f"cannot use in timeline.layers context"
        )
        raise LibraryResolveError(msg)
    elif context == "effects" and effect.layers:
        # $use in effects context but effect only has layers — not valid here
        msg = (
            f"Library effect {name!r} only defines timeline layers, "
            f"cannot use in step effects context"
        )
        raise LibraryResolveError(msg)
    else:
        msg = f"Library effect {name!r} has no layers or effects defined"
        raise LibraryResolveError(msg)

    # Apply inline overrides (anything in ref that's not $use/$params/$overrides)
    overrides = {k: v for k, v in ref.items() if not k.startswith("$")}
    # $overrides: dot-path targeted overrides
    # Format: {"<layer_index>.<path>": value} for layer-specific,
    #         {"<path>": value} for all-layers (only when single template item)
    path_overrides = ref.get("$overrides", {})

    # Separate indexed vs global overrides
    indexed_overrides: dict[int, dict[str, Any]] = {}
    global_overrides: dict[str, Any] = {}
    for path, value in path_overrides.items():
        parts = path.split(".", 1)
        if parts[0].isdigit() and len(parts) > 1:
            idx = int(parts[0])
            indexed_overrides.setdefault(idx, {})[parts[1]] = value
        else:
            global_overrides[path] = value

    # Interpolate templates with params
    result = []
    for i, item in enumerate(template):
        interpolated = _interpolate(item, resolved_params)
        # Apply top-level overrides (e.g. start, duration from the $use block)
        if overrides:
            interpolated = {**interpolated, **overrides}
        # Apply global dot-path overrides (all layers)
        for path, value in global_overrides.items():
            _set_nested(interpolated, path, value)
        # Apply indexed overrides (specific layer)
        if i in indexed_overrides:
            for path, value in indexed_overrides[i].items():
                _set_nested(interpolated, path, value)
        result.append(interpolated)

    return result


def _resolve_params(effect: LibraryEffect, user_params: dict[str, Any]) -> dict[str, Any]:
    """Merge user-supplied params with defaults, validate required ones."""
    resolved: dict[str, Any] = {}
    for name, schema in effect.parameters.items():
        if name in user_params:
            resolved[name] = user_params[name]
        elif schema.default is not None:
            resolved[name] = schema.default
        else:
            msg = f"Missing required parameter {name!r} for library effect {effect.name!r}"
            raise LibraryResolveError(msg)

    # Warn about unknown params
    unknown = set(user_params.keys()) - set(effect.parameters.keys())
    if unknown:
        logger.warning(
            "Unknown parameters for %r: %s (will be ignored)",
            effect.name,
            ", ".join(sorted(unknown)),
        )

    return resolved


def _interpolate(obj: Any, params: dict[str, Any]) -> Any:
    """Recursively interpolate {{ expr }} templates in a structure."""
    if isinstance(obj, str):
        return _interpolate_string(obj, params)
    if isinstance(obj, dict):
        return {k: _interpolate(v, params) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate(item, params) for item in obj]
    return obj


def _interpolate_string(s: str, params: dict[str, Any]) -> Any:
    """Evaluate template expressions in a string.

    If the ENTIRE string is a single {{ expr }}, returns the native Python
    value (number, bool, etc). Otherwise returns a string with interpolated
    segments.
    """
    # Fast path: entire string is a single template
    m = re.fullmatch(r"\{\{\s*(.+?)\s*\}\}", s)
    if m:
        return _safe_eval(m.group(1), params)

    # Multi-segment: replace each {{ expr }} with str(result)
    def _replacer(match: re.Match) -> str:
        result = _safe_eval(match.group(1), params)
        return str(result)

    result = _TEMPLATE_RE.sub(_replacer, s)
    return result


def _safe_eval(expr: str, params: dict[str, Any]) -> Any:
    """Evaluate a simple expression with only param names allowed.

    Supports arithmetic (+, -, *, /, //, %), comparisons, and basic
    builtins (min, max, abs, round, int, float, str).
    """
    import builtins as _builtins_mod

    allowed = {n: getattr(_builtins_mod, n) for n in _SAFE_NAMES if hasattr(_builtins_mod, n)}

    # Build a restricted namespace
    namespace: dict[str, Any] = {"__builtins__": allowed}
    namespace.update(params)

    try:
        return eval(expr, namespace)  # noqa: S307
    except Exception as exc:
        msg = f"Template expression error: {expr!r} — {exc}"
        raise LibraryResolveError(msg) from exc


def _set_nested(obj: Any, path: str, value: Any) -> None:
    """Set a value at a dot-separated path, supporting list indices.

    Example: _set_nested(d, "animators.0.keyframes.1.v", 0.5)
    """
    parts = path.split(".")
    current = obj
    for part in parts[:-1]:
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            return
    last = parts[-1]
    if isinstance(current, list):
        current[int(last)] = value
    elif isinstance(current, dict):
        current[last] = value
