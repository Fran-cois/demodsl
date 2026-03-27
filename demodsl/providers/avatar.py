"""Avatar providers — animated (free) + D-ID, HeyGen, SadTalker (paid)."""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from pathlib import Path

import numpy as np

from demodsl.providers.base import AvatarProvider, AvatarProviderFactory

logger = logging.getLogger(__name__)


# ── Free: Animated avatar (bounce / waveform / pulse) ─────────────────────────

class AnimatedAvatarProvider(AvatarProvider):
    """Generates a simple animated avatar clip from a static image + audio amplitude.

    Uses Pillow + numpy to produce frames, then ffmpeg to encode.
    No external API needed — completely free.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path(".")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._counter = 0

    def generate(
        self,
        audio_path: Path,
        *,
        image: str | None = None,
        size: int = 120,
        style: str = "bounce",
        shape: str = "circle",
    ) -> Path:
        from PIL import Image, ImageDraw, ImageFilter
        from pydub import AudioSegment

        self._counter += 1

        # Load audio and extract amplitude envelope
        audio = AudioSegment.from_file(str(audio_path))
        fps = 30
        duration_s = len(audio) / 1000.0
        total_frames = max(1, int(duration_s * fps))
        amplitudes = self._extract_amplitudes(audio, total_frames)

        # Load or create avatar image
        avatar_img = self._load_avatar(image, size)

        # Apply shape mask
        avatar_img = self._apply_shape(avatar_img, shape, size)

        # Canvas size: slightly larger than avatar for animation room
        canvas_size = int(size * 1.4)
        half = canvas_size // 2

        # Generate frames
        frames_dir = self._output_dir / f"avatar_frames_{self._counter:03d}"
        frames_dir.mkdir(exist_ok=True)

        for i in range(total_frames):
            amp = amplitudes[i]  # 0.0 – 1.0

            canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

            if style == "bounce":
                # Avatar bounces up/down based on amplitude
                offset_y = int(-amp * size * 0.15)
                scale = 1.0 + amp * 0.08
                scaled_size = int(size * scale)
                scaled = avatar_img.resize((scaled_size, scaled_size), Image.LANCZOS)
                x = half - scaled_size // 2
                y = half - scaled_size // 2 + offset_y
                canvas.paste(scaled, (x, y), scaled)

            elif style == "waveform":
                # Static avatar with animated waveform ring
                x = half - size // 2
                y = half - size // 2
                canvas.paste(avatar_img, (x, y), avatar_img)
                # Draw waveform ring around avatar
                draw = ImageDraw.Draw(canvas)
                ring_radius = size // 2 + 4 + int(amp * 12)
                ring_width = 2 + int(amp * 4)
                green = int(100 + amp * 155)
                draw.ellipse(
                    [half - ring_radius, half - ring_radius,
                     half + ring_radius, half + ring_radius],
                    outline=(100, green, 255, int(180 + amp * 75)),
                    width=ring_width,
                )

            elif style == "pulse":
                # Avatar scales/pulses with audio
                scale = 1.0 + amp * 0.2
                scaled_size = int(size * scale)
                scaled = avatar_img.resize((scaled_size, scaled_size), Image.LANCZOS)
                # Add glow behind
                if amp > 0.1:
                    glow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
                    glow_draw = ImageDraw.Draw(glow)
                    glow_r = int(scaled_size // 2 + amp * 15)
                    glow_draw.ellipse(
                        [half - glow_r, half - glow_r,
                         half + glow_r, half + glow_r],
                        fill=(100, 150, 255, int(amp * 100)),
                    )
                    glow = glow.filter(ImageFilter.GaussianBlur(radius=8))
                    canvas = Image.alpha_composite(canvas, glow)
                x = half - scaled_size // 2
                y = half - scaled_size // 2
                canvas.paste(scaled, (x, y), scaled)
            else:
                # Fallback: static
                x = half - size // 2
                y = half - size // 2
                canvas.paste(avatar_img, (x, y), avatar_img)

            canvas.save(frames_dir / f"frame_{i:05d}.png")

        # Encode frames to video with ffmpeg (VP9 + alpha or H.264)
        out_path = self._output_dir / f"avatar_{self._counter:03d}.webm"
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%05d.png"),
            "-c:v", "libvpx-vp9",
            "-pix_fmt", "yuva420p",  # alpha support
            "-b:v", "1M",
            "-an",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("ffmpeg avatar encode failed: %s", result.stderr[-300:])
            # Fallback: H.264 without alpha
            out_path = out_path.with_suffix(".mp4")
            cmd_fallback = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", str(frames_dir / "frame_%05d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-crf", "23", "-an",
                str(out_path),
            ]
            subprocess.run(cmd_fallback, capture_output=True, text=True, check=True)

        # Cleanup frames
        import shutil
        shutil.rmtree(frames_dir, ignore_errors=True)

        logger.info("Generated avatar clip: %s (%.1fs)", out_path.name, duration_s)
        return out_path

    def close(self) -> None:
        pass

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _extract_amplitudes(audio: "AudioSegment", num_frames: int) -> list[float]:
        """Extract normalized amplitude envelope from audio, one value per frame."""
        samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
        if audio.channels > 1:
            samples = samples[::audio.channels]  # mono

        chunk_size = max(1, len(samples) // num_frames)
        amplitudes: list[float] = []
        for i in range(num_frames):
            start = i * chunk_size
            end = min(start + chunk_size, len(samples))
            chunk = samples[start:end]
            if len(chunk) == 0:
                amplitudes.append(0.0)
            else:
                rms = np.sqrt(np.mean(chunk ** 2))
                amplitudes.append(float(rms))

        # Normalize to 0-1
        max_amp = max(amplitudes) if amplitudes else 1.0
        if max_amp > 0:
            amplitudes = [a / max_amp for a in amplitudes]

        # Smooth the amplitude curve to avoid jitter
        smoothed: list[float] = []
        window = 3
        for i in range(len(amplitudes)):
            start = max(0, i - window)
            end = min(len(amplitudes), i + window + 1)
            smoothed.append(sum(amplitudes[start:end]) / (end - start))

        return smoothed

    @staticmethod
    def _load_avatar(image: str | None, size: int) -> "Image.Image":
        """Load avatar image from path or generate a default one."""
        from PIL import Image, ImageDraw, ImageFont

        if image and Path(image).exists():
            img = Image.open(image).convert("RGBA")
            img = img.resize((size, size), Image.LANCZOS)
            return img

        # Generate default avatar: colored circle with a letter
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Avatar background
        presets = {
            "robot": ((80, 120, 200), "🤖"),
            "circle": ((100, 200, 150), "●"),
        }
        preset = presets.get(image or "", ((130, 100, 220), "N"))
        bg_color, char = preset

        draw.ellipse([2, 2, size - 3, size - 3], fill=(*bg_color, 230))

        # Draw character/letter
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size // 3)
        except (OSError, IOError):
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), char, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((size - tw) / 2, (size - th) / 2 - bbox[1]),
            char, fill=(255, 255, 255, 255), font=font,
        )
        return img

    @staticmethod
    def _apply_shape(img: "Image.Image", shape: str, size: int) -> "Image.Image":
        """Apply shape mask (circle, rounded, square) to avatar image."""
        from PIL import Image, ImageDraw

        if shape == "square":
            return img

        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)

        if shape == "circle":
            draw.ellipse([0, 0, size - 1, size - 1], fill=255)
        elif shape == "rounded":
            radius = size // 5
            draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
        else:
            draw.ellipse([0, 0, size - 1, size - 1], fill=255)

        img.putalpha(mask)
        return img


# ── Paid: D-ID Talking Head ──────────────────────────────────────────────────

class DIDProvider(AvatarProvider):
    """Generate talking-head video via the D-ID API.

    Requires D_ID_API_KEY environment variable or api_key parameter.
    Pricing: ~$0.05/second of generated video.
    """

    API_BASE = "https://api.d-id.com"

    def __init__(
        self, output_dir: Path | None = None, api_key: str | None = None,
    ) -> None:
        raw_key = api_key or os.environ.get("D_ID_API_KEY", "")
        # Support ${ENV_VAR} syntax
        if raw_key.startswith("${") and raw_key.endswith("}"):
            raw_key = os.environ.get(raw_key[2:-1], "")
        self._api_key = raw_key
        if not self._api_key:
            raise EnvironmentError(
                "D_ID_API_KEY not set. Set the env var or pass api_key in avatar config."
            )
        self._output_dir = output_dir or Path(".")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._counter = 0

    def generate(
        self,
        audio_path: Path,
        *,
        image: str | None = None,
        size: int = 120,
        style: str = "bounce",
        shape: str = "circle",
    ) -> Path:
        import httpx

        self._counter += 1

        # 1. Upload audio
        audio_url = self._upload_audio(audio_path)

        # 2. Determine source image
        source_url = self._resolve_image(image)

        # 3. Create talk
        talk_id = self._create_talk(source_url, audio_url)

        # 4. Poll for result
        result_url = self._poll_talk(talk_id)

        # 5. Download result video
        out_path = self._output_dir / f"avatar_did_{self._counter:03d}.mp4"
        resp = httpx.get(result_url, timeout=120)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)

        logger.info("D-ID avatar clip: %s", out_path.name)
        return out_path

    def close(self) -> None:
        pass

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Basic {self._api_key}",
            "Content-Type": "application/json",
        }

    def _upload_audio(self, audio_path: Path) -> str:
        """Upload audio file to D-ID and return the URL."""
        import httpx

        with open(audio_path, "rb") as f:
            resp = httpx.post(
                f"{self.API_BASE}/audios",
                headers={"Authorization": f"Basic {self._api_key}"},
                files={"audio": (audio_path.name, f, "audio/mpeg")},
                timeout=60,
            )
        resp.raise_for_status()
        return resp.json()["url"]

    def _resolve_image(self, image: str | None) -> str:
        """Resolve image to a URL. Uploads local files to D-ID."""
        import httpx

        if not image:
            # Use D-ID default presenter
            return "https://d-id-public-bucket.s3.us-west-2.amazonaws.com/alice.jpg"

        if image.startswith("http"):
            return image

        if Path(image).exists():
            with open(image, "rb") as f:
                resp = httpx.post(
                    f"{self.API_BASE}/images",
                    headers={"Authorization": f"Basic {self._api_key}"},
                    files={"image": (Path(image).name, f, "image/jpeg")},
                    timeout=60,
                )
            resp.raise_for_status()
            return resp.json()["url"]

        return "https://d-id-public-bucket.s3.us-west-2.amazonaws.com/alice.jpg"

    def _create_talk(self, source_url: str, audio_url: str) -> str:
        """Create a D-ID talk and return the talk ID."""
        import httpx

        payload = {
            "source_url": source_url,
            "script": {
                "type": "audio",
                "audio_url": audio_url,
            },
        }
        resp = httpx.post(
            f"{self.API_BASE}/talks",
            json=payload,
            headers=self._headers(),
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def _poll_talk(self, talk_id: str, timeout: float = 120) -> str:
        """Poll until the talk is ready, return the result video URL."""
        import time

        import httpx

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            resp = httpx.get(
                f"{self.API_BASE}/talks/{talk_id}",
                headers=self._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            if status == "done":
                return data["result_url"]
            if status == "error":
                raise RuntimeError(f"D-ID talk failed: {data.get('error', 'unknown')}")
            time.sleep(3)

        raise TimeoutError(f"D-ID talk {talk_id} did not complete within {timeout}s")


# ── Paid: HeyGen Talking Head ────────────────────────────────────────────────

class HeyGenProvider(AvatarProvider):
    """Generate talking-head video via the HeyGen API.

    Requires HEYGEN_API_KEY environment variable or api_key parameter.
    """

    API_BASE = "https://api.heygen.com/v2"

    def __init__(
        self, output_dir: Path | None = None, api_key: str | None = None,
    ) -> None:
        raw_key = api_key or os.environ.get("HEYGEN_API_KEY", "")
        if raw_key.startswith("${") and raw_key.endswith("}"):
            raw_key = os.environ.get(raw_key[2:-1], "")
        self._api_key = raw_key
        if not self._api_key:
            raise EnvironmentError(
                "HEYGEN_API_KEY not set. Set the env var or pass api_key in avatar config."
            )
        self._output_dir = output_dir or Path(".")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._counter = 0

    def generate(
        self,
        audio_path: Path,
        *,
        image: str | None = None,
        size: int = 120,
        style: str = "bounce",
        shape: str = "circle",
    ) -> Path:
        import httpx

        self._counter += 1

        # 1. Upload audio to HeyGen
        audio_asset_id = self._upload_audio(audio_path)

        # 2. Create avatar video
        video_id = self._create_video(audio_asset_id, image)

        # 3. Poll for completion
        result_url = self._poll_video(video_id)

        # 4. Download
        out_path = self._output_dir / f"avatar_heygen_{self._counter:03d}.mp4"
        resp = httpx.get(result_url, timeout=120)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)

        logger.info("HeyGen avatar clip: %s", out_path.name)
        return out_path

    def close(self) -> None:
        pass

    def _headers(self) -> dict[str, str]:
        return {
            "X-Api-Key": self._api_key,
            "Content-Type": "application/json",
        }

    def _upload_audio(self, audio_path: Path) -> str:
        import httpx

        with open(audio_path, "rb") as f:
            resp = httpx.post(
                f"{self.API_BASE}/assets/upload",
                headers={"X-Api-Key": self._api_key},
                files={"file": (audio_path.name, f, "audio/mpeg")},
                timeout=60,
            )
        resp.raise_for_status()
        return resp.json()["data"]["asset_id"]

    def _create_video(self, audio_asset_id: str, image: str | None) -> str:
        import httpx

        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "talking_photo",
                        "talking_photo_url": image if image and image.startswith("http")
                        else "https://d-id-public-bucket.s3.us-west-2.amazonaws.com/alice.jpg",
                    },
                    "voice": {
                        "type": "audio",
                        "audio_asset_id": audio_asset_id,
                    },
                }
            ],
        }
        resp = httpx.post(
            f"{self.API_BASE}/video/generate",
            json=payload,
            headers=self._headers(),
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["data"]["video_id"]

    def _poll_video(self, video_id: str, timeout: float = 180) -> str:
        import time

        import httpx

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            resp = httpx.get(
                f"{self.API_BASE}/video_status.get?video_id={video_id}",
                headers=self._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            status = data.get("status")
            if status == "completed":
                return data["video_url"]
            if status == "failed":
                raise RuntimeError(f"HeyGen video failed: {data.get('error', 'unknown')}")
            time.sleep(5)

        raise TimeoutError(f"HeyGen video {video_id} did not complete within {timeout}s")


# ── Free (self-hosted): SadTalker ────────────────────────────────────────────

class SadTalkerProvider(AvatarProvider):
    """Generate talking-head video via SadTalker (local, requires GPU).

    Expects `sadtalker` CLI or Python package installed locally.
    Completely free but requires a GPU for reasonable speed.
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        sadtalker_path: str | None = None,
    ) -> None:
        self._output_dir = output_dir or Path(".")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._sadtalker_path = sadtalker_path or os.environ.get(
            "SADTALKER_PATH", "sadtalker"
        )
        self._counter = 0

    def generate(
        self,
        audio_path: Path,
        *,
        image: str | None = None,
        size: int = 120,
        style: str = "bounce",
        shape: str = "circle",
    ) -> Path:
        self._counter += 1

        if not image or not Path(image).exists():
            logger.warning("SadTalker requires a source image. Using animated fallback.")
            fallback = AnimatedAvatarProvider(output_dir=self._output_dir)
            return fallback.generate(
                audio_path, image=image, size=size, style=style, shape=shape,
            )

        out_path = self._output_dir / f"avatar_sadtalker_{self._counter:03d}.mp4"

        cmd = [
            "python", "-m", "sadtalker",
            "--driven_audio", str(audio_path),
            "--source_image", str(image),
            "--result_dir", str(self._output_dir),
            "--enhancer", "gfpgan",
        ]
        logger.info("Running SadTalker: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            logger.warning("SadTalker failed: %s", result.stderr[-300:])
            logger.info("Falling back to animated avatar")
            fallback = AnimatedAvatarProvider(output_dir=self._output_dir)
            return fallback.generate(
                audio_path, image=image, size=size, style=style, shape=shape,
            )

        # SadTalker outputs to result_dir — find the latest mp4
        results = sorted(self._output_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if results:
            results[-1].rename(out_path)
        else:
            raise FileNotFoundError("SadTalker produced no output")

        logger.info("SadTalker avatar clip: %s", out_path.name)
        return out_path

    def close(self) -> None:
        pass


# ── Registration ──────────────────────────────────────────────────────────────

AvatarProviderFactory.register("animated", AnimatedAvatarProvider)
AvatarProviderFactory.register("d-id", DIDProvider)
AvatarProviderFactory.register("heygen", HeyGenProvider)
AvatarProviderFactory.register("sadtalker", SadTalkerProvider)
