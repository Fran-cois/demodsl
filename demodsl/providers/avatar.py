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
        narration_text: str | None = None,
    ) -> Path:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
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

            elif style == "equalizer":
                # ── Windows XP Media Player equalizer bars ───────────
                draw = ImageDraw.Draw(canvas)
                num_bars = 7
                bar_w = max(4, canvas_size // (num_bars * 2))
                gap = max(2, bar_w // 2)
                total_w = num_bars * bar_w + (num_bars - 1) * gap
                start_x = (canvas_size - total_w) // 2
                floor_y = canvas_size - 10

                # XP neon green/yellow/red gradient
                xp_colors = [
                    (0, 255, 0, 230),
                    (50, 255, 0, 230),
                    (100, 255, 0, 230),
                    (180, 255, 0, 230),
                    (255, 255, 0, 230),
                    (255, 160, 0, 230),
                    (255, 50, 0, 230),
                ]

                # Dark rounded background
                draw.rounded_rectangle(
                    [4, 4, canvas_size - 5, canvas_size - 5],
                    radius=12, fill=(15, 15, 40, 200),
                )

                rng = np.random.default_rng(i)
                for b in range(num_bars):
                    jitter = rng.uniform(0.3, 1.0)
                    bar_amp = min(1.0, amp * jitter + rng.uniform(0, 0.1))
                    bar_h = int(bar_amp * (canvas_size - 30))
                    bx = start_x + b * (bar_w + gap)

                    seg_h = max(3, bar_w)
                    num_segs = max(1, bar_h // (seg_h + 1))
                    for s in range(num_segs):
                        sy = floor_y - (s + 1) * (seg_h + 1)
                        color_idx = min(len(xp_colors) - 1,
                                        int(s / max(1, num_segs) * len(xp_colors)))
                        draw.rectangle(
                            [bx, sy, bx + bar_w, sy + seg_h],
                            fill=xp_colors[color_idx],
                        )

                    # Peak hold indicator
                    if num_segs > 0:
                        peak_y = floor_y - num_segs * (seg_h + 1) - 3
                        draw.rectangle(
                            [bx, peak_y, bx + bar_w, peak_y + 2],
                            fill=(255, 255, 255, 200),
                        )

            elif style == "xp_bliss":
                # ── Windows XP Bliss wallpaper homage ────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size

                # Sky gradient (XP blue)
                for row in range(cs // 2):
                    t = row / max(1, cs // 2)
                    r = int(50 + t * 80)
                    g = int(120 + t * 60)
                    b_col = int(220 - t * 30)
                    draw.line([(0, row), (cs, row)], fill=(r, g, b_col, 255))

                # Green hills
                for row in range(cs // 2, cs):
                    t = (row - cs // 2) / max(1, cs // 2)
                    g = int(180 - t * 60)
                    draw.line([(0, row), (cs, row)], fill=(60, g, 30, 255))

                # Wavy hill line
                for px in range(cs):
                    hill_y = int(cs // 2 + math.sin(px * 0.05 + i * 0.1) * 15
                                + math.sin(px * 0.02) * 10)
                    draw.line([(px, hill_y), (px, hill_y + 3)],
                              fill=(80, 200, 50, 255))

                # Sun bounces with amplitude
                sun_r = 12 + int(amp * 8)
                sun_x = cs // 4 + int(math.sin(i * 0.05) * 20)
                sun_y = 20 + int(-amp * 15)
                for gr in range(sun_r + 10, sun_r, -2):
                    alpha = int(60 * (1 - (gr - sun_r) / 10))
                    draw.ellipse(
                        [sun_x - gr, sun_y - gr, sun_x + gr, sun_y + gr],
                        fill=(255, 255, 100, max(0, alpha)),
                    )
                draw.ellipse(
                    [sun_x - sun_r, sun_y - sun_r,
                     sun_x + sun_r, sun_y + sun_r],
                    fill=(255, 240, 50, 255),
                )

                # Musical notes floating up
                if amp > 0.15:
                    try:
                        note_font = ImageFont.truetype(
                            "/System/Library/Fonts/Apple Color Emoji.ttc", 16)
                    except (OSError, IOError):
                        note_font = ImageFont.load_default()
                    notes = ["♪", "♫", "♬"]
                    for ni in range(int(amp * 4)):
                        nx = int(cs * 0.5 + math.sin(i * 0.2 + ni * 2) * cs * 0.3)
                        ny = int(cs * 0.6 - amp * 30 - ni * 18
                                 + math.sin(i * 0.15 + ni) * 8)
                        note_alpha = int(200 * (1 - ni / 4))
                        draw.text((nx, ny), notes[ni % len(notes)],
                                  fill=(255, 255, 255, max(50, note_alpha)),
                                  font=note_font)

            elif style == "clippy":
                # ── Clippy v2 — faithful to the original Office assistant ───
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx, cy_base = cs // 2, cs // 2

                # Idle sway: gentle left-right lean
                sway = math.sin(i * 0.12) * 3
                # Bounce when speaking
                bounce = int(amp * 8)

                cy = cy_base - bounce

                # ── Yellow speech bubble background (like original) ──
                bub_pad = int(cs * 0.04)
                draw.rounded_rectangle(
                    [bub_pad, bub_pad, cs - bub_pad, cs - bub_pad],
                    radius=int(cs * 0.12),
                    fill=(255, 255, 230, 210),
                    outline=(200, 190, 140, 255), width=2,
                )

                # ── Scale factors relative to canvas ──
                # Original Clippy is a tall paperclip ~3:1 aspect
                hw = int(cs * 0.12)  # half-width of clip wire
                wire_w = max(3, int(cs * 0.025))
                silver = (165, 170, 175, 255)
                silver_hi = (210, 215, 220, 255)
                silver_dk = (120, 125, 130, 255)

                # Clippy top: ~30% from top
                top_y = int(cy - cs * 0.22)
                bot_y = int(cy + cs * 0.28)
                mid_y = int((top_y + bot_y) / 2)

                # Shift for sway
                sx = int(sway)

                # ── Outer wire (the big U going down then up) ──
                # Left descending arm
                pts_outer = [
                    (cx - hw + sx, top_y),
                    (cx - hw + sx, bot_y - hw),
                ]
                draw.line(pts_outer, fill=silver, width=wire_w)
                # Bottom curve
                draw.arc(
                    [cx - hw + sx, bot_y - hw * 2,
                     cx + hw + sx, bot_y],
                    start=0, end=180, fill=silver, width=wire_w,
                )
                # Right ascending arm
                draw.line(
                    [(cx + hw + sx, bot_y - hw),
                     (cx + hw + sx, mid_y + int(cs * 0.02))],
                    fill=silver, width=wire_w,
                )

                # ── Inner wire (the inner loop going back down) ──
                inner_hw = int(hw * 0.55)
                inner_top = mid_y - int(cs * 0.02)
                inner_bot = bot_y - int(cs * 0.08)
                # Top curve of inner loop
                draw.arc(
                    [cx - inner_hw + sx, inner_top - inner_hw,
                     cx + inner_hw + sx, inner_top + inner_hw],
                    start=180, end=0, fill=silver_hi, width=wire_w,
                )
                # Left inner arm going down
                draw.line(
                    [(cx - inner_hw + sx, inner_top),
                     (cx - inner_hw + sx, inner_bot - inner_hw)],
                    fill=silver_hi, width=wire_w,
                )
                # Inner bottom curve
                draw.arc(
                    [cx - inner_hw + sx, inner_bot - inner_hw * 2,
                     cx + inner_hw + sx, inner_bot],
                    start=0, end=180, fill=silver_hi, width=wire_w,
                )
                # Right inner arm going up
                draw.line(
                    [(cx + inner_hw + sx, inner_bot - inner_hw),
                     (cx + inner_hw + sx, inner_top)],
                    fill=silver_hi, width=wire_w,
                )

                # ── Top curve (the "head" of the paperclip) ──
                draw.arc(
                    [cx - hw + sx, top_y - hw,
                     cx + hw + sx, top_y + hw],
                    start=180, end=360, fill=silver, width=wire_w,
                )

                # ── Big expressive eyes (trademark Clippy feature) ──
                eye_w = int(cs * 0.09)
                eye_h = int(cs * 0.11)
                eye_y = top_y + int(cs * 0.02)
                eye_gap = int(cs * 0.03)

                # Eye whites
                le = (cx - eye_gap - eye_w + sx, eye_y - eye_h // 2,
                      cx - eye_gap + sx, eye_y + eye_h // 2)
                re = (cx + eye_gap + sx, eye_y - eye_h // 2,
                      cx + eye_gap + eye_w + sx, eye_y + eye_h // 2)
                draw.ellipse(le, fill=(255, 255, 255, 255),
                             outline=(100, 100, 100, 255), width=1)
                draw.ellipse(re, fill=(255, 255, 255, 255),
                             outline=(100, 100, 100, 255), width=1)

                # Pupils — follow audio amplitude + wander
                pupil_r = max(2, int(cs * 0.028))
                look_x = int(math.sin(i * 0.15) * cs * 0.015)
                look_y = int(math.cos(i * 0.12) * cs * 0.01) - int(amp * cs * 0.02)
                for ex in [le, re]:
                    pcx = (ex[0] + ex[2]) // 2 + look_x
                    pcy = (ex[1] + ex[3]) // 2 + look_y
                    draw.ellipse(
                        [pcx - pupil_r, pcy - pupil_r,
                         pcx + pupil_r, pcy + pupil_r],
                        fill=(30, 30, 30, 255),
                    )
                    # Glint
                    gl = max(1, pupil_r // 2)
                    draw.ellipse(
                        [pcx - pupil_r + 1, pcy - pupil_r + 1,
                         pcx - pupil_r + 1 + gl, pcy - pupil_r + 1 + gl],
                        fill=(255, 255, 255, 200),
                    )

                # ── Eyebrows — raise when speaking ──
                brow_lift = int(amp * cs * 0.03)
                brow_y = eye_y - eye_h // 2 - int(cs * 0.02) - brow_lift
                brow_len = int(cs * 0.06)
                # Left brow (slightly angled)
                draw.line(
                    [(cx - eye_gap - eye_w + sx + 2, brow_y + 2),
                     (cx - eye_gap + sx - 2, brow_y)],
                    fill=silver_dk, width=max(2, wire_w - 1),
                )
                # Right brow
                draw.line(
                    [(cx + eye_gap + sx + 2, brow_y),
                     (cx + eye_gap + eye_w + sx - 2, brow_y + 2)],
                    fill=silver_dk, width=max(2, wire_w - 1),
                )

                # ── Mouth — opens with amplitude ──
                mouth_y = eye_y + eye_h // 2 + int(cs * 0.03)
                mouth_w = int(cs * 0.06)
                mouth_open = int(amp * cs * 0.05) + 1
                if amp > 0.15:
                    # Open mouth (ellipse)
                    draw.ellipse(
                        [cx - mouth_w + sx, mouth_y,
                         cx + mouth_w + sx, mouth_y + mouth_open * 2],
                        fill=(80, 40, 40, 200),
                        outline=(100, 100, 100, 255), width=1,
                    )
                else:
                    # Closed smile
                    draw.arc(
                        [cx - mouth_w + sx, mouth_y - int(cs * 0.02),
                         cx + mouth_w + sx, mouth_y + int(cs * 0.02)],
                        start=10, end=170, fill=(100, 100, 100, 255),
                        width=max(1, wire_w - 1),
                    )

                # ── Narration text (progressive word reveal) ──
                try:
                    txt_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc",
                        max(9, int(cs * 0.06)))
                except (OSError, IOError):
                    txt_font = ImageFont.load_default()

                text_y = bot_y + int(cs * 0.02)
                avail_h = cs - bub_pad - text_y
                avail_w = cs - bub_pad * 2 - int(cs * 0.08)

                if avail_h > int(cs * 0.06) and narration_text:
                    # Progressive reveal: show words up to current frame
                    words = narration_text.split()
                    progress = (i + 1) / max(1, total_frames)
                    n_words = max(1, int(len(words) * progress))
                    visible = " ".join(words[:n_words])

                    # Word-wrap into lines
                    lines: list[str] = []
                    current_line = ""
                    for w in visible.split():
                        test = f"{current_line} {w}".strip()
                        bbox = txt_font.getbbox(test)
                        tw = bbox[2] - bbox[0] if bbox else len(test) * 6
                        if tw > avail_w and current_line:
                            lines.append(current_line)
                            current_line = w
                        else:
                            current_line = test
                    if current_line:
                        lines.append(current_line)

                    # Draw lines (limit to available height)
                    line_h = int(cs * 0.075)
                    max_lines = max(1, avail_h // line_h)
                    # Show last N lines if overflow
                    display_lines = lines[-max_lines:]
                    for li, line_text in enumerate(display_lines):
                        draw.text(
                            (bub_pad + int(cs * 0.04), text_y + li * line_h),
                            line_text,
                            fill=(80, 80, 70, 210), font=txt_font,
                        )
                elif avail_h > int(cs * 0.06):
                    # Fallback: no narration text
                    draw.text(
                        (bub_pad + int(cs * 0.06), text_y),
                        "..." if amp > 0.1 else "",
                        fill=(80, 80, 70, 160), font=txt_font,
                    )

            elif style == "visualizer":
                # ── Circular spectrum (Windows Media Player style) ───
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                center = cs // 2

                # Dark circular background
                draw.ellipse([4, 4, cs - 5, cs - 5], fill=(10, 10, 30, 210))

                num_rays = 24
                rng_v = np.random.default_rng(i)
                for r in range(num_rays):
                    angle = (2 * math.pi * r / num_rays) + i * 0.02
                    jitter = rng_v.uniform(0.4, 1.0)
                    ray_amp = min(1.0, amp * jitter + rng_v.uniform(0, 0.08))
                    inner_r = size // 4
                    outer_r = inner_r + int(ray_amp * size * 0.4)

                    x0 = center + int(math.cos(angle) * inner_r)
                    y0 = center + int(math.sin(angle) * inner_r)
                    x1 = center + int(math.cos(angle) * outer_r)
                    y1 = center + int(math.sin(angle) * outer_r)

                    # Rainbow hue cycle
                    hue = (r / num_rays + i * 0.005) % 1.0
                    cr = int(255 * max(0, min(1, abs(hue * 6 - 3) - 1)))
                    cg = int(255 * max(0, min(1, 2 - abs(hue * 6 - 2))))
                    cb = int(255 * max(0, min(1, 2 - abs(hue * 6 - 4))))
                    alpha = int(150 + ray_amp * 105)
                    draw.line([(x0, y0), (x1, y1)],
                              fill=(cr, cg, cb, alpha), width=3)

                # Inner avatar
                inner_size = size // 2
                inner_img = avatar_img.resize(
                    (inner_size, inner_size), Image.LANCZOS)
                ix = center - inner_size // 2
                iy = center - inner_size // 2
                canvas.paste(inner_img, (ix, iy), inner_img)

                # Outer ring pulse
                ring_r = size // 4 + 2
                ring_alpha = int(100 + amp * 155)
                draw.ellipse(
                    [center - ring_r, center - ring_r,
                     center + ring_r, center + ring_r],
                    outline=(150, 150, 255, ring_alpha), width=2,
                )

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
        narration_text: str | None = None,
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
        narration_text: str | None = None,
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
        narration_text: str | None = None,
    ) -> Path:
        self._counter += 1

        if not image or not Path(image).exists():
            logger.warning("SadTalker requires a source image. Using animated fallback.")
            fallback = AnimatedAvatarProvider(output_dir=self._output_dir)
            return fallback.generate(
                audio_path, image=image, size=size, style=style, shape=shape,
                narration_text=narration_text,
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
