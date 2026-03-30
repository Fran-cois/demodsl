"""Tests for demodsl.effects.sanitize — input sanitization for browser effects."""

from __future__ import annotations

import pytest

from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_css_colors_list,
    sanitize_css_position,
    sanitize_css_selector,
    sanitize_html_text,
    sanitize_js_string,
    sanitize_number,
)


# ── sanitize_css_color ────────────────────────────────────────────────────────


class TestSanitizeCssColor:
    @pytest.mark.parametrize(
        "color", ["#fff", "#FFF", "#aabbcc", "#AABBCC", "#aabbccdd"]
    )
    def test_valid_hex(self, color: str) -> None:
        assert sanitize_css_color(color) == color

    @pytest.mark.parametrize("color", ["red", "blue", "transparent", "currentcolor"])
    def test_named_colors(self, color: str) -> None:
        assert sanitize_css_color(color) == color

    def test_rgb(self) -> None:
        assert sanitize_css_color("rgb(255, 0, 128)") == "rgb(255, 0, 128)"

    def test_rgba(self) -> None:
        assert sanitize_css_color("rgba(255, 0, 128, 0.5)") == "rgba(255, 0, 128, 0.5)"

    def test_hsl(self) -> None:
        assert sanitize_css_color("hsl(120, 100%, 50%)") == "hsl(120, 100%, 50%)"

    def test_hsla(self) -> None:
        assert (
            sanitize_css_color("hsla(120, 100%, 50%, 0.7)")
            == "hsla(120, 100%, 50%, 0.7)"
        )

    @pytest.mark.parametrize(
        "malicious",
        [
            "red; background: url(evil)",
            "#fff; } * { display: none",
            "expression(alert(1))",
            "javascript:alert(1)",
            "'; DROP TABLE users; --",
            "</style><script>alert(1)</script>",
        ],
    )
    def test_rejects_malicious_values(self, malicious: str) -> None:
        assert sanitize_css_color(malicious) == "#888888"

    def test_strips_whitespace(self) -> None:
        assert sanitize_css_color("  #ff0000  ") == "#ff0000"


# ── sanitize_number ──────────────────────────────────────────────────────────


class TestSanitizeNumber:
    def test_valid_float(self) -> None:
        assert sanitize_number(0.5) == 0.5

    def test_valid_int(self) -> None:
        assert sanitize_number(3) == 3.0

    def test_string_number(self) -> None:
        assert sanitize_number("1.5") == 1.5

    def test_invalid_string_returns_default(self) -> None:
        assert sanitize_number("abc", default=0.8) == 0.8

    def test_none_returns_default(self) -> None:
        assert sanitize_number(None, default=1.0) == 1.0  # type: ignore[arg-type]

    def test_clamps_min(self) -> None:
        assert sanitize_number(-5.0, min_val=0.0) == 0.0

    def test_clamps_max(self) -> None:
        assert sanitize_number(100.0, max_val=1.0) == 1.0

    def test_clamps_both(self) -> None:
        assert sanitize_number(50.0, min_val=0.0, max_val=10.0) == 10.0


# ── sanitize_html_text ───────────────────────────────────────────────────────


class TestSanitizeHtmlText:
    def test_plain_text(self) -> None:
        assert sanitize_html_text("Hello world") == "Hello world"

    def test_escapes_angle_brackets(self) -> None:
        assert (
            sanitize_html_text("<script>alert(1)</script>")
            == "&lt;script&gt;alert(1)&lt;/script&gt;"
        )

    def test_escapes_ampersand(self) -> None:
        assert sanitize_html_text("A & B") == "A &amp; B"

    def test_escapes_quotes(self) -> None:
        assert sanitize_html_text('He said "hello"') == "He said &quot;hello&quot;"

    def test_escapes_single_quotes(self) -> None:
        assert sanitize_html_text("it's") == "it&#x27;s"


# ── sanitize_js_string ──────────────────────────────────────────────────────


class TestSanitizeJsString:
    def test_plain_text(self) -> None:
        assert sanitize_js_string("Hello") == "Hello"

    def test_escapes_single_quote(self) -> None:
        assert sanitize_js_string("it's") == "it\\'s"

    def test_escapes_double_quote(self) -> None:
        assert sanitize_js_string('say "hi"') == 'say \\"hi\\"'

    def test_escapes_backslash(self) -> None:
        assert sanitize_js_string("a\\b") == "a\\\\b"

    def test_escapes_backtick(self) -> None:
        assert sanitize_js_string("hello`world") == "hello\\`world"

    def test_escapes_template_literal(self) -> None:
        assert sanitize_js_string("${evil}") == "\\${evil}"

    def test_escapes_closing_script(self) -> None:
        assert sanitize_js_string("</script>") == "<\\/script>"

    def test_escapes_newlines(self) -> None:
        assert sanitize_js_string("line1\nline2") == "line1\\nline2"

    @pytest.mark.parametrize(
        "malicious",
        [
            "'; alert(document.cookie); //",
            '"; document.location="evil.com"; //',
            "${document.cookie}",
            "`+alert(1)+`",
        ],
    )
    def test_neutralizes_injection_attempts(self, malicious: str) -> None:
        sanitized = sanitize_js_string(malicious)
        # Dangerous characters are escaped
        assert sanitized != malicious
        assert "${" not in sanitized or "\\${" in sanitized  # template literals escaped
        assert "`" not in sanitized or "\\`" in sanitized  # backticks escaped


# ── sanitize_css_position ────────────────────────────────────────────────────


class TestSanitizeCssPosition:
    def test_valid_position(self) -> None:
        assert sanitize_css_position("top-right") == "top-right"

    def test_invalid_returns_default(self) -> None:
        result = sanitize_css_position("evil; display:none")
        assert result in {
            "top",
            "bottom",
            "left",
            "right",
            "center",
            "top-left",
            "top-right",
            "bottom-left",
            "bottom-right",
            "top-center",
            "bottom-center",
        }

    def test_custom_allowed_set(self) -> None:
        result = sanitize_css_position("top", allowed=frozenset({"top", "bottom"}))
        assert result == "top"

    def test_custom_allowed_rejects(self) -> None:
        result = sanitize_css_position("left", allowed=frozenset({"top", "bottom"}))
        assert result in {"top", "bottom"}


# ── sanitize_css_colors_list ─────────────────────────────────────────────────


class TestSanitizeCssColorsList:
    def test_all_valid(self) -> None:
        result = sanitize_css_colors_list(["#ff0000", "blue", "rgb(0,0,0)"])
        assert result == ["#ff0000", "blue", "rgb(0,0,0)"]

    def test_some_invalid(self) -> None:
        result = sanitize_css_colors_list(["#ff0000", "evil;code", "blue"])
        assert result == ["#ff0000", "#888888", "blue"]


# ── sanitize_css_selector ────────────────────────────────────────────────────────


class TestSanitizeCssSelector:
    @pytest.mark.parametrize(
        "selector",
        [
            ".error-500",
            "#my-id",
            "div",
            "div.cls",
            "div > span",
            "[data-error='true']",
            "ul li:nth-child(2)",
            "body *",
            "h1, h2, h3",
            "a + b ~ c",
        ],
    )
    def test_valid_selectors(self, selector: str) -> None:
        assert sanitize_css_selector(selector) == selector

    def test_strips_whitespace(self) -> None:
        assert sanitize_css_selector("  .error  ") == ".error"

    @pytest.mark.parametrize(
        "selector",
        [
            ".err{color:red}",
            ".err;alert(1)",
            "div}body{background:red",
            ".err\x00",
        ],
    )
    def test_rejects_dangerous_selectors(self, selector: str) -> None:
        with pytest.raises(ValueError, match="disallowed characters"):
            sanitize_css_selector(selector)

    def test_empty_selector_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            sanitize_css_selector("")

    def test_whitespace_only_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            sanitize_css_selector("   ")
