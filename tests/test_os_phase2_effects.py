"""Unit tests for Phase 2+3 macOS overlay effects."""

from __future__ import annotations

from unittest.mock import MagicMock

from demodsl.effects.browser import (
    _BROWSER_EFFECTS,
    ControlCenterEffect,
    LaunchpadEffect,
    MissionControlEffect,
    NotificationCenterEffect,
    SpotlightSearchEffect,
    SystemSettingsEffect,
)
from demodsl.models import Effect


# ── Spotlight search ──────────────────────────────────────────────────────────


class TestSpotlightSearch:
    def test_default_generates_js(self) -> None:
        m = MagicMock()
        SpotlightSearchEffect().inject(m, {})
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "__demodsl_spotlight_search" in js
        assert "Visual Studio" in js  # default query
        assert "Top Hit" in js

    def test_custom_query_and_typing_speed(self) -> None:
        m = MagicMock()
        SpotlightSearchEffect().inject(m, {"query": "Terminal", "typing_speed": 0.03})
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "'Terminal'" in js
        assert "30" in js  # typing_speed * 1000

    def test_custom_results(self) -> None:
        m = MagicMock()
        SpotlightSearchEffect().inject(
            m,
            {
                "query": "foo",
                "results": [
                    {"icon": "X", "name": "My App", "subtitle": "subtitle"},
                ],
            },
        )
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "My App" in js

    def test_xss_escaped(self) -> None:
        m = MagicMock()
        SpotlightSearchEffect().inject(
            m,
            {
                "query": "<script>alert(1)</script>",
            },
        )
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "<script>" not in js


# ── Control Center ────────────────────────────────────────────────────────────


class TestControlCenter:
    def test_default(self) -> None:
        m = MagicMock()
        ControlCenterEffect().inject(m, {})
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "__demodsl_control_center" in js
        assert "Wi-Fi" in js
        assert "Bluetooth" in js

    def test_wifi_off_shows_off(self) -> None:
        m = MagicMock()
        ControlCenterEffect().inject(m, {"wifi": False, "bluetooth": False})
        js = "".join(c.args[0] for c in m.call_args_list)
        # both should show Off label
        assert js.count("Off") >= 2

    def test_brightness_percent(self) -> None:
        m = MagicMock()
        ControlCenterEffect().inject(m, {"brightness": 0.25, "volume": 0.9})
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "25%" in js
        assert "90%" in js


# ── Notification Center ───────────────────────────────────────────────────────


class TestNotificationCenter:
    def test_default(self) -> None:
        m = MagicMock()
        NotificationCenterEffect().inject(m, {})
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "__demodsl_notification_center" in js
        assert "Messages" in js

    def test_custom_notifications(self) -> None:
        m = MagicMock()
        NotificationCenterEffect().inject(
            m,
            {
                "notifications": [
                    {
                        "app": "Slack",
                        "icon": "#",
                        "title": "New msg",
                        "body": "hi",
                        "time": "now",
                    },
                ],
                "show_widgets": False,
            },
        )
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "Slack" in js
        assert "Weather" not in js  # widgets disabled

    def test_widgets_on(self) -> None:
        m = MagicMock()
        NotificationCenterEffect().inject(m, {"show_widgets": True})
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "Weather" in js


# ── Mission Control ───────────────────────────────────────────────────────────


class TestMissionControl:
    def test_default(self) -> None:
        m = MagicMock()
        MissionControlEffect().inject(m, {})
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "__demodsl_mission_control" in js
        assert "Safari" in js

    def test_custom_windows(self) -> None:
        m = MagicMock()
        MissionControlEffect().inject(
            m,
            {
                "windows": [
                    {"title": "MyApp", "color": "#123456"},
                ],
            },
        )
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "MyApp" in js
        assert "#123456" in js


# ── Launchpad ─────────────────────────────────────────────────────────────────


class TestLaunchpad:
    def test_default(self) -> None:
        m = MagicMock()
        LaunchpadEffect().inject(m, {})
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "__demodsl_launchpad" in js
        assert "Safari" in js

    def test_highlight_glow(self) -> None:
        m = MagicMock()
        LaunchpadEffect().inject(m, {"highlight": 0})
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "0 0 40px" in js


# ── System Settings ───────────────────────────────────────────────────────────


class TestSystemSettings:
    def test_default_wifi(self) -> None:
        m = MagicMock()
        SystemSettingsEffect().inject(m, {})
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "__demodsl_system_settings" in js
        assert "Wi-Fi" in js
        assert "Home-WiFi" in js

    def test_category_appearance(self) -> None:
        m = MagicMock()
        SystemSettingsEffect().inject(m, {"category": "Appearance"})
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "Appearance" in js
        assert "Light" in js  # segmented control

    def test_custom_items(self) -> None:
        m = MagicMock()
        SystemSettingsEffect().inject(
            m,
            {
                "category": "Custom",
                "items": [
                    {"label": "My Setting", "type": "toggle", "on": True},
                ],
            },
        )
        js = "".join(c.args[0] for c in m.call_args_list)
        assert "My Setting" in js


# ── Registration ──────────────────────────────────────────────────────────────


class TestRegistration:
    def test_all_phase2_3_registered(self) -> None:
        for name in (
            "spotlight_search",
            "control_center",
            "notification_center",
            "mission_control",
            "launchpad",
            "system_settings",
        ):
            assert name in _BROWSER_EFFECTS

    def test_model_accepts_phase2_3(self) -> None:
        Effect(type="spotlight_search", query="q", typing_speed=0.1)
        Effect(type="control_center", wifi=True, brightness=0.5)
        Effect(type="notification_center", show_widgets=True)
        Effect(
            type="mission_control",
            highlight=1,
            windows=[{"title": "x", "color": "#000"}],
        )
        Effect(type="launchpad", highlight=0)
        Effect(type="system_settings", category="Wi-Fi")
