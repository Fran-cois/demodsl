"""Phase 2 — Expression DSL for animated properties.

A minimal, sandboxed mini-language compiled to a pure-Python callable that
evaluates per-frame. NO eval/exec — we parse with ``ast`` and walk a
whitelisted set of nodes.

Supported:
- numeric and list literals
- arithmetic +, -, *, /, //, %, **, unary -+, parentheses
- variables: ``time``, ``layer_time``, ``duration``, ``fps``
- function calls (whitelisted): ``sin, cos, tan, abs, min, max, clamp,
  round, floor, ceil, sqrt, pi, e, wiggle, loopOut, linear, random,
  parent``
- attribute access on ``parent``: ``parent.position``, ``parent.scale``, …
"""

from __future__ import annotations

import ast
import math
import random as _stdrandom
from dataclasses import dataclass, field
from typing import Any, Callable

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Num,
    ast.Constant,
    ast.Load,
    ast.Name,
    ast.Call,
    ast.Tuple,
    ast.List,
    ast.Attribute,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Subscript,
    ast.Index,
    ast.Slice,
    ast.keyword,  # for func(name=value)
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.IfExp,
    ast.BoolOp,
    ast.And,
    ast.Or,
)


class ExpressionError(ValueError):
    """Raised when an expression is invalid or unsafe."""


@dataclass
class EvalEnv:
    """Per-frame evaluation environment passed to expressions."""

    time: float = 0.0
    layer_time: float = 0.0
    duration: float = 0.0
    fps: float = 30.0
    seed: int = 0
    parent_transform: Any = None  # demodsl.models.timeline.Transform | None
    extras: dict[str, Any] = field(default_factory=dict)


# ── Built-in functions ──────────────────────────────────────────────────────


def _wiggle(freq: float, amp: float, seed: int = 0, *, env: EvalEnv) -> float:
    """Smooth pseudo-random oscillation (sum of sinusoids).

    Reproducible per-seed. Returns a scalar in approximately ``[-amp, amp]``.
    """
    t = env.time
    base = (seed * 1000 + env.seed) % 9973
    return amp * (
        0.6 * math.sin(2 * math.pi * freq * t + base)
        + 0.4 * math.sin(2 * math.pi * freq * 2.17 * t + base * 1.7)
    )


def _loop_out(value_at_layer_time: float, cycle: float, *, env: EvalEnv) -> float:
    # Placeholder — implemented at the property-track sampling level.
    return value_at_layer_time


def _linear(t: float, a: float, b: float, va: float, vb: float) -> float:
    if t <= a:
        return va
    if t >= b:
        return vb
    if b - a == 0:
        return vb
    return va + (vb - va) * (t - a) / (b - a)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _random(seed: int = 0, *, env: EvalEnv) -> float:
    r = _stdrandom.Random(seed ^ env.seed)
    return r.random()


_SAFE_NAMES = {"pi": math.pi, "e": math.e, "tau": math.tau}

_SAFE_CALLS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "sqrt": math.sqrt,
    "log": math.log,
    "exp": math.exp,
    "pow": math.pow,
    "clamp": _clamp,
}

_ENV_CALLS = {
    "wiggle": _wiggle,
    "loopOut": _loop_out,
    "linear": _linear,
    "random": _random,
}


# ── Parser / evaluator ──────────────────────────────────────────────────────


def _check(node: ast.AST) -> None:
    """Recursively reject non-whitelisted AST nodes."""
    for child in ast.walk(node):
        if not isinstance(child, _ALLOWED_NODES):
            raise ExpressionError(f"Disallowed expression construct: {type(child).__name__}")
        if isinstance(child, ast.Attribute):
            # Only allow attribute access on parent (parent.position, …).
            if not (isinstance(child.value, ast.Name) and child.value.id == "parent"):
                raise ExpressionError("Attribute access only allowed on 'parent'.")


def compile_expression(expr: str) -> Callable[[EvalEnv], Any]:
    """Compile a DSL expression to a callable ``env → value``.

    Raises :class:`ExpressionError` for unsafe or malformed expressions.
    """
    if not isinstance(expr, str) or not expr.strip():
        raise ExpressionError("Empty expression.")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"Syntax error in expression: {exc}") from exc
    _check(tree)

    def evaluate(env: EvalEnv) -> Any:
        return _eval(tree.body, env)

    return evaluate


def _eval(node: ast.AST, env: EvalEnv) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Num):  # py<3.12 fallback
        return node.n
    if isinstance(node, ast.UnaryOp):
        v = _eval(node.operand, env)
        if isinstance(node.op, ast.USub):
            return -v
        if isinstance(node.op, ast.UAdd):
            return +v
        raise ExpressionError(f"Unsupported unary op: {type(node.op).__name__}")
    if isinstance(node, ast.BinOp):
        a = _eval(node.left, env)
        b = _eval(node.right, env)
        op = node.op
        if isinstance(op, ast.Add):
            return _vec_op(a, b, lambda x, y: x + y)
        if isinstance(op, ast.Sub):
            return _vec_op(a, b, lambda x, y: x - y)
        if isinstance(op, ast.Mult):
            return _vec_op(a, b, lambda x, y: x * y)
        if isinstance(op, ast.Div):
            return _vec_op(a, b, lambda x, y: x / y)
        if isinstance(op, ast.FloorDiv):
            return _vec_op(a, b, lambda x, y: x // y)
        if isinstance(op, ast.Mod):
            return _vec_op(a, b, lambda x, y: x % y)
        if isinstance(op, ast.Pow):
            return _vec_op(a, b, lambda x, y: x**y)
        raise ExpressionError(f"Unsupported binary op: {type(op).__name__}")
    if isinstance(node, ast.Name):
        if node.id == "time":
            return env.time
        if node.id == "layer_time":
            return env.layer_time
        if node.id == "duration":
            return env.duration
        if node.id == "fps":
            return env.fps
        if node.id in _SAFE_NAMES:
            return _SAFE_NAMES[node.id]
        if node.id in env.extras:
            return env.extras[node.id]
        raise ExpressionError(f"Unknown identifier: {node.id}")
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval(e, env) for e in node.elts]
    if isinstance(node, ast.Subscript):
        seq = _eval(node.value, env)
        idx = _eval(node.slice, env)
        return seq[int(idx)]
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id == "parent":
            if env.parent_transform is None:
                raise ExpressionError("'parent' is not set on this layer.")
            return getattr(env.parent_transform, node.attr)
        raise ExpressionError("Only parent.<attr> is allowed.")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ExpressionError("Only direct function calls are allowed.")
        fname = node.func.id
        args = [_eval(a, env) for a in node.args]
        kwargs = {kw.arg: _eval(kw.value, env) for kw in node.keywords if kw.arg}
        if fname in _SAFE_CALLS:
            return _SAFE_CALLS[fname](*args, **kwargs)
        if fname in _ENV_CALLS:
            return _ENV_CALLS[fname](*args, env=env, **kwargs)
        raise ExpressionError(f"Unknown function: {fname}")
    raise ExpressionError(f"Unsupported node: {type(node).__name__}")


def _vec_op(a: Any, b: Any, op: Callable[[float, float], float]) -> Any:
    """Operator that broadcasts scalars across lists element-wise."""
    if isinstance(a, list) and isinstance(b, list):
        return [op(x, y) for x, y in zip(a, b)]
    if isinstance(a, list):
        return [op(x, b) for x in a]
    if isinstance(b, list):
        return [op(a, y) for y in b]
    return op(a, b)
