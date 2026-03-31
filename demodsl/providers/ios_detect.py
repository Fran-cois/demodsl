"""Auto-detect a booted iOS simulator via ``xcrun simctl``."""

from __future__ import annotations

import json
import logging
import subprocess

logger = logging.getLogger(__name__)


def detect_booted_simulator() -> dict[str, str] | None:
    """Return ``{'device_name': …, 'udid': …}`` for the first booted iOS sim.

    Returns ``None`` if no simulator is booted or ``xcrun`` is unavailable.
    """
    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "booted", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        devices = data.get("devices", {})
        for _runtime, device_list in devices.items():
            for dev in device_list:
                if dev.get("state") == "Booted":
                    name = dev.get("name", "Unknown")
                    udid = dev.get("udid", "")
                    logger.info(
                        "Auto-detected booted iOS simulator: %s (%s)", name, udid
                    )
                    return {"device_name": name, "udid": udid}
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        logger.debug("xcrun simctl not available — skipping auto-detect")
    return None
