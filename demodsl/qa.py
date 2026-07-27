"""Automated post-render defect report (issue #24).

A render can be perfectly valid and still be *bad*: an annotation drawn
past the frame edge, a subtitle behind the avatar bubble, six seconds of
dead air after a skipped step, narration cut off at the end of its shot,
a blank opening frame, a low-contrast accent on a light page. None of
those are visible to config validation, and watching 90 s of video per
site does not scale.

``demodsl qa output.mp4 --manifest run.json`` turns them into findings.
Everything except the blank-frame check is deterministic rectangle /
timeline math over the **run manifest** the renderer emits:

.. code-block:: jsonc

    {"duration": 92.4,
     "frame": {"width": 1920, "height": 1080},
     "steps": [{"index": 0, "action": "hover", "t": 0.0, "duration": 6.2,
                "narration_duration": 4.1, "locator": "[text] Featured",
                "motion": true}],
     "overlays": [{"kind": "annotation", "t": 34.2, "duration": 2.0,
                   "rect": {"x": 1830, "y": 400, "w": 180, "h": 90},
                   "color": "#6366F1", "background": "#FFFFFF"}],
     "skipped_steps": [{"index": 7, "code": "step.locator_unreachable", ...}]}

Missing sections never fail the report: the corresponding check is
listed in ``checks_skipped`` so a caller can tell "clean" from "not
verified".
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from demodsl.color_utils import contrast_ratio

logger = logging.getLogger(__name__)

__all__ = [
    "Finding",
    "QAReport",
    "analyze",
    "analyze_file",
    "DEAD_AIR_SECONDS",
    "COLLISION_AREA_RATIO",
    "MIN_OVERLAY_CONTRAST",
]

#: A silent, motionless stretch longer than this reads as a mistake.
DEAD_AIR_SECONDS = 4.0
#: Overlap above this share of the smaller overlay is a collision.
COLLISION_AREA_RATIO = 0.12
#: WCAG AA for large text / UI components.
MIN_OVERLAY_CONTRAST = 3.0
#: Narration allowed to spill past its shot before it is reported.
AUDIO_OVERRUN_TOLERANCE = 0.25

_SEVERITY_WEIGHT = {"error": 0.18, "warn": 0.06, "info": 0.0}


@dataclass
class Finding:
    code: str
    t: float
    severity: str
    detail: str
    step: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QAReport:
    score: float = 1.0
    findings: list[Finding] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)
    checks_skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "findings": [f.to_dict() for f in self.findings],
            "checks_run": self.checks_run,
            "checks_skipped": self.checks_skipped,
        }

    def codes(self) -> list[str]:
        return [f.code for f in self.findings]


# ── Geometry helpers ─────────────────────────────────────────────────────────


def _rect(entry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    r = entry.get("rect")
    if not isinstance(r, dict):
        return None
    try:
        return (float(r["x"]), float(r["y"]), float(r["w"]), float(r["h"]))
    except (KeyError, TypeError, ValueError):
        return None


def _intersection_area(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    dx = min(ax + aw, bx + bw) - max(ax, bx)
    dy = min(ay + ah, by + bh) - max(ay, by)
    return dx * dy if dx > 0 and dy > 0 else 0.0


def _overlaps_in_time(a: dict[str, Any], b: dict[str, Any]) -> bool:
    a0 = float(a.get("t", 0.0))
    a1 = a0 + float(a.get("duration", 0.0) or 0.0)
    b0 = float(b.get("t", 0.0))
    b1 = b0 + float(b.get("duration", 0.0) or 0.0)
    return a0 <= b1 and b0 <= a1


# ── Individual checks ────────────────────────────────────────────────────────


def _check_offscreen(manifest: dict[str, Any]) -> list[Finding]:
    frame = manifest.get("frame") or {}
    width = float(frame.get("width") or 0)
    height = float(frame.get("height") or 0)
    findings: list[Finding] = []
    if not width or not height:
        return findings
    for overlay in manifest.get("overlays") or []:
        rect = _rect(overlay)
        if rect is None:
            continue
        x, y, w, h = rect
        over_right = (x + w) - width
        over_bottom = (y + h) - height
        parts = []
        if over_right > 1:
            parts.append(f"{over_right:.0f}px past the right edge")
        if over_bottom > 1:
            parts.append(f"{over_bottom:.0f}px past the bottom edge")
        if x < -1:
            parts.append(f"{-x:.0f}px past the left edge")
        if y < -1:
            parts.append(f"{-y:.0f}px past the top edge")
        if parts:
            findings.append(
                Finding(
                    code="overlay.offscreen",
                    t=float(overlay.get("t", 0.0)),
                    severity="error",
                    detail=f"{overlay.get('kind', 'overlay')} bbox extends " + " and ".join(parts),
                    step=overlay.get("step"),
                )
            )
    return findings


def _check_collisions(manifest: dict[str, Any]) -> list[Finding]:
    overlays = [o for o in (manifest.get("overlays") or []) if _rect(o) is not None]
    findings: list[Finding] = []
    for i, a in enumerate(overlays):
        for b in overlays[i + 1 :]:
            if not _overlaps_in_time(a, b):
                continue
            ra, rb = _rect(a), _rect(b)
            assert ra is not None and rb is not None
            inter = _intersection_area(ra, rb)
            if inter <= 0:
                continue
            smaller = min(ra[2] * ra[3], rb[2] * rb[3]) or 1.0
            ratio = inter / smaller
            if ratio >= COLLISION_AREA_RATIO:
                findings.append(
                    Finding(
                        code="overlay.collision",
                        t=max(float(a.get("t", 0.0)), float(b.get("t", 0.0))),
                        severity="warn",
                        detail=(
                            f"{a.get('kind', 'overlay')} overlaps "
                            f"{b.get('kind', 'overlay')} ({ratio * 100:.0f}% area)"
                        ),
                    )
                )
    return findings


def _check_timeline(manifest: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    steps = manifest.get("steps") or []
    skipped_indexes = {
        entry.get("index") for entry in (manifest.get("skipped_steps") or []) if entry
    }
    for step in steps:
        idx = step.get("index")
        t = float(step.get("t", 0.0))
        duration = float(step.get("duration", 0.0) or 0.0)
        narration = float(step.get("narration_duration", 0.0) or 0.0)

        if narration and narration > duration + AUDIO_OVERRUN_TOLERANCE:
            findings.append(
                Finding(
                    code="audio.overrun",
                    t=t,
                    severity="error",
                    detail=(f"narration exceeds its step by {narration - duration:.1f}s (cut off)"),
                    step=idx,
                )
            )

        silent = duration - narration
        motion = bool(step.get("motion", step.get("action") not in ("pause", "wait_for")))
        if idx in skipped_indexes:
            motion = False
        if silent >= DEAD_AIR_SECONDS and not motion:
            findings.append(
                Finding(
                    code="shot.dead_air",
                    t=t + narration,
                    severity="warn",
                    detail=f"{silent:.1f}s with no narration and no motion",
                    step=idx,
                )
            )
    return findings


def _check_skipped(manifest: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for entry in manifest.get("skipped_steps") or []:
        findings.append(
            Finding(
                code=entry.get("code") or "step.locator_unreachable",
                t=float(entry.get("t", 0.0) or 0.0),
                severity="warn",
                detail=(
                    f"step '{entry.get('action')}' {entry.get('locator', '')} was degraded "
                    f"({entry.get('error', 'unknown error')})"
                ),
                step=entry.get("index"),
            )
        )
    return findings


def _check_contrast(manifest: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for overlay in manifest.get("overlays") or []:
        color = overlay.get("color")
        background = overlay.get("background")
        if not color or not background:
            continue
        ratio = contrast_ratio(color, background)
        if ratio is None or ratio >= MIN_OVERLAY_CONTRAST:
            continue
        findings.append(
            Finding(
                code="overlay.contrast",
                t=float(overlay.get("t", 0.0)),
                severity="warn",
                detail=f"accent {color} on background {background}: {ratio:.1f}:1",
                step=overlay.get("step"),
            )
        )
    return findings


def _sample_frame_variance(video: Path, timestamps: list[float]) -> list[tuple[float, float]]:
    """Return ``(t, stddev)`` for each sampled frame using ffmpeg's signalstats."""
    if shutil.which("ffmpeg") is None:
        raise FileNotFoundError("ffmpeg not available")
    out: list[tuple[float, float]] = []
    for t in timestamps:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-ss",
                f"{t:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                "signalstats,metadata=print:key=lavfi.signalstats.YDIF",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        stderr = proc.stderr or ""
        # signalstats exposes YMIN/YMAX in the frame metadata dump; the
        # spread between them is a cheap, dependency-free "is this frame
        # blank?" signal.
        spread = 0.0
        ymin = _grep_float(stderr, "YMIN:")
        ymax = _grep_float(stderr, "YMAX:")
        if ymin is not None and ymax is not None:
            spread = ymax - ymin
        out.append((t, spread))
    return out


def _grep_float(text: str, token: str) -> float | None:
    for line in text.splitlines():
        pos = line.find(token)
        if pos >= 0:
            try:
                return float(line[pos + len(token) :].split()[0])
            except (IndexError, ValueError):
                return None
    return None


def _check_blank_frames(manifest: dict[str, Any], video: Path) -> list[Finding]:
    duration = float(manifest.get("duration") or 0.0)
    if duration <= 0:
        return []
    samples = [0.5, 1.5, 2.5] + [duration * r for r in (0.25, 0.5, 0.75)]
    samples = [t for t in samples if t < duration]
    findings: list[Finding] = []
    blank_run: list[float] = []
    for t, spread in _sample_frame_variance(video, samples):
        if spread < 8.0:
            blank_run.append(t)
    if blank_run:
        findings.append(
            Finding(
                code="frame.uniform",
                t=min(blank_run),
                severity="error",
                detail=(
                    f"{len(blank_run)} sampled frame(s) are blank/uniform "
                    f"(t={', '.join(f'{t:.1f}s' for t in blank_run)})"
                ),
            )
        )
    return findings


# ── Entry points ─────────────────────────────────────────────────────────────


def analyze(manifest: dict[str, Any], *, video: Path | None = None) -> QAReport:
    """Run every applicable check over *manifest* and score the render."""
    report = QAReport()

    if manifest.get("overlays"):
        report.checks_run += ["overlay.offscreen", "overlay.collision", "overlay.contrast"]
        report.findings += _check_offscreen(manifest)
        report.findings += _check_collisions(manifest)
        report.findings += _check_contrast(manifest)
    else:
        report.checks_skipped += ["overlay.offscreen", "overlay.collision", "overlay.contrast"]

    if manifest.get("steps"):
        report.checks_run += ["audio.overrun", "shot.dead_air"]
        report.findings += _check_timeline(manifest)
    else:
        report.checks_skipped += ["audio.overrun", "shot.dead_air"]

    if manifest.get("skipped_steps"):
        report.checks_run.append("step.locator_unreachable")
        report.findings += _check_skipped(manifest)

    if video is not None and Path(video).exists():
        try:
            report.findings += _check_blank_frames(manifest, Path(video))
            report.checks_run.append("frame.uniform")
        except (FileNotFoundError, subprocess.SubprocessError, OSError) as exc:
            logger.debug("frame.uniform check skipped: %s", exc)
            report.checks_skipped.append("frame.uniform")
    else:
        report.checks_skipped.append("frame.uniform")

    report.findings.sort(key=lambda f: (f.t, f.code))
    penalty = sum(_SEVERITY_WEIGHT.get(f.severity, 0.0) for f in report.findings)
    report.score = round(max(0.0, 1.0 - penalty), 3)
    return report


def analyze_file(manifest_path: Path, *, video: Path | None = None) -> QAReport:
    """Load a run manifest from disk and analyse it."""
    manifest = json.loads(Path(manifest_path).read_text("utf-8"))
    return analyze(manifest, video=video)
