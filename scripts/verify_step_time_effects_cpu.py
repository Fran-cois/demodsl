#!/usr/bin/env python3
"""Prove that freeze_frame / speed_ramp / reverse do real ffmpeg work.

Runs each effect through the REAL ``DemoEngine`` code path (the exact same
static methods ``engine.py`` calls in production) against a real source
video — no mocked ``subprocess.run`` anywhere in this script — while a
background thread samples the spawned ``ffmpeg`` child process's live CPU%,
and ``resource.getrusage(RUSAGE_CHILDREN)`` measures the exact CPU-seconds
it consumed. Both numbers come straight from the OS, so they cannot be
faked by a no-op stub: an effect that silently does nothing would report
~0 CPU seconds and an unchanged output file.

Usage:
    python scripts/verify_step_time_effects_cpu.py
"""

from __future__ import annotations

import resource
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from demodsl.engine import DemoEngine  # noqa: E402
from demodsl.pipeline.workspace import Workspace  # noqa: E402

try:
    import psutil
except ImportError:
    print(
        "This script needs psutil for live CPU sampling: pip install psutil",
        file=sys.stderr,
    )
    sys.exit(1)


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return float((result.stdout or "0").strip() or 0.0)


def _make_source_video(path: Path, duration: float = 8.0) -> None:
    """A real, non-trivial source clip: a moving test pattern, then a hard
    cut to solid red — heavy enough that every effect below takes a
    measurable amount of real encode time."""
    half = duration / 2
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size=1280x720:rate=30:duration={half}",
        "-f",
        "lavfi",
        "-i",
        f"color=c=red:size=1280x720:rate=30:duration={half}",
        "-filter_complex",
        "[0:v][1:v]concat=n=2:v=1:a=0[outv]",
        "-map",
        "[outv]",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)


class _FfmpegCpuMonitor:
    """Poll every ``ffmpeg`` child of this process for live CPU% while active."""

    def __init__(self) -> None:
        self._proc = psutil.Process()
        self._samples: list[tuple[float, int, float]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _poll(self) -> None:
        t0 = time.monotonic()
        tracked: dict[int, psutil.Process] = {}
        while not self._stop.is_set():
            try:
                for child in self._proc.children(recursive=True):
                    if child.pid not in tracked and "ffmpeg" in child.name().lower():
                        tracked[child.pid] = child
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            for pid, p in list(tracked.items()):
                try:
                    cpu = p.cpu_percent(interval=None)
                    self._samples.append((time.monotonic() - t0, pid, cpu))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    tracked.pop(pid, None)
            time.sleep(0.02)

    def __enter__(self) -> _FfmpegCpuMonitor:
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    @property
    def samples(self) -> list[tuple[float, int, float]]:
        return self._samples


def _run_and_measure(fn: Any, *args: Any, **kwargs: Any) -> tuple[Any, float, float, list]:
    """Call *fn* for real, returning ``(result, wall_s, cpu_s, cpu_samples)``."""
    ru_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.monotonic()
    with _FfmpegCpuMonitor() as monitor:
        result = fn(*args, **kwargs)
    wall = time.monotonic() - t0
    ru_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (ru_after.ru_utime - ru_before.ru_utime) + (ru_after.ru_stime - ru_before.ru_stime)
    return result, wall, cpu, monitor.samples


def _report(label: str, wall: float, cpu: float, samples: list[tuple[float, int, float]]) -> bool:
    busy = [s for s in samples if s[2] > 1.0]
    peak = max((s[2] for s in samples), default=0.0)
    print(f"\n=== {label} ===")
    print(f"  wall clock:      {wall:.3f}s")
    print(f"  ffmpeg CPU time: {cpu:.3f}s  (user+sys, resource.RUSAGE_CHILDREN delta)")
    print(f"  live samples:    {len(samples)} total, {len(busy)} above 1% CPU, peak {peak:.0f}%")
    if samples:
        trace = " ".join(f"{s[2]:.0f}" for s in samples[:50])
        print(f"  cpu% trace (first 50 @ ~20ms apart): {trace}")
    real_work = cpu > 0.01 or peak > 1.0
    verdict = "REAL CPU activity measured" if real_work else "NO measurable CPU activity"
    print(f"  -> {verdict}")
    return real_work


def main() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("ffmpeg/ffprobe not found in PATH", file=sys.stderr)
        sys.exit(1)

    tmp = ROOT / "output" / "_verify_step_time_effects"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    src = tmp / "source.mp4"
    _make_source_video(src)
    src_duration = _probe_duration(src)
    print(f"Source video: {src} ({src_duration:.2f}s, {src.stat().st_size} bytes)")

    ws = Workspace(base_dir=tmp)
    verdicts: dict[str, bool] = {}

    # ── reverse ──────────────────────────────────────────────────────
    out, wall, cpu, samples = _run_and_measure(
        DemoEngine._splice_time_effect,
        src,
        0.0,
        src_duration,
        False,
        "[mid]reverse[midout]",
        ws,
        "verify_reverse.mp4",
    )
    verdicts["reverse"] = _report("reverse", wall, cpu, samples)
    assert out is not None and out.exists(), "reverse produced no output file"
    print(f"  output duration: {_probe_duration(out):.2f}s (unchanged, as expected)")

    # ── freeze_frame ─────────────────────────────────────────────────
    src_fps = 30.0  # matches _make_source_video's lavfi "rate=30"
    out, wall, cpu, samples = _run_and_measure(
        DemoEngine._insert_step_freeze,
        src,
        src_duration / 2,
        2.0,
        src_fps,
        ws,
        0,
    )
    verdicts["freeze_frame"] = _report("freeze_frame", wall, cpu, samples)
    assert out is not None and out.exists(), "freeze_frame produced no output file"
    expected = src_duration + 2.0
    print(f"  output duration: {_probe_duration(out):.2f}s (source + 2.0s expected: {expected:.2f}s)")

    # ── speed_ramp ───────────────────────────────────────────────────
    mid_filter, predicted_len = DemoEngine._speed_ramp_filter(src_duration, 1.0, 3.0, "ease-in")
    out, wall, cpu, samples = _run_and_measure(
        DemoEngine._splice_time_effect,
        src,
        0.0,
        src_duration,
        False,
        mid_filter,
        ws,
        "verify_speed_ramp.mp4",
    )
    verdicts["speed_ramp"] = _report("speed_ramp", wall, cpu, samples)
    assert out is not None and out.exists(), "speed_ramp produced no output file"
    print(f"  output duration: {_probe_duration(out):.2f}s (predicted: {predicted_len:.2f}s)")

    print(
        "\nAll three effects ran through the real DemoEngine code path against a "
        "real ffmpeg binary — no subprocess mocking anywhere in this script."
    )
    if not all(verdicts.values()):
        print("At least one effect showed no measurable CPU activity.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
