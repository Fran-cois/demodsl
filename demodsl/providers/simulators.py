"""Local iOS Simulator / Android emulator discovery and boot management.

Pure-subprocess helpers around ``xcrun simctl`` (iOS) and ``adb`` /
``emulator`` (Android). Every function degrades gracefully when the platform
tools are missing — they log at debug level and return empty results instead
of raising, so mobile demos still work against remote or real devices.

The single entry point used by :class:`~demodsl.providers.mobile.AppiumMobileProvider`
is :func:`resolve_local_device`, which turns a ``device_name: auto`` or
``auto_boot: true`` config into a concrete ``(device_name, udid)`` pair,
booting a local simulator/emulator when requested.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demodsl.models import MobileConfig

logger = logging.getLogger(__name__)

_SIMCTL_TIMEOUT = 15
_ADB_TIMEOUT = 15
_POLL_INTERVAL = 2.0


@dataclass(frozen=True)
class SimDevice:
    """A local simulator/emulator instance."""

    platform: str  # "ios" | "android"
    name: str
    udid: str  # iOS UDID or Android serial (e.g. "emulator-5554")
    state: str  # "Booted" | "Shutdown" | "device" | "offline" | …
    runtime: str = ""  # iOS runtime label / Android AVD name

    @property
    def is_booted(self) -> bool:
        return self.state.lower() in ("booted", "device")


# ── iOS (xcrun simctl) ────────────────────────────────────────────────────────


def _xcrun_available() -> bool:
    return shutil.which("xcrun") is not None


def list_ios_simulators() -> list[SimDevice]:
    """List available iOS simulators (all states). Empty if simctl is absent."""
    if not _xcrun_available():
        return []
    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "--json"],
            capture_output=True,
            text=True,
            timeout=_SIMCTL_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("simctl list failed: %s", exc)
        return []
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        logger.debug("simctl JSON parse failed: %s", exc)
        return []

    devices: list[SimDevice] = []
    for runtime, dev_list in data.get("devices", {}).items():
        # e.g. "com.apple.CoreSimulator.SimRuntime.iOS-17-2" → "iOS 17 2"
        runtime_label = runtime.split(".")[-1].replace("-", " ")
        for dev in dev_list:
            if not dev.get("isAvailable", True):
                continue
            devices.append(
                SimDevice(
                    platform="ios",
                    name=dev.get("name", "Unknown"),
                    udid=dev.get("udid", ""),
                    state=dev.get("state", "Unknown"),
                    runtime=runtime_label,
                )
            )
    return devices


def detect_booted_ios() -> SimDevice | None:
    """Return the first booted iOS simulator, or ``None``."""
    for dev in list_ios_simulators():
        if dev.is_booted:
            logger.info("Booted iOS simulator: %s (%s)", dev.name, dev.udid)
            return dev
    return None


def boot_ios(name_or_udid: str, timeout: int = 120) -> SimDevice | None:
    """Boot an iOS simulator by name or UDID and wait until fully booted."""
    if not _xcrun_available():
        logger.warning("xcrun not available — cannot boot iOS simulator")
        return None

    target: SimDevice | None = None
    for dev in list_ios_simulators():
        if name_or_udid in (dev.udid, dev.name):
            target = dev
            break
    if target is None:
        logger.warning("iOS simulator '%s' not found", name_or_udid)
        return None
    if target.is_booted:
        return target

    try:
        # simctl boot exits 0 on success; a non-zero "Unable to boot ...
        # current state Booted" is harmless — bootstatus below is the gate.
        subprocess.run(
            ["xcrun", "simctl", "boot", target.udid],
            capture_output=True,
            text=True,
            timeout=_SIMCTL_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("simctl boot failed: %s", exc)
        return None

    # Bring the Simulator UI to the foreground so the screen is visible.
    if shutil.which("open"):
        subprocess.run(["open", "-a", "Simulator"], capture_output=True)

    # Block until the device reports fully booted (or timeout).
    try:
        subprocess.run(
            ["xcrun", "simctl", "bootstatus", target.udid, "-b"],
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Timed out waiting for iOS simulator '%s' to boot", target.name)
        return None
    except FileNotFoundError:
        return None

    booted = detect_booted_ios()
    if booted and booted.udid == target.udid:
        logger.info("iOS simulator booted: %s", target.name)
        return booted
    return booted


# ── Android (adb + emulator) ──────────────────────────────────────────────────


def _adb_available() -> bool:
    return shutil.which("adb") is not None


def _emulator_bin() -> str | None:
    return shutil.which("emulator")


def list_android_avds() -> list[str]:
    """List defined Android Virtual Devices. Empty if the SDK is absent."""
    emulator = _emulator_bin()
    if not emulator:
        return []
    try:
        result = subprocess.run(
            [emulator, "-list-avds"],
            capture_output=True,
            text=True,
            timeout=_ADB_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("emulator -list-avds failed: %s", exc)
        return []
    if result.returncode != 0:
        return []
    return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]


def _android_avd_name(serial: str) -> str | None:
    """Best-effort AVD name for a running emulator serial."""
    try:
        result = subprocess.run(
            ["adb", "-s", serial, "emu", "avd", "name"],
            capture_output=True,
            text=True,
            timeout=_ADB_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    for ln in result.stdout.splitlines():
        stripped = ln.strip()
        if stripped and stripped != "OK":
            return stripped
    return None


def list_running_android() -> list[SimDevice]:
    """List running Android *emulators* (real/remote devices are excluded)."""
    if not _adb_available():
        return []
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=_ADB_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("adb devices failed: %s", exc)
        return []

    devices: list[SimDevice] = []
    for line in result.stdout.splitlines()[1:]:  # skip "List of devices attached"
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        if not serial.startswith("emulator-"):
            continue  # only local emulators, not physical/remote devices
        name = _android_avd_name(serial) or serial
        devices.append(
            SimDevice(
                platform="android",
                name=name,
                udid=serial,
                state=state,
                runtime=name,
            )
        )
    return devices


def detect_running_android() -> SimDevice | None:
    """Return the first booted Android emulator, or ``None``."""
    for dev in list_running_android():
        if dev.is_booted:
            logger.info("Running Android emulator: %s (%s)", dev.name, dev.udid)
            return dev
    return None


def boot_android(avd: str, timeout: int = 120) -> SimDevice | None:
    """Boot an Android emulator for *avd* and wait until it finishes booting."""
    emulator = _emulator_bin()
    if not emulator or not _adb_available():
        logger.warning("emulator/adb not available — cannot boot Android emulator")
        return None
    if avd not in list_android_avds():
        logger.warning("AVD '%s' not found (run 'emulator -list-avds')", avd)
        return None

    # Launch the emulator detached; it keeps running past this process.
    subprocess.Popen(  # noqa: S603 — args are validated AVD names, not user shell
        [emulator, "-avd", avd, "-no-snapshot-save"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        subprocess.run(["adb", "wait-for-device"], timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("adb wait-for-device failed: %s", exc)
        return None

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = subprocess.run(
                ["adb", "shell", "getprop", "sys.boot_completed"],
                capture_output=True,
                text=True,
                timeout=_ADB_TIMEOUT,
            )
            if r.stdout.strip() == "1":
                logger.info("Android emulator booted: %s", avd)
                return detect_running_android()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        time.sleep(_POLL_INTERVAL)

    logger.warning("Timed out waiting for Android emulator '%s' to boot", avd)
    return None


# ── Unified resolver ──────────────────────────────────────────────────────────


def resolve_local_device(config: MobileConfig) -> tuple[str, str | None]:
    """Resolve a local simulator/emulator into ``(device_name, udid)``.

    Only acts when ``device_name`` is ``"auto"`` or ``auto_boot`` is set;
    otherwise the config values are returned unchanged so remote/real-device
    demos are untouched. Raises :class:`RuntimeError` with an actionable
    message when a local device is required but none can be found or booted.
    """
    device_name = config.device_name
    udid = config.udid
    is_auto = device_name.strip().lower() == "auto"

    if not is_auto and not config.auto_boot:
        return device_name, udid

    if config.platform == "ios":
        booted = detect_booted_ios()
        if booted is None and config.auto_boot:
            target = None if is_auto else device_name
            if target is None:
                sims = list_ios_simulators()
                target = sims[0].name if sims else None
            if target:
                booted = boot_ios(target, config.boot_timeout)
        if booted is None:
            raise RuntimeError(
                "No booted iOS simulator found. Boot one (Simulator.app or "
                "'xcrun simctl boot <name>'), set a concrete 'device_name', "
                "or add 'auto_boot: true' to the mobile config."
            )
        return booted.name, booted.udid

    # Android
    running = detect_running_android()
    if running is None and config.auto_boot:
        avd = config.avd or (None if is_auto else device_name)
        if avd is None:
            avds = list_android_avds()
            avd = avds[0] if avds else None
        if avd:
            running = boot_android(avd, config.boot_timeout)
    if running is None:
        raise RuntimeError(
            "No running Android emulator found. Start one ('emulator -avd "
            "<name>'), set 'avd' + 'auto_boot: true', or use a concrete "
            "'device_name'/'udid'."
        )
    return running.name, running.udid
