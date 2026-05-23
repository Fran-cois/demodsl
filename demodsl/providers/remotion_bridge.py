"""Bridge module — serializes DemoDSL pipeline data to Remotion JSON props
and invokes the Remotion renderer via subprocess."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path to the remotion/ project relative to the demodsl package root
_REMOTION_DIR = Path(__file__).resolve().parent.parent.parent / "remotion"


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
    return paths


def _rewrite_paths_relative(props: dict[str, Any], public_dir: Path) -> None:
    """Rewrite all media src paths in props to be relative to public_dir.

    Remotion serves staticFile()/relative URLs from the publicDir via its
    bundle webserver, while absolute file paths and file:// URIs are rejected.
    """
    pub = public_dir.resolve()

    def _rel(p: str) -> str:
        if p.startswith(("http://", "https://")):
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

        result = subprocess.run(
            cmd,
            cwd=str(_REMOTION_DIR),
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                logger.info("[remotion] %s", line)

        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else "Unknown error"
            logger.error("Remotion render failed:\n%s", error_msg)
            raise RuntimeError(f"Remotion render failed: {error_msg[-3000:]}")

        if not output_path.exists():
            raise RuntimeError(f"Remotion render produced no output at {output_path}")

        logger.info("Remotion render complete: %s", output_path)
        return output_path

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
