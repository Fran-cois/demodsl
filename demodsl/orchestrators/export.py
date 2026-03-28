"""ExportOrchestrator — video export, verification, and cloud deployment."""

from __future__ import annotations

import logging
from pathlib import Path

from demodsl.models import DemoConfig

logger = logging.getLogger(__name__)


class ExportOrchestrator:
    """Handles final video export, format conversion, verification,
    and cloud deployment."""

    def __init__(self, config: DemoConfig) -> None:
        self.config = config

    # ── Export ─────────────────────────────────────────────────────────────

    def export_video(
        self,
        source: Path,
        dest: Path,
        *,
        audio: Path | None = None,
    ) -> None:
        """Export video to *dest*, converting to MP4 H.264 and merging audio if provided."""
        import shutil
        import subprocess

        needs_conversion = self._needs_conversion(source, dest)

        if needs_conversion or audio:
            logger.info(
                "Converting %s → MP4 H.264 (%s)%s",
                source.name, dest.name,
                " + narration audio" if audio else "",
            )
            cmd = ["ffmpeg", "-y", "-i", str(source)]
            if audio and audio.exists():
                cmd += ["-i", str(audio)]
            cmd += [
                "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            ]
            if audio and audio.exists():
                cmd += [
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:a", "aac", "-b:a", "128k", "-shortest",
                ]
            else:
                cmd += ["-an"]
            cmd.append(str(dest))
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=600,
                )
            except subprocess.TimeoutExpired:
                logger.warning("ffmpeg conversion timed out after 600s, falling back to raw copy")
                shutil.copy2(source, dest)
                self.verify_video(dest)
                return
            if result.returncode != 0:
                logger.warning("ffmpeg conversion failed: %s", result.stderr[-200:])
                logger.info("Falling back to raw copy")
                shutil.copy2(source, dest)
        else:
            shutil.copy2(source, dest)

        self.verify_video(dest)

    @staticmethod
    def _needs_conversion(source: Path, dest: Path) -> bool:
        """Check if source is WebM/VP8 but dest expects MP4."""
        import subprocess

        if dest.suffix.lower() != ".mp4":
            return False
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=format_name",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(source),
                ],
                capture_output=True, text=True, timeout=10,
            )
            fmt = result.stdout.strip()
            return "webm" in fmt or "matroska" in fmt
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def verify_video(path: Path) -> None:
        """Verify output video is valid — log result."""
        import subprocess

        if not path.exists():
            logger.error("VERIFY FAIL: file does not exist: %s", path)
            return

        size = path.stat().st_size
        if size == 0:
            logger.error("VERIFY FAIL: file is empty: %s", path)
            return

        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=format_name,duration",
                    "-show_entries", "stream=codec_name,width,height",
                    "-of", "default=noprint_wrappers=1",
                    str(path),
                ],
                capture_output=True, text=True, timeout=10,
            )
            lines = result.stdout.strip().split("\n")
            info = dict(line.split("=", 1) for line in lines if "=" in line)

            fmt = info.get("format_name", "unknown")
            codec = info.get("codec_name", "unknown")
            w = info.get("width", "?")
            h = info.get("height", "?")
            dur = info.get("duration", "?")

            if path.suffix.lower() == ".mp4" and "mp4" not in fmt and "mov" not in fmt:
                logger.error(
                    "VERIFY FAIL: %s has extension .mp4 but format is '%s' (codec=%s)",
                    path.name, fmt, codec,
                )
                return

            logger.info(
                "VERIFY OK: %s → %s/%s %sx%s %.1fs (%s)",
                path.name, fmt, codec, w, h,
                float(dur) if dur != "?" else 0,
                _human_size(size),
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("VERIFY SKIP: ffprobe not available, cannot verify %s", path.name)

    # ── Cloud deployment ──────────────────────────────────────────────────

    def deploy_to_cloud(self, video_path: Path) -> str | None:
        """Upload video to cloud provider if deploy config is set. Returns URL or None."""
        deploy_cfg = (
            self.config.output.deploy
            if self.config.output and self.config.output.deploy
            else None
        )
        if deploy_cfg is None:
            return None

        from demodsl.providers.deploy import DeployProviderFactory

        provider_name = deploy_cfg.provider
        kwargs = deploy_cfg.model_dump(exclude_none=True)
        kwargs.pop("provider", None)

        deployer = DeployProviderFactory.create(provider_name, **kwargs)
        try:
            prefix = deploy_cfg.prefix.rstrip("/")
            remote_key = f"{prefix}/{video_path.name}" if prefix else video_path.name
            url = deployer.upload(video_path, remote_key)
            return url
        finally:
            deployer.close()


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.0f}{unit}"
        nbytes /= 1024
    return f"{nbytes:.1f}TB"
