"""Tests for local simulator/emulator discovery and boot management."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from demodsl.models import MobileConfig
from demodsl.providers import simulators
from demodsl.providers.simulators import (
    SimDevice,
    boot_android,
    detect_booted_ios,
    detect_running_android,
    list_android_avds,
    list_ios_simulators,
    list_running_android,
    resolve_local_device,
)

# ── Fixtures / helpers ────────────────────────────────────────────────────────

_SIMCTL_JSON = json.dumps(
    {
        "devices": {
            "com.apple.CoreSimulator.SimRuntime.iOS-17-2": [
                {
                    "name": "iPhone 15 Pro",
                    "udid": "AAAA-1111",
                    "state": "Booted",
                    "isAvailable": True,
                },
                {
                    "name": "iPhone 15",
                    "udid": "BBBB-2222",
                    "state": "Shutdown",
                    "isAvailable": True,
                },
                {
                    "name": "Retired",
                    "udid": "CCCC-3333",
                    "state": "Shutdown",
                    "isAvailable": False,
                },
            ]
        }
    }
)

_ADB_DEVICES = "List of devices attached\nemulator-5554\tdevice\n192.168.1.5:5555\tdevice\n"


def _completed(stdout: str = "", returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    m.returncode = returncode
    return m


# ── SimDevice ─────────────────────────────────────────────────────────────────


class TestSimDevice:
    def test_is_booted_ios(self) -> None:
        assert SimDevice("ios", "iPhone", "u", "Booted").is_booted
        assert not SimDevice("ios", "iPhone", "u", "Shutdown").is_booted

    def test_is_booted_android(self) -> None:
        assert SimDevice("android", "avd", "emulator-5554", "device").is_booted
        assert not SimDevice("android", "avd", "emulator-5554", "offline").is_booted


# ── iOS ───────────────────────────────────────────────────────────────────────


class TestIOSDiscovery:
    def test_list_none_without_xcrun(self) -> None:
        with patch.object(simulators.shutil, "which", return_value=None):
            assert list_ios_simulators() == []

    def test_list_parses_and_filters_unavailable(self) -> None:
        with (
            patch.object(simulators.shutil, "which", return_value="/usr/bin/xcrun"),
            patch.object(simulators.subprocess, "run", return_value=_completed(_SIMCTL_JSON)),
        ):
            sims = list_ios_simulators()
        names = [s.name for s in sims]
        assert names == ["iPhone 15 Pro", "iPhone 15"]  # "Retired" filtered out
        assert sims[0].runtime == "iOS 17 2"

    def test_detect_booted(self) -> None:
        with (
            patch.object(simulators.shutil, "which", return_value="/usr/bin/xcrun"),
            patch.object(simulators.subprocess, "run", return_value=_completed(_SIMCTL_JSON)),
        ):
            booted = detect_booted_ios()
        assert booted is not None
        assert booted.udid == "AAAA-1111"

    def test_list_empty_on_bad_json(self) -> None:
        with (
            patch.object(simulators.shutil, "which", return_value="/usr/bin/xcrun"),
            patch.object(simulators.subprocess, "run", return_value=_completed("not json")),
        ):
            assert list_ios_simulators() == []

    def test_list_empty_on_timeout(self) -> None:
        with (
            patch.object(simulators.shutil, "which", return_value="/usr/bin/xcrun"),
            patch.object(
                simulators.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("xcrun", 15),
            ),
        ):
            assert list_ios_simulators() == []


# ── Android ───────────────────────────────────────────────────────────────────


class TestAndroidDiscovery:
    def test_avds_none_without_emulator(self) -> None:
        with patch.object(simulators.shutil, "which", return_value=None):
            assert list_android_avds() == []

    def test_list_avds(self) -> None:
        with (
            patch.object(simulators.shutil, "which", return_value="/sdk/emulator"),
            patch.object(
                simulators.subprocess, "run", return_value=_completed("Pixel_7_API_34\nTablet\n")
            ),
        ):
            assert list_android_avds() == ["Pixel_7_API_34", "Tablet"]

    def test_running_excludes_physical_devices(self) -> None:
        def _fake_run(cmd, *a, **k):
            if cmd[:2] == ["adb", "devices"]:
                return _completed(_ADB_DEVICES)
            # avd name lookup
            return _completed("OK\nPixel_7_API_34\n")

        with (
            patch.object(simulators.shutil, "which", return_value="/sdk/adb"),
            patch.object(simulators.subprocess, "run", side_effect=_fake_run),
        ):
            running = list_running_android()
        # Only the emulator-5554 serial, not the 192.168.* physical device
        assert len(running) == 1
        assert running[0].udid == "emulator-5554"
        assert running[0].name == "Pixel_7_API_34"
        assert running[0].is_booted

    def test_detect_running(self) -> None:
        def _fake_run(cmd, *a, **k):
            if cmd[:2] == ["adb", "devices"]:
                return _completed("List of devices attached\nemulator-5554\tdevice\n")
            return _completed("OK\nmy_avd\n")

        with (
            patch.object(simulators.shutil, "which", return_value="/sdk/adb"),
            patch.object(simulators.subprocess, "run", side_effect=_fake_run),
        ):
            dev = detect_running_android()
        assert dev is not None
        assert dev.udid == "emulator-5554"

    def test_boot_android_missing_avd(self) -> None:
        with (
            patch.object(simulators.shutil, "which", return_value="/sdk/emulator"),
            patch.object(simulators.subprocess, "run", return_value=_completed("other_avd\n")),
        ):
            assert boot_android("nope") is None


# ── resolve_local_device ──────────────────────────────────────────────────────


class TestResolveLocalDevice:
    def test_passthrough_when_concrete(self) -> None:
        cfg = MobileConfig(platform="ios", device_name="iPhone 15 Pro", bundle_id="com.x")
        # No patching needed: resolver must not touch subprocess.
        name, udid = resolve_local_device(cfg)
        assert name == "iPhone 15 Pro"
        assert udid is None

    def test_ios_auto_uses_booted(self) -> None:
        cfg = MobileConfig(platform="ios", device_name="auto", bundle_id="com.x")
        with patch.object(
            simulators,
            "detect_booted_ios",
            return_value=SimDevice("ios", "iPhone 15 Pro", "AAAA-1111", "Booted"),
        ):
            name, udid = resolve_local_device(cfg)
        assert name == "iPhone 15 Pro"
        assert udid == "AAAA-1111"

    def test_ios_auto_no_device_raises(self) -> None:
        cfg = MobileConfig(platform="ios", device_name="auto", bundle_id="com.x")
        with patch.object(simulators, "detect_booted_ios", return_value=None):
            with pytest.raises(RuntimeError, match="No booted iOS simulator"):
                resolve_local_device(cfg)

    def test_ios_auto_boot_named(self) -> None:
        cfg = MobileConfig(
            platform="ios",
            device_name="iPhone 15",
            bundle_id="com.x",
            auto_boot=True,
        )
        booted = SimDevice("ios", "iPhone 15", "BBBB-2222", "Booted")
        with (
            patch.object(simulators, "detect_booted_ios", return_value=None),
            patch.object(simulators, "boot_ios", return_value=booted) as boot,
        ):
            name, udid = resolve_local_device(cfg)
        boot.assert_called_once_with("iPhone 15", 120)
        assert udid == "BBBB-2222"

    def test_android_auto_uses_running(self) -> None:
        cfg = MobileConfig(platform="android", device_name="auto", app_package="com.x")
        with patch.object(
            simulators,
            "detect_running_android",
            return_value=SimDevice("android", "Pixel_7", "emulator-5554", "device"),
        ):
            name, udid = resolve_local_device(cfg)
        assert udid == "emulator-5554"

    def test_android_auto_boot_uses_avd(self) -> None:
        cfg = MobileConfig(
            platform="android",
            device_name="auto",
            app_package="com.x",
            auto_boot=True,
            avd="Pixel_7_API_34",
        )
        booted = SimDevice("android", "Pixel_7_API_34", "emulator-5554", "device")
        with (
            patch.object(simulators, "detect_running_android", return_value=None),
            patch.object(simulators, "boot_android", return_value=booted) as boot,
        ):
            name, udid = resolve_local_device(cfg)
        boot.assert_called_once_with("Pixel_7_API_34", 120)
        assert udid == "emulator-5554"

    def test_android_no_emulator_raises(self) -> None:
        cfg = MobileConfig(platform="android", device_name="auto", app_package="com.x")
        with patch.object(simulators, "detect_running_android", return_value=None):
            with pytest.raises(RuntimeError, match="No running Android emulator"):
                resolve_local_device(cfg)
