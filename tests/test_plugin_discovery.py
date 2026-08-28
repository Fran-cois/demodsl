"""Tests for the plugin entry-point loaders in demodsl.engine."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from demodsl.effects.registry import BrowserEffect, EffectRegistry
from demodsl.engine import (
    _accepts_one_arg,
    _discover_effect_plugins,
    _pre_register_plugin_effect_types,
)
from demodsl.models.effects import (
    _PLUGIN_EFFECT_TYPES,
    EFFECT_VALID_PARAMS,
    register_plugin_effect_type,
)


class _PluginEffect(BrowserEffect):
    effect_id = "acme_effect"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        pass


def _entry_point(name: str, obj: Any) -> MagicMock:
    ep = MagicMock()
    ep.name = name
    ep.value = f"acme_pkg:{name}"
    ep.load.return_value = obj
    return ep


@pytest.fixture(autouse=True)
def _restore_plugin_globals() -> Any:
    types_before = set(_PLUGIN_EFFECT_TYPES)
    params_before = {k: set(v) for k, v in EFFECT_VALID_PARAMS.items()}
    yield
    _PLUGIN_EFFECT_TYPES.clear()
    _PLUGIN_EFFECT_TYPES.update(types_before)
    EFFECT_VALID_PARAMS.clear()
    EFFECT_VALID_PARAMS.update(params_before)


# ── _accepts_one_arg ──────────────────────────────────────────────────────────


class TestAcceptsOneArg:
    def test_one_positional(self) -> None:
        assert _accepts_one_arg(lambda registry: None) is True

    def test_no_argument(self) -> None:
        assert _accepts_one_arg(lambda: None) is False

    def test_two_required_arguments(self) -> None:
        assert _accepts_one_arg(lambda a, b: None) is False

    def test_var_args(self) -> None:
        assert _accepts_one_arg(lambda *a: None) is True


# ── _discover_effect_plugins ──────────────────────────────────────────────────


class TestDiscoverEffectPlugins:
    def test_registers_a_subclass_under_the_entry_point_name(self) -> None:
        reg = EffectRegistry()
        with patch(
            "importlib.metadata.entry_points", return_value=[_entry_point("acme", _PluginEffect)]
        ):
            _discover_effect_plugins(reg)
        assert reg.is_browser_effect("acme")
        assert "acme" in _PLUGIN_EFFECT_TYPES

    def test_registers_an_instance(self) -> None:
        reg = EffectRegistry()
        ep = _entry_point("acme", _PluginEffect())
        with patch("importlib.metadata.entry_points", return_value=[ep]):
            _discover_effect_plugins(reg)
        assert reg.is_browser_effect("acme")

    def test_register_callable_taking_the_registry(self) -> None:
        reg = EffectRegistry()

        def register(registry: Any) -> None:
            registry.register_browser("from_callable", _PluginEffect())

        with patch(
            "importlib.metadata.entry_points", return_value=[_entry_point("acme", register)]
        ):
            _discover_effect_plugins(reg)
        assert reg.is_browser_effect("from_callable")

    def test_register_callable_returning_a_mapping(self) -> None:
        reg = EffectRegistry()
        with patch(
            "importlib.metadata.entry_points",
            return_value=[_entry_point("acme", lambda: {"from_mapping": _PluginEffect})],
        ):
            _discover_effect_plugins(reg)
        assert reg.is_browser_effect("from_mapping")

    def test_a_typeerror_inside_register_is_not_retried_without_the_registry(self) -> None:
        """The old ``except TypeError`` fallback masked real plugin bugs."""
        calls: list[int] = []

        def register(registry: Any) -> None:
            calls.append(len(calls))
            raise TypeError("bug inside the plugin")

        reg = EffectRegistry()
        with patch(
            "importlib.metadata.entry_points", return_value=[_entry_point("acme", register)]
        ):
            _discover_effect_plugins(reg)
        assert len(calls) == 1

    def test_a_broken_plugin_does_not_stop_the_others(self) -> None:
        broken = MagicMock()
        broken.name = "broken"
        broken.value = "broken_pkg:nope"
        broken.load.side_effect = ImportError("missing dependency")
        reg = EffectRegistry()
        with patch(
            "importlib.metadata.entry_points",
            return_value=[broken, _entry_point("acme", _PluginEffect)],
        ):
            _discover_effect_plugins(reg)
        assert reg.is_browser_effect("acme")

    def test_unsupported_object_is_skipped(self) -> None:
        reg = EffectRegistry()
        with patch("importlib.metadata.entry_points", return_value=[_entry_point("acme", 42)]):
            _discover_effect_plugins(reg)
        assert not reg.is_browser_effect("acme")


# ── register_plugin_effect_type ───────────────────────────────────────────────


class TestRegisterPluginEffectType:
    def test_new_name_takes_the_given_params(self) -> None:
        register_plugin_effect_type("acme_effect", valid_params={"a", "b"})
        assert EFFECT_VALID_PARAMS["acme_effect"] == {"a", "b"}

    def test_redefining_a_core_effect_unions_instead_of_shrinking(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        core_params = set(EFFECT_VALID_PARAMS["retro_browser"])
        with caplog.at_level("WARNING"):
            register_plugin_effect_type("retro_browser", valid_params={"text"})
        assert core_params <= EFFECT_VALID_PARAMS["retro_browser"]
        assert "already declares params" in caplog.text

    def test_identical_params_are_silent(self, caplog: pytest.LogCaptureFixture) -> None:
        same = set(EFFECT_VALID_PARAMS["retro_browser"])
        with caplog.at_level("WARNING"):
            register_plugin_effect_type("retro_browser", valid_params=same)
        assert caplog.text == ""


class TestPreRegistration:
    """Effect types must be known before the config is parsed."""

    def test_a_single_effect_plugin_registers_its_entry_point_name(self) -> None:
        with patch(
            "importlib.metadata.entry_points", return_value=[_entry_point("acme", _PluginEffect)]
        ):
            _pre_register_plugin_effect_types()
        assert "acme" in _PLUGIN_EFFECT_TYPES

    def test_a_multi_effect_plugin_registers_every_real_name(self) -> None:
        """The names only exist inside register(), which has to run early too."""

        def register(registry: Any) -> dict[str, Any]:
            register_plugin_effect_type("acme_editor", {"accent"})
            register_plugin_effect_type("acme_writer", {"accent"})
            return {}

        with patch(
            "importlib.metadata.entry_points", return_value=[_entry_point("acme_apps", register)]
        ):
            _pre_register_plugin_effect_types()
        assert {"acme_editor", "acme_writer"} <= _PLUGIN_EFFECT_TYPES

    def test_the_declared_params_come_along(self) -> None:
        def register(registry: Any) -> dict[str, Any]:
            register_plugin_effect_type("acme_editor", {"accent", "code"})
            return {}

        with patch(
            "importlib.metadata.entry_points", return_value=[_entry_point("acme_apps", register)]
        ):
            _pre_register_plugin_effect_types()
        assert EFFECT_VALID_PARAMS["acme_editor"] == {"accent", "code"}

    def test_the_model_then_accepts_the_effect(self) -> None:
        from demodsl.models import Effect

        def register(registry: Any) -> dict[str, Any]:
            register_plugin_effect_type("acme_editor", {"accent"})
            return {}

        with patch(
            "importlib.metadata.entry_points", return_value=[_entry_point("acme_apps", register)]
        ):
            _pre_register_plugin_effect_types()
        assert Effect(type="acme_editor").type == "acme_editor"

    def test_a_broken_plugin_does_not_stop_pre_registration(self) -> None:
        broken = MagicMock()
        broken.name = "broken"
        broken.value = "broken:nope"
        broken.load.side_effect = ImportError("missing dependency")
        with patch(
            "importlib.metadata.entry_points",
            return_value=[broken, _entry_point("acme", _PluginEffect)],
        ):
            _pre_register_plugin_effect_types()
        assert "acme" in _PLUGIN_EFFECT_TYPES

    def test_it_stays_quiet(self, caplog: pytest.LogCaptureFixture) -> None:
        """Discovery proper logs the plugins; the pre-pass must not double it."""
        with caplog.at_level("INFO"):
            with patch(
                "importlib.metadata.entry_points",
                return_value=[_entry_point("acme", _PluginEffect)],
            ):
                _pre_register_plugin_effect_types()
        assert "Discovered browser effect plugin" not in caplog.text
