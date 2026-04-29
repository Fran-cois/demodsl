"""Performance tests for browser effects injection and OS background overlay."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from demodsl.effects.browser import register_all_browser_effects
from demodsl.effects.os_background import OsBackgroundOverlay
from demodsl.effects.registry import EffectRegistry
from demodsl.models import DemoConfig, Scenario
from demodsl.models.overlays import BackgroundConfig

ITERATIONS = 200


# ── OS Background Overlay perf ────────────────────────────────────────────────


@pytest.mark.perf
class TestOsBackgroundPerf:
    def test_macos_js_generation(self, perf_timer) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "theme": "dark"})
        result, timer = perf_timer("os_bg_macos_js_gen", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                overlay._build_macos_js()
        assert result.mean_ms < 5

    def test_windows_js_generation(self, perf_timer) -> None:
        overlay = OsBackgroundOverlay({"os": "windows", "theme": "dark"})
        result, timer = perf_timer("os_bg_windows_js_gen", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                overlay._build_windows_js()
        assert result.mean_ms < 5

    def test_macos_inject(self, perf_timer) -> None:
        overlay = OsBackgroundOverlay({"os": "macos"})
        mock_eval = MagicMock()
        result, timer = perf_timer("os_bg_macos_inject", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                overlay.inject(mock_eval)
        assert result.mean_ms < 5

    def test_windows_inject(self, perf_timer) -> None:
        overlay = OsBackgroundOverlay({"os": "windows"})
        mock_eval = MagicMock()
        result, timer = perf_timer("os_bg_windows_inject", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                overlay.inject(mock_eval)
        assert result.mean_ms < 5

    def test_disabled_noop(self, perf_timer) -> None:
        overlay = OsBackgroundOverlay({"enabled": False})
        mock_eval = MagicMock()
        result, timer = perf_timer("os_bg_disabled_noop", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                overlay.inject(mock_eval)
        assert result.mean_ms < 0.5

    def test_init_from_dict(self, perf_timer) -> None:
        config = {
            "os": "macos",
            "theme": "dark",
            "wallpaper_color": "#1a1a2e",
            "window_title": "Test App",
            "show_dock": True,
            "show_menu_bar": True,
        }
        result, timer = perf_timer("os_bg_init", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                OsBackgroundOverlay(config)
        assert result.mean_ms < 1


# ── BackgroundConfig model perf ───────────────────────────────────────────────


@pytest.mark.perf
class TestBackgroundConfigPerf:
    def test_parse_defaults(self, perf_timer) -> None:
        result, timer = perf_timer("bg_config_defaults", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                BackgroundConfig()
        assert result.mean_ms < 10

    def test_parse_full(self, perf_timer) -> None:
        data = {
            "enabled": True,
            "os": "windows",
            "theme": "light",
            "wallpaper_color": "#0c1445",
            "window_title": "Edge",
            "show_dock": True,
            "show_menu_bar": False,
        }
        result, timer = perf_timer("bg_config_full", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                BackgroundConfig(**data)
        assert result.mean_ms < 10

    def test_model_dump(self, perf_timer) -> None:
        cfg = BackgroundConfig(os="macos", theme="dark")
        result, timer = perf_timer("bg_config_dump", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                cfg.model_dump()
        assert result.mean_ms < 5

    def test_scenario_with_background_parse(self, perf_timer) -> None:
        data: dict[str, Any] = {
            "name": "bg_test",
            "url": "https://example.com",
            "steps": [{"action": "navigate", "url": "https://example.com"}],
            "background": {"os": "macos", "theme": "dark", "window_title": "Test"},
        }
        result, timer = perf_timer("scenario_with_bg_parse", ITERATIONS)
        for _ in range(ITERATIONS):
            with timer:
                Scenario(**data)
        assert result.mean_ms < 50


# ── Browser effects injection perf ────────────────────────────────────────────


@pytest.mark.perf
class TestBrowserEffectInjectPerf:
    """Measure JS generation speed for all 67 effects."""

    @pytest.fixture(autouse=True)
    def _setup_registry(self) -> None:
        self.registry = EffectRegistry()
        register_all_browser_effects(self.registry)
        self.mock_eval = MagicMock()

    def test_all_effects_inject_batch(self, perf_timer) -> None:
        """Inject all 67 effects in a single batch — measures total throughput."""
        names = list(self.registry.browser_effects)
        iterations = 50
        result, timer = perf_timer("all_67_effects_inject_batch", iterations)
        for _ in range(iterations):
            with timer:
                for name in names:
                    handler = self.registry.get_browser_effect(name)
                    handler.inject(self.mock_eval, {})
        # All 67 effects injected in under 100ms
        assert result.mean_ms < 100

    @pytest.mark.parametrize(
        "effect_name",
        [
            "spotlight",
            "confetti",
            "chart_draw",
            "skeleton_loading",
            "device_frame",
            "notification_toast",
            "morph_transition",
            "perspective_tilt",
            "glassmorphism_float",
            "dark_mode_toggle",
            "keyboard_shortcut",
            "heatmap",
            "zoom_through",
        ],
    )
    def test_individual_effect_inject(self, perf_timer, effect_name: str) -> None:
        handler = self.registry.get_browser_effect(effect_name)
        iterations = 200
        result, timer = perf_timer(f"inject_{effect_name}", iterations)
        for _ in range(iterations):
            with timer:
                handler.inject(self.mock_eval, {})
        assert result.mean_ms < 5

    def test_effect_js_size_budget(self) -> None:
        """No single effect JS should exceed 20KB — keeps page evaluation fast."""
        for name in self.registry.browser_effects:
            handler = self.registry.get_browser_effect(name)
            capture: list[str] = []
            handler.inject(lambda js: capture.append(js), {})
            js_size = len(capture[0]) if capture else 0
            assert js_size < 20_000, f"Effect '{name}' JS is {js_size} bytes (> 20KB)"


# ── JS generation size benchmarks ─────────────────────────────────────────────


@pytest.mark.perf
class TestJsSizeBenchmarks:
    def test_macos_js_size(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "show_dock": True, "show_menu_bar": True})
        js = overlay._build_macos_js()
        assert len(js) < 15_000, f"macOS JS is {len(js)} bytes"
        assert len(js) > 1_000, "macOS JS suspiciously small"

    def test_windows_js_size(self) -> None:
        overlay = OsBackgroundOverlay({"os": "windows", "show_dock": True})
        js = overlay._build_windows_js()
        assert len(js) < 10_000, f"Windows JS is {len(js)} bytes"
        assert len(js) > 1_000, "Windows JS suspiciously small"

    def test_macos_minimal_js_size(self) -> None:
        overlay = OsBackgroundOverlay({"os": "macos", "show_dock": False, "show_menu_bar": False})
        js = overlay._build_macos_js()
        # Without dock and menu bar, should be significantly smaller
        full_overlay = OsBackgroundOverlay(
            {"os": "macos", "show_dock": True, "show_menu_bar": True}
        )
        full_js = full_overlay._build_macos_js()
        assert len(js) < len(full_js)


# ── Config loading with background ───────────────────────────────────────────


@pytest.mark.perf
class TestConfigWithBackgroundPerf:
    def test_full_config_with_background(self, perf_timer) -> None:
        data: dict[str, Any] = {
            "metadata": {"title": "BG Perf Test", "version": "1"},
            "scenarios": [
                {
                    "name": "s1",
                    "url": "https://example.com",
                    "background": {
                        "os": "macos",
                        "theme": "dark",
                        "wallpaper_color": "#1a1a2e",
                        "window_title": "Perf Test",
                    },
                    "steps": [
                        {"action": "navigate", "url": "https://example.com"},
                        {
                            "action": "click",
                            "locator": {"type": "css", "value": "#btn"},
                            "effects": [{"type": "spotlight"}, {"type": "chart_draw"}],
                        },
                        {
                            "action": "scroll",
                            "direction": "down",
                            "pixels": 300,
                            "effects": [{"type": "skeleton_loading"}],
                        },
                    ],
                }
            ],
        }
        iterations = 100
        result, timer = perf_timer("full_config_with_bg", iterations)
        for _ in range(iterations):
            with timer:
                DemoConfig(**data)
        assert result.mean_ms < 100

    def test_multi_scenario_with_backgrounds(self, perf_timer) -> None:
        scenarios = []
        for i in range(5):
            scenarios.append(
                {
                    "name": f"s{i}",
                    "url": "https://example.com",
                    "background": {
                        "os": "macos" if i % 2 == 0 else "windows",
                        "theme": "dark",
                    },
                    "steps": [
                        {"action": "navigate", "url": "https://example.com"},
                        {
                            "action": "click",
                            "locator": {"type": "css", "value": "#btn"},
                            "effects": [{"type": "confetti"}],
                        },
                    ],
                }
            )
        data: dict[str, Any] = {
            "metadata": {"title": "Multi BG", "version": "1"},
            "scenarios": scenarios,
        }
        iterations = 50
        result, timer = perf_timer("multi_scenario_bg", iterations)
        for _ in range(iterations):
            with timer:
                DemoConfig(**data)
        assert result.mean_ms < 200
