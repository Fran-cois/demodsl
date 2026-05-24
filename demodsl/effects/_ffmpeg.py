"""Centralized ``ffmpeg``/``ffprobe`` subprocess runner.

Replaces the dozens of ad-hoc ``subprocess.run(["ffmpeg", ...], check=True,
capture_output=True, timeout=600)`` call-sites scattered across the pipeline.
Provides:

* consistent timeout default;
* consistent ``check=True`` + stderr-bearing :class:`RuntimeError` on failure;
* uniform logging of the failing command (debug level on success, error on
  failure) for easier post-mortem diagnosis.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Sequence

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 600  # seconds


def run_ffmpeg(
    cmd: Sequence[str],
    *,
    timeout: int | None = DEFAULT_TIMEOUT,
    check: bool = True,
    context: str | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run an ffmpeg/ffprobe command with uniform error handling.

    Parameters
    ----------
    cmd:
        The full argv (first element is usually ``"ffmpeg"`` or ``"ffprobe"``).
    timeout:
        Hard timeout in seconds. ``None`` disables the timeout.
    check:
        Raise :class:`RuntimeError` on non-zero exit when true.
    context:
        Optional short label included in the error message (e.g. ``"restore_audio"``).
    """
    label = context or (cmd[0] if cmd else "ffmpeg")
    logger.debug("%s: %s", label, " ".join(str(a) for a in cmd))
    try:
        return subprocess.run(
            list(cmd),
            capture_output=True,
            timeout=timeout,
            check=check,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error(
            "%s: timed out after %ss — cmd=%s",
            label,
            timeout,
            " ".join(str(a) for a in cmd),
        )
        raise RuntimeError(f"{label}: ffmpeg timed out after {timeout}s") from exc
    except subprocess.CalledProcessError as exc:
        stderr_tail = (exc.stderr or b"").decode("utf-8", errors="replace")[-2000:]
        logger.error(
            "%s: exit=%d cmd=%s\nstderr (tail):\n%s",
            label,
            exc.returncode,
            " ".join(str(a) for a in cmd),
            stderr_tail,
        )
        raise RuntimeError(
            f"{label}: ffmpeg failed (exit {exc.returncode}). stderr tail: {stderr_tail[-400:]}"
        ) from exc
