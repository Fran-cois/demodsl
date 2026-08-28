"""Tests for the plugin-facing side of the theme system."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from demodsl.models.theme import (
    _BUILTIN_PRESETS,
    THEME_PRESETS,
    ThemeConfig,
    discover_theme_presets,
)
from demodsl.theme import resolve_theme, theme_palette

_WINXP = {
    "accent": "#245EDC",
    "ink": "#0A0A0A",
    "surface": "#ECE9D8",
    "mark_positive": "#008000",
    "mark_negative": "#C00000",
    "font": "Tahoma",
}


@pytest.fixture(autouse=True)
def _restore_presets() -> Any:
    """Discovery mutates a module-level registry — put it back."""
    import demodsl.models.theme as theme_mod

    before = {k: dict(v) for k, v in THEME_PRESETS.items()}
    discovered = theme_mod._presets_discovered
    theme_mod._presets_discovered = False
    yield
    THEME_PRESETS.clear()
    THEME_PRESETS.update(before)
    theme_mod._presets_discovered = discovered


def _entry_point(name: str, obj: Any) -> MagicMock:
    ep = MagicMock()
    ep.name = name
    ep.value = f"acme_themes:{name}"
    ep.load.return_value = obj
    return ep


class TestPresetDiscovery:
    def test_a_mapping_becomes_a_preset_named_after_the_entry_point(self) -> None:
        with patch("importlib.metadata.entry_points", return_value=[_entry_point("winxp", _WINXP)]):
            presets = discover_theme_presets()
        assert presets["winxp"]["accent"] == "#245EDC"

    def test_a_callable_can_contribute_a_family(self) -> None:
        family = {"winxp": _WINXP, "vista": dict(_WINXP, surface="#0A246A", ink="#FFFFFF")}
        ep = _entry_point("old_os", lambda: family)
        with patch("importlib.metadata.entry_points", return_value=[ep]):
            presets = discover_theme_presets()
        assert {"winxp", "vista"} <= set(presets)

    def test_discovered_preset_is_usable_by_name(self) -> None:
        with patch("importlib.metadata.entry_points", return_value=[_entry_point("winxp", _WINXP)]):
            theme = resolve_theme("winxp")
        assert isinstance(theme, ThemeConfig)
        assert theme.font == "Tahoma"

    def test_config_accepts_a_plugin_preset_by_name(self) -> None:
        from demodsl.models import DemoConfig, Metadata, Scenario

        with patch("importlib.metadata.entry_points", return_value=[_entry_point("winxp", _WINXP)]):
            config = DemoConfig(
                metadata=Metadata(title="t"),
                theme="winxp",
                scenarios=[
                    Scenario(
                        name="s",
                        url="https://example.com",
                        steps=[{"action": "pause", "wait": 1}],
                    )
                ],
            )
        assert config.theme is not None
        assert config.theme.accent == "#245EDC"

    def test_builtins_cannot_be_shadowed(self, caplog: pytest.LogCaptureFixture) -> None:
        hijack = _entry_point("neutral", dict(_WINXP))
        with caplog.at_level("WARNING"):
            with patch("importlib.metadata.entry_points", return_value=[hijack]):
                presets = discover_theme_presets()
        assert presets["neutral"]["accent"] == "#2563EB"
        assert "built-in preset" in caplog.text

    def test_an_unreadable_preset_is_refused(self, caplog: pytest.LogCaptureFixture) -> None:
        unreadable = {"accent": "#FFFFFF", "ink": "#FEFEFE", "surface": "#FFFFFF"}
        with caplog.at_level("WARNING"):
            with patch(
                "importlib.metadata.entry_points",
                return_value=[_entry_point("washed", unreadable)],
            ):
                presets = discover_theme_presets()
        assert "washed" not in presets
        assert "Failed to load theme plugin" in caplog.text

    def test_a_broken_plugin_does_not_break_the_others(self) -> None:
        broken = MagicMock()
        broken.name = "broken"
        broken.value = "broken:nope"
        broken.load.side_effect = ImportError("missing dependency")
        with patch(
            "importlib.metadata.entry_points",
            return_value=[broken, _entry_point("winxp", _WINXP)],
        ):
            presets = discover_theme_presets()
        assert "winxp" in presets

    def test_discovery_runs_once(self) -> None:
        with patch("importlib.metadata.entry_points", return_value=[]) as eps:
            discover_theme_presets()
            discover_theme_presets()
        assert eps.call_count == 1

    def test_unknown_name_lists_the_plugin_presets_too(self) -> None:
        with patch("importlib.metadata.entry_points", return_value=[_entry_point("winxp", _WINXP)]):
            with pytest.raises(ValueError, match="winxp"):
                resolve_theme("nope")


class TestThemePalette:
    def test_themeless_is_an_empty_mapping(self) -> None:
        assert theme_palette(None) == {}

    def test_carries_the_raw_tokens(self) -> None:
        palette = theme_palette(_WINXP)
        assert palette["accent"] == "#245EDC"
        assert palette["surface"] == "#ECE9D8"
        assert palette["font"] == "Tahoma"

    def test_derives_what_a_renderer_needs(self) -> None:
        palette = theme_palette(_WINXP)
        for key in ("accent_soft", "accent_strong", "on_accent", "ink_muted", "border"):
            assert palette[key].startswith("#"), key

    def test_on_accent_is_readable(self) -> None:
        from demodsl.color_utils import contrast_ratio

        palette = theme_palette(_WINXP)
        assert (contrast_ratio(palette["on_accent"], palette["accent"]) or 0) >= 4.5

    def test_glow_is_a_four_stop_ramp(self) -> None:
        assert len(theme_palette(_WINXP)["glow"]) == 4

    def test_accepts_a_preset_name(self) -> None:
        assert theme_palette("neutral")["accent"] == "#2563EB"

    def test_accepts_a_theme_instance(self) -> None:
        assert theme_palette(ThemeConfig(**_WINXP))["font"] == "Tahoma"

    def test_reports_light_or_dark(self) -> None:
        assert theme_palette(_WINXP)["is_light"] is True
        assert theme_palette("dark-dev")["is_light"] is False


class TestPipelineContextTheme:
    def test_defaults_to_none(self) -> None:
        from pathlib import Path

        from demodsl.pipeline.stages import PipelineContext

        assert PipelineContext(workspace_root=Path(".")).theme is None

    def test_a_stage_can_read_the_palette_off_the_context(self) -> None:
        from pathlib import Path

        from demodsl.pipeline.stages import PipelineContext

        ctx = PipelineContext(workspace_root=Path("."), theme=ThemeConfig(**_WINXP))
        assert theme_palette(ctx.theme)["accent"] == "#245EDC"
