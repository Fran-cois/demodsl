"""Bridge module — serializes DemoDSL pipeline data to Remotion JSON props
and invokes the Remotion renderer via subprocess."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path to the remotion/ project relative to the demodsl package root
_REMOTION_DIR = Path(__file__).resolve().parent.parent.parent / "remotion"

_DEFAULT_RENDER_TIMEOUT_S = 600


def _render_timeout() -> int:
    """Render timeout in seconds, overridable via ``DEMODSL_REMOTION_TIMEOUT``.

    An invalid or non-positive value falls back to the default: disabling the
    timeout entirely would let a hung render block the pipeline forever.
    """
    raw = os.environ.get("DEMODSL_REMOTION_TIMEOUT")
    if not raw:
        return _DEFAULT_RENDER_TIMEOUT_S
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "DEMODSL_REMOTION_TIMEOUT=%r is not an integer — using %ds",
            raw,
            _DEFAULT_RENDER_TIMEOUT_S,
        )
        return _DEFAULT_RENDER_TIMEOUT_S
    if value <= 0:
        logger.warning(
            "DEMODSL_REMOTION_TIMEOUT=%r must be positive — using %ds",
            raw,
            _DEFAULT_RENDER_TIMEOUT_S,
        )
        return _DEFAULT_RENDER_TIMEOUT_S
    return value


def _apply_default_concurrency() -> None:
    """Fill in a smarter ``REMOTION_CONCURRENCY`` default when unset.

    Remotion's own default caps at 8 workers and only uses half the cores
    below that (``round(min(8, cpus/2))``), regardless of how many cores the
    machine actually has. Measured on an 11-core Mac: the default (6
    workers) rendered a 660-frame demo in 26s; ``REMOTION_CONCURRENCY`` set
    to the real core count rendered the same demo in 21s (~19% faster).

    Mutates the current process's environment (rather than building a
    separate ``env=`` dict for the subprocess) so it keeps inheriting
    whatever the deployment sets on the container — see
    ``tests/test_remotion_env.py`` for why an explicit ``env=`` is unsafe
    here. Never overrides an already-set value.
    """
    if os.environ.get("REMOTION_CONCURRENCY"):
        return
    cpu_count = os.cpu_count()
    if cpu_count and cpu_count > 2:
        os.environ["REMOTION_CONCURRENCY"] = str(cpu_count - 1)


def check_remotion_available() -> bool:
    """Check that Node.js and the Remotion project are available."""
    if not shutil.which("node"):
        logger.error("Node.js not found — required for Remotion renderer")
        return False
    if not shutil.which("npx"):
        logger.error("npx not found — required for Remotion renderer")
        return False
    if not (_REMOTION_DIR / "package.json").exists():
        logger.error("Remotion project not found at %s", _REMOTION_DIR)
        return False
    if not (_REMOTION_DIR / "node_modules").exists():
        logger.warning(
            "Remotion dependencies not installed. Run: cd %s && npm install",
            _REMOTION_DIR,
        )
        return False
    return True


def build_props(
    *,
    segments: list[dict[str, Any]],
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    intro: dict[str, Any] | None = None,
    outro: dict[str, Any] | None = None,
    watermark: dict[str, Any] | None = None,
    reviewer: dict[str, Any] | None = None,
    live_avatar: dict[str, Any] | None = None,
    progress_bar: dict[str, Any] | None = None,
    audio_visualizer: dict[str, Any] | None = None,
    step_effects: list[dict[str, Any]] | None = None,
    avatars: list[dict[str, Any]] | None = None,
    subtitles: list[dict[str, Any]] | None = None,
    transitions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a DemoProps dict matching the Remotion TypeScript interface."""
    props: dict[str, Any] = {
        "fps": fps,
        "width": width,
        "height": height,
        "segments": segments,
        "stepEffects": step_effects or [],
        "avatars": avatars or [],
        "subtitles": subtitles or [],
    }
    if intro:
        props["intro"] = _convert_intro(intro)
    if outro:
        props["outro"] = _convert_outro(outro)
    if watermark:
        props["watermark"] = _convert_watermark(watermark)
    if reviewer:
        props["reviewer"] = _convert_reviewer(reviewer)
    if live_avatar:
        props["liveAvatar"] = {
            "accent": str(live_avatar.get("accent") or "#6366F1"),
            "position": live_avatar.get("position", "bottom-right"),
            "size": live_avatar.get("size", 168),
            "mouth": live_avatar.get("mouth") or [],
        }
    if progress_bar:
        props["progressBar"] = {
            "accent": str(progress_bar.get("accent") or "#6366F1"),
            "position": progress_bar.get("position", "top"),
            "height": progress_bar.get("height", 6),
        }
    if audio_visualizer:
        props["audioVisualizer"] = {
            "style": audio_visualizer.get("style", "bars"),
            "accent": str(audio_visualizer.get("accent") or "#6366F1"),
            "position": audio_visualizer.get("position", "bottom-center"),
            "size": audio_visualizer.get("size", 220),
            "rainbow": bool(audio_visualizer.get("rainbow", False)),
            "bandData": audio_visualizer.get("bandData") or [],
        }
    if transitions:
        props["transitions"] = transitions
    return props


def _collect_media_paths(props: dict[str, Any]) -> list[Path]:
    """Collect all absolute media paths referenced in props."""
    paths: list[Path] = []
    for seg in props.get("segments", []) or []:
        src = seg.get("src")
        if src and not src.startswith(("http://", "https://")):
            paths.append(Path(src))
    for av in props.get("avatars", []) or []:
        src = av.get("src")
        if src and not src.startswith(("http://", "https://")):
            paths.append(Path(src))
    wm = props.get("watermark") or {}
    img = wm.get("image")
    if img and not str(img).startswith(("http://", "https://")):
        paths.append(Path(img))
    rev = props.get("reviewer") or {}
    rimg = rev.get("image")
    if rimg and not str(rimg).startswith(("http://", "https://", "data:")):
        paths.append(Path(rimg))
    return paths


def _rewrite_paths_relative(props: dict[str, Any], public_dir: Path) -> None:
    """Rewrite all media src paths in props to be relative to public_dir.

    Remotion serves staticFile()/relative URLs from the publicDir via its
    bundle webserver, while absolute file paths and file:// URIs are rejected.
    """
    pub = public_dir.resolve()

    def _rel(p: str) -> str:
        if p.startswith(("http://", "https://", "data:")):
            return p
        try:
            return str(Path(p).resolve().relative_to(pub))
        except ValueError:
            return p

    for seg in props.get("segments", []) or []:
        if "src" in seg:
            seg["src"] = _rel(seg["src"])
    for av in props.get("avatars", []) or []:
        if "src" in av:
            av["src"] = _rel(av["src"])
    wm = props.get("watermark")
    if wm and "image" in wm:
        wm["image"] = _rel(wm["image"])
    rev = props.get("reviewer")
    if rev and "image" in rev:
        rev["image"] = _rel(rev["image"])


def _run_remotion_streaming(
    cmd: list[str], *, cwd: str, timeout_s: int
) -> subprocess.CompletedProcess:
    """Like ``subprocess.run(capture_output=True)``, but logs stdout lines AS
    THEY ARRIVE instead of buffering everything until the process exits.

    With plain ``capture_output=True`` the caller (demobro2's render task,
    which streams this process's own stdout line-by-line to drive a progress
    bar) sees zero new lines for the entire multi-minute Remotion render —
    only a burst of buffered output once it's already done — so the bar looks
    frozen right when the actual rendering work happens.
    """
    import threading

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def _drain_stdout() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            if line:
                logger.info("[remotion] %s", line)
                stdout_lines.append(line)

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            line = line.rstrip("\n")
            if line:
                stderr_lines.append(line)

    t_out = threading.Thread(target=_drain_stdout, daemon=True)
    t_err = threading.Thread(target=_drain_stderr, daemon=True)
    t_out.start()
    t_err.start()

    try:
        returncode = proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        t_out.join(timeout=5)
        t_err.join(timeout=5)
        raise
    t_out.join(timeout=10)
    t_err.join(timeout=10)

    return subprocess.CompletedProcess(
        cmd, returncode, "\n".join(stdout_lines), "\n".join(stderr_lines)
    )


def render_via_remotion(props: dict[str, Any], output_path: Path) -> Path:
    """Write props JSON and invoke the Remotion render subprocess.

    Args:
        props: DemoProps dict to pass to Remotion.
        output_path: Where to write the rendered MP4.

    Returns:
        Path to the rendered video file.

    Raises:
        RuntimeError: If the Remotion render fails.
    """
    if not check_remotion_available():
        raise RuntimeError(
            "Remotion is not available. Install Node.js and run "
            f"'cd {_REMOTION_DIR} && npm install'"
        )

    # Determine a publicDir that contains every media file. Remotion's bundle
    # webserver only serves files from inside publicDir (referenced as
    # staticFile / relative URLs). Absolute file paths and file:// URIs are
    # rejected by @remotion/renderer's downloader.
    media_paths = _collect_media_paths(props)
    if media_paths:
        try:
            import os

            common = Path(os.path.commonpath([str(p.resolve()) for p in media_paths]))
        except ValueError:
            common = media_paths[0].resolve().parent
        public_dir = common if common.is_dir() else common.parent
    else:
        public_dir = output_path.resolve().parent

    _rewrite_paths_relative(props, public_dir)

    # Write props to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        dir=str(output_path.parent),
    ) as f:
        json.dump(props, f, default=str)
        props_path = Path(f.name)

    try:
        cmd = [
            "npx",
            "tsx",
            str(_REMOTION_DIR / "src" / "render-entry.ts"),
            "--props",
            str(props_path),
            "--output",
            str(output_path),
            "--public-dir",
            str(public_dir),
        ]
        logger.info("Running Remotion render: %s", " ".join(cmd))

        # Remotion occasionally fails transiently (e.g. "Timeout (30000ms)
        # exceeded ... Loading <Img> with src=blob:") — one retry recovers it
        # and is far cheaper than losing a whole multi-minute pipeline run.
        last_error: str = "Unknown error"
        missing_output = False
        timeout_s = _render_timeout()
        _apply_default_concurrency()
        for attempt in (1, 2):
            result = _run_remotion_streaming(cmd, cwd=str(_REMOTION_DIR), timeout_s=timeout_s)

            if result.returncode == 0 and output_path.exists():
                logger.info("Remotion render complete: %s", output_path)
                return output_path

            missing_output = result.returncode == 0
            last_error = (
                f"exited 0 but produced no output at {output_path}"
                if missing_output
                else (result.stderr if result.stderr else "Unknown error")
            )
            if attempt == 1:
                logger.warning(
                    "Remotion render failed (attempt 1/2) — retrying once:\n%s",
                    last_error[-800:],
                )

        if missing_output:
            logger.error("Remotion render produced no output at %s", output_path)
            raise RuntimeError(f"Remotion render produced no output at {output_path}")

        logger.error("Remotion render failed:\n%s", last_error)
        raise RuntimeError(f"Remotion render failed: {last_error[-3000:]}")

    finally:
        # Clean up temp props file
        props_path.unlink(missing_ok=True)


def get_video_duration(video_path: Path) -> float:
    """Get the duration of a video file in seconds via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError):
        logger.warning("Could not determine duration for %s, defaulting to 10s", video_path)
        return 10.0


# ── Conversion helpers ────────────────────────────────────────────────────────


def _convert_intro(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "durationInSeconds": config.get("duration", 3.0),
        "text": config.get("text"),
        "subtitle": config.get("subtitle"),
        "fontSize": config.get("font_size", 60),
        "fontColor": config.get("font_color", "#FFFFFF"),
        "backgroundColor": config.get("background_color", "#1a1a1a"),
    }


def _convert_outro(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "durationInSeconds": config.get("duration", 4.0),
        "text": config.get("text"),
        "subtitle": config.get("subtitle"),
        "cta": config.get("cta"),
        "fontColor": config.get("font_color", "#FFFFFF"),
        "backgroundColor": config.get("background_color", "#1a1a1a"),
    }


def _convert_watermark(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "image": str(config.get("image", "")),
        "position": config.get("position", "bottom_right"),
        "opacity": config.get("opacity", 0.7),
        "size": config.get("size", 100),
    }


def _convert_reviewer(config: dict[str, Any]) -> dict[str, Any]:
    """Reviewer badge props; without an image, embed the builtin portrait."""
    from demodsl.effects.reviewer_portrait import portrait_data_uri

    accent = str(config.get("accent") or "#6366F1")
    image = config.get("image")
    src = str(Path(image).resolve()) if image else portrait_data_uri(accent)
    return {
        "image": src,
        "name": str(config.get("name") or "Alex Rivera"),
        "title": str(config.get("title") or "Senior CRO Reviewer"),
        "company": str(config.get("company") or "DemoBro"),
        "accent": accent,
        "position": config.get("position", "bottom-left"),
        "size": config.get("size", 88),
    }


def convert_effects(effects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert DemoDSL effect dicts to Remotion EffectConfig format."""
    result = []
    for eff in effects:
        converted: dict[str, Any] = {"type": eff.get("type", "")}
        # Map snake_case params to camelCase
        field_map = {
            "duration": "duration",
            "intensity": "intensity",
            "color": "color",
            "speed": "speed",
            "scale": "scale",
            "seed": "seed",
            "direction": "direction",
            "target_x": "targetX",
            "target_y": "targetY",
            "ratio": "ratio",
        }
        for py_key, ts_key in field_map.items():
            if py_key in eff and eff[py_key] is not None:
                converted[ts_key] = eff[py_key]
        result.append(converted)
    return result
