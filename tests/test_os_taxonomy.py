"""Tests for the OS usage taxonomy and the os_setting command."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demodsl.commands import OsSettingCommand, get_mobile_command
from demodsl.models import DemoConfig, Locator, MobileConfig, Scenario, Step
from demodsl.os_taxonomy import (
    OS_TAXONOMY,
    OsSetting,
    default_narration,
    get_setting,
    list_settings,
    normalise_bool,
    parse_setting_expr,
    resolve_recipe,
)
from demodsl.providers.base import MobileProvider

# ── parse_setting_expr ────────────────────────────────────────────────────────


class TestParseSettingExpr:
    def test_key_and_value(self) -> None:
        assert parse_setting_expr("network.airplane_mode=on") == ("network.airplane_mode", "on")

    def test_strips_settings_prefix(self) -> None:
        assert parse_setting_expr("settings.network.wifi=off") == ("network.wifi", "off")

    def test_bare_key_no_value(self) -> None:
        assert parse_setting_expr("general.about") == ("general.about", None)

    def test_whitespace_and_empty_value(self) -> None:
        assert parse_setting_expr("  battery.settings =  ") == ("battery.settings", None)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            parse_setting_expr("   ")


# ── normalise_bool ────────────────────────────────────────────────────────────


class TestNormaliseBool:
    @pytest.mark.parametrize("token", ["on", "true", "1", "YES", "Enable", "enabled"])
    def test_truthy(self, token: str) -> None:
        assert normalise_bool(token) is True

    @pytest.mark.parametrize("token", ["off", "false", "0", "no", "Disable", "disabled"])
    def test_falsy(self, token: str) -> None:
        assert normalise_bool(token) is False

    def test_none_defaults_on(self) -> None:
        assert normalise_bool(None) is True

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid boolean"):
            normalise_bool("maybe")


# ── registry lookup ───────────────────────────────────────────────────────────


class TestGetSetting:
    def test_found(self) -> None:
        spec = get_setting("network.airplane_mode")
        assert spec.title == "Airplane Mode"
        assert spec.kind == "toggle"

    def test_strips_prefix(self) -> None:
        assert get_setting("settings.display.dark_mode").key == "display.dark_mode"

    def test_unknown_suggests(self) -> None:
        with pytest.raises(KeyError, match="airplane"):
            get_setting("network.airplanemode")

    def test_list_settings_sorted_nonempty(self) -> None:
        keys = list_settings()
        assert keys == sorted(keys)
        assert "network.airplane_mode" in keys


class TestRegistryIntegrity:
    @pytest.mark.parametrize("key", list(OS_TAXONOMY.keys()))
    def test_key_matches_and_has_recipe(self, key: str) -> None:
        spec = OS_TAXONOMY[key]
        assert spec.key == key
        assert spec.ios is not None or spec.android is not None

    @pytest.mark.parametrize("key", list(OS_TAXONOMY.keys()))
    def test_recipes_have_usable_controls(self, key: str) -> None:
        spec = OS_TAXONOMY[key]
        for recipe in (spec.ios, spec.android):
            if recipe is None:
                continue
            ctrl = recipe.control
            if ctrl.kind == "choice":
                assert ctrl.choices, f"{key}: choice control needs choices"
                # Every choice locator must be a valid DSL Locator.
                for loc in ctrl.choices.values():
                    Locator(**loc)
            else:
                assert ctrl.locator is not None, f"{key}: {ctrl.kind} needs a locator"
                Locator(**ctrl.locator)
            for hop in recipe.path:
                Locator(**hop)


# ── resolve_recipe ────────────────────────────────────────────────────────────


class TestResolveRecipe:
    def test_ios(self) -> None:
        recipe = resolve_recipe("network.airplane_mode", "ios")
        assert recipe.control.kind == "toggle"
        assert recipe.control.locator == {"type": "xpath", "value": "(//XCUIElementTypeSwitch)[1]"}

    def test_android(self) -> None:
        recipe = resolve_recipe("network.airplane_mode", "android")
        assert recipe.path  # Android needs to open Network & internet first

    def test_missing_platform_recipe_raises(self) -> None:
        spec = OsSetting(key="x.y", title="X", kind="open", ios=None, android=None)
        OS_TAXONOMY["x.y"] = spec
        try:
            with pytest.raises(ValueError, match="no recipe"):
                resolve_recipe("x.y", "ios")
        finally:
            del OS_TAXONOMY["x.y"]

    def test_labels_override_navigation(self) -> None:
        localized = {"General": {"type": "text", "value": "Général"}}
        recipe = resolve_recipe("general.about", "ios", labels=localized)
        assert recipe.path[0] == {"type": "text", "value": "Général"}


class TestDefaultNarration:
    def test_toggle_on(self) -> None:
        assert default_narration("network.airplane_mode", "on") == "Turning Airplane Mode on."

    def test_toggle_off(self) -> None:
        assert default_narration("network.airplane_mode", "off") == "Turning Airplane Mode off."

    def test_open(self) -> None:
        assert default_narration("general.about", None) == "Opening About settings."


# ── Step model integration ────────────────────────────────────────────────────


class TestStepModel:
    def test_shorthand_expands(self) -> None:
        step = Step(os="network.airplane_mode=on")
        assert step.action == "os_setting"
        assert step.setting == "network.airplane_mode"
        assert step.value == "on"

    def test_shorthand_strips_prefix(self) -> None:
        step = Step(os="settings.display.dark_mode=off")
        assert step.setting == "display.dark_mode"
        assert step.value == "off"

    def test_structured_form(self) -> None:
        step = Step(action="os_setting", setting="general.about")
        assert step.action == "os_setting"
        assert step.setting == "general.about"

    def test_labels_override_field(self) -> None:
        step = Step(
            action="os_setting",
            setting="general.about",
            labels={"General": {"type": "text", "value": "Général"}},
        )
        assert step.labels == {"General": {"type": "text", "value": "Général"}}

    def test_missing_setting_raises(self) -> None:
        with pytest.raises(ValueError, match="os_setting"):
            Step(action="os_setting")

    def test_valid_in_mobile_scenario(self) -> None:
        scenario = Scenario(
            name="s",
            mobile=MobileConfig(
                platform="ios", device_name="auto", bundle_id="com.apple.Preferences"
            ),
            steps=[Step(os="network.airplane_mode=on", wait=0.0)],
        )
        cfg = DemoConfig(metadata={"title": "t"}, scenarios=[scenario])
        assert cfg.scenarios[0].steps[0].setting == "network.airplane_mode"


# ── OsSettingCommand ──────────────────────────────────────────────────────────


def _mock_mobile(platform: str = "ios") -> MagicMock:
    m = MagicMock(spec=MobileProvider)
    m.platform = platform
    return m


class TestOsSettingCommand:
    def test_registered(self) -> None:
        assert isinstance(get_mobile_command("os_setting"), OsSettingCommand)

    def test_requires_setting(self) -> None:
        m = _mock_mobile()
        with pytest.raises(ValueError, match="requires 'setting'"):
            OsSettingCommand().execute(m, Step(action="os_setting", setting=None))

    def test_unknown_platform_raises(self) -> None:
        m = _mock_mobile(platform="windows")
        with pytest.raises(ValueError, match="known platform"):
            OsSettingCommand().execute(m, Step(os="network.airplane_mode=on"))

    def test_toggle_taps_when_state_differs(self) -> None:
        m = _mock_mobile("ios")
        m.get_attribute.return_value = "0"  # currently off
        OsSettingCommand().execute(m, Step(os="network.airplane_mode=on"))
        m.tap.assert_called_once()  # off → on: one tap

    def test_toggle_is_idempotent_when_already_on(self) -> None:
        m = _mock_mobile("ios")
        m.get_attribute.return_value = "1"  # already on
        OsSettingCommand().execute(m, Step(os="network.airplane_mode=on"))
        m.tap.assert_not_called()  # already on → no tap

    def test_toggle_taps_when_state_unreadable(self) -> None:
        m = _mock_mobile("ios")
        m.get_attribute.return_value = None
        OsSettingCommand().execute(m, Step(os="network.airplane_mode=on"))
        m.tap.assert_called_once()

    def test_open_navigates_and_taps(self) -> None:
        m = _mock_mobile("ios")
        OsSettingCommand().execute(m, Step(os="general.about"))
        # general.about ios: 1 nav hop (General) + 1 tap on About = 2 taps
        assert m.tap.call_count == 2

    def test_choice_taps_mapped_option(self) -> None:
        m = _mock_mobile("ios")
        OsSettingCommand().execute(m, Step(os="display.dark_mode=on"))
        # 1 nav hop (Display & Brightness) + 1 tap on Dark = 2 taps
        assert m.tap.call_count == 2
        last = m.tap.call_args_list[-1]
        assert last.kwargs["locator"].value == "Dark"

    def test_describe(self) -> None:
        desc = OsSettingCommand().describe(Step(os="network.airplane_mode=on"))
        assert "network.airplane_mode" in desc
        assert "on" in desc

    def test_labels_override_localises_nav_hop(self) -> None:
        m = _mock_mobile("ios")
        OsSettingCommand().execute(
            m,
            Step(
                action="os_setting",
                setting="general.about",
                labels={"General": {"type": "text", "value": "Général"}},
            ),
        )
        # first tap is the (localised) navigation hop
        first = m.tap.call_args_list[0]
        assert first.kwargs["locator"].value == "Général"
