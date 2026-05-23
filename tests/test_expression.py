"""Unit tests for demodsl.effects.expression — sandboxed DSL."""

from __future__ import annotations

import math

import pytest

from demodsl.effects.expression import (
    EvalEnv,
    ExpressionError,
    compile_expression,
)


class _FakeParentTransform:
    position = [100.0, 200.0]
    scale = 1.5
    rotation = 30.0
    opacity = 0.5


# ── Literals & arithmetic ───────────────────────────────────────────────────


class TestArithmetic:
    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("1 + 2", 3),
            ("10 - 4", 6),
            ("3 * 4", 12),
            ("7 / 2", 3.5),
            ("7 // 2", 3),
            ("7 % 3", 1),
            ("2 ** 10", 1024),
            ("-5", -5),
            ("+5", 5),
            ("(1 + 2) * 3", 9),
        ],
    )
    def test_basic(self, expr: str, expected: float) -> None:
        fn = compile_expression(expr)
        assert fn(EvalEnv()) == expected

    def test_list_literal(self) -> None:
        fn = compile_expression("[1, 2, 3]")
        assert fn(EvalEnv()) == [1, 2, 3]

    def test_vec_broadcast_scalar_list(self) -> None:
        fn = compile_expression("[10, 20] + 5")
        assert fn(EvalEnv()) == [15, 25]

    def test_vec_op_two_lists(self) -> None:
        fn = compile_expression("[1, 2] + [10, 20]")
        assert fn(EvalEnv()) == [11, 22]

    def test_subscript(self) -> None:
        fn = compile_expression("[100, 200][1]")
        assert fn(EvalEnv()) == 200


# ── Environment vars ────────────────────────────────────────────────────────


class TestEnvironment:
    def test_time(self) -> None:
        fn = compile_expression("time * 2")
        assert fn(EvalEnv(time=5.0)) == 10.0

    def test_layer_time(self) -> None:
        fn = compile_expression("layer_time")
        assert fn(EvalEnv(layer_time=1.5)) == 1.5

    def test_duration_and_fps(self) -> None:
        fn = compile_expression("duration + fps")
        assert fn(EvalEnv(duration=10.0, fps=30.0)) == 40.0

    def test_unknown_identifier_raises(self) -> None:
        fn = compile_expression("foo")
        with pytest.raises(ExpressionError, match="Unknown identifier"):
            fn(EvalEnv())

    def test_extras(self) -> None:
        fn = compile_expression("x + y")
        env = EvalEnv(extras={"x": 3, "y": 4})
        assert fn(env) == 7


# ── Whitelisted functions ───────────────────────────────────────────────────


class TestFunctions:
    def test_sin_cos(self) -> None:
        fn = compile_expression("sin(0) + cos(0)")
        assert fn(EvalEnv()) == pytest.approx(1.0)

    def test_clamp(self) -> None:
        fn = compile_expression("clamp(15, 0, 10)")
        assert fn(EvalEnv()) == 10
        fn2 = compile_expression("clamp(-5, 0, 10)")
        assert fn2(EvalEnv()) == 0

    def test_min_max_abs(self) -> None:
        assert compile_expression("min(3, 5, 1)")(EvalEnv()) == 1
        assert compile_expression("max(3, 5, 1)")(EvalEnv()) == 5
        assert compile_expression("abs(-7)")(EvalEnv()) == 7

    def test_pi_constant(self) -> None:
        assert compile_expression("pi")(EvalEnv()) == pytest.approx(math.pi)

    def test_wiggle_reproducible(self) -> None:
        fn = compile_expression("wiggle(1, 10)")
        env = EvalEnv(time=0.25, seed=42)
        assert fn(env) == fn(env)

    def test_linear_inside_range(self) -> None:
        fn = compile_expression("linear(time, 0, 1, 0, 100)")
        assert fn(EvalEnv(time=0.5)) == 50.0

    def test_linear_clamps(self) -> None:
        fn = compile_expression("linear(time, 0, 1, 0, 100)")
        assert fn(EvalEnv(time=-1.0)) == 0
        assert fn(EvalEnv(time=2.0)) == 100

    def test_unknown_function(self) -> None:
        fn = compile_expression("foo(1)")
        with pytest.raises(ExpressionError, match="Unknown function"):
            fn(EvalEnv())


# ── Parent attribute access ─────────────────────────────────────────────────


class TestParent:
    def test_parent_position(self) -> None:
        fn = compile_expression("parent.position")
        env = EvalEnv(parent_transform=_FakeParentTransform())
        assert fn(env) == [100.0, 200.0]

    def test_parent_scale(self) -> None:
        fn = compile_expression("parent.scale * 2")
        env = EvalEnv(parent_transform=_FakeParentTransform())
        assert fn(env) == 3.0

    def test_parent_none_raises(self) -> None:
        fn = compile_expression("parent.position")
        with pytest.raises(ExpressionError, match="not set"):
            fn(EvalEnv(parent_transform=None))


# ── Safety / sandbox ────────────────────────────────────────────────────────


class TestSandbox:
    @pytest.mark.parametrize(
        "expr",
        [
            "__import__('os').system('ls')",  # function call ok shape, name unknown
            "().__class__.__bases__",  # attribute on non-parent rejected
            "open('foo')",
            "globals()",
        ],
    )
    def test_rejected_unsafe(self, expr: str) -> None:
        # Either raises at compile (disallowed nodes / attribute rules)
        # or at evaluation (unknown function/identifier).
        try:
            fn = compile_expression(expr)
        except ExpressionError:
            return
        with pytest.raises(ExpressionError):
            fn(EvalEnv())

    def test_attribute_only_on_parent(self) -> None:
        with pytest.raises(ExpressionError, match="parent"):
            compile_expression("time.real")

    def test_empty_expression(self) -> None:
        with pytest.raises(ExpressionError, match="Empty"):
            compile_expression("")

    def test_syntax_error(self) -> None:
        with pytest.raises(ExpressionError, match="Syntax"):
            compile_expression("1 +")

    def test_assignment_rejected(self) -> None:
        # `=` is a Statement which fails `mode='eval'` parsing.
        with pytest.raises(ExpressionError):
            compile_expression("x = 1")

    def test_lambda_rejected(self) -> None:
        with pytest.raises(ExpressionError):
            compile_expression("(lambda: 1)()")

    def test_comprehension_rejected(self) -> None:
        with pytest.raises(ExpressionError):
            compile_expression("[x for x in [1,2,3]]")

    def test_too_long(self) -> None:
        with pytest.raises(ExpressionError, match="too long"):
            compile_expression("1+" * 1100 + "1")

    def test_too_many_nodes(self) -> None:
        # 200 chained additions -> >512 AST nodes
        with pytest.raises(ExpressionError, match="too complex"):
            compile_expression("+".join(["1"] * 300))

    def test_too_deep(self) -> None:
        # Right-associative chain of additions builds a deeply nested tree.
        # Wrap each term in parens to force the parser to keep nesting.
        depth = 40
        expr = "1" + "".join(f"+sin({i})" for i in range(depth))
        # The above is shallow; build a unary-recursive expression instead.
        expr = "-" * 40 + "1"
        with pytest.raises(ExpressionError, match="too deeply"):
            compile_expression(expr)


# ── Comparison & boolean / IfExp ────────────────────────────────────────────


class TestComparison:
    def test_ifexp(self) -> None:
        fn = compile_expression("100 if time > 1 else 0")
        assert fn(EvalEnv(time=2.0)) == 100
        assert fn(EvalEnv(time=0.5)) == 0

    def test_bool_and_or(self) -> None:
        fn = compile_expression("1 if (time > 0 and time < 5) else 0")
        assert fn(EvalEnv(time=2.5)) == 1
        assert fn(EvalEnv(time=10.0)) == 0
