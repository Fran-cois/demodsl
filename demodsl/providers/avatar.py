"""Avatar providers — animated (free) + D-ID, HeyGen, SadTalker (paid)."""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from demodsl.providers.base import AvatarProvider, AvatarProviderFactory

if TYPE_CHECKING:
    from PIL.Image import Image as _PILImage
    from pydub import AudioSegment

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
        background_shape: str = "square",
        narration_text: str | None = None,
    ) -> Path:
        from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
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
                    [
                        half - ring_radius,
                        half - ring_radius,
                        half + ring_radius,
                        half + ring_radius,
                    ],
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
                        [half - glow_r, half - glow_r, half + glow_r, half + glow_r],
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
                    radius=12,
                    fill=(15, 15, 40, 200),
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
                        color_idx = min(
                            len(xp_colors) - 1,
                            int(s / max(1, num_segs) * len(xp_colors)),
                        )
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
                    hill_y = int(
                        cs // 2 + math.sin(px * 0.05 + i * 0.1) * 15 + math.sin(px * 0.02) * 10
                    )
                    draw.line([(px, hill_y), (px, hill_y + 3)], fill=(80, 200, 50, 255))

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
                    [sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r],
                    fill=(255, 240, 50, 255),
                )

                # Musical notes floating up
                if amp > 0.15:
                    try:
                        note_font = ImageFont.truetype(
                            "/System/Library/Fonts/Apple Color Emoji.ttc", 16
                        )
                    except OSError:
                        note_font = ImageFont.load_default()
                    notes = ["♪", "♫", "♬"]
                    for ni in range(int(amp * 4)):
                        nx = int(cs * 0.5 + math.sin(i * 0.2 + ni * 2) * cs * 0.3)
                        ny = int(cs * 0.6 - amp * 30 - ni * 18 + math.sin(i * 0.15 + ni) * 8)
                        note_alpha = int(200 * (1 - ni / 4))
                        draw.text(
                            (nx, ny),
                            notes[ni % len(notes)],
                            fill=(255, 255, 255, max(50, note_alpha)),
                            font=note_font,
                        )

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
                    outline=(200, 190, 140, 255),
                    width=2,
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
                    [cx - hw + sx, bot_y - hw * 2, cx + hw + sx, bot_y],
                    start=0,
                    end=180,
                    fill=silver,
                    width=wire_w,
                )
                # Right ascending arm
                draw.line(
                    [
                        (cx + hw + sx, bot_y - hw),
                        (cx + hw + sx, mid_y + int(cs * 0.02)),
                    ],
                    fill=silver,
                    width=wire_w,
                )

                # ── Inner wire (the inner loop going back down) ──
                inner_hw = int(hw * 0.55)
                inner_top = mid_y - int(cs * 0.02)
                inner_bot = bot_y - int(cs * 0.08)
                # Top curve of inner loop
                draw.arc(
                    [
                        cx - inner_hw + sx,
                        inner_top - inner_hw,
                        cx + inner_hw + sx,
                        inner_top + inner_hw,
                    ],
                    start=180,
                    end=0,
                    fill=silver_hi,
                    width=wire_w,
                )
                # Left inner arm going down
                draw.line(
                    [
                        (cx - inner_hw + sx, inner_top),
                        (cx - inner_hw + sx, inner_bot - inner_hw),
                    ],
                    fill=silver_hi,
                    width=wire_w,
                )
                # Inner bottom curve
                draw.arc(
                    [
                        cx - inner_hw + sx,
                        inner_bot - inner_hw * 2,
                        cx + inner_hw + sx,
                        inner_bot,
                    ],
                    start=0,
                    end=180,
                    fill=silver_hi,
                    width=wire_w,
                )
                # Right inner arm going up
                draw.line(
                    [
                        (cx + inner_hw + sx, inner_bot - inner_hw),
                        (cx + inner_hw + sx, inner_top),
                    ],
                    fill=silver_hi,
                    width=wire_w,
                )

                # ── Top curve (the "head" of the paperclip) ──
                draw.arc(
                    [cx - hw + sx, top_y - hw, cx + hw + sx, top_y + hw],
                    start=180,
                    end=360,
                    fill=silver,
                    width=wire_w,
                )

                # ── Big expressive eyes (trademark Clippy feature) ──
                eye_w = int(cs * 0.09)
                eye_h = int(cs * 0.11)
                eye_y = top_y + int(cs * 0.02)
                eye_gap = int(cs * 0.03)

                # Eye whites
                le = (
                    cx - eye_gap - eye_w + sx,
                    eye_y - eye_h // 2,
                    cx - eye_gap + sx,
                    eye_y + eye_h // 2,
                )
                re = (
                    cx + eye_gap + sx,
                    eye_y - eye_h // 2,
                    cx + eye_gap + eye_w + sx,
                    eye_y + eye_h // 2,
                )
                draw.ellipse(le, fill=(255, 255, 255, 255), outline=(100, 100, 100, 255), width=1)
                draw.ellipse(re, fill=(255, 255, 255, 255), outline=(100, 100, 100, 255), width=1)

                # Pupils — follow audio amplitude + wander
                pupil_r = max(2, int(cs * 0.028))
                look_x = int(math.sin(i * 0.15) * cs * 0.015)
                look_y = int(math.cos(i * 0.12) * cs * 0.01) - int(amp * cs * 0.02)
                for ex in [le, re]:
                    pcx = (ex[0] + ex[2]) // 2 + look_x
                    pcy = (ex[1] + ex[3]) // 2 + look_y
                    draw.ellipse(
                        [pcx - pupil_r, pcy - pupil_r, pcx + pupil_r, pcy + pupil_r],
                        fill=(30, 30, 30, 255),
                    )
                    # Glint
                    gl = max(1, pupil_r // 2)
                    draw.ellipse(
                        [
                            pcx - pupil_r + 1,
                            pcy - pupil_r + 1,
                            pcx - pupil_r + 1 + gl,
                            pcy - pupil_r + 1 + gl,
                        ],
                        fill=(255, 255, 255, 200),
                    )

                # ── Eyebrows — raise when speaking ──
                brow_lift = int(amp * cs * 0.03)
                brow_y = eye_y - eye_h // 2 - int(cs * 0.02) - brow_lift
                int(cs * 0.06)
                # Left brow (slightly angled)
                draw.line(
                    [
                        (cx - eye_gap - eye_w + sx + 2, brow_y + 2),
                        (cx - eye_gap + sx - 2, brow_y),
                    ],
                    fill=silver_dk,
                    width=max(2, wire_w - 1),
                )
                # Right brow
                draw.line(
                    [
                        (cx + eye_gap + sx + 2, brow_y),
                        (cx + eye_gap + eye_w + sx - 2, brow_y + 2),
                    ],
                    fill=silver_dk,
                    width=max(2, wire_w - 1),
                )

                # ── Mouth — opens with amplitude ──
                mouth_y = eye_y + eye_h // 2 + int(cs * 0.03)
                mouth_w = int(cs * 0.06)
                mouth_open = int(amp * cs * 0.05) + 1
                if amp > 0.15:
                    # Open mouth (ellipse)
                    draw.ellipse(
                        [
                            cx - mouth_w + sx,
                            mouth_y,
                            cx + mouth_w + sx,
                            mouth_y + mouth_open * 2,
                        ],
                        fill=(80, 40, 40, 200),
                        outline=(100, 100, 100, 255),
                        width=1,
                    )
                else:
                    # Closed smile
                    draw.arc(
                        [
                            cx - mouth_w + sx,
                            mouth_y - int(cs * 0.02),
                            cx + mouth_w + sx,
                            mouth_y + int(cs * 0.02),
                        ],
                        start=10,
                        end=170,
                        fill=(100, 100, 100, 255),
                        width=max(1, wire_w - 1),
                    )

                # ── Narration text (progressive word reveal) ──
                try:
                    txt_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(9, int(cs * 0.06))
                    )
                except OSError:
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
                            fill=(80, 80, 70, 210),
                            font=txt_font,
                        )
                elif avail_h > int(cs * 0.06):
                    # Fallback: no narration text
                    draw.text(
                        (bub_pad + int(cs * 0.06), text_y),
                        "..." if amp > 0.1 else "",
                        fill=(80, 80, 70, 160),
                        font=txt_font,
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
                    draw.line([(x0, y0), (x1, y1)], fill=(cr, cg, cb, alpha), width=3)

                # Inner avatar
                inner_size = size // 2
                inner_img = avatar_img.resize((inner_size, inner_size), Image.LANCZOS)
                ix = center - inner_size // 2
                iy = center - inner_size // 2
                canvas.paste(inner_img, (ix, iy), inner_img)

                # Outer ring pulse
                ring_r = size // 4 + 2
                ring_alpha = int(100 + amp * 155)
                draw.ellipse(
                    [
                        center - ring_r,
                        center - ring_r,
                        center + ring_r,
                        center + ring_r,
                    ],
                    outline=(150, 150, 255, ring_alpha),
                    width=2,
                )

            elif style == "pacman":
                # ── Pac-Man arcade ────────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size

                # Black arcade background
                draw.rounded_rectangle(
                    [2, 2, cs - 3, cs - 3],
                    radius=10,
                    fill=(0, 0, 20, 220),
                )

                # Pac-Man: mouth opens/closes with amplitude
                pac_r = int(cs * 0.18)
                pac_cx = int(cs * 0.32)
                pac_cy = cs // 2
                # Mouth angle: 5° (closed) to 45° (open)
                mouth_angle = 5 + int(amp * 40)
                draw.pieslice(
                    [pac_cx - pac_r, pac_cy - pac_r, pac_cx + pac_r, pac_cy + pac_r],
                    start=mouth_angle,
                    end=360 - mouth_angle,
                    fill=(255, 255, 0, 255),
                )
                # Pac-Man eye
                eye_r = max(2, int(pac_r * 0.15))
                eye_x = pac_cx + int(pac_r * 0.2)
                eye_y = pac_cy - int(pac_r * 0.4)
                draw.ellipse(
                    [eye_x - eye_r, eye_y - eye_r, eye_x + eye_r, eye_y + eye_r],
                    fill=(0, 0, 0, 255),
                )

                # Dots (pellets) — some eaten based on frame progress
                dot_r = max(2, int(cs * 0.025))
                num_dots = 4
                progress = (i + 1) / max(1, total_frames)
                eaten = int(progress * num_dots)
                for d in range(num_dots):
                    if d < eaten:
                        continue
                    dx = int(cs * 0.52 + d * cs * 0.1)
                    dy = cs // 2
                    draw.ellipse(
                        [dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r],
                        fill=(255, 255, 255, 220),
                    )

                # Ghost — colorful, bouncing
                ghost_colors = [
                    (255, 0, 0, 230),
                    (255, 184, 255, 230),
                    (0, 255, 255, 230),
                    (255, 184, 82, 230),
                ]
                gc = ghost_colors[i % len(ghost_colors)]
                ghost_r = int(cs * 0.13)
                ghost_cx = int(cs * 0.78 + math.sin(i * 0.15) * cs * 0.06)
                ghost_cy = int(cs // 2 + math.cos(i * 0.2) * cs * 0.04)
                # Ghost body: top half circle + rectangle bottom
                draw.ellipse(
                    [
                        ghost_cx - ghost_r,
                        ghost_cy - ghost_r,
                        ghost_cx + ghost_r,
                        ghost_cy + int(ghost_r * 0.3),
                    ],
                    fill=gc,
                )
                draw.rectangle(
                    [
                        ghost_cx - ghost_r,
                        ghost_cy,
                        ghost_cx + ghost_r,
                        ghost_cy + ghost_r,
                    ],
                    fill=gc,
                )
                # Ghost wavy bottom
                wave_segs = 3
                seg_w = (ghost_r * 2) // wave_segs
                for ws in range(wave_segs):
                    wx = ghost_cx - ghost_r + ws * seg_w
                    wy = ghost_cy + ghost_r
                    draw.pieslice(
                        [wx, wy - seg_w // 2, wx + seg_w, wy + seg_w // 2],
                        start=0,
                        end=180,
                        fill=gc,
                    )
                # Ghost eyes
                for ex_off in [-int(ghost_r * 0.35), int(ghost_r * 0.35)]:
                    ew = max(2, int(ghost_r * 0.3))
                    eh = max(3, int(ghost_r * 0.35))
                    ecx = ghost_cx + ex_off
                    ecy = ghost_cy - int(ghost_r * 0.15)
                    draw.ellipse(
                        [ecx - ew, ecy - eh, ecx + ew, ecy + eh],
                        fill=(255, 255, 255, 255),
                    )
                    # Pupil
                    pw = max(1, ew // 2)
                    draw.ellipse(
                        [ecx - pw + 1, ecy - pw, ecx + pw + 1, ecy + pw],
                        fill=(20, 20, 100, 255),
                    )

                # Score text
                try:
                    score_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(10, int(cs * 0.07))
                    )
                except OSError:
                    score_font = ImageFont.load_default()
                score = int(progress * 9990)
                draw.text(
                    (int(cs * 0.05), int(cs * 0.06)),
                    f"SCORE {score:04d}",
                    fill=(255, 255, 255, 200),
                    font=score_font,
                )

            elif style == "space_invader":
                # ── Space Invaders pixel-art ──────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size

                # Black starfield background
                draw.rectangle([0, 0, cs, cs], fill=(0, 0, 10, 230))
                rng_si = np.random.default_rng(42)
                for _ in range(15):
                    sx = int(rng_si.uniform(4, cs - 4))
                    sy = int(rng_si.uniform(4, cs - 4))
                    sr = rng_si.choice([1, 1, 1, 2])
                    brightness = int(rng_si.uniform(100, 255))
                    draw.ellipse(
                        [sx - sr, sy - sr, sx + sr, sy + sr],
                        fill=(brightness, brightness, brightness, 200),
                    )

                # Pixel size for the invader sprite
                px = max(2, int(cs * 0.028))

                # Classic Space Invader sprite (11x8 grid, 2-frame animation)
                sprite_a = [
                    [0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
                    [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
                    [0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0],
                    [0, 1, 1, 0, 1, 1, 1, 0, 1, 1, 0],
                    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                    [1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1],
                    [1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 1],
                    [0, 0, 0, 1, 1, 0, 1, 1, 0, 0, 0],
                ]
                sprite_b = [
                    [0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
                    [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1],
                    [1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1],
                    [1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1],
                    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                    [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
                    [0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
                    [0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0],
                ]
                # Alternate frames
                sprite = sprite_a if (i // 8) % 2 == 0 else sprite_b

                # Invader color: classic green
                inv_color = (0, 255, 68, 255)

                # Draw invader centered, with horizontal sway
                sway_x = int(math.sin(i * 0.08) * cs * 0.08)
                inv_w = len(sprite[0]) * px
                inv_h = len(sprite) * px
                base_x = (cs - inv_w) // 2 + sway_x
                base_y = int(cs * 0.15)

                for row_idx, row in enumerate(sprite):
                    for col_idx, val in enumerate(row):
                        if val:
                            bx = base_x + col_idx * px
                            by = base_y + row_idx * px
                            draw.rectangle(
                                [bx, by, bx + px - 1, by + px - 1],
                                fill=inv_color,
                            )

                # Missile from invader when amplitude is high
                if amp > 0.2:
                    missile_x = base_x + inv_w // 2
                    missile_y = base_y + inv_h + int(amp * cs * 0.3)
                    missile_h = max(4, int(cs * 0.06))
                    draw.rectangle(
                        [
                            missile_x - 1,
                            missile_y,
                            missile_x + 1,
                            missile_y + missile_h,
                        ],
                        fill=(255, 255, 255, 230),
                    )

                # Shield blocks at bottom (green, pixelated)
                shield_y = int(cs * 0.75)
                shield_color = (0, 200, 0, 180)
                for sh in range(3):
                    sh_x = int(cs * 0.2 + sh * cs * 0.25)
                    for sr in range(3):
                        for sc in range(5):
                            draw.rectangle(
                                [
                                    sh_x + sc * px,
                                    shield_y + sr * px,
                                    sh_x + (sc + 1) * px - 1,
                                    shield_y + (sr + 1) * px - 1,
                                ],
                                fill=shield_color,
                            )

                # Player cannon at bottom
                cannon_w = int(cs * 0.08)
                cannon_h = int(cs * 0.04)
                cannon_x = cs // 2 - cannon_w // 2
                cannon_y = int(cs * 0.88)
                draw.rectangle(
                    [cannon_x, cannon_y, cannon_x + cannon_w, cannon_y + cannon_h],
                    fill=(0, 255, 0, 230),
                )
                # Cannon barrel
                barrel_w = max(2, px)
                draw.rectangle(
                    [
                        cs // 2 - barrel_w,
                        cannon_y - cannon_h,
                        cs // 2 + barrel_w,
                        cannon_y,
                    ],
                    fill=(0, 255, 0, 230),
                )

                # Score
                try:
                    sc_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(9, int(cs * 0.06))
                    )
                except OSError:
                    sc_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.05), int(cs * 0.04)),
                    f"SCORE {int((i / max(1, total_frames)) * 1500):04d}",
                    fill=(255, 255, 255, 200),
                    font=sc_font,
                )

            elif style == "mario_block":
                # ── Mario "?" block ───────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size

                # Blue sky background
                for row in range(cs):
                    t = row / cs
                    r = int(92 + t * 30)
                    g = int(148 + t * 40)
                    b_col = int(252 - t * 20)
                    draw.line([(0, row), (cs, row)], fill=(r, g, b_col, 255))

                # Block bounces with amplitude
                block_size = int(cs * 0.35)
                block_x = (cs - block_size) // 2
                bounce_offset = int(amp * cs * 0.12)
                block_y = int(cs * 0.45) - bounce_offset

                # Block body (orange/brown)
                draw.rounded_rectangle(
                    [block_x, block_y, block_x + block_size, block_y + block_size],
                    radius=4,
                    fill=(230, 160, 30, 255),
                    outline=(140, 90, 10, 255),
                    width=max(2, int(cs * 0.015)),
                )

                # Inner darker border
                inset = int(cs * 0.025)
                draw.rounded_rectangle(
                    [
                        block_x + inset,
                        block_y + inset,
                        block_x + block_size - inset,
                        block_y + block_size - inset,
                    ],
                    radius=3,
                    outline=(180, 110, 20, 200),
                    width=max(1, int(cs * 0.008)),
                )

                # "?" character
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc",
                        max(14, int(block_size * 0.55)),
                    )
                except OSError:
                    q_font = ImageFont.load_default()

                q_bbox = draw.textbbox((0, 0), "?", font=q_font)
                q_w = q_bbox[2] - q_bbox[0]
                q_h = q_bbox[3] - q_bbox[1]
                # Shadow
                draw.text(
                    (
                        block_x + (block_size - q_w) // 2 + 2,
                        block_y + (block_size - q_h) // 2 - q_bbox[1] + 2,
                    ),
                    "?",
                    fill=(140, 90, 10, 180),
                    font=q_font,
                )
                # "?" in white
                draw.text(
                    (
                        block_x + (block_size - q_w) // 2,
                        block_y + (block_size - q_h) // 2 - q_bbox[1],
                    ),
                    "?",
                    fill=(255, 255, 255, 255),
                    font=q_font,
                )

                # Corner rivets
                rivet_r = max(2, int(cs * 0.02))
                rivet_inset = int(cs * 0.04)
                for rx, ry in [
                    (block_x + rivet_inset, block_y + rivet_inset),
                    (block_x + block_size - rivet_inset, block_y + rivet_inset),
                    (block_x + rivet_inset, block_y + block_size - rivet_inset),
                    (
                        block_x + block_size - rivet_inset,
                        block_y + block_size - rivet_inset,
                    ),
                ]:
                    draw.ellipse(
                        [rx - rivet_r, ry - rivet_r, rx + rivet_r, ry + rivet_r],
                        fill=(180, 110, 20, 200),
                    )

                # Coin popping out when amplitude > 0.3
                if amp > 0.3:
                    coin_r = int(cs * 0.06)
                    coin_x = cs // 2
                    coin_y = block_y - int((amp - 0.3) * cs * 0.4) - coin_r
                    # Coin (golden circle)
                    draw.ellipse(
                        [
                            coin_x - coin_r,
                            coin_y - coin_r,
                            coin_x + coin_r,
                            coin_y + coin_r,
                        ],
                        fill=(255, 215, 0, 255),
                        outline=(200, 160, 0, 255),
                        width=2,
                    )
                    # "$" on coin
                    try:
                        coin_font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc",
                            max(8, int(coin_r * 1.1)),
                        )
                    except OSError:
                        coin_font = ImageFont.load_default()
                    cb = draw.textbbox((0, 0), "$", font=coin_font)
                    cw = cb[2] - cb[0]
                    ch = cb[3] - cb[1]
                    draw.text(
                        (coin_x - cw // 2, coin_y - ch // 2 - cb[1]),
                        "$",
                        fill=(180, 120, 0, 255),
                        font=coin_font,
                    )

                    # Sparkles around coin
                    for sp in range(3):
                        sp_angle = math.pi * 2 * sp / 3 + i * 0.3
                        sp_dist = coin_r + int(amp * cs * 0.06) + sp * 4
                        sp_x = coin_x + int(math.cos(sp_angle) * sp_dist)
                        sp_y = coin_y + int(math.sin(sp_angle) * sp_dist)
                        sp_r = max(1, int(cs * 0.012))
                        draw.ellipse(
                            [sp_x - sp_r, sp_y - sp_r, sp_x + sp_r, sp_y + sp_r],
                            fill=(255, 255, 200, int(200 * amp)),
                        )

            elif style == "nyan_cat":
                # ── Nyan Cat — pixel-art cat on rainbow ───────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size

                # Dark blue starfield background
                draw.rectangle([0, 0, cs, cs], fill=(10, 10, 50, 255))

                # Scrolling stars
                rng_nc = np.random.default_rng(42)
                star_positions = [
                    (int(rng_nc.uniform(0, cs)), int(rng_nc.uniform(0, cs))) for _ in range(20)
                ]
                for sx_base, sy in star_positions:
                    sx = (sx_base - i * 3) % cs
                    sr = rng_nc.choice([1, 1, 2])
                    draw.ellipse(
                        [sx - sr, sy - sr, sx + sr, sy + sr],
                        fill=(255, 255, 255, int(rng_nc.uniform(120, 255))),
                    )

                # Rainbow trail (6 bands) flowing left
                rainbow_colors = [
                    (255, 0, 0, 200),  # red
                    (255, 154, 0, 200),  # orange
                    (255, 255, 0, 200),  # yellow
                    (0, 255, 0, 200),  # green
                    (0, 0, 255, 200),  # blue
                    (130, 0, 200, 200),  # violet
                ]
                band_h = max(3, int(cs * 0.04))
                cat_cx = int(cs * 0.55)
                cat_cy = int(cs * 0.45 + math.sin(i * 0.2) * cs * 0.04)  # bounce
                rainbow_start_y = cat_cy - len(rainbow_colors) * band_h // 2
                trail_end = cat_cx - int(cs * 0.12)

                for bi, bc in enumerate(rainbow_colors):
                    by = rainbow_start_y + bi * band_h
                    # Wavy trail
                    for px_x in range(0, trail_end, 2):
                        wave = int(math.sin(px_x * 0.06 + i * 0.15 + bi * 0.5) * 2)
                        draw.rectangle(
                            [px_x, by + wave, px_x + 2, by + band_h + wave],
                            fill=bc,
                        )

                # Nyan cat body: Pop-Tart (pink rectangle)
                tart_w = int(cs * 0.18)
                tart_h = int(cs * 0.14)
                tart_x = cat_cx - tart_w // 2
                tart_y = cat_cy - tart_h // 2
                draw.rounded_rectangle(
                    [tart_x, tart_y, tart_x + tart_w, tart_y + tart_h],
                    radius=3,
                    fill=(255, 180, 200, 255),
                    outline=(200, 120, 140, 255),
                    width=2,
                )
                # Sprinkles on Pop-Tart
                rng_sprinkle = np.random.default_rng(123)
                sprinkle_colors = [
                    (255, 0, 100, 200),
                    (100, 255, 100, 200),
                    (100, 100, 255, 200),
                    (255, 255, 0, 200),
                ]
                for _ in range(6):
                    spr_x = int(rng_sprinkle.uniform(tart_x + 4, tart_x + tart_w - 4))
                    spr_y = int(rng_sprinkle.uniform(tart_y + 4, tart_y + tart_h - 4))
                    draw.ellipse(
                        [spr_x - 1, spr_y - 1, spr_x + 1, spr_y + 1],
                        fill=sprinkle_colors[int(rng_sprinkle.integers(0, len(sprinkle_colors)))],
                    )

                # Cat face (gray, right side of tart)
                face_r = int(cs * 0.06)
                face_cx = tart_x + tart_w + face_r - 2
                face_cy = cat_cy
                draw.ellipse(
                    [
                        face_cx - face_r,
                        face_cy - face_r,
                        face_cx + face_r,
                        face_cy + face_r,
                    ],
                    fill=(120, 120, 120, 255),
                )
                # Cat ears (triangles)
                ear_size = int(face_r * 0.6)
                for ear_dx in [-int(face_r * 0.5), int(face_r * 0.5)]:
                    ear_cx = face_cx + ear_dx
                    ear_top = face_cy - face_r - ear_size + 2
                    draw.polygon(
                        [
                            (ear_cx - ear_size // 2, face_cy - face_r + 3),
                            (ear_cx + ear_size // 2, face_cy - face_r + 3),
                            (ear_cx, ear_top),
                        ],
                        fill=(120, 120, 120, 255),
                    )
                # Cat eyes
                cat_eye_r = max(1, int(face_r * 0.18))
                for edx in [-int(face_r * 0.3), int(face_r * 0.3)]:
                    draw.ellipse(
                        [
                            face_cx + edx - cat_eye_r,
                            face_cy - int(face_r * 0.15) - cat_eye_r,
                            face_cx + edx + cat_eye_r,
                            face_cy - int(face_r * 0.15) + cat_eye_r,
                        ],
                        fill=(30, 30, 30, 255),
                    )
                # Mouth — opens with audio
                mouth_open = max(1, int(amp * face_r * 0.4))
                draw.ellipse(
                    [
                        face_cx - int(face_r * 0.2),
                        face_cy + int(face_r * 0.1),
                        face_cx + int(face_r * 0.2),
                        face_cy + int(face_r * 0.1) + mouth_open,
                    ],
                    fill=(200, 80, 80, 200),
                )

                # Cat legs (4 little stubs below the tart)
                leg_w = max(2, int(cs * 0.025))
                leg_h = max(3, int(cs * 0.04))
                legs_y = tart_y + tart_h
                for li, leg_off in enumerate([0.2, 0.4, 0.6, 0.8]):
                    lx = tart_x + int(tart_w * leg_off) - leg_w // 2
                    # Alternate leg animation
                    leg_ext = int(math.sin(i * 0.3 + li * 1.5) * 3)
                    draw.rectangle(
                        [lx, legs_y, lx + leg_w, legs_y + leg_h + leg_ext],
                        fill=(120, 120, 120, 255),
                    )

                # Cat tail
                tail_x = tart_x - int(cs * 0.02)
                tail_wave = int(math.sin(i * 0.25) * cs * 0.02)
                draw.rectangle(
                    [
                        tail_x - leg_w,
                        cat_cy - leg_w + tail_wave,
                        tail_x,
                        cat_cy + leg_w + tail_wave,
                    ],
                    fill=(120, 120, 120, 255),
                )

            elif style == "matrix":
                # ── Matrix digital rain ───────────────────────────────
                draw = ImageDraw.Draw(canvas)
                cs = canvas_size

                # Pure black background
                draw.rectangle([0, 0, cs, cs], fill=(0, 0, 0, 240))

                # Matrix characters (katakana-inspired + digits)
                matrix_chars = list("0123456789ABCDEFアイウエオカキクケコサシスセソ")

                try:
                    m_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.06))
                    )
                except OSError:
                    m_font = ImageFont.load_default()

                char_h = max(8, int(cs * 0.07))
                num_cols = max(3, cs // (char_h + 2))

                # Each column has a "head" position that scrolls down
                rng_m = np.random.default_rng(42)
                col_speeds = rng_m.uniform(0.3, 1.5, size=num_cols)
                col_offsets = rng_m.uniform(0, cs, size=num_cols)

                for col in range(num_cols):
                    col_x = int(col * (cs / num_cols))
                    # Speed influenced by amplitude
                    speed = col_speeds[col] * (0.5 + amp * 1.5)
                    head_y = (col_offsets[col] + i * speed * 4) % (cs + char_h * 6)

                    # Trail of characters (brightest at head, fading)
                    trail_len = max(3, int(6 + amp * 4))
                    for t_idx in range(trail_len):
                        cy_pos = int(head_y - t_idx * char_h)
                        if cy_pos < -char_h or cy_pos > cs:
                            continue
                        # Brightness fades from head
                        brightness = max(0, 255 - t_idx * (200 // trail_len))
                        if t_idx == 0:
                            # Head character is white/bright green
                            color = (180, 255, 180, min(255, brightness + 60))
                        else:
                            color = (0, brightness, 0, min(255, brightness))

                        char = matrix_chars[int(rng_m.integers(0, len(matrix_chars)))]
                        draw.text(
                            (col_x, cy_pos),
                            char,
                            fill=color,
                            font=m_font,
                        )

                # Central avatar with green ring
                inner_size = size // 2
                inner_img = avatar_img.resize((inner_size, inner_size), Image.LANCZOS)
                center = cs // 2
                ix = center - inner_size // 2
                iy = center - inner_size // 2
                # Dark circle behind avatar for contrast
                bg_r = inner_size // 2 + 6
                draw.ellipse(
                    [center - bg_r, center - bg_r, center + bg_r, center + bg_r],
                    fill=(0, 0, 0, 220),
                )
                canvas.paste(inner_img, (ix, iy), inner_img)
                # Green ring
                ring_r = inner_size // 2 + 4
                ring_alpha = int(120 + amp * 135)
                draw.ellipse(
                    [
                        center - ring_r,
                        center - ring_r,
                        center + ring_r,
                        center + ring_r,
                    ],
                    outline=(0, 255, 70, ring_alpha),
                    width=2,
                )

            elif style == "pickle_rick":
                # ── Pickle Rick — "I turned myself into a pickle!" ────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2

                # Lab / sewer dark background
                draw.rounded_rectangle(
                    [2, 2, cs - 3, cs - 3],
                    radius=10,
                    fill=(25, 40, 25, 220),
                )

                # Bounce with audio
                bounce = int(amp * cs * 0.06)
                cy = int(cs * 0.48) - bounce

                # Slight tilt/sway when speaking
                sway = int(math.sin(i * 0.15) * 3)

                # ── Pickle body — wider, stubbier proportions ──
                body_w = int(cs * 0.22)
                body_h = int(cs * 0.30)
                body_color = (86, 140, 10, 255)
                body_darker = (65, 110, 5, 255)
                body_outline = (45, 80, 0, 255)

                # Main body ellipse
                draw.ellipse(
                    [cx - body_w + sway, cy - body_h, cx + body_w + sway, cy + body_h],
                    fill=body_color,
                    outline=body_outline,
                    width=max(2, int(cs * 0.015)),
                )

                # Darker shading on left side for depth
                shade_w = int(body_w * 0.85)
                draw.ellipse(
                    [
                        cx - body_w + sway,
                        cy - body_h,
                        cx - body_w + shade_w + sway,
                        cy + body_h,
                    ],
                    fill=body_darker,
                )
                # Re-draw main on top, slightly offset for highlight effect
                draw.ellipse(
                    [
                        cx - body_w + int(cs * 0.02) + sway,
                        cy - body_h + int(cs * 0.01),
                        cx + body_w - int(cs * 0.01) + sway,
                        cy + body_h - int(cs * 0.01),
                    ],
                    fill=body_color,
                )

                # Pickle bumps (warts)
                bump_r = max(2, int(cs * 0.018))
                bump_color = (60, 105, 5, 180)
                bump_positions = [
                    (-0.10, -0.06),
                    (0.10, 0.02),
                    (-0.06, 0.14),
                    (0.08, 0.18),
                    (-0.12, 0.08),
                    (0.12, -0.10),
                    (0.04, -0.18),
                    (-0.08, 0.22),
                ]
                for bx_f, by_f in bump_positions:
                    bx = cx + int(bx_f * cs) + sway
                    by = cy + int(by_f * cs)
                    draw.ellipse(
                        [bx - bump_r, by - bump_r, bx + bump_r, by + bump_r],
                        fill=bump_color,
                    )

                # ── Face — centered in upper portion of pickle ──
                face_cy = cy - int(body_h * 0.22)

                # ── Thick angry unibrow ──
                brow_lift = int(amp * cs * 0.025)
                brow_y = face_cy - int(cs * 0.055) - brow_lift
                brow_w = int(cs * 0.15)
                brow_thickness = max(3, int(cs * 0.022))
                # V-shaped angry brow
                draw.line(
                    [
                        (cx - brow_w + sway, brow_y + int(cs * 0.015)),
                        (cx - int(cs * 0.02) + sway, brow_y - int(cs * 0.01)),
                        (cx + int(cs * 0.02) + sway, brow_y - int(cs * 0.01)),
                        (cx + brow_w + sway, brow_y + int(cs * 0.015)),
                    ],
                    fill=(40, 65, 0, 255),
                    width=brow_thickness,
                )

                # ── Eyes — large, expressive, slightly uneven (Rick-style) ──
                eye_gap = int(cs * 0.05)
                eye_y = face_cy

                # Left eye (slightly bigger)
                le_w = int(cs * 0.065)
                le_h = int(cs * 0.075)
                le_cx = cx - eye_gap - le_w // 2 + sway
                draw.ellipse(
                    [le_cx - le_w, eye_y - le_h, le_cx + le_w, eye_y + le_h],
                    fill=(255, 255, 255, 255),
                    outline=(40, 65, 0, 255),
                    width=2,
                )
                # Right eye (slightly smaller)
                re_w = int(cs * 0.058)
                re_h = int(cs * 0.068)
                re_cx = cx + eye_gap + re_w // 2 + sway
                draw.ellipse(
                    [re_cx - re_w, eye_y - re_h, re_cx + re_w, eye_y + re_h],
                    fill=(255, 255, 255, 255),
                    outline=(40, 65, 0, 255),
                    width=2,
                )

                # Pupils — look around erratically (Rick energy)
                look_x = int(math.sin(i * 0.2) * cs * 0.015)
                look_y = int(math.cos(i * 0.16) * cs * 0.01)
                for ecx in [le_cx, re_cx]:
                    pupil_r = max(3, int(cs * 0.028))
                    draw.ellipse(
                        [
                            ecx + look_x - pupil_r,
                            eye_y + look_y - pupil_r,
                            ecx + look_x + pupil_r,
                            eye_y + look_y + pupil_r,
                        ],
                        fill=(20, 20, 20, 255),
                    )
                    # Glint
                    gl = max(1, pupil_r // 3)
                    draw.ellipse(
                        [
                            ecx + look_x - pupil_r + 2,
                            eye_y + look_y - pupil_r + 1,
                            ecx + look_x - pupil_r + 2 + gl,
                            eye_y + look_y - pupil_r + 1 + gl,
                        ],
                        fill=(255, 255, 255, 200),
                    )

                # ── Mouth — wide manic grin / yell ──
                mouth_y = face_cy + int(cs * 0.06)
                mouth_w = int(cs * 0.10)
                mouth_open = max(3, int(amp * cs * 0.07))
                if amp > 0.12:
                    # Open mouth — screaming
                    draw.ellipse(
                        [
                            cx - mouth_w + sway,
                            mouth_y,
                            cx + mouth_w + sway,
                            mouth_y + mouth_open * 2 + 2,
                        ],
                        fill=(100, 25, 25, 240),
                        outline=(40, 65, 0, 255),
                        width=1,
                    )
                    # Top teeth row
                    teeth_w = int(mouth_w * 0.7)
                    teeth_h = max(2, int(cs * 0.018))
                    draw.rectangle(
                        [
                            cx - teeth_w + sway,
                            mouth_y + 1,
                            cx + teeth_w + sway,
                            mouth_y + teeth_h + 1,
                        ],
                        fill=(245, 245, 230, 255),
                    )
                    # Bottom teeth
                    if mouth_open > 6:
                        bot_teeth_y = mouth_y + mouth_open * 2 - teeth_h
                        draw.rectangle(
                            [
                                cx - teeth_w + sway,
                                bot_teeth_y,
                                cx + teeth_w + sway,
                                bot_teeth_y + teeth_h,
                            ],
                            fill=(245, 245, 230, 255),
                        )
                    # Tongue hint
                    tongue_r = int(mouth_w * 0.3)
                    draw.ellipse(
                        [
                            cx - tongue_r + sway,
                            mouth_y + mouth_open,
                            cx + tongue_r + sway,
                            mouth_y + mouth_open * 2,
                        ],
                        fill=(200, 80, 80, 180),
                    )
                else:
                    # Cocky smirk
                    draw.arc(
                        [
                            cx - mouth_w + sway,
                            mouth_y - int(cs * 0.015),
                            cx + mouth_w + sway,
                            mouth_y + int(cs * 0.035),
                        ],
                        start=5,
                        end=175,
                        fill=(40, 65, 0, 255),
                        width=max(2, int(cs * 0.018)),
                    )

                # ── Rat limbs (Rick's rodent body parts) ──
                limb_color = (195, 155, 120, 240)
                limb_w = max(3, int(cs * 0.02))

                # Left arm — gesticulates
                arm_angle = math.sin(i * 0.22) * 0.4 + 0.3
                la_x1 = cx - body_w + int(cs * 0.02) + sway
                la_y1 = cy - int(body_h * 0.08)
                la_x2 = la_x1 - int(cs * 0.14 * math.cos(arm_angle))
                la_y2 = la_y1 + int(cs * 0.10 * math.sin(arm_angle))
                draw.line([(la_x1, la_y1), (la_x2, la_y2)], fill=limb_color, width=limb_w)
                # Hand (3 fingers)
                for f_angle in [-0.4, 0.0, 0.4]:
                    fx = la_x2 + int(math.cos(arm_angle + f_angle) * cs * 0.02)
                    fy = la_y2 + int(math.sin(arm_angle + f_angle) * cs * 0.02)
                    draw.line(
                        [(la_x2, la_y2), (fx, fy)],
                        fill=limb_color,
                        width=max(1, limb_w - 1),
                    )

                # Right arm
                ra_angle = -math.sin(i * 0.18) * 0.3 - 0.4
                ra_x1 = cx + body_w - int(cs * 0.02) + sway
                ra_y1 = cy - int(body_h * 0.08)
                ra_x2 = ra_x1 + int(cs * 0.14 * math.cos(-ra_angle))
                ra_y2 = ra_y1 + int(cs * 0.10 * math.sin(-ra_angle))
                draw.line([(ra_x1, ra_y1), (ra_x2, ra_y2)], fill=limb_color, width=limb_w)
                for f_angle in [-0.4, 0.0, 0.4]:
                    fx = ra_x2 + int(math.cos(-ra_angle + f_angle) * cs * 0.02)
                    fy = ra_y2 + int(math.sin(-ra_angle + f_angle) * cs * 0.02)
                    draw.line(
                        [(ra_x2, ra_y2), (fx, fy)],
                        fill=limb_color,
                        width=max(1, limb_w - 1),
                    )

                # Legs — dangly rat legs
                for leg_side in [-1, 1]:
                    lx1 = cx + int(body_w * 0.35 * leg_side) + sway
                    ly1 = cy + body_h - 3
                    leg_swing = int(math.sin(i * 0.25 + leg_side * 1.5) * 5)
                    lx2 = lx1 + int(cs * 0.03 * leg_side) + leg_swing
                    ly2 = ly1 + int(cs * 0.10)
                    draw.line([(lx1, ly1), (lx2, ly2)], fill=limb_color, width=limb_w)
                    # Foot
                    foot_w = max(3, int(cs * 0.025))
                    draw.ellipse(
                        [lx2 - foot_w, ly2 - 2, lx2 + foot_w, ly2 + int(cs * 0.015)],
                        fill=limb_color,
                    )

                # ── "I'M PICKLE RICK!" shout when loud ──
                if amp > 0.4:
                    try:
                        shout_font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc",
                            max(9, int(cs * 0.06)),
                        )
                    except OSError:
                        shout_font = ImageFont.load_default()
                    shout = "I'M PICKLE RICK!"
                    sb = draw.textbbox((0, 0), shout, font=shout_font)
                    sw = sb[2] - sb[0]
                    txt_x = cx - sw // 2
                    txt_y = int(cs * 0.87)
                    # Shadow
                    draw.text(
                        (txt_x + 1, txt_y + 1),
                        shout,
                        fill=(0, 50, 0, 160),
                        font=shout_font,
                    )
                    # Green glow text
                    draw.text(
                        (txt_x, txt_y),
                        shout,
                        fill=(100, 255, 0, int(200 + amp * 55)),
                        font=shout_font,
                    )

            elif style == "chrome_dino":
                # ── Chrome T-Rex (offline dinosaur) ───────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2

                # Desert ground + sky
                sky_h = int(cs * 0.7)
                draw.rectangle([0, 0, cs, sky_h], fill=(247, 247, 247, 255))
                draw.rectangle([0, sky_h, cs, cs], fill=(230, 230, 230, 255))
                # Ground line
                draw.line([(0, sky_h), (cs, sky_h)], fill=(83, 83, 83, 255), width=2)
                # Ground texture dots
                rng_cd = np.random.default_rng(42)
                for _ in range(12):
                    gx = int(rng_cd.uniform(10, cs - 10))
                    draw.rectangle(
                        [gx, sky_h + 4, gx + 2, sky_h + 6],
                        fill=(180, 180, 180, 200),
                    )

                # T-Rex pixel art (simplified, dark gray)
                px = max(2, int(cs * 0.03))
                dino_color = (83, 83, 83, 255)
                bounce = int(amp * cs * 0.06)
                dino_x = int(cs * 0.28)
                dino_y = sky_h - px * 8 - bounce

                # T-Rex sprite (10x8 simplified)
                dino_sprite = [
                    [0, 0, 0, 0, 1, 1, 1, 1, 0, 0],
                    [0, 0, 0, 0, 1, 0, 1, 1, 0, 0],
                    [0, 0, 0, 0, 1, 1, 1, 1, 0, 0],
                    [0, 0, 0, 1, 1, 1, 1, 0, 0, 0],
                    [1, 0, 1, 1, 1, 1, 1, 1, 0, 0],
                    [1, 1, 1, 1, 1, 1, 0, 0, 0, 0],
                    [0, 1, 1, 1, 1, 1, 0, 0, 0, 0],
                    [0, 0, 1, 0, 0, 1, 0, 0, 0, 0],
                ]
                # Alternate leg frames
                if (i // 4) % 2 == 0:
                    dino_sprite[7] = [0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
                for ry, row in enumerate(dino_sprite):
                    for cx_s, val in enumerate(row):
                        if val:
                            draw.rectangle(
                                [
                                    dino_x + cx_s * px,
                                    dino_y + ry * px,
                                    dino_x + (cx_s + 1) * px - 1,
                                    dino_y + (ry + 1) * px - 1,
                                ],
                                fill=dino_color,
                            )

                # Cacti scrolling right-to-left
                cactus_x = int(cs * 0.75 - (i * 3) % int(cs * 0.5))
                cactus_h = int(cs * 0.12)
                cactus_w = px * 2
                draw.rectangle(
                    [cactus_x, sky_h - cactus_h, cactus_x + cactus_w, sky_h],
                    fill=dino_color,
                )
                # Cactus arms
                draw.rectangle(
                    [
                        cactus_x - cactus_w,
                        sky_h - int(cactus_h * 0.7),
                        cactus_x,
                        sky_h - int(cactus_h * 0.5),
                    ],
                    fill=dino_color,
                )
                draw.rectangle(
                    [
                        cactus_x + cactus_w,
                        sky_h - int(cactus_h * 0.5),
                        cactus_x + cactus_w * 2,
                        sky_h - int(cactus_h * 0.3),
                    ],
                    fill=dino_color,
                )

                # "NO INTERNET" text
                if amp > 0.3:
                    try:
                        err_font = ImageFont.truetype(
                            "/System/Library/Fonts/Courier.dfont",
                            max(8, int(cs * 0.05)),
                        )
                    except OSError:
                        err_font = ImageFont.load_default()
                    draw.text(
                        (int(cs * 0.15), int(cs * 0.12)),
                        "No internet",
                        fill=(83, 83, 83, int(180 + amp * 75)),
                        font=err_font,
                    )

                # Score
                try:
                    sc_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.045))
                    )
                except OSError:
                    sc_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.7), int(cs * 0.05)),
                    f"{int(i * 3):05d}",
                    fill=(83, 83, 83, 200),
                    font=sc_font,
                )

            elif style == "marvin":
                # ── Marvin the Paranoid Android (H2G2) ────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2

                # Deep space background
                draw.rectangle([0, 0, cs, cs], fill=(5, 5, 20, 240))
                rng_mv = np.random.default_rng(77)
                for _ in range(20):
                    sx = int(rng_mv.uniform(3, cs - 3))
                    sy = int(rng_mv.uniform(3, cs - 3))
                    draw.ellipse(
                        [sx - 1, sy - 1, sx + 1, sy + 1],
                        fill=(255, 255, 255, int(rng_mv.uniform(60, 180))),
                    )

                bounce = int(amp * cs * 0.03)
                cy = int(cs * 0.48) - bounce

                # ── Giant round head (Marvin is 90% head) ──
                head_r = int(cs * 0.25)
                head_color = (180, 185, 190, 255)
                head_dark = (140, 145, 150, 255)
                # Head sphere
                draw.ellipse(
                    [cx - head_r, cy - head_r, cx + head_r, cy + head_r],
                    fill=head_color,
                    outline=(100, 105, 110, 255),
                    width=2,
                )
                # Head shading (darker left side)
                draw.ellipse(
                    [cx - head_r, cy - head_r, cx - int(head_r * 0.3), cy + head_r],
                    fill=head_dark,
                )

                # ── Visor / face plate — triangular depressed zone ──
                visor_w = int(head_r * 1.2)
                visor_h = int(head_r * 0.6)
                visor_y = cy + int(head_r * 0.05)
                draw.rounded_rectangle(
                    [
                        cx - visor_w // 2,
                        visor_y - visor_h // 2,
                        cx + visor_w // 2,
                        visor_y + visor_h // 2,
                    ],
                    radius=int(cs * 0.03),
                    fill=(60, 65, 70, 220),
                )

                # ── Sad droopy triangle eyes ──
                eye_r = int(cs * 0.04)
                eye_gap = int(cs * 0.08)
                eye_y = visor_y - int(visor_h * 0.1)
                # Triangle-shaped sad eyes (droopy outer corners)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    # Sad red/amber glow
                    glow_alpha = int(120 + amp * 135)
                    draw.ellipse(
                        [
                            ecx - eye_r - 2,
                            eye_y - eye_r - 2,
                            ecx + eye_r + 2,
                            eye_y + eye_r + 2,
                        ],
                        fill=(200, 80, 40, glow_alpha // 2),
                    )
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r],
                        fill=(200, 100, 50, glow_alpha),
                    )
                    # Droopy brow line (sad)
                    brow_outer = eye_y - eye_r - int(cs * 0.015)
                    brow_inner = brow_outer + int(cs * 0.02)
                    draw.line(
                        [
                            (ecx - eye_r * side, brow_inner),
                            (ecx + eye_r * side, brow_outer),
                        ],
                        fill=(80, 85, 90, 255),
                        width=max(2, int(cs * 0.012)),
                    )

                # ── Thin sad mouth line ──
                mouth_y = visor_y + int(visor_h * 0.25)
                mouth_w = int(cs * 0.06)
                # Sad downturned arc
                draw.arc(
                    [
                        cx - mouth_w,
                        mouth_y - int(cs * 0.02),
                        cx + mouth_w,
                        mouth_y + int(cs * 0.03),
                    ],
                    start=190,
                    end=350,
                    fill=(200, 100, 50, 200),
                    width=max(2, int(cs * 0.012)),
                )

                # ── Small body below head ──
                body_w = int(cs * 0.15)
                body_top = cy + head_r - 3
                body_bot = body_top + int(cs * 0.18)
                draw.rounded_rectangle(
                    [cx - body_w, body_top, cx + body_w, body_bot],
                    radius=int(cs * 0.03),
                    fill=(160, 165, 170, 255),
                    outline=(100, 105, 110, 255),
                    width=1,
                )

                # Stubby arms (hanging limp, depressed)
                arm_w = max(2, int(cs * 0.018))
                for side in [-1, 1]:
                    ax = cx + body_w * side
                    draw.line(
                        [
                            (ax, body_top + int(cs * 0.03)),
                            (
                                ax + int(cs * 0.08 * side),
                                body_top + int(cs * 0.14 + amp * cs * 0.02),
                            ),
                        ],
                        fill=head_color,
                        width=arm_w,
                    )

                # Stubby legs
                for side in [-1, 1]:
                    lx = cx + int(body_w * 0.5 * side)
                    draw.line(
                        [(lx, body_bot), (lx, body_bot + int(cs * 0.06))],
                        fill=head_color,
                        width=arm_w,
                    )
                    draw.ellipse(
                        [
                            lx - int(cs * 0.02),
                            body_bot + int(cs * 0.05),
                            lx + int(cs * 0.02),
                            body_bot + int(cs * 0.07),
                        ],
                        fill=(120, 125, 130, 255),
                    )

                # Depressive quote
                if amp > 0.25:
                    try:
                        q_font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc",
                            max(8, int(cs * 0.04)),
                        )
                    except OSError:
                        q_font = ImageFont.load_default()
                    quotes = [
                        "Life... don't talk to",
                        "me about life.",
                        "Brain the size of",
                        "a planet...",
                        "I think you ought",
                        "to know I'm feeling",
                        "very depressed.",
                    ]
                    qi = (i // 20) % (len(quotes) - 1)
                    draw.text(
                        (int(cs * 0.08), int(cs * 0.88)),
                        quotes[qi],
                        fill=(150, 160, 180, int(150 + amp * 100)),
                        font=q_font,
                    )

            elif style == "mac128k":
                # ── Macintosh 128K with face ──────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2

                # Light beige desk background
                draw.rectangle([0, 0, cs, cs], fill=(220, 210, 195, 255))

                bounce = int(amp * cs * 0.04)
                cy = int(cs * 0.45) - bounce

                # ── Mac body (beige box with rounded top) ──
                mac_w = int(cs * 0.36)
                mac_h = int(cs * 0.42)
                mac_color = (225, 220, 200, 255)
                mac_border = (170, 165, 150, 255)

                draw.rounded_rectangle(
                    [
                        cx - mac_w // 2,
                        cy - mac_h // 2,
                        cx + mac_w // 2,
                        cy + mac_h // 2,
                    ],
                    radius=int(cs * 0.04),
                    fill=mac_color,
                    outline=mac_border,
                    width=max(2, int(cs * 0.012)),
                )

                # ── Screen (slightly greenish/white) ──
                scr_w = int(mac_w * 0.72)
                scr_h = int(mac_h * 0.55)
                scr_x = cx - scr_w // 2
                scr_y = cy - mac_h // 2 + int(mac_h * 0.12)
                draw.rounded_rectangle(
                    [scr_x, scr_y, scr_x + scr_w, scr_y + scr_h],
                    radius=int(cs * 0.02),
                    fill=(180, 210, 180, 255),
                    outline=(100, 100, 90, 255),
                    width=2,
                )

                # ── Eyes on screen ──
                eye_w = int(scr_w * 0.18)
                eye_h = int(scr_h * 0.28)
                eye_gap = int(scr_w * 0.08)
                eye_y = scr_y + int(scr_h * 0.25)

                look_x = int(math.sin(i * 0.18) * cs * 0.01)
                look_y = int(math.cos(i * 0.14) * cs * 0.008)

                for side in [-1, 1]:
                    ecx = cx + (eye_gap + eye_w // 2) * side
                    # Eye outline (dark pixel-style)
                    draw.rounded_rectangle(
                        [ecx - eye_w // 2, eye_y, ecx + eye_w // 2, eye_y + eye_h],
                        radius=2,
                        fill=(30, 60, 30, 255),
                    )
                    # Inner white
                    draw.rounded_rectangle(
                        [
                            ecx - eye_w // 2 + 2,
                            eye_y + 2,
                            ecx + eye_w // 2 - 2,
                            eye_y + eye_h - 2,
                        ],
                        radius=1,
                        fill=(200, 230, 200, 255),
                    )
                    # Pupil
                    pr = max(2, int(eye_w * 0.25))
                    draw.ellipse(
                        [
                            ecx + look_x - pr,
                            eye_y + eye_h // 2 + look_y - pr,
                            ecx + look_x + pr,
                            eye_y + eye_h // 2 + look_y + pr,
                        ],
                        fill=(30, 60, 30, 255),
                    )

                # ── Smile on screen ──
                smile_y = scr_y + int(scr_h * 0.65)
                smile_w = int(scr_w * 0.25)
                mouth_open_h = int(amp * scr_h * 0.15)
                if amp > 0.15:
                    draw.ellipse(
                        [
                            cx - smile_w,
                            smile_y,
                            cx + smile_w,
                            smile_y + mouth_open_h + 3,
                        ],
                        fill=(30, 60, 30, 230),
                    )
                else:
                    draw.arc(
                        [
                            cx - smile_w,
                            smile_y - int(cs * 0.015),
                            cx + smile_w,
                            smile_y + int(cs * 0.02),
                        ],
                        start=10,
                        end=170,
                        fill=(30, 60, 30, 220),
                        width=2,
                    )

                # ── Floppy slot below screen ──
                slot_w = int(mac_w * 0.3)
                slot_h = max(3, int(cs * 0.015))
                slot_y = cy + mac_h // 2 - int(mac_h * 0.15)
                draw.rounded_rectangle(
                    [cx - slot_w // 2, slot_y, cx + slot_w // 2, slot_y + slot_h],
                    radius=1,
                    fill=(140, 135, 120, 255),
                )

                # ── Base/stand ──
                base_w = int(mac_w * 0.5)
                base_h = int(cs * 0.03)
                base_y = cy + mac_h // 2
                draw.rectangle(
                    [cx - base_w // 2, base_y, cx + base_w // 2, base_y + base_h],
                    fill=mac_border,
                )
                # Wider foot
                draw.rectangle(
                    [
                        cx - int(base_w * 0.7),
                        base_y + base_h,
                        cx + int(base_w * 0.7),
                        base_y + base_h + int(cs * 0.015),
                    ],
                    fill=mac_border,
                )

                # "hello" text when speaking
                if amp > 0.35:
                    try:
                        hello_font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc",
                            max(8, int(cs * 0.05)),
                        )
                    except OSError:
                        hello_font = ImageFont.load_default()
                    draw.text(
                        (int(cs * 0.32), int(cs * 0.86)),
                        "hello",
                        fill=(100, 95, 80, int(180 + amp * 75)),
                        font=hello_font,
                    )

            elif style == "floppy_disk":
                # ── 3.5" Floppy Disk with face ───────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2

                # Desk background
                draw.rectangle([0, 0, cs, cs], fill=(60, 55, 70, 240))

                bounce = int(amp * cs * 0.04)
                cy = int(cs * 0.48) - bounce

                # ── Floppy body (dark blue/black) ──
                fl_w = int(cs * 0.38)
                fl_h = int(cs * 0.40)
                fl_color = (30, 30, 35, 255)

                draw.rounded_rectangle(
                    [cx - fl_w // 2, cy - fl_h // 2, cx + fl_w // 2, cy + fl_h // 2],
                    radius=int(cs * 0.02),
                    fill=fl_color,
                    outline=(80, 80, 90, 255),
                    width=2,
                )

                # ── Metal slider at top ──
                slider_w = int(fl_w * 0.45)
                slider_h = int(fl_h * 0.18)
                slider_y = cy - fl_h // 2 + int(fl_h * 0.04)
                draw.rectangle(
                    [
                        cx - slider_w // 2,
                        slider_y,
                        cx + slider_w // 2,
                        slider_y + slider_h,
                    ],
                    fill=(160, 165, 170, 255),
                    outline=(120, 125, 130, 255),
                    width=1,
                )
                # Slider hole
                hole_w = int(slider_w * 0.25)
                hole_h = int(slider_h * 0.7)
                draw.rectangle(
                    [
                        cx - hole_w // 2 + int(slider_w * 0.15),
                        slider_y + (slider_h - hole_h) // 2,
                        cx + hole_w // 2 + int(slider_w * 0.15),
                        slider_y + (slider_h + hole_h) // 2,
                    ],
                    fill=(40, 40, 45, 255),
                )

                # ── Label area (white sticker) ──
                label_w = int(fl_w * 0.8)
                label_h = int(fl_h * 0.35)
                label_y = cy + int(fl_h * 0.05)
                draw.rounded_rectangle(
                    [cx - label_w // 2, label_y, cx + label_w // 2, label_y + label_h],
                    radius=3,
                    fill=(240, 235, 220, 255),
                    outline=(200, 195, 180, 255),
                    width=1,
                )

                # Lines on label
                line_color = (180, 175, 165, 200)
                for li in range(4):
                    ly = label_y + int(label_h * 0.2) + li * int(label_h * 0.18)
                    draw.line(
                        [(cx - label_w // 2 + 6, ly), (cx + label_w // 2 - 6, ly)],
                        fill=line_color,
                        width=1,
                    )

                # ── Eyes on the metal slider area ──
                eye_r = max(3, int(cs * 0.032))
                eye_y_pos = slider_y + slider_h + int(fl_h * 0.08)
                eye_gap = int(cs * 0.06)
                look_x = int(math.sin(i * 0.2) * cs * 0.008)

                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(255, 255, 255, 255),
                        outline=(80, 80, 90, 255),
                        width=1,
                    )
                    pr = max(1, eye_r // 2)
                    draw.ellipse(
                        [
                            ecx + look_x - pr,
                            eye_y_pos - pr,
                            ecx + look_x + pr,
                            eye_y_pos + pr,
                        ],
                        fill=(20, 20, 30, 255),
                    )

                # ── Mouth — grumpy ──
                mouth_y_pos = eye_y_pos + int(cs * 0.04)
                mouth_w = int(cs * 0.05)
                if amp > 0.15:
                    draw.ellipse(
                        [
                            cx - mouth_w,
                            mouth_y_pos,
                            cx + mouth_w,
                            mouth_y_pos + int(amp * cs * 0.04) + 2,
                        ],
                        fill=(200, 80, 80, 200),
                    )
                else:
                    # Grumpy frown
                    draw.arc(
                        [
                            cx - mouth_w,
                            mouth_y_pos,
                            cx + mouth_w,
                            mouth_y_pos + int(cs * 0.03),
                        ],
                        start=200,
                        end=340,
                        fill=(200, 100, 100, 200),
                        width=max(2, int(cs * 0.012)),
                    )

                # ── "1.44 MB" label text ──
                try:
                    mb_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.04))
                    )
                except OSError:
                    mb_font = ImageFont.load_default()
                draw.text(
                    (cx - label_w // 2 + 6, label_y + int(label_h * 0.05)),
                    "1.44 MB",
                    fill=(100, 95, 85, 200),
                    font=mb_font,
                )

                # Arms (tiny, floppy-like)
                arm_w = max(2, int(cs * 0.015))
                limb_color = (60, 60, 70, 230)
                for side in [-1, 1]:
                    ax = cx + (fl_w // 2) * side
                    wave = int(math.sin(i * 0.2 + side) * cs * 0.02)
                    draw.line(
                        [
                            (ax, cy + int(fl_h * 0.05)),
                            (ax + int(cs * 0.08 * side), cy + int(fl_h * 0.1) + wave),
                        ],
                        fill=limb_color,
                        width=arm_w,
                    )

                # "Save icon!" shout
                if amp > 0.45:
                    try:
                        s_font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc",
                            max(8, int(cs * 0.045)),
                        )
                    except OSError:
                        s_font = ImageFont.load_default()
                    draw.text(
                        (int(cs * 0.18), int(cs * 0.88)),
                        "I AM the save icon!",
                        fill=(200, 200, 220, int(180 + amp * 75)),
                        font=s_font,
                    )

            elif style == "bsod":
                # ── Blue Screen of Death ──────────────────────────────
                draw = ImageDraw.Draw(canvas)
                cs = canvas_size

                # Classic BSOD blue background
                draw.rectangle([0, 0, cs, cs], fill=(0, 0, 170, 255))

                # Scanlines effect
                for row in range(0, cs, 3):
                    draw.line([(0, row), (cs, row)], fill=(0, 0, 150, 40), width=1)

                try:
                    bsod_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.038))
                    )
                except OSError:
                    bsod_font = ImageFont.load_default()

                try:
                    title_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.045))
                    )
                except OSError:
                    title_font = bsod_font

                text_color = (255, 255, 255, 255)
                y_pos = int(cs * 0.08)

                # Title bar
                title = " Windows "
                tb = draw.textbbox((0, 0), title, font=title_font)
                tw = tb[2] - tb[0]
                draw.rectangle(
                    [
                        int(cs * 0.15),
                        y_pos,
                        int(cs * 0.15) + tw + 8,
                        y_pos + int(cs * 0.06),
                    ],
                    fill=(170, 170, 170, 255),
                )
                draw.text(
                    (int(cs * 0.15) + 4, y_pos + 2),
                    title,
                    fill=(0, 0, 170, 255),
                    font=title_font,
                )
                y_pos += int(cs * 0.10)

                # Error text (progressive reveal)
                lines = [
                    "A problem has been",
                    "detected and Windows",
                    "has been shut down.",
                    "",
                    "IRQL_NOT_LESS_OR_EQUAL",
                    "",
                    "Technical information:",
                    "*** STOP: 0x0000000A",
                ]
                progress = (i + 1) / max(1, total_frames)
                visible_lines = max(1, int(len(lines) * progress))

                for li in range(min(visible_lines, len(lines))):
                    draw.text(
                        (int(cs * 0.06), y_pos + li * int(cs * 0.055)),
                        lines[li],
                        fill=text_color,
                        font=bsod_font,
                    )

                # Sad emoticon :( — bounces with audio
                sad_y = int(cs * 0.72) - int(amp * cs * 0.05)
                try:
                    sad_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(20, int(cs * 0.16))
                    )
                except OSError:
                    sad_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.35), sad_y),
                    ":(",
                    fill=text_color,
                    font=sad_font,
                )

                # Blinking cursor
                if (i // 15) % 2 == 0:
                    cursor_y = y_pos + visible_lines * int(cs * 0.055)
                    draw.rectangle(
                        [
                            int(cs * 0.06),
                            cursor_y,
                            int(cs * 0.06) + int(cs * 0.03),
                            cursor_y + int(cs * 0.04),
                        ],
                        fill=text_color,
                    )

            elif style == "bugdroid":
                # ── Android Bugdroid ──────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2

                # Light green gradient background
                for row in range(cs):
                    t = row / cs
                    draw.line(
                        [(0, row), (cs, row)],
                        fill=(
                            int(200 + t * 30),
                            int(230 + t * 20),
                            int(200 + t * 30),
                            255,
                        ),
                    )

                bounce = int(amp * cs * 0.04)
                cy = int(cs * 0.50) - bounce

                # Android green
                ag = (61, 220, 132, 255)  # #3DDC84
                ag_outline = (30, 150, 80, 255)

                # ── Head (half-circle on top) ──
                head_w = int(cs * 0.22)
                head_h = int(cs * 0.15)
                head_top = cy - int(cs * 0.18)
                draw.pieslice(
                    [cx - head_w, head_top, cx + head_w, head_top + head_h * 2],
                    start=180,
                    end=0,
                    fill=ag,
                    outline=ag_outline,
                    width=2,
                )

                # ── Antennae ──
                ant_len = int(cs * 0.08)
                ant_w = max(2, int(cs * 0.012))
                for side, angle in [(-1, -30), (1, -30)]:
                    ax = cx + int(head_w * 0.5 * side)
                    ay = head_top + int(head_h * 0.2)
                    tip_x = ax + int(math.sin(math.radians(angle * side)) * ant_len)
                    tip_y = ay - int(math.cos(math.radians(angle * side)) * ant_len)
                    draw.line([(ax, ay), (tip_x, tip_y)], fill=ag, width=ant_w)
                    draw.ellipse(
                        [tip_x - 2, tip_y - 2, tip_x + 2, tip_y + 2],
                        fill=ag,
                    )

                # ── Eyes ──
                eye_r = max(2, int(cs * 0.025))
                eye_y = head_top + int(head_h * 0.65)
                eye_gap = int(head_w * 0.45)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r],
                        fill=(255, 255, 255, 255),
                    )

                # ── Body (rounded rectangle) ──
                body_w = int(cs * 0.22)
                body_top = head_top + head_h
                body_h = int(cs * 0.22)
                draw.rounded_rectangle(
                    [cx - body_w, body_top, cx + body_w, body_top + body_h],
                    radius=int(cs * 0.03),
                    fill=ag,
                    outline=ag_outline,
                    width=2,
                )

                # ── Arms (rounded rectangles on sides) ──
                arm_w_px = int(cs * 0.06)
                arm_h_px = int(body_h * 0.7)
                arm_gap = int(cs * 0.02)
                arm_wave = int(math.sin(i * 0.2) * cs * 0.03)
                for side in [-1, 1]:
                    ax = cx + (body_w + arm_gap) * side
                    arm_top = body_top + int(body_h * 0.1) + (arm_wave * side)
                    draw.rounded_rectangle(
                        [
                            ax - arm_w_px // 2 * (1 if side == -1 else 1),
                            arm_top,
                            ax + arm_w_px // 2 * (1 if side == -1 else 1),
                            arm_top + arm_h_px,
                        ],
                        radius=int(arm_w_px * 0.4),
                        fill=ag,
                    )

                # ── Legs ──
                leg_w_px = int(cs * 0.06)
                leg_h = int(cs * 0.10)
                for side in [-1, 1]:
                    lx = cx + int(body_w * 0.45 * side)
                    draw.rounded_rectangle(
                        [
                            lx - leg_w_px // 2,
                            body_top + body_h - 2,
                            lx + leg_w_px // 2,
                            body_top + body_h + leg_h,
                        ],
                        radius=int(leg_w_px * 0.4),
                        fill=ag,
                    )

                # ── Mouth (opens with audio) ──
                if amp > 0.2:
                    mouth_w = int(head_w * 0.5)
                    mouth_h = max(2, int(amp * cs * 0.04))
                    mouth_y = eye_y + int(cs * 0.035)
                    draw.rounded_rectangle(
                        [cx - mouth_w, mouth_y, cx + mouth_w, mouth_y + mouth_h],
                        radius=2,
                        fill=(255, 255, 255, 200),
                    )

            elif style == "qr_code":
                # ── QR Code with eyes ─────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2

                # White background
                draw.rectangle([0, 0, cs, cs], fill=(255, 255, 255, 250))

                # ── QR-code-like pattern ──
                px = max(2, int(cs * 0.03))
                margin = int(cs * 0.08)
                grid = (cs - margin * 2) // px

                # Three corner markers (classic QR)
                marker_size = max(3, grid // 5)
                corners = [(0, 0), (grid - marker_size, 0), (0, grid - marker_size)]
                for mx, my in corners:
                    for r in range(marker_size):
                        for c in range(marker_size):
                            is_border = (
                                r == 0 or r == marker_size - 1 or c == 0 or c == marker_size - 1
                            )
                            is_inner = 1 < r < marker_size - 2 and 1 < c < marker_size - 2
                            if is_border or is_inner:
                                bx = margin + (mx + c) * px
                                by = margin + (my + r) * px
                                draw.rectangle(
                                    [bx, by, bx + px - 1, by + px - 1],
                                    fill=(0, 0, 0, 255),
                                )

                # Random data pattern (seeded but varies slightly with amp)
                rng_qr = np.random.default_rng(99)
                for r in range(grid):
                    for c in range(grid):
                        # Skip corners
                        in_corner = False
                        for mx, my in corners:
                            if mx <= c < mx + marker_size and my <= r < my + marker_size:
                                in_corner = True
                        # Skip center eye zone
                        center_zone = (
                            grid // 2 - 3 <= c <= grid // 2 + 3
                            and grid // 2 - 3 <= r <= grid // 2 + 3
                        )
                        if not in_corner and not center_zone:
                            if rng_qr.random() < 0.35:
                                bx = margin + c * px
                                by = margin + r * px
                                draw.rectangle(
                                    [bx, by, bx + px - 1, by + px - 1],
                                    fill=(0, 0, 0, 255),
                                )

                # ── Eyes in center of QR code ──
                eye_r = max(3, int(cs * 0.04))
                eye_y = cs // 2 - int(cs * 0.02)
                eye_gap = int(cs * 0.06)

                # White background behind eyes
                eye_bg_r = eye_r + 6
                draw.rounded_rectangle(
                    [
                        cx - eye_gap - eye_bg_r,
                        eye_y - eye_bg_r,
                        cx + eye_gap + eye_bg_r,
                        eye_y + eye_bg_r + int(cs * 0.06),
                    ],
                    radius=4,
                    fill=(255, 255, 255, 255),
                )

                look_x = int(math.sin(i * 0.2) * cs * 0.01)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r],
                        fill=(255, 255, 255, 255),
                        outline=(0, 0, 0, 255),
                        width=2,
                    )
                    pr = max(2, eye_r // 2)
                    draw.ellipse(
                        [ecx + look_x - pr, eye_y - pr, ecx + look_x + pr, eye_y + pr],
                        fill=(0, 0, 0, 255),
                    )

                # Mouth
                mouth_y = eye_y + int(cs * 0.045)
                mouth_w = int(cs * 0.04)
                if amp > 0.15:
                    draw.ellipse(
                        [
                            cx - mouth_w,
                            mouth_y,
                            cx + mouth_w,
                            mouth_y + int(amp * cs * 0.04) + 2,
                        ],
                        fill=(0, 0, 0, 200),
                    )
                else:
                    draw.line(
                        [(cx - mouth_w, mouth_y + 2), (cx + mouth_w, mouth_y + 2)],
                        fill=(0, 0, 0, 180),
                        width=2,
                    )

                # "SCAN ME!" text
                if amp > 0.4:
                    try:
                        scan_font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc",
                            max(8, int(cs * 0.045)),
                        )
                    except OSError:
                        scan_font = ImageFont.load_default()
                    draw.text(
                        (int(cs * 0.3), int(cs * 0.88)),
                        "SCAN ME!",
                        fill=(0, 0, 0, int(180 + amp * 75)),
                        font=scan_font,
                    )

            elif style == "gpu_sweat":
                # ── GPU (graphics card) sweating ──────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2

                # Dark case interior background
                draw.rectangle([0, 0, cs, cs], fill=(25, 25, 30, 245))

                bounce = int(amp * cs * 0.02)
                cy = int(cs * 0.48) - bounce

                # ── GPU PCB (green board) ──
                pcb_w = int(cs * 0.42)
                pcb_h = int(cs * 0.30)
                pcb_color = (20, 80, 20, 255)
                pcb_x = cx - pcb_w // 2
                pcb_y = cy - pcb_h // 2

                draw.rounded_rectangle(
                    [pcb_x, pcb_y, pcb_x + pcb_w, pcb_y + pcb_h],
                    radius=int(cs * 0.015),
                    fill=pcb_color,
                    outline=(40, 100, 40, 255),
                    width=2,
                )

                # ── GPU cooler/shroud (dark, with fan) ──
                shroud_w = int(pcb_w * 0.85)
                shroud_h = int(pcb_h * 0.75)
                shroud_x = cx - shroud_w // 2
                shroud_y = pcb_y + int(pcb_h * 0.12)
                draw.rounded_rectangle(
                    [shroud_x, shroud_y, shroud_x + shroud_w, shroud_y + shroud_h],
                    radius=int(cs * 0.02),
                    fill=(40, 40, 45, 255),
                    outline=(70, 70, 80, 255),
                    width=1,
                )

                # ── Fan (spinning faster with amplitude) ──
                fan_cx = cx
                fan_cy = shroud_y + shroud_h // 2
                fan_r = int(shroud_h * 0.38)
                # Fan circle
                draw.ellipse(
                    [fan_cx - fan_r, fan_cy - fan_r, fan_cx + fan_r, fan_cy + fan_r],
                    fill=(50, 50, 55, 255),
                    outline=(80, 80, 90, 255),
                    width=1,
                )
                # Fan blades (spin speed based on amp)
                num_blades = 7
                spin_speed = 0.1 + amp * 0.5
                for b in range(num_blades):
                    angle = (2 * math.pi * b / num_blades) + i * spin_speed
                    inner_r = int(fan_r * 0.2)
                    outer_r = int(fan_r * 0.85)
                    # Curved blade (two lines making a thick arc)
                    for dr in range(inner_r, outer_r, 2):
                        curve = math.sin((dr - inner_r) / (outer_r - inner_r) * math.pi) * 0.3
                        bx = fan_cx + int(math.cos(angle + curve) * dr)
                        by = fan_cy + int(math.sin(angle + curve) * dr)
                        draw.ellipse([bx - 1, by - 1, bx + 1, by + 1], fill=(90, 90, 100, 200))
                # Fan center cap
                draw.ellipse(
                    [
                        fan_cx - int(fan_r * 0.18),
                        fan_cy - int(fan_r * 0.18),
                        fan_cx + int(fan_r * 0.18),
                        fan_cy + int(fan_r * 0.18),
                    ],
                    fill=(60, 60, 65, 255),
                    outline=(100, 100, 110, 255),
                    width=1,
                )

                # ── Eyes on the shroud (above fan) ──
                eye_r = max(2, int(cs * 0.025))
                eye_y_pos = shroud_y + int(shroud_h * 0.12)
                eye_gap = int(cs * 0.06)
                look_x = int(math.sin(i * 0.18) * cs * 0.008)

                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(255, 255, 255, 255),
                    )
                    pr = max(1, eye_r // 2)
                    draw.ellipse(
                        [
                            ecx + look_x - pr,
                            eye_y_pos - pr,
                            ecx + look_x + pr,
                            eye_y_pos + pr,
                        ],
                        fill=(20, 20, 30, 255),
                    )
                    # Worried brows (higher with amp)
                    brow_raise = int(amp * cs * 0.015)
                    brow_y = eye_y_pos - eye_r - int(cs * 0.012) - brow_raise
                    draw.line(
                        [
                            (ecx - eye_r, brow_y + int(cs * 0.008) * side),
                            (ecx + eye_r, brow_y - int(cs * 0.008) * side),
                        ],
                        fill=(200, 200, 210, 200),
                        width=max(1, int(cs * 0.01)),
                    )

                # Worried mouth
                mouth_y_pos = shroud_y + shroud_h - int(cs * 0.04)
                mouth_w_px = int(cs * 0.04)
                draw.arc(
                    [
                        cx - mouth_w_px,
                        mouth_y_pos,
                        cx + mouth_w_px,
                        mouth_y_pos + int(cs * 0.025),
                    ],
                    start=200,
                    end=340,
                    fill=(200, 200, 210, 200),
                    width=max(1, int(cs * 0.01)),
                )

                # ── PCI-E connector at bottom ──
                pcie_w = int(pcb_w * 0.7)
                pcie_h = max(3, int(cs * 0.02))
                draw.rectangle(
                    [
                        cx - pcie_w // 2,
                        pcb_y + pcb_h,
                        cx + pcie_w // 2,
                        pcb_y + pcb_h + pcie_h,
                    ],
                    fill=(200, 170, 50, 255),
                )
                # Gold pins
                pin_count = 12
                pin_w = pcie_w // (pin_count * 2)
                for p in range(pin_count):
                    px_pin = cx - pcie_w // 2 + int(p * pcie_w / pin_count) + 2
                    draw.rectangle(
                        [px_pin, pcb_y + pcb_h, px_pin + pin_w, pcb_y + pcb_h + pcie_h],
                        fill=(220, 190, 60, 255),
                    )

                # ── Sweat drops (more with higher amplitude) ──
                num_drops = max(1, int(amp * 5))
                for d in range(num_drops):
                    drop_x = cx + int(cs * 0.2 * math.sin(i * 0.1 + d * 2))
                    drop_base_y = shroud_y - int(cs * 0.01)
                    drop_y = drop_base_y + int((i * 2 + d * 15) % int(cs * 0.15))
                    drop_r = max(2, int(cs * 0.015))
                    # Teardrop shape
                    draw.ellipse(
                        [
                            drop_x - drop_r,
                            drop_y,
                            drop_x + drop_r,
                            drop_y + int(drop_r * 1.5),
                        ],
                        fill=(100, 180, 255, int(150 + amp * 100)),
                    )
                    # Pointy top
                    draw.polygon(
                        [
                            (drop_x, drop_y - drop_r),
                            (drop_x - drop_r, drop_y + 2),
                            (drop_x + drop_r, drop_y + 2),
                        ],
                        fill=(100, 180, 255, int(130 + amp * 80)),
                    )

                # Temperature indicator
                temp = int(40 + amp * 60)
                temp_color = (
                    min(255, int(temp * 2.5)),
                    max(0, int(255 - temp * 2)),
                    50,
                    220,
                )
                try:
                    t_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.04))
                    )
                except OSError:
                    t_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.65), int(cs * 0.88)),
                    f"{temp}°C",
                    fill=temp_color,
                    font=t_font,
                )

            elif style == "rubber_duck":
                # ── Rubber Duck debugging companion ───────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx, cy_base = cs // 2, int(cs * 0.50)
                bounce = int(amp * cs * 0.025)
                cy = cy_base - bounce

                # Water surface (blue)
                water_y = cy + int(cs * 0.12)
                draw.rectangle([0, water_y, cs, cs], fill=(60, 140, 220, 200))
                # Ripples
                for r_idx in range(3):
                    ripple_w = int(cs * (0.15 + r_idx * 0.08))
                    ripple_y = water_y + int(cs * 0.02) + r_idx * int(cs * 0.03)
                    wave_off = int(math.sin(i * 0.15 + r_idx) * cs * 0.01)
                    draw.arc(
                        [
                            cx - ripple_w + wave_off,
                            ripple_y,
                            cx + ripple_w + wave_off,
                            ripple_y + int(cs * 0.02),
                        ],
                        start=0,
                        end=180,
                        fill=(100, 180, 255, 120),
                        width=max(1, int(cs * 0.005)),
                    )

                # Duck body (big yellow ellipse)
                body_w = int(cs * 0.22)
                body_h = int(cs * 0.16)
                duck_yellow = (255, 220, 50, 255)
                draw.ellipse(
                    [cx - body_w, cy - body_h // 2, cx + body_w, cy + body_h],
                    fill=duck_yellow,
                )

                # Duck head (circle on top)
                head_r = int(cs * 0.10)
                head_cx = cx + int(cs * 0.04)
                head_cy = cy - int(cs * 0.10)
                draw.ellipse(
                    [
                        head_cx - head_r,
                        head_cy - head_r,
                        head_cx + head_r,
                        head_cy + head_r,
                    ],
                    fill=duck_yellow,
                )

                # Beak (orange)
                beak_x = head_cx + head_r - int(cs * 0.02)
                beak_y = head_cy + int(cs * 0.01)
                beak_w = int(cs * 0.08)
                beak_h = int(cs * 0.03)
                mouth_open = int(amp * cs * 0.015)
                # Upper beak
                draw.polygon(
                    [
                        (beak_x, beak_y - beak_h),
                        (beak_x + beak_w, beak_y),
                        (beak_x, beak_y),
                    ],
                    fill=(255, 140, 0, 255),
                )
                # Lower beak
                draw.polygon(
                    [
                        (beak_x, beak_y + mouth_open),
                        (beak_x + beak_w - int(cs * 0.02), beak_y + mouth_open),
                        (beak_x, beak_y + beak_h + mouth_open),
                    ],
                    fill=(230, 120, 0, 255),
                )

                # Eyes
                eye_r = max(2, int(cs * 0.022))
                eye_x = head_cx + int(cs * 0.03)
                eye_y = head_cy - int(cs * 0.02)
                draw.ellipse(
                    [eye_x - eye_r, eye_y - eye_r, eye_x + eye_r, eye_y + eye_r],
                    fill=(255, 255, 255, 255),
                )
                pr = max(1, eye_r // 2)
                look_x = int(math.sin(i * 0.2) * cs * 0.008)
                draw.ellipse(
                    [eye_x + look_x - pr, eye_y - pr, eye_x + look_x + pr, eye_y + pr],
                    fill=(10, 10, 10, 255),
                )

                # Eyebrow (judgmental arch)
                brow_y_pos = eye_y - eye_r - int(cs * 0.015)
                draw.line(
                    [
                        (eye_x - eye_r - 2, brow_y_pos + int(cs * 0.01)),
                        (eye_x + eye_r + 2, brow_y_pos - int(cs * 0.005)),
                    ],
                    fill=(180, 140, 0, 255),
                    width=max(1, int(cs * 0.012)),
                )

                # Speech bubble with judgmental text
                quotes = [
                    "Have you tried\nreading the docs?",
                    "That's a bold\nchoice of variable.",
                    "I see no tests.",
                    "Ship it!\n(just kidding)",
                    "console.log?\nReally?",
                    "It works?\nBut WHY?",
                ]
                q_idx = (i // 40) % len(quotes)
                bubble_x = cx - int(cs * 0.22)
                bubble_y = cy - int(cs * 0.30)
                bubble_w = int(cs * 0.25)
                bubble_h = int(cs * 0.13)
                draw.rounded_rectangle(
                    [bubble_x, bubble_y, bubble_x + bubble_w, bubble_y + bubble_h],
                    radius=int(cs * 0.02),
                    fill=(255, 255, 255, 230),
                    outline=(200, 200, 200, 255),
                    width=1,
                )
                # Tail
                draw.polygon(
                    [
                        (bubble_x + int(bubble_w * 0.6), bubble_y + bubble_h),
                        (bubble_x + int(bubble_w * 0.7), bubble_y + bubble_h),
                        (head_cx - head_r, head_cy - int(cs * 0.02)),
                    ],
                    fill=(255, 255, 255, 230),
                )
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.025))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (bubble_x + int(cs * 0.015), bubble_y + int(cs * 0.015)),
                    quotes[q_idx],
                    fill=(40, 40, 40, 255),
                    font=q_font,
                )

            elif style == "fail_whale":
                # ── Twitter Fail Whale ────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.02)
                cy = int(cs * 0.52) - bounce

                # Sky gradient (light blue)
                for row in range(cs):
                    r_val = int(135 + row * 60 / cs)
                    g_val = int(200 + row * 30 / cs)
                    b_val = int(235 + row * 15 / cs)
                    draw.line(
                        [(0, row), (cs, row)],
                        fill=(min(255, r_val), min(255, g_val), min(255, b_val), 255),
                    )

                # Whale body (light blue/grey)
                whale_color = (120, 180, 220, 255)
                body_w = int(cs * 0.25)
                body_h = int(cs * 0.14)
                draw.ellipse(
                    [cx - body_w, cy - body_h, cx + body_w, cy + body_h],
                    fill=whale_color,
                )

                # Whale belly (lighter)
                belly_w = int(body_w * 0.75)
                belly_h = int(body_h * 0.55)
                draw.ellipse(
                    [cx - belly_w, cy - int(body_h * 0.1), cx + belly_w, cy + belly_h],
                    fill=(170, 210, 240, 255),
                )

                # Tail fin
                tail_x = cx - body_w - int(cs * 0.02)
                draw.polygon(
                    [
                        (tail_x, cy),
                        (tail_x - int(cs * 0.08), cy - int(cs * 0.08)),
                        (tail_x - int(cs * 0.03), cy),
                        (tail_x - int(cs * 0.08), cy + int(cs * 0.06)),
                    ],
                    fill=whale_color,
                )

                # Eye
                eye_x = cx + int(cs * 0.10)
                eye_y = cy - int(cs * 0.04)
                eye_r = max(2, int(cs * 0.02))
                draw.ellipse(
                    [eye_x - eye_r, eye_y - eye_r, eye_x + eye_r, eye_y + eye_r],
                    fill=(255, 255, 255, 255),
                )
                pr = max(1, eye_r // 2)
                draw.ellipse(
                    [eye_x - pr, eye_y - pr, eye_x + pr, eye_y + pr],
                    fill=(30, 30, 50, 255),
                )

                # Calm smile
                smile_cx = cx + int(cs * 0.08)
                smile_y = cy + int(cs * 0.02)
                draw.arc(
                    [
                        smile_cx - int(cs * 0.04),
                        smile_y,
                        smile_cx + int(cs * 0.04),
                        smile_y + int(cs * 0.03),
                    ],
                    start=0,
                    end=180,
                    fill=(80, 80, 100, 200),
                    width=max(1, int(cs * 0.008)),
                )

                # Water spout
                spout_x = cx + int(cs * 0.02)
                spout_y = cy - body_h - int(cs * 0.02)
                for sp in range(3):
                    sp_h = int(cs * (0.04 + sp * 0.02)) + int(math.sin(i * 0.2 + sp) * cs * 0.01)
                    sp_x = spout_x + int(math.sin(i * 0.15 + sp * 1.5) * cs * 0.015)
                    draw.line(
                        [
                            (sp_x, spout_y),
                            (sp_x + int(cs * 0.01) * (sp - 1), spout_y - sp_h),
                        ],
                        fill=(100, 180, 255, 180),
                        width=max(1, int(cs * 0.006)),
                    )

                # Birds carrying the whale (ropes + birds)
                num_birds = 5
                for b_idx in range(num_birds):
                    bx = cx - int(cs * 0.18) + int(b_idx * cs * 0.09)
                    by = cy - body_h - int(cs * 0.12) + int(math.sin(i * 0.2 + b_idx) * cs * 0.015)
                    # Rope
                    draw.line(
                        [
                            (bx, by + int(cs * 0.02)),
                            (
                                cx + int((b_idx - 2) * cs * 0.06),
                                cy - body_h + int(cs * 0.02),
                            ),
                        ],
                        fill=(160, 140, 100, 200),
                        width=max(1, int(cs * 0.004)),
                    )
                    # Bird (simple V shape)
                    bw = int(cs * 0.025)
                    draw.line(
                        [(bx - bw, by + int(cs * 0.01)), (bx, by)],
                        fill=(80, 80, 80, 255),
                        width=max(1, int(cs * 0.006)),
                    )
                    draw.line(
                        [(bx, by), (bx + bw, by + int(cs * 0.01))],
                        fill=(80, 80, 80, 255),
                        width=max(1, int(cs * 0.006)),
                    )

                # Error text at bottom
                try:
                    err_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.028))
                    )
                except OSError:
                    err_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.18), int(cs * 0.82)),
                    "Twitter is over capacity.",
                    fill=(100, 100, 120, 200),
                    font=err_font,
                )
                draw.text(
                    (int(cs * 0.22), int(cs * 0.87)),
                    "Please wait a moment...",
                    fill=(130, 130, 150, 160),
                    font=err_font,
                )

            elif style == "server_rack":
                # ── Overheating server rack ────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.015)
                cy = int(cs * 0.48) - bounce

                # Dark server room background
                draw.rectangle([0, 0, cs, cs], fill=(15, 18, 25, 245))

                # Rack body (dark grey metallic)
                rack_w = int(cs * 0.30)
                rack_h = int(cs * 0.45)
                rack_x = cx - rack_w // 2
                rack_y = cy - rack_h // 2
                draw.rounded_rectangle(
                    [rack_x, rack_y, rack_x + rack_w, rack_y + rack_h],
                    radius=int(cs * 0.015),
                    fill=(50, 55, 60, 255),
                    outline=(80, 85, 90, 255),
                    width=2,
                )

                # Server units (horizontal slices)
                num_units = 5
                unit_h = rack_h // (num_units + 1)
                for u in range(num_units):
                    uy = rack_y + int(cs * 0.02) + u * unit_h
                    uw = rack_w - int(cs * 0.04)
                    ux = rack_x + int(cs * 0.02)
                    draw.rounded_rectangle(
                        [ux, uy, ux + uw, uy + unit_h - 3],
                        radius=2,
                        fill=(35, 38, 45, 255),
                        outline=(65, 68, 75, 255),
                        width=1,
                    )
                    # Blinking LED per unit
                    led_on = ((i + u * 7) % 20) < 12
                    led_color = (0, 255, 0, 200) if led_on else (0, 60, 0, 150)
                    draw.ellipse(
                        [ux + 4, uy + unit_h // 2 - 2, ux + 8, uy + unit_h // 2 + 2],
                        fill=led_color,
                    )
                    # Activity LED (amber, flickers with amp)
                    act_on = amp > 0.3 and ((i + u * 3) % 8) < 4
                    act_color = (255, 180, 0, 200) if act_on else (60, 40, 0, 100)
                    draw.ellipse(
                        [ux + 12, uy + unit_h // 2 - 2, ux + 16, uy + unit_h // 2 + 2],
                        fill=act_color,
                    )

                # Red angry eyes
                eye_r = max(2, int(cs * 0.025))
                eye_y_pos = rack_y + int(rack_h * 0.18)
                eye_gap = int(cs * 0.07)
                glow_intensity = int(150 + amp * 105)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    # Red glow
                    for gr in range(3):
                        glow_r = eye_r + gr * 2
                        draw.ellipse(
                            [
                                ecx - glow_r,
                                eye_y_pos - glow_r,
                                ecx + glow_r,
                                eye_y_pos + glow_r,
                            ],
                            fill=(glow_intensity, 0, 0, 40),
                        )
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(255, 50, 30, 255),
                    )
                    pr = max(1, eye_r // 3)
                    draw.ellipse(
                        [ecx - pr, eye_y_pos - pr, ecx + pr, eye_y_pos + pr],
                        fill=(255, 200, 50, 255),
                    )

                # Smoke particles rising
                num_smoke = max(2, int(amp * 8))
                for s in range(num_smoke):
                    sx = cx + int(math.sin(i * 0.08 + s * 1.7) * cs * 0.12)
                    sy_base = rack_y - int(cs * 0.02)
                    sy = sy_base - int((i * 1.5 + s * 20) % (cs * 0.25))
                    smoke_r = int(cs * 0.015 + (i * 0.5 + s * 10) % 8)
                    smoke_alpha = max(0, 120 - int((i * 1.5 + s * 20) % (cs * 0.25)))
                    draw.ellipse(
                        [sx - smoke_r, sy - smoke_r, sx + smoke_r, sy + smoke_r],
                        fill=(140, 140, 150, smoke_alpha),
                    )

                # Temperature bar at bottom
                bar_x = rack_x
                bar_w = rack_w
                bar_h = max(3, int(cs * 0.015))
                bar_y = rack_y + rack_h + int(cs * 0.02)
                draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(40, 40, 40, 200))
                fill_w = int(bar_w * (0.3 + amp * 0.7))
                bar_color = (255, int(200 * (1 - amp)), 0, 255)
                draw.rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], fill=bar_color)

            elif style == "cursor_hand":
                # ── Mouse cursor / pointing hand ──────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.02)
                cy = int(cs * 0.48) - bounce

                # Light background (desktop feel)
                draw.rectangle([0, 0, cs, cs], fill=(230, 235, 240, 245))

                # Hand cursor (white pointer hand)
                hand_cx = cx + int(math.sin(i * 0.15) * cs * 0.06)
                hand_cy = cy + int(math.cos(i * 0.12) * cs * 0.04)

                # Pointer finger (index pointing up)
                finger_w = int(cs * 0.035)
                finger_h = int(cs * 0.12)
                finger_x = hand_cx - finger_w // 2
                finger_y = hand_cy - int(cs * 0.18)
                draw.rounded_rectangle(
                    [finger_x, finger_y, finger_x + finger_w, finger_y + finger_h],
                    radius=int(cs * 0.015),
                    fill=(255, 255, 255, 255),
                    outline=(30, 30, 30, 255),
                    width=max(1, int(cs * 0.008)),
                )

                # Palm (rounded rectangle below finger)
                palm_w = int(cs * 0.12)
                palm_h = int(cs * 0.10)
                palm_x = hand_cx - palm_w // 2
                palm_y = finger_y + finger_h - int(cs * 0.015)
                draw.rounded_rectangle(
                    [palm_x, palm_y, palm_x + palm_w, palm_y + palm_h],
                    radius=int(cs * 0.02),
                    fill=(255, 255, 255, 255),
                    outline=(30, 30, 30, 255),
                    width=max(1, int(cs * 0.008)),
                )

                # Other fingers (curled, smaller rounded rects)
                for f_idx in range(3):
                    fx = palm_x + int(cs * 0.025) + f_idx * int(cs * 0.03)
                    fy = palm_y + int(cs * 0.04)
                    fw = int(cs * 0.025)
                    fh = int(cs * 0.04)
                    draw.rounded_rectangle(
                        [fx, fy, fx + fw, fy + fh],
                        radius=int(cs * 0.008),
                        fill=(240, 240, 240, 255),
                        outline=(30, 30, 30, 255),
                        width=max(1, int(cs * 0.006)),
                    )

                # Thumb
                thumb_x = palm_x - int(cs * 0.02)
                thumb_y = palm_y + int(cs * 0.02)
                draw.rounded_rectangle(
                    [
                        thumb_x,
                        thumb_y,
                        thumb_x + int(cs * 0.035),
                        thumb_y + int(cs * 0.045),
                    ],
                    radius=int(cs * 0.01),
                    fill=(245, 245, 245, 255),
                    outline=(30, 30, 30, 255),
                    width=max(1, int(cs * 0.006)),
                )

                # Eyes on the palm
                eye_r = max(2, int(cs * 0.018))
                eye_y_pos = palm_y + int(palm_h * 0.35)
                eye_gap = int(cs * 0.025)
                for side in [-1, 1]:
                    ecx = hand_cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(255, 255, 255, 255),
                        outline=(30, 30, 30, 200),
                        width=1,
                    )
                    pr = max(1, eye_r // 2)
                    look_dir = int(math.sin(i * 0.2) * cs * 0.005)
                    draw.ellipse(
                        [
                            ecx + look_dir - pr,
                            eye_y_pos - pr,
                            ecx + look_dir + pr,
                            eye_y_pos + pr,
                        ],
                        fill=(10, 10, 10, 255),
                    )

                # Bossy speech bubble
                quotes = [
                    "Click here!",
                    "No, not THERE!",
                    "Double-click!",
                    "STOP scrolling!",
                    "Right-click NOW!",
                    "Hover over that!",
                ]
                q_idx = (i // 35) % len(quotes)
                bubble_x = hand_cx + int(cs * 0.08)
                bubble_y = hand_cy - int(cs * 0.22)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.028))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                text = quotes[q_idx]
                bbox = q_font.getbbox(text)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                pad = int(cs * 0.015)
                draw.rounded_rectangle(
                    [
                        bubble_x,
                        bubble_y,
                        bubble_x + tw + pad * 2,
                        bubble_y + th + pad * 2,
                    ],
                    radius=int(cs * 0.015),
                    fill=(50, 50, 60, 230),
                    outline=(100, 100, 110, 255),
                    width=1,
                )
                draw.text(
                    (bubble_x + pad, bubble_y + pad),
                    text,
                    fill=(255, 255, 255, 255),
                    font=q_font,
                )

            elif style == "vhs_tape":
                # ── VHS cassette tape ─────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.018)
                cy = int(cs * 0.48) - bounce

                # 90s gradient bg
                for row in range(cs):
                    t_row = row / cs
                    draw.line(
                        [(0, row), (cs, row)],
                        fill=(
                            int(20 + t_row * 30),
                            int(10 + t_row * 15),
                            int(40 + t_row * 30),
                            245,
                        ),
                    )

                # VHS body (black rectangle)
                tape_w = int(cs * 0.38)
                tape_h = int(cs * 0.24)
                tape_x = cx - tape_w // 2
                tape_y = cy - tape_h // 2
                draw.rounded_rectangle(
                    [tape_x, tape_y, tape_x + tape_w, tape_y + tape_h],
                    radius=int(cs * 0.015),
                    fill=(25, 25, 30, 255),
                    outline=(60, 60, 70, 255),
                    width=2,
                )

                # Label sticker area (top part)
                label_w = int(tape_w * 0.85)
                label_h = int(tape_h * 0.35)
                label_x = cx - label_w // 2
                label_y = tape_y + int(cs * 0.015)
                draw.rounded_rectangle(
                    [label_x, label_y, label_x + label_w, label_y + label_h],
                    radius=int(cs * 0.008),
                    fill=(240, 235, 220, 255),
                )
                try:
                    lbl_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.022))
                    )
                except OSError:
                    lbl_font = ImageFont.load_default()
                draw.text(
                    (label_x + int(cs * 0.01), label_y + int(cs * 0.008)),
                    "VHS  SP  T-120",
                    fill=(40, 40, 50, 255),
                    font=lbl_font,
                )

                # Tape reels (two circles in the lower window)
                window_y = label_y + label_h + int(cs * 0.015)
                window_h = tape_h - label_h - int(cs * 0.045)
                window_w = int(tape_w * 0.65)
                window_x = cx - window_w // 2
                draw.rounded_rectangle(
                    [window_x, window_y, window_x + window_w, window_y + window_h],
                    radius=int(cs * 0.008),
                    fill=(15, 15, 18, 255),
                )

                # Left reel (bigger = more tape left)
                reel_r = int(cs * 0.03 + amp * cs * 0.01)
                reel_lx = window_x + int(window_w * 0.28)
                reel_ly = window_y + window_h // 2
                draw.ellipse(
                    [
                        reel_lx - reel_r,
                        reel_ly - reel_r,
                        reel_lx + reel_r,
                        reel_ly + reel_r,
                    ],
                    fill=(60, 50, 40, 255),
                    outline=(100, 90, 80, 255),
                    width=1,
                )
                # Right reel (smaller)
                reel_r2 = int(cs * 0.025)
                reel_rx = window_x + int(window_w * 0.72)
                draw.ellipse(
                    [
                        reel_rx - reel_r2,
                        reel_ly - reel_r2,
                        reel_rx + reel_r2,
                        reel_ly + reel_r2,
                    ],
                    fill=(60, 50, 40, 255),
                    outline=(100, 90, 80, 255),
                    width=1,
                )
                # Spinning spokes
                for reel_cx_pos, rr in [(reel_lx, reel_r), (reel_rx, reel_r2)]:
                    for sp in range(3):
                        angle = i * 0.15 + sp * (2 * math.pi / 3)
                        sx1 = reel_cx_pos + int(math.cos(angle) * rr * 0.3)
                        sy1 = reel_ly + int(math.sin(angle) * rr * 0.3)
                        sx2 = reel_cx_pos + int(math.cos(angle) * rr * 0.85)
                        sy2 = reel_ly + int(math.sin(angle) * rr * 0.85)
                        draw.line([(sx1, sy1), (sx2, sy2)], fill=(130, 120, 100, 200), width=1)

                # Tape strip between reels
                draw.line(
                    [(reel_lx, reel_ly - reel_r), (reel_rx, reel_ly - reel_r2)],
                    fill=(80, 50, 30, 200),
                    width=max(1, int(cs * 0.004)),
                )
                draw.line(
                    [(reel_lx, reel_ly + reel_r), (reel_rx, reel_ly + reel_r2)],
                    fill=(80, 50, 30, 200),
                    width=max(1, int(cs * 0.004)),
                )

                # Eyes (on the tape reels)
                for reel_cx_pos in [reel_lx, reel_rx]:
                    eye_r_px = max(2, int(cs * 0.012))
                    draw.ellipse(
                        [
                            reel_cx_pos - eye_r_px,
                            reel_ly - eye_r_px,
                            reel_cx_pos + eye_r_px,
                            reel_ly + eye_r_px,
                        ],
                        fill=(255, 255, 255, 255),
                    )
                    pip = max(1, eye_r_px // 2)
                    draw.ellipse(
                        [
                            reel_cx_pos - pip,
                            reel_ly - pip,
                            reel_cx_pos + pip,
                            reel_ly + pip,
                        ],
                        fill=(10, 10, 10, 255),
                    )

                # Nostalgic quote
                quotes = [
                    "Be kind, rewind!",
                    "Not the Bic pen!",
                    "I was HD once...",
                    "Tracking... tracking...",
                    "EP mode = pain",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.025))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.22), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(200, 180, 140, 200),
                    font=q_font,
                )

                # VHS scan lines effect
                for sl_y in range(0, cs, 3):
                    draw.line([(0, sl_y), (cs, sl_y)], fill=(0, 0, 0, 15))

            elif style == "cloud":
                # ── Cute but capricious Cloud ─────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.025)
                cy = int(cs * 0.45) - bounce

                # Sky gradient
                for row in range(cs):
                    t_row = row / cs
                    b = int(200 + t_row * 55)
                    draw.line(
                        [(0, row), (cs, row)],
                        fill=(
                            int(100 + t_row * 60),
                            int(160 + t_row * 50),
                            min(255, b),
                            245,
                        ),
                    )

                # Cloud body (multiple overlapping circles)
                cloud_color = (255, 255, 255, 240)
                centers = [
                    (cx - int(cs * 0.10), cy + int(cs * 0.02), int(cs * 0.08)),
                    (cx - int(cs * 0.04), cy - int(cs * 0.03), int(cs * 0.09)),
                    (cx + int(cs * 0.05), cy - int(cs * 0.04), int(cs * 0.10)),
                    (cx + int(cs * 0.12), cy, int(cs * 0.07)),
                    (cx, cy + int(cs * 0.03), int(cs * 0.09)),
                ]
                for ccx, ccy, cr in centers:
                    draw.ellipse(
                        [ccx - cr, ccy - cr, ccx + cr, ccy + cr],
                        fill=cloud_color,
                    )

                # Flat bottom
                cloud_bottom = cy + int(cs * 0.07)
                draw.rectangle(
                    [
                        cx - int(cs * 0.17),
                        cy + int(cs * 0.01),
                        cx + int(cs * 0.18),
                        cloud_bottom,
                    ],
                    fill=cloud_color,
                )

                # Eyes (slightly sinister)
                eye_r = max(2, int(cs * 0.022))
                eye_y_pos = cy - int(cs * 0.005)
                eye_gap = int(cs * 0.055)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(50, 50, 70, 255),
                    )
                    # Gleam
                    gleam_r = max(1, eye_r // 3)
                    draw.ellipse(
                        [
                            ecx - eye_r // 2 - gleam_r,
                            eye_y_pos - eye_r // 2 - gleam_r,
                            ecx - eye_r // 2 + gleam_r,
                            eye_y_pos - eye_r // 2 + gleam_r,
                        ],
                        fill=(255, 255, 255, 200),
                    )

                # Smirk
                smirk_y = cy + int(cs * 0.025)
                draw.arc(
                    [
                        cx - int(cs * 0.04),
                        smirk_y,
                        cx + int(cs * 0.025),
                        smirk_y + int(cs * 0.025),
                    ],
                    start=0,
                    end=180,
                    fill=(60, 60, 80, 220),
                    width=max(1, int(cs * 0.01)),
                )

                # Rosy cheeks
                for side in [-1, 1]:
                    cheek_x = cx + int(cs * 0.07) * side
                    cheek_y = cy + int(cs * 0.015)
                    draw.ellipse(
                        [
                            cheek_x - int(cs * 0.015),
                            cheek_y - int(cs * 0.008),
                            cheek_x + int(cs * 0.015),
                            cheek_y + int(cs * 0.008),
                        ],
                        fill=(255, 150, 150, 80),
                    )

                # Rain drops (from bottom of cloud, more with amplitude)
                num_rain = max(1, int(amp * 6))
                for rd in range(num_rain):
                    rx = (
                        cx
                        - int(cs * 0.12)
                        + int(rd * cs * 0.05)
                        + int(math.sin(i * 0.1 + rd) * cs * 0.02)
                    )
                    ry_base = cloud_bottom + int(cs * 0.02)
                    ry = ry_base + int((i * 2 + rd * 18) % int(cs * 0.20))
                    drop_len = int(cs * 0.02)
                    draw.line(
                        [(rx, ry), (rx, ry + drop_len)],
                        fill=(100, 160, 255, int(180 - rd * 20)),
                        width=max(1, int(cs * 0.005)),
                    )

                # Lightning bolt (on high amp)
                if amp > 0.6:
                    lx = cx + int(math.sin(i * 0.3) * cs * 0.08)
                    ly = cloud_bottom
                    bolt_points = [
                        (lx, ly),
                        (lx - int(cs * 0.02), ly + int(cs * 0.06)),
                        (lx + int(cs * 0.015), ly + int(cs * 0.055)),
                        (lx - int(cs * 0.01), ly + int(cs * 0.12)),
                    ]
                    draw.line(
                        bolt_points,
                        fill=(255, 255, 100, 220),
                        width=max(2, int(cs * 0.01)),
                    )

                # Capricious quote
                quotes = [
                    "I own your data.",
                    "Pay more, store more.",
                    "Oops, 503 again!",
                    "Trust the cloud~",
                    "Auto-scaling... $$$",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.025))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.22), int(cs * 0.85)),
                    quotes[q_idx],
                    fill=(200, 200, 220, 200),
                    font=q_font,
                )

            elif style == "wifi_low":
                # ── Wi-Fi one-bar icon ────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                cy = int(cs * 0.55)

                # Dark background
                draw.rectangle([0, 0, cs, cs], fill=(20, 22, 30, 245))

                # Wi-Fi arcs (only first one lit, rest grey)
                arc_cx = cx
                arc_cy = cy + int(cs * 0.05)
                num_arcs = 4
                for a_idx in range(num_arcs):
                    arc_r = int(cs * (0.06 + a_idx * 0.05))
                    if a_idx == 0:
                        arc_color = (80, 200, 80, 255)
                    else:
                        # Flicker: sometimes a second arc barely shows
                        flicker = (i % (30 + a_idx * 10)) < 3 and a_idx == 1
                        arc_color = (80, 200, 80, 100) if flicker else (50, 55, 60, 180)
                    draw.arc(
                        [
                            arc_cx - arc_r,
                            arc_cy - arc_r,
                            arc_cx + arc_r,
                            arc_cy + arc_r,
                        ],
                        start=225,
                        end=315,
                        fill=arc_color,
                        width=max(2, int(cs * 0.012)),
                    )

                # Dot at center bottom
                dot_r = max(2, int(cs * 0.02))
                draw.ellipse(
                    [arc_cx - dot_r, arc_cy - dot_r, arc_cx + dot_r, arc_cy + dot_r],
                    fill=(80, 200, 80, 255),
                )

                # Eyes (on the dot area, slightly above)
                eye_r = max(2, int(cs * 0.018))
                eye_y_pos = arc_cy - int(cs * 0.06)
                eye_gap = int(cs * 0.04)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(200, 200, 210, 255),
                    )
                    pr = max(1, eye_r // 2)
                    draw.ellipse(
                        [ecx - pr, eye_y_pos - pr, ecx + pr, eye_y_pos + pr],
                        fill=(20, 20, 30, 255),
                    )

                # Stuttering text (cuts off mid-sentence)
                stutter_texts = [
                    "I was say—",
                    "Wait, wh—",
                    "Can you hea—",
                    "The signal is—",
                    "Loading...",
                    "Reconnec—",
                    "Bufferin—",
                    "Almost th—",
                ]
                # Change text more often to simulate drops
                t_idx = (i // 25) % len(stutter_texts)
                try:
                    t_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.028))
                    )
                except OSError:
                    t_font = ImageFont.load_default()

                # Glitch: sometimes text disappears
                if (i % 15) < 12:
                    draw.text(
                        (int(cs * 0.22), int(cs * 0.82)),
                        stutter_texts[t_idx],
                        fill=(150, 200, 150, 180),
                        font=t_font,
                    )

                # Connection bar indicator
                bar_y = int(cs * 0.20)
                bar_w = int(cs * 0.30)
                bar_x = cx - bar_w // 2
                bar_h = max(3, int(cs * 0.012))
                draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(40, 45, 50, 200))
                # Only ~15% filled
                fill_pct = 0.10 + amp * 0.08
                draw.rectangle(
                    [bar_x, bar_y, bar_x + int(bar_w * fill_pct), bar_y + bar_h],
                    fill=(80, 200, 80, 200),
                )

            elif style == "nokia3310":
                # ── Nokia 3310 — the indestructible ───────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.015)
                cy = int(cs * 0.48) - bounce

                # Dark bg
                draw.rectangle([0, 0, cs, cs], fill=(25, 25, 35, 245))

                # Phone body (dark blue / navy, rounded)
                phone_w = int(cs * 0.22)
                phone_h = int(cs * 0.42)
                phone_x = cx - phone_w // 2
                phone_y = cy - phone_h // 2
                draw.rounded_rectangle(
                    [phone_x, phone_y, phone_x + phone_w, phone_y + phone_h],
                    radius=int(cs * 0.03),
                    fill=(15, 25, 80, 255),
                    outline=(30, 50, 120, 255),
                    width=2,
                )

                # Screen (greenish LCD)
                screen_w = int(phone_w * 0.72)
                screen_h = int(phone_h * 0.22)
                screen_x = cx - screen_w // 2
                screen_y = phone_y + int(phone_h * 0.10)
                draw.rounded_rectangle(
                    [screen_x, screen_y, screen_x + screen_w, screen_y + screen_h],
                    radius=int(cs * 0.008),
                    fill=(140, 170, 100, 255),
                )

                # Snake pixel line on screen
                snake_len = 6
                for s in range(snake_len):
                    sx = screen_x + int(screen_w * 0.15) + s * int(cs * 0.012)
                    sy_offset = int(math.sin(i * 0.2 + s * 0.8) * cs * 0.015)
                    sy = screen_y + screen_h // 2 + sy_offset
                    px_sz = max(2, int(cs * 0.01))
                    draw.rectangle(
                        [sx, sy, sx + px_sz, sy + px_sz],
                        fill=(40, 60, 20, 255),
                    )

                # Eyes on the screen
                eye_r = max(2, int(cs * 0.012))
                eye_y_pos = screen_y + int(screen_h * 0.35)
                eye_gap = int(cs * 0.03)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(40, 60, 20, 255),
                    )

                # Keypad buttons (4x3 grid)
                kp_start_y = phone_y + int(phone_h * 0.45)
                kp_w = int(phone_w * 0.65)
                kp_x_start = cx - kp_w // 2
                btn_w = int(kp_w / 3) - 2
                btn_h = max(3, int(phone_h * 0.06))
                for row in range(4):
                    for col in range(3):
                        bx = kp_x_start + col * (btn_w + 2)
                        by = kp_start_y + row * (btn_h + 3)
                        draw.rounded_rectangle(
                            [bx, by, bx + btn_w, by + btn_h],
                            radius=2,
                            fill=(25, 40, 100, 255),
                            outline=(40, 60, 140, 255),
                            width=1,
                        )

                # Warrior quote
                quotes = [
                    "I AM indestructible.",
                    "Drop test? Please.",
                    "iPhones are fragile.",
                    "Snake > your apps",
                    "21 days battery!",
                    "Nokia connecting\npeople since 1998",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.024))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.18), int(cs * 0.85)),
                    quotes[q_idx],
                    fill=(100, 140, 200, 200),
                    font=q_font,
                )

            elif style == "cookie":
                # ── Browser Cookie — creepy tracking biscuit ──────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.02)
                cy = int(cs * 0.48) - bounce

                # Cookie body (beige/tan circle)
                cookie_r = int(cs * 0.16)
                cookie_color = (210, 170, 100, 255)
                draw.ellipse(
                    [cx - cookie_r, cy - cookie_r, cx + cookie_r, cy + cookie_r],
                    fill=cookie_color,
                    outline=(180, 140, 70, 255),
                    width=2,
                )

                # Chocolate chips (dark brown dots)
                chip_positions = [
                    (-0.06, -0.08),
                    (0.08, -0.05),
                    (-0.03, 0.06),
                    (0.05, 0.08),
                    (-0.08, 0.02),
                    (0.09, 0.01),
                    (-0.01, -0.11),
                    (0.03, 0.11),
                ]
                for cpx, cpy in chip_positions:
                    chip_cx = cx + int(cpx * cs)
                    chip_cy = cy + int(cpy * cs)
                    chip_r = max(2, int(cs * 0.015))
                    draw.ellipse(
                        [
                            chip_cx - chip_r,
                            chip_cy - chip_r,
                            chip_cx + chip_r,
                            chip_cy + chip_r,
                        ],
                        fill=(70, 40, 20, 255),
                    )

                # Cookie bite (remove a piece from top-right)
                bite_cx = cx + int(cs * 0.10)
                bite_cy = cy - int(cs * 0.10)
                bite_r = int(cs * 0.05)
                draw.ellipse(
                    [
                        bite_cx - bite_r,
                        bite_cy - bite_r,
                        bite_cx + bite_r,
                        bite_cy + bite_r,
                    ],
                    fill=(0, 0, 0, 0),
                )

                # Creepy eyes (slightly too big, gleaming)
                eye_r = max(3, int(cs * 0.030))
                eye_y_pos = cy - int(cs * 0.025)
                eye_gap = int(cs * 0.055)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(255, 255, 255, 255),
                    )
                    # Pupils that follow
                    pr = max(1, int(eye_r * 0.55))
                    look_x = int(math.sin(i * 0.18) * cs * 0.01)
                    look_y = int(math.cos(i * 0.14) * cs * 0.005)
                    draw.ellipse(
                        [
                            ecx + look_x - pr,
                            eye_y_pos + look_y - pr,
                            ecx + look_x + pr,
                            eye_y_pos + look_y + pr,
                        ],
                        fill=(10, 10, 10, 255),
                    )
                    # Gleam
                    gl = max(1, pr // 2)
                    draw.ellipse(
                        [
                            ecx + look_x - pr + 1,
                            eye_y_pos + look_y - pr + 1,
                            ecx + look_x - pr + 1 + gl,
                            eye_y_pos + look_y - pr + 1 + gl,
                        ],
                        fill=(255, 255, 255, 200),
                    )

                # Sly grin
                grin_y = cy + int(cs * 0.04)
                draw.arc(
                    [
                        cx - int(cs * 0.06),
                        grin_y,
                        cx + int(cs * 0.06),
                        grin_y + int(cs * 0.04),
                    ],
                    start=0,
                    end=180,
                    fill=(70, 40, 20, 255),
                    width=max(2, int(cs * 0.01)),
                )

                # Creepy quote
                quotes = [
                    "I know what\nyou browsed.",
                    "Accept ALL\ncookies...?",
                    "Tracking you\nsince 2003.",
                    "Third-party\nfriends say hi!",
                    "Clear me?\nI'll be back.",
                    "Mmm... your\ndata is tasty.",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.024))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.18), int(cs * 0.80)),
                    quotes[q_idx],
                    fill=(200, 170, 120, 200),
                    font=q_font,
                )

            elif style == "modem56k":
                # ── 56k Modem — dial-up nostalgia ─────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.012)
                cy = int(cs * 0.48) - bounce

                # Dark 90s desk bg
                draw.rectangle([0, 0, cs, cs], fill=(35, 30, 25, 245))

                # Modem body (beige rectangular box)
                modem_w = int(cs * 0.38)
                modem_h = int(cs * 0.12)
                modem_x = cx - modem_w // 2
                modem_y = cy - modem_h // 2
                draw.rounded_rectangle(
                    [modem_x, modem_y, modem_x + modem_w, modem_y + modem_h],
                    radius=int(cs * 0.008),
                    fill=(210, 200, 180, 255),
                    outline=(170, 160, 140, 255),
                    width=2,
                )

                # LEDs row (blinking pattern)
                num_leds = 8
                led_labels = ["PWR", "TX", "RX", "DTR", "CD", "OH", "RD", "SD"]
                led_start_x = modem_x + int(cs * 0.02)
                led_y = modem_y + int(modem_h * 0.25)
                led_spacing = (modem_w - int(cs * 0.04)) // num_leds
                for l_idx in range(num_leds):
                    lx = led_start_x + l_idx * led_spacing
                    # Different blink patterns
                    if l_idx == 0:  # PWR always on
                        led_color = (0, 220, 0, 255)
                    elif l_idx in (1, 2):  # TX/RX fast blink with amp
                        led_on = amp > 0.2 and ((i + l_idx * 3) % 6) < 3
                        led_color = (0, 220, 0, 230) if led_on else (0, 50, 0, 150)
                    else:  # Others slow random
                        led_on = ((i + l_idx * 7) % 25) < 10
                        led_color = (0, 200, 0, 200) if led_on else (0, 40, 0, 120)
                    led_r = max(2, int(cs * 0.008))
                    draw.ellipse(
                        [lx, led_y, lx + led_r * 2, led_y + led_r * 2],
                        fill=led_color,
                    )
                    # Label below
                    try:
                        led_font = ImageFont.truetype(
                            "/System/Library/Fonts/Courier.dfont",
                            max(8, int(cs * 0.014)),
                        )
                    except OSError:
                        led_font = ImageFont.load_default()
                    draw.text(
                        (lx - 1, led_y + led_r * 2 + 2),
                        led_labels[l_idx],
                        fill=(100, 90, 70, 200),
                        font=led_font,
                    )

                # Eyes (on top of modem)
                eye_r = max(2, int(cs * 0.020))
                eye_y_pos = modem_y - int(cs * 0.015)
                eye_gap = int(cs * 0.06)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(210, 200, 180, 255),
                        outline=(170, 160, 140, 200),
                        width=1,
                    )
                    pr = max(1, eye_r // 2)
                    draw.ellipse(
                        [ecx - pr, eye_y_pos - pr, ecx + pr, eye_y_pos + pr],
                        fill=(40, 35, 25, 255),
                    )

                # Dial-up sound visualization (waveform)
                wave_y_center = cy + int(cs * 0.15)
                num_pts = 40
                for wp in range(num_pts):
                    wx = int(cs * 0.15) + int(wp * cs * 0.7 / num_pts)
                    freq1 = math.sin(wp * 0.5 + i * 0.3) * cs * 0.025 * amp
                    freq2 = math.sin(wp * 1.2 + i * 0.5) * cs * 0.015 * amp
                    wy = wave_y_center + int(freq1 + freq2)
                    dot_r = max(1, int(cs * 0.004))
                    draw.ellipse(
                        [wx - dot_r, wy - dot_r, wx + dot_r, wy + dot_r],
                        fill=(0, 200, 0, int(100 + amp * 155)),
                    )

                # Modem speak (mix of text and sounds)
                quotes = [
                    "psshhh-kkkk!",
                    "ding-ding-ding...",
                    "SKREEEEE!",
                    "bzzzt... connected!",
                    "56k is enough.",
                    "Downloading at\n5.6 KB/s...",
                    "GET OFF\nTHE PHONE!",
                ]
                q_idx = (i // 30) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.025))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.20), int(cs * 0.78)),
                    quotes[q_idx],
                    fill=(0, 200, 0, int(150 + amp * 100)),
                    font=q_font,
                )

                # Phone cord
                cord_x = modem_x + modem_w - int(cs * 0.02)
                cord_y = modem_y + modem_h // 2
                for c_seg in range(8):
                    c_sx = cord_x + c_seg * int(cs * 0.012)
                    c_sy = cord_y + int(math.sin(c_seg * 1.0 + i * 0.1) * cs * 0.012)
                    c_ex = cord_x + (c_seg + 1) * int(cs * 0.012)
                    c_ey = cord_y + int(math.sin((c_seg + 1) * 1.0 + i * 0.1) * cs * 0.012)
                    draw.line(
                        [(c_sx, c_sy), (c_ex, c_ey)],
                        fill=(80, 80, 80, 200),
                        width=max(1, int(cs * 0.005)),
                    )

            elif style == "esc_key":
                # ── Escape key — panicked runaway ─────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                # Shaking/vibrating with amplitude
                shake_x = int(math.sin(i * 0.8) * cs * 0.02 * (0.5 + amp))
                shake_y = int(math.cos(i * 1.1) * cs * 0.015 * (0.5 + amp))
                cy = int(cs * 0.46) + shake_y

                # Dark keyboard-like background
                draw.rectangle([0, 0, cs, cs], fill=(30, 32, 38, 245))

                # Key body (rounded square, keycap look)
                key_sz = int(cs * 0.24)
                key_x = cx - key_sz // 2 + shake_x
                key_y = cy - key_sz // 2
                # Shadow
                draw.rounded_rectangle(
                    [key_x + 3, key_y + 5, key_x + key_sz + 3, key_y + key_sz + 5],
                    radius=int(cs * 0.025),
                    fill=(15, 15, 20, 200),
                )
                # Keycap
                draw.rounded_rectangle(
                    [key_x, key_y, key_x + key_sz, key_y + key_sz],
                    radius=int(cs * 0.025),
                    fill=(55, 58, 65, 255),
                    outline=(90, 93, 100, 255),
                    width=2,
                )
                # Inner depression
                inset = int(cs * 0.015)
                draw.rounded_rectangle(
                    [
                        key_x + inset,
                        key_y + inset,
                        key_x + key_sz - inset,
                        key_y + key_sz - inset,
                    ],
                    radius=int(cs * 0.015),
                    fill=(65, 68, 78, 255),
                )

                # "ESC" text
                try:
                    esc_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.045))
                    )
                except OSError:
                    esc_font = ImageFont.load_default()
                esc_bbox = esc_font.getbbox("ESC")
                esc_tw = esc_bbox[2] - esc_bbox[0]
                draw.text(
                    (key_x + key_sz // 2 - esc_tw // 2, key_y + int(cs * 0.02)),
                    "ESC",
                    fill=(200, 200, 210, 255),
                    font=esc_font,
                )

                # Panicked eyes (wide open)
                eye_r = max(3, int(cs * 0.028))
                eye_y_pos = key_y + int(key_sz * 0.48)
                eye_gap = int(cs * 0.05)
                for side in [-1, 1]:
                    ecx = key_x + key_sz // 2 + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(255, 255, 255, 255),
                    )
                    # Tiny pupils (panicked = small)
                    pr = max(1, eye_r // 3)
                    look_dir = int(math.sin(i * 0.3) * cs * 0.008)
                    draw.ellipse(
                        [
                            ecx + look_dir - pr,
                            eye_y_pos - pr,
                            ecx + look_dir + pr,
                            eye_y_pos + pr,
                        ],
                        fill=(10, 10, 10, 255),
                    )

                # Open screaming mouth
                mouth_cx = key_x + key_sz // 2
                mouth_y = eye_y_pos + int(cs * 0.04)
                mouth_r = max(3, int(cs * 0.02 + amp * cs * 0.015))
                draw.ellipse(
                    [
                        mouth_cx - mouth_r,
                        mouth_y - mouth_r,
                        mouth_cx + mouth_r,
                        mouth_y + int(mouth_r * 0.7),
                    ],
                    fill=(40, 40, 50, 255),
                )

                # Sweat drops (panicking)
                for sd in range(2):
                    sx = key_x + int(key_sz * (0.15 + sd * 0.7)) + shake_x
                    sy = key_y - int(cs * 0.01) - int((i * 2 + sd * 30) % int(cs * 0.08))
                    dr = max(2, int(cs * 0.01))
                    draw.ellipse(
                        [sx - dr, sy, sx + dr, sy + int(dr * 1.4)],
                        fill=(100, 180, 255, 180),
                    )

                # Panicked quotes
                quotes = [
                    "LET ME OUT!",
                    "Ctrl+Alt+Del??",
                    "Task Manager!",
                    "NOT RESPONDING!",
                    "Force quit! NOW!",
                    "Alt+F4! Alt+F4!",
                ]
                q_idx = (i // 30) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.026))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.20), int(cs * 0.84)),
                    quotes[q_idx],
                    fill=(255, 100, 100, 220),
                    font=q_font,
                )

            elif style == "sad_mac":
                # ── Sad Mac — classic dead Macintosh ──────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.01)
                cy = int(cs * 0.47) - bounce

                # Mac body (beige/platinum)
                mac_color = (200, 195, 180, 255)
                mac_w = int(cs * 0.28)
                mac_h = int(cs * 0.34)
                mac_x = cx - mac_w // 2
                mac_y = cy - mac_h // 2
                draw.rounded_rectangle(
                    [mac_x, mac_y, mac_x + mac_w, mac_y + mac_h],
                    radius=int(cs * 0.02),
                    fill=mac_color,
                    outline=(160, 155, 140, 255),
                    width=2,
                )

                # Screen (dark, with sad mac icon)
                screen_w = int(mac_w * 0.75)
                screen_h = int(mac_h * 0.55)
                screen_x = cx - screen_w // 2
                screen_y = mac_y + int(mac_h * 0.08)
                draw.rectangle(
                    [screen_x, screen_y, screen_x + screen_w, screen_y + screen_h],
                    fill=(10, 10, 15, 255),
                )

                # Sad Mac icon on screen (small Mac outline with X eyes)
                icon_w = int(screen_w * 0.35)
                icon_h = int(screen_h * 0.55)
                icon_x = screen_x + screen_w // 2 - icon_w // 2
                icon_y = screen_y + int(screen_h * 0.12)
                draw.rounded_rectangle(
                    [icon_x, icon_y, icon_x + icon_w, icon_y + icon_h],
                    radius=int(cs * 0.008),
                    outline=(120, 180, 120, 255),
                    width=max(1, int(cs * 0.006)),
                )
                # Inner screen area on icon
                iscr_m = int(cs * 0.008)
                draw.rectangle(
                    [
                        icon_x + iscr_m,
                        icon_y + iscr_m,
                        icon_x + icon_w - iscr_m,
                        icon_y + int(icon_h * 0.6),
                    ],
                    outline=(120, 180, 120, 200),
                    width=1,
                )

                # X eyes on the icon screen
                x_sz = max(2, int(cs * 0.015))
                icon_cx = icon_x + icon_w // 2
                icon_eye_y = icon_y + int(icon_h * 0.25)
                for side in [-1, 1]:
                    x_cx = icon_cx + int(cs * 0.02) * side
                    draw.line(
                        [
                            (x_cx - x_sz, icon_eye_y - x_sz),
                            (x_cx + x_sz, icon_eye_y + x_sz),
                        ],
                        fill=(120, 180, 120, 255),
                        width=max(1, int(cs * 0.005)),
                    )
                    draw.line(
                        [
                            (x_cx + x_sz, icon_eye_y - x_sz),
                            (x_cx - x_sz, icon_eye_y + x_sz),
                        ],
                        fill=(120, 180, 120, 255),
                        width=max(1, int(cs * 0.005)),
                    )

                # Sad mouth on icon
                draw.arc(
                    [
                        icon_cx - int(cs * 0.015),
                        icon_eye_y + int(cs * 0.015),
                        icon_cx + int(cs * 0.015),
                        icon_eye_y + int(cs * 0.03),
                    ],
                    start=200,
                    end=340,
                    fill=(120, 180, 120, 255),
                    width=max(1, int(cs * 0.005)),
                )

                # Error code below icon
                try:
                    code_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.02))
                    )
                except OSError:
                    code_font = ImageFont.load_default()
                err_codes = ["0000000F", "0000FFEE", "DEADBEEF", "0000000D"]
                err_code = err_codes[(i // 50) % len(err_codes)]
                draw.text(
                    (
                        screen_x + int(screen_w * 0.18),
                        screen_y + screen_h - int(cs * 0.035),
                    ),
                    err_code,
                    fill=(120, 180, 120, 200),
                    font=code_font,
                )

                # Floppy slot below screen
                slot_w = int(mac_w * 0.35)
                slot_h = max(3, int(cs * 0.01))
                slot_y_pos = screen_y + screen_h + int(cs * 0.025)
                draw.rectangle(
                    [
                        cx - slot_w // 2,
                        slot_y_pos,
                        cx + slot_w // 2,
                        slot_y_pos + slot_h,
                    ],
                    fill=(140, 135, 120, 255),
                )

                # Base/stand
                base_w = int(mac_w * 0.6)
                base_h = max(4, int(cs * 0.015))
                draw.rectangle(
                    [
                        cx - base_w // 2,
                        mac_y + mac_h,
                        cx + base_w // 2,
                        mac_y + mac_h + base_h,
                    ],
                    fill=(170, 165, 150, 255),
                )

                # Traumatized quote
                quotes = [
                    "Sad Mac 0000000F",
                    "I've seen things...",
                    "Logic board: gone.",
                    "Capacitor leak...",
                    "Not the screwdriver!",
                    "I was vintage!",
                ]
                q_idx = (i // 45) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.025))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.18), int(cs * 0.85)),
                    quotes[q_idx],
                    fill=(120, 180, 120, 180),
                    font=q_font,
                )

            elif style == "usb_cable":
                # ── Tangled USB cable ─────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.02)
                cy = int(cs * 0.48) - bounce

                # Light grey desk bg
                draw.rectangle([0, 0, cs, cs], fill=(40, 42, 48, 245))

                # USB-A connector (the end you always flip)
                plug_w = int(cs * 0.10)
                plug_h = int(cs * 0.06)
                plug_x = cx - plug_w // 2
                plug_y = cy - int(cs * 0.04)
                # Metal shell
                draw.rounded_rectangle(
                    [plug_x, plug_y, plug_x + plug_w, plug_y + plug_h],
                    radius=int(cs * 0.008),
                    fill=(180, 185, 190, 255),
                    outline=(140, 145, 150, 255),
                    width=2,
                )
                # Inner plastic (white)
                inner_w = int(plug_w * 0.75)
                inner_h = int(plug_h * 0.45)
                inner_x = cx - inner_w // 2
                inner_y = plug_y + int(plug_h * 0.25)
                draw.rectangle(
                    [inner_x, inner_y, inner_x + inner_w, inner_y + inner_h],
                    fill=(240, 240, 245, 255),
                )
                # USB symbol on the plastic
                usb_sym_x = inner_x + inner_w // 2
                usb_sym_y = inner_y + inner_h // 2
                sym_r = max(2, int(cs * 0.008))
                draw.ellipse(
                    [
                        usb_sym_x - sym_r,
                        usb_sym_y - sym_r,
                        usb_sym_x + sym_r,
                        usb_sym_y + sym_r,
                    ],
                    outline=(100, 100, 110, 255),
                    width=1,
                )

                # Eyes on the connector face
                eye_r = max(2, int(cs * 0.015))
                eye_y_pos = plug_y + int(plug_h * 0.4)
                eye_gap = int(cs * 0.025)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(255, 255, 255, 255),
                    )
                    pr = max(1, eye_r // 2)
                    # Frustrated look direction
                    lx = int(math.sin(i * 0.15) * cs * 0.005)
                    draw.ellipse(
                        [ecx + lx - pr, eye_y_pos - pr, ecx + lx + pr, eye_y_pos + pr],
                        fill=(10, 10, 10, 255),
                    )
                    # Angry brows
                    brow_y = eye_y_pos - eye_r - int(cs * 0.008)
                    draw.line(
                        [
                            (ecx - eye_r, brow_y - int(cs * 0.005) * side),
                            (ecx + eye_r, brow_y + int(cs * 0.005) * side),
                        ],
                        fill=(140, 145, 150, 255),
                        width=max(1, int(cs * 0.008)),
                    )

                # Frustrated mouth
                mouth_y = plug_y + plug_h - int(cs * 0.012)
                draw.arc(
                    [
                        cx - int(cs * 0.02),
                        mouth_y,
                        cx + int(cs * 0.02),
                        mouth_y + int(cs * 0.015),
                    ],
                    start=200,
                    end=340,
                    fill=(140, 145, 150, 255),
                    width=max(1, int(cs * 0.008)),
                )

                # Tangled cable below the plug
                cable_start_y = plug_y + plug_h
                cable_color = (60, 60, 65, 255)
                pts = []
                num_segments = 30
                for seg in range(num_segments):
                    t = seg / num_segments
                    sx = cx + int(math.sin(t * 6 + i * 0.05) * cs * 0.12)
                    sy = cable_start_y + int(t * cs * 0.30)
                    pts.append((sx, sy))
                for p_idx in range(len(pts) - 1):
                    draw.line(
                        [pts[p_idx], pts[p_idx + 1]],
                        fill=cable_color,
                        width=max(2, int(cs * 0.008)),
                    )

                # "3 tries" indicator — arrows showing flip attempts
                arrow_y = cy - int(cs * 0.16)
                for attempt in range(3):
                    ax = cx - int(cs * 0.08) + attempt * int(cs * 0.08)
                    # Arrow
                    arr_color = (255, 80, 80, 200) if attempt < 2 else (80, 255, 80, 200)
                    rotation = math.pi if attempt < 2 else 0
                    draw.line(
                        [
                            (ax, arrow_y - int(cs * 0.015)),
                            (ax, arrow_y + int(cs * 0.015)),
                        ],
                        fill=arr_color,
                        width=max(1, int(cs * 0.006)),
                    )
                    if attempt < 2:
                        draw.text(
                            (ax - int(cs * 0.008), arrow_y - int(cs * 0.03)),
                            "✗",
                            fill=(255, 80, 80, 200),
                            font=q_font if "q_font" in dir() else None,
                        )
                    else:
                        draw.text(
                            (ax - int(cs * 0.008), arrow_y - int(cs * 0.03)),
                            "✓",
                            fill=(80, 255, 80, 200),
                            font=q_font if "q_font" in dir() else None,
                        )

                # Quote
                quotes = [
                    "Wrong side. Again.",
                    "Flip it! No, back!",
                    "3rd time's a charm",
                    "USB-C is a myth.",
                    "50/50 chance,\n0% success",
                ]
                q_idx = (i // 35) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.025))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.20), int(cs * 0.83)),
                    quotes[q_idx],
                    fill=(180, 185, 190, 200),
                    font=q_font,
                )

            elif style == "hourglass":
                # ── Windows hourglass cursor — the slow talker ────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                cy = int(cs * 0.48)

                # Dark patient bg
                draw.rectangle([0, 0, cs, cs], fill=(25, 28, 35, 245))

                # Hourglass frame
                hg_w = int(cs * 0.16)
                hg_h = int(cs * 0.32)
                hg_x = cx - hg_w // 2
                hg_y = cy - hg_h // 2

                frame_color = (200, 180, 100, 255)
                # Top bar
                draw.rectangle(
                    [
                        hg_x - int(cs * 0.02),
                        hg_y,
                        hg_x + hg_w + int(cs * 0.02),
                        hg_y + int(cs * 0.015),
                    ],
                    fill=frame_color,
                )
                # Bottom bar
                draw.rectangle(
                    [
                        hg_x - int(cs * 0.02),
                        hg_y + hg_h - int(cs * 0.015),
                        hg_x + hg_w + int(cs * 0.02),
                        hg_y + hg_h,
                    ],
                    fill=frame_color,
                )

                # Glass shape (two triangles meeting in center)
                glass_color = (180, 200, 220, 120)
                mid_y = hg_y + hg_h // 2
                # Upper half
                draw.polygon(
                    [
                        (hg_x, hg_y + int(cs * 0.015)),
                        (hg_x + hg_w, hg_y + int(cs * 0.015)),
                        (cx + int(cs * 0.01), mid_y),
                        (cx - int(cs * 0.01), mid_y),
                    ],
                    fill=glass_color,
                    outline=(160, 180, 200, 180),
                    width=1,
                )
                # Lower half
                draw.polygon(
                    [
                        (cx - int(cs * 0.01), mid_y),
                        (cx + int(cs * 0.01), mid_y),
                        (hg_x + hg_w, hg_y + hg_h - int(cs * 0.015)),
                        (hg_x, hg_y + hg_h - int(cs * 0.015)),
                    ],
                    fill=glass_color,
                    outline=(160, 180, 200, 180),
                    width=1,
                )

                # Sand — falling grains
                sand_color = (220, 190, 100, 255)
                # Upper sand level decreases over time
                cycle = (i % 120) / 120.0  # 4 second cycle
                upper_fill = max(0, 1.0 - cycle)
                lower_fill = cycle
                # Upper sand
                if upper_fill > 0.05:
                    sand_top = (
                        hg_y
                        + int(cs * 0.015)
                        + int((1 - upper_fill) * (hg_h // 2 - int(cs * 0.02)))
                    )
                    sand_w_at_top = int(hg_w * (1 - (1 - upper_fill) * 0.9))
                    draw.polygon(
                        [
                            (cx - sand_w_at_top // 2, sand_top),
                            (cx + sand_w_at_top // 2, sand_top),
                            (cx + int(cs * 0.008), mid_y - 2),
                            (cx - int(cs * 0.008), mid_y - 2),
                        ],
                        fill=sand_color,
                    )
                # Lower sand pile
                if lower_fill > 0.05:
                    pile_h = int(lower_fill * (hg_h // 2 - int(cs * 0.02)))
                    pile_bottom = hg_y + hg_h - int(cs * 0.015)
                    pile_top = pile_bottom - pile_h
                    pile_w = int(hg_w * min(1.0, lower_fill * 1.2))
                    draw.polygon(
                        [
                            (cx - pile_w // 2, pile_bottom),
                            (cx + pile_w // 2, pile_bottom),
                            (cx + int(pile_w * 0.2), pile_top),
                            (cx - int(pile_w * 0.2), pile_top),
                        ],
                        fill=sand_color,
                    )
                # Falling stream
                if cycle > 0.01 and cycle < 0.95:
                    draw.line(
                        [(cx, mid_y), (cx, mid_y + int(cs * 0.05))],
                        fill=sand_color,
                        width=max(1, int(cs * 0.004)),
                    )

                # Sleepy eyes on the glass
                eye_r = max(2, int(cs * 0.018))
                eye_y_pos = hg_y + int(hg_h * 0.22)
                eye_gap = int(cs * 0.035)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    # Half-closed eyes (sleepy)
                    draw.arc(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        start=0,
                        end=180,
                        fill=(180, 160, 100, 255),
                        width=max(1, int(cs * 0.008)),
                    )
                    # Pupil below the lid
                    pr = max(1, eye_r // 3)
                    draw.ellipse(
                        [ecx - pr, eye_y_pos, ecx + pr, eye_y_pos + pr * 2],
                        fill=(80, 70, 40, 255),
                    )

                # Slow text — appears letter by letter
                slow_texts = [
                    "Please... wait...",
                    "Loading... still...",
                    "Almost... there...",
                    "Just... a... sec...",
                    "Patience... is...",
                ]
                t_idx = (i // 50) % len(slow_texts)
                full_text = slow_texts[t_idx]
                visible_chars = min(len(full_text), (i % 50) // 3 + 1)
                shown_text = full_text[:visible_chars]
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.026))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.20), int(cs * 0.84)),
                    shown_text,
                    fill=(200, 180, 100, 200),
                    font=q_font,
                )

            elif style == "firewire":
                # ── FireWire — the forgotten cable ────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.01)
                cy = int(cs * 0.48) - bounce

                # Dark dusty drawer bg
                draw.rectangle([0, 0, cs, cs], fill=(45, 38, 30, 245))

                # FireWire connector (trapezoidal shape, 6-pin)
                plug_w = int(cs * 0.14)
                plug_h = int(cs * 0.08)
                plug_x = cx - plug_w // 2
                plug_y = cy - plug_h // 2
                # Trapezoidal body (narrower at top)
                draw.polygon(
                    [
                        (plug_x + int(cs * 0.01), plug_y),
                        (plug_x + plug_w - int(cs * 0.01), plug_y),
                        (plug_x + plug_w, plug_y + plug_h),
                        (plug_x, plug_y + plug_h),
                    ],
                    fill=(170, 170, 175, 255),
                    outline=(130, 130, 135, 255),
                    width=2,
                )

                # 6 pins
                for pin in range(6):
                    px = plug_x + int(cs * 0.025) + pin * int((plug_w - int(cs * 0.05)) / 5)
                    py = plug_y + int(plug_h * 0.35)
                    pin_r = max(1, int(cs * 0.005))
                    draw.ellipse(
                        [px - pin_r, py - pin_r, px + pin_r, py + pin_r],
                        fill=(220, 190, 60, 255),
                    )

                # Sad eyes on connector
                eye_r = max(2, int(cs * 0.018))
                eye_y_pos = plug_y + int(plug_h * 0.5)
                eye_gap = int(cs * 0.03)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(200, 200, 210, 255),
                    )
                    pr = max(1, eye_r // 2)
                    # Looking down (sad)
                    draw.ellipse(
                        [ecx - pr, eye_y_pos + 1, ecx + pr, eye_y_pos + pr * 2 + 1],
                        fill=(50, 50, 60, 255),
                    )

                # Single tear
                tear_x = cx + eye_gap + eye_r
                tear_y = eye_y_pos + eye_r
                tear_drop_y = tear_y + int((i * 0.8) % (cs * 0.06))
                tear_r = max(1, int(cs * 0.008))
                draw.ellipse(
                    [
                        tear_x - tear_r,
                        tear_drop_y,
                        tear_x + tear_r,
                        tear_drop_y + int(tear_r * 1.5),
                    ],
                    fill=(100, 160, 255, 150),
                )

                # Cable dangling below
                cable_y = plug_y + plug_h
                for seg in range(15):
                    t = seg / 15
                    sx = cx + int(math.sin(t * 4 + i * 0.03) * cs * 0.06)
                    sy = cable_y + int(t * cs * 0.22)
                    sx2 = cx + int(math.sin((seg + 1) / 15 * 4 + i * 0.03) * cs * 0.06)
                    sy2 = cable_y + int((seg + 1) / 15 * cs * 0.22)
                    draw.line(
                        [(sx, sy), (sx2, sy2)],
                        fill=(100, 100, 105, 200),
                        width=max(2, int(cs * 0.006)),
                    )

                # Dust particles
                for dp in range(4):
                    dx = cx + int(math.sin(i * 0.05 + dp * 2) * cs * 0.18)
                    dy = int(cs * 0.25) + int(math.cos(i * 0.03 + dp * 1.5) * cs * 0.12)
                    draw.ellipse(
                        [dx - 1, dy - 1, dx + 1, dy + 1],
                        fill=(180, 170, 140, 60),
                    )

                # Nostalgic glory quotes
                quotes = [
                    "I was the future!",
                    "400 Mbps in 1999!",
                    "Apple loved me...",
                    "USB killed me.",
                    "Remember iMovie?",
                    "Living in a drawer.",
                ]
                q_idx = (i // 45) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.025))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.18), int(cs * 0.84)),
                    quotes[q_idx],
                    fill=(180, 160, 120, 180),
                    font=q_font,
                )

                # FireWire logo text
                try:
                    fw_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.02))
                    )
                except OSError:
                    fw_font = ImageFont.load_default()
                draw.text(
                    (cx - int(cs * 0.06), plug_y - int(cs * 0.035)),
                    "FireWire 400",
                    fill=(170, 170, 175, 140),
                    font=fw_font,
                )

            elif style == "ai_hallucinated":
                # ── Hallucinating AI robot ────────────────────────────
                import math
                import random

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.015)
                cy = int(cs * 0.46) - bounce

                # Glitchy gradient bg
                for row in range(cs):
                    glitch = int(math.sin(row * 0.1 + i * 0.2) * 10)
                    r_val = min(255, max(0, 20 + glitch))
                    draw.line(
                        [(0, row), (cs, row)],
                        fill=(r_val, 15, int(30 + row * 20 / cs), 245),
                    )

                # Robot head (slightly distorted rectangle)
                head_w = int(cs * 0.22)
                head_h = int(cs * 0.20)
                # Distortion oscillation
                distort = int(math.sin(i * 0.15) * cs * 0.008)
                head_x = cx - head_w // 2 + distort
                head_y = cy - head_h // 2
                draw.rounded_rectangle(
                    [head_x, head_y, head_x + head_w, head_y + head_h],
                    radius=int(cs * 0.02),
                    fill=(60, 65, 80, 255),
                    outline=(100, 110, 140, 255),
                    width=2,
                )

                # Antenna
                ant_x = cx + distort
                draw.line(
                    [(ant_x, head_y), (ant_x, head_y - int(cs * 0.05))],
                    fill=(100, 110, 140, 255),
                    width=max(1, int(cs * 0.006)),
                )
                # Blinking antenna ball (changes color erratically)
                ant_colors = [
                    (255, 50, 50),
                    (50, 255, 50),
                    (50, 50, 255),
                    (255, 255, 50),
                    (255, 50, 255),
                ]
                ant_col = ant_colors[i % len(ant_colors)]
                ant_r = max(2, int(cs * 0.012))
                draw.ellipse(
                    [
                        ant_x - ant_r,
                        head_y - int(cs * 0.05) - ant_r,
                        ant_x + ant_r,
                        head_y - int(cs * 0.05) + ant_r,
                    ],
                    fill=(*ant_col, 255),
                )

                # Eyes — one normal, one glitching
                eye_r = max(3, int(cs * 0.025))
                eye_y_pos = head_y + int(head_h * 0.35)
                eye_gap = int(cs * 0.05)
                # Left eye (normal-ish)
                lecx = cx - eye_gap + distort
                draw.ellipse(
                    [lecx - eye_r, eye_y_pos - eye_r, lecx + eye_r, eye_y_pos + eye_r],
                    fill=(200, 220, 255, 255),
                )
                pr = max(1, eye_r // 2)
                draw.ellipse(
                    [lecx - pr, eye_y_pos - pr, lecx + pr, eye_y_pos + pr],
                    fill=(20, 30, 50, 255),
                )
                # Right eye (spiral / glitching)
                recx = cx + eye_gap + distort
                draw.ellipse(
                    [recx - eye_r, eye_y_pos - eye_r, recx + eye_r, eye_y_pos + eye_r],
                    fill=(200, 220, 255, 255),
                )
                # Spiral in right eye
                for sp_i in range(12):
                    angle = i * 0.3 + sp_i * 0.5
                    sp_r = int(eye_r * sp_i / 12)
                    sp_x = recx + int(math.cos(angle) * sp_r * 0.5)
                    sp_y = eye_y_pos + int(math.sin(angle) * sp_r * 0.5)
                    draw.ellipse([sp_x - 1, sp_y - 1, sp_x + 1, sp_y + 1], fill=(20, 30, 50, 200))

                # Confused smile
                mouth_y = head_y + int(head_h * 0.72)
                draw.arc(
                    [
                        cx - int(cs * 0.04) + distort,
                        mouth_y,
                        cx + int(cs * 0.04) + distort,
                        mouth_y + int(cs * 0.025),
                    ],
                    start=0,
                    end=180,
                    fill=(150, 160, 200, 200),
                    width=max(1, int(cs * 0.008)),
                )

                # Hallucination quotes (mixing facts + nonsense)
                quotes = [
                    "Napoleon invented\nthe USB port.",
                    "Add 2 eggs to\nyour TCP/IP stack.",
                    "The Earth is\na sourdough bread.",
                    "Preheat the\nblockchain to 180C.",
                    "Lincoln coded\nthe first API.",
                    "Fold the neural\nnetwork gently.",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.024))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.16), int(cs * 0.80)),
                    quotes[q_idx],
                    fill=(180, 190, 255, 200),
                    font=q_font,
                )

                # Glitch lines (horizontal)
                if amp > 0.3:
                    num_glitch = max(1, int(amp * 4))
                    rng = random.Random(i)
                    for _ in range(num_glitch):
                        gy = rng.randint(0, cs)
                        gw = rng.randint(int(cs * 0.1), int(cs * 0.4))
                        gx = rng.randint(0, cs - gw)
                        draw.rectangle(
                            [gx, gy, gx + gw, gy + max(2, int(cs * 0.005))],
                            fill=(
                                rng.randint(100, 255),
                                rng.randint(0, 100),
                                rng.randint(100, 255),
                                80,
                            ),
                        )

            elif style == "tamagotchi":
                # ── Abandoned Tamagotchi ───────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.015)
                cy = int(cs * 0.48) - bounce

                # Dark nostalgic bg
                draw.rectangle([0, 0, cs, cs], fill=(30, 25, 40, 245))

                # Egg body (rounded oval)
                egg_w = int(cs * 0.18)
                egg_h = int(cs * 0.26)
                egg_x = cx - egg_w // 2
                egg_y = cy - egg_h // 2
                # Translucent colored shell
                egg_color = (220, 180, 250, 255)
                draw.ellipse(
                    [egg_x, egg_y, egg_x + egg_w, egg_y + egg_h],
                    fill=egg_color,
                    outline=(180, 140, 210, 255),
                    width=2,
                )

                # Screen (small greenish LCD in center)
                screen_w = int(egg_w * 0.65)
                screen_h = int(egg_h * 0.35)
                screen_x = cx - screen_w // 2
                screen_y = egg_y + int(egg_h * 0.18)
                draw.rounded_rectangle(
                    [screen_x, screen_y, screen_x + screen_w, screen_y + screen_h],
                    radius=int(cs * 0.008),
                    fill=(140, 170, 100, 255),
                    outline=(100, 130, 70, 255),
                    width=1,
                )

                # Pixel pet on screen (simple 5x5 pixel face)
                px_sz = max(2, int(cs * 0.012))
                pet_cx = screen_x + screen_w // 2
                pet_cy = screen_y + screen_h // 2
                # Body
                for dx in range(-2, 3):
                    for dy in range(-1, 2):
                        draw.rectangle(
                            [
                                pet_cx + dx * px_sz - px_sz // 2,
                                pet_cy + dy * px_sz - px_sz // 2,
                                pet_cx + dx * px_sz + px_sz // 2,
                                pet_cy + dy * px_sz + px_sz // 2,
                            ],
                            fill=(40, 60, 20, 255),
                        )
                # Eyes (pixels)
                for side in [-1, 1]:
                    ex = pet_cx + side * px_sz
                    ey = pet_cy - px_sz
                    draw.rectangle(
                        [
                            ex - px_sz // 2,
                            ey - px_sz // 2,
                            ex + px_sz // 2,
                            ey + px_sz // 2,
                        ],
                        fill=(140, 170, 100, 255),
                    )
                # Sad pixel mouth
                draw.rectangle(
                    [
                        pet_cx - px_sz,
                        pet_cy + px_sz - px_sz // 2,
                        pet_cx + px_sz,
                        pet_cy + px_sz + px_sz // 2,
                    ],
                    fill=(40, 60, 20, 255),
                )

                # Hearts meter (empty = hungry)
                hearts_y = screen_y + screen_h + int(cs * 0.015)
                for h_idx in range(4):
                    hx = egg_x + int(cs * 0.02) + h_idx * int(cs * 0.035)
                    # Empty heart
                    max(2, int(cs * 0.012))
                    draw.text((hx, hearts_y), "♡", fill=(150, 100, 100, 180))

                # Three buttons below egg
                btn_y = egg_y + egg_h + int(cs * 0.015)
                for b_idx in range(3):
                    bx = cx - int(cs * 0.05) + b_idx * int(cs * 0.05)
                    btn_r = max(2, int(cs * 0.012))
                    draw.ellipse(
                        [bx - btn_r, btn_y - btn_r, bx + btn_r, btn_y + btn_r],
                        fill=(180, 140, 210, 255),
                        outline=(150, 110, 180, 255),
                        width=1,
                    )

                # Abandonment quotes
                quotes = [
                    "Feed me... pls...",
                    "It's been 28 years.",
                    "Why did you leave?",
                    "I'm still here...",
                    "Hungry since 1998.",
                    "Battery... fading...",
                ]
                q_idx = (i // 45) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.024))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.20), int(cs * 0.85)),
                    quotes[q_idx],
                    fill=(200, 170, 230, 180),
                    font=q_font,
                )

            elif style == "lasso_tool":
                # ── Photoshop lasso/selection tool ─────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.015)
                cy = int(cs * 0.48) - bounce

                # Photoshop grey canvas bg
                # Checkerboard pattern (transparency indicator)
                checker_sz = max(4, int(cs * 0.025))
                for row in range(0, cs, checker_sz):
                    for col in range(0, cs, checker_sz):
                        c = 200 if (row // checker_sz + col // checker_sz) % 2 == 0 else 220
                        draw.rectangle(
                            [col, row, col + checker_sz, row + checker_sz],
                            fill=(c, c, c, 245),
                        )

                # Lasso tool cursor (lasso shape)
                lasso_x = cx + int(math.sin(i * 0.12) * cs * 0.05)
                lasso_y = cy + int(math.cos(i * 0.10) * cs * 0.03)

                # Lasso loop
                loop_pts = []
                num_pts = 20
                for p in range(num_pts):
                    angle = p * 2 * math.pi / num_pts
                    r_loop = int(cs * 0.08 + math.sin(angle * 3 + i * 0.1) * cs * 0.015)
                    lx = lasso_x + int(math.cos(angle) * r_loop)
                    ly = lasso_y + int(math.sin(angle) * r_loop * 0.7) - int(cs * 0.05)
                    loop_pts.append((lx, ly))

                # Marching ants (dashed selection border)
                dash_offset = i % 8
                for p_idx in range(len(loop_pts)):
                    p1 = loop_pts[p_idx]
                    p2 = loop_pts[(p_idx + 1) % len(loop_pts)]
                    if (p_idx + dash_offset // 2) % 2 == 0:
                        draw.line([p1, p2], fill=(0, 0, 0, 220), width=max(1, int(cs * 0.006)))
                    else:
                        draw.line(
                            [p1, p2],
                            fill=(255, 255, 255, 220),
                            width=max(1, int(cs * 0.006)),
                        )

                # Lasso handle (line from loop to cursor)
                handle_x = lasso_x + int(cs * 0.06)
                handle_y = lasso_y + int(cs * 0.06)
                draw.line(
                    [
                        (lasso_x + int(cs * 0.05), lasso_y - int(cs * 0.02)),
                        (handle_x, handle_y),
                    ],
                    fill=(80, 80, 90, 200),
                    width=max(1, int(cs * 0.005)),
                )

                # Eyes on the handle/cursor area
                eye_r = max(2, int(cs * 0.02))
                eye_y_pos = handle_y + int(cs * 0.02)
                eye_gap = int(cs * 0.03)
                for side in [-1, 1]:
                    ecx = handle_x + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(255, 255, 255, 255),
                        outline=(60, 60, 70, 200),
                        width=1,
                    )
                    pr = max(1, eye_r // 2)
                    # Intense look (focused)
                    draw.ellipse(
                        [ecx - pr, eye_y_pos - pr, ecx + pr, eye_y_pos + pr],
                        fill=(10, 10, 10, 255),
                    )

                # Determined little mouth
                draw.line(
                    [
                        (handle_x - int(cs * 0.02), eye_y_pos + int(cs * 0.025)),
                        (handle_x + int(cs * 0.02), eye_y_pos + int(cs * 0.025)),
                    ],
                    fill=(80, 80, 90, 200),
                    width=max(1, int(cs * 0.008)),
                )

                # Obsessive quotes
                quotes = [
                    "I WILL select it.",
                    "Feather: 0px. Sharp.",
                    "Anti-alias ALWAYS.",
                    "Crop the universe!",
                    "Deselect? NEVER.",
                    "Ctrl+D is a crime.",
                ]
                q_idx = (i // 35) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.025))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.18), int(cs * 0.83)),
                    quotes[q_idx],
                    fill=(80, 80, 100, 200),
                    font=q_font,
                )

            elif style == "battery_low":
                # ── Battery at 1% — dying fast ────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                cy = int(cs * 0.46)

                # Urgent red-tinted bg
                red_tint = int(30 + amp * 30)
                draw.rectangle([0, 0, cs, cs], fill=(red_tint, 10, 10, 245))

                # Battery body (vertical)
                bat_w = int(cs * 0.18)
                bat_h = int(cs * 0.30)
                bat_x = cx - bat_w // 2
                bat_y = cy - bat_h // 2
                # Outline
                draw.rounded_rectangle(
                    [bat_x, bat_y, bat_x + bat_w, bat_y + bat_h],
                    radius=int(cs * 0.015),
                    fill=(20, 20, 25, 255),
                    outline=(200, 50, 50, 255),
                    width=2,
                )
                # Terminal nub on top
                nub_w = int(bat_w * 0.4)
                nub_h = max(3, int(cs * 0.02))
                draw.rounded_rectangle(
                    [cx - nub_w // 2, bat_y - nub_h, cx + nub_w // 2, bat_y],
                    radius=int(cs * 0.005),
                    fill=(200, 50, 50, 255),
                )

                # Almost empty fill (1% = tiny red sliver at bottom)
                fill_h = max(3, int(bat_h * 0.04))
                # Blink the fill
                if (i % 10) < 7:
                    draw.rectangle(
                        [
                            bat_x + 3,
                            bat_y + bat_h - fill_h - 3,
                            bat_x + bat_w - 3,
                            bat_y + bat_h - 3,
                        ],
                        fill=(255, 30, 30, 255),
                    )

                # "1%" text
                try:
                    pct_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.06))
                    )
                except OSError:
                    pct_font = ImageFont.load_default()
                pct_text = "1%"
                bbox = pct_font.getbbox(pct_text)
                tw = bbox[2] - bbox[0]
                draw.text(
                    (cx - tw // 2, bat_y + int(bat_h * 0.3)),
                    pct_text,
                    fill=(255, 50, 50, 220),
                    font=pct_font,
                )

                # Panicked eyes
                eye_r = max(2, int(cs * 0.022))
                eye_y_pos = bat_y + int(bat_h * 0.20)
                eye_gap = int(cs * 0.04)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(255, 200, 200, 255),
                    )
                    pr = max(1, eye_r // 3)
                    draw.ellipse(
                        [ecx - pr, eye_y_pos - pr, ecx + pr, eye_y_pos + pr],
                        fill=(100, 10, 10, 255),
                    )

                # Frantic text — talks fast then cuts off
                fast_texts = [
                    "PLUG ME IN NOW",
                    "I'm dying here—",
                    "Find a charger!!",
                    "5% was 10 min ago",
                    "Low power mo—",
                    "Shutting dow—",
                ]
                t_idx = (i // 25) % len(fast_texts)
                full_text = fast_texts[t_idx]
                # Text gets cut off abruptly on some
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.026))
                    )
                except OSError:
                    q_font = ImageFont.load_default()

                # Blink out occasionally (dying)
                if (i % 40) < 35:
                    draw.text(
                        (int(cs * 0.15), int(cs * 0.83)),
                        full_text,
                        fill=(255, 100, 100, 220),
                        font=q_font,
                    )

                # Screen flicker effect
                if amp > 0.5 and (i % 12) < 2:
                    draw.rectangle([0, 0, cs, cs], fill=(0, 0, 0, 180))

            elif style == "incognito":
                # ── Chrome Incognito detective ────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.018)
                cy = int(cs * 0.48) - bounce

                # Dark mysterious bg
                draw.rectangle([0, 0, cs, cs], fill=(25, 25, 30, 245))

                # Hat (fedora shape)
                hat_brim_w = int(cs * 0.26)
                hat_brim_h = max(3, int(cs * 0.018))
                hat_brim_y = cy - int(cs * 0.08)
                draw.ellipse(
                    [
                        cx - hat_brim_w // 2,
                        hat_brim_y - hat_brim_h,
                        cx + hat_brim_w // 2,
                        hat_brim_y + hat_brim_h,
                    ],
                    fill=(55, 55, 60, 255),
                )
                # Hat crown
                crown_w = int(cs * 0.16)
                crown_h = int(cs * 0.08)
                draw.rounded_rectangle(
                    [
                        cx - crown_w // 2,
                        hat_brim_y - crown_h,
                        cx + crown_w // 2,
                        hat_brim_y,
                    ],
                    radius=int(cs * 0.02),
                    fill=(55, 55, 60, 255),
                )
                # Hat band
                draw.rectangle(
                    [
                        cx - crown_w // 2,
                        hat_brim_y - int(cs * 0.015),
                        cx + crown_w // 2,
                        hat_brim_y,
                    ],
                    fill=(70, 70, 80, 255),
                )

                # Face (shadowy silhouette)
                face_w = int(cs * 0.18)
                face_h = int(cs * 0.14)
                face_x = cx - face_w // 2
                face_y = hat_brim_y - int(cs * 0.01)
                draw.ellipse(
                    [face_x, face_y, face_x + face_w, face_y + face_h],
                    fill=(45, 45, 50, 255),
                )

                # Glasses (big round dark glasses)
                glass_r = max(4, int(cs * 0.035))
                glass_y = face_y + int(face_h * 0.35)
                glass_gap = int(cs * 0.06)
                for side in [-1, 1]:
                    gcx = cx + glass_gap * side
                    # Glass lens
                    draw.ellipse(
                        [
                            gcx - glass_r,
                            glass_y - glass_r,
                            gcx + glass_r,
                            glass_y + glass_r,
                        ],
                        fill=(20, 20, 25, 255),
                        outline=(100, 100, 110, 255),
                        width=max(1, int(cs * 0.006)),
                    )
                    # Subtle eye gleam
                    gleam_r = max(1, glass_r // 4)
                    gleam_x = gcx + int(math.sin(i * 0.15) * glass_r * 0.3)
                    draw.ellipse(
                        [
                            gleam_x - gleam_r,
                            glass_y - gleam_r,
                            gleam_x + gleam_r,
                            glass_y + gleam_r,
                        ],
                        fill=(80, 80, 90, 200),
                    )
                # Bridge between glasses
                draw.line(
                    [
                        (cx - glass_gap + glass_r, glass_y),
                        (cx + glass_gap - glass_r, glass_y),
                    ],
                    fill=(100, 100, 110, 255),
                    width=max(1, int(cs * 0.005)),
                )
                # Temple arms
                for side in [-1, 1]:
                    arm_x = cx + glass_gap * side + glass_r * side
                    draw.line(
                        [
                            (arm_x, glass_y),
                            (arm_x + int(cs * 0.03) * side, glass_y - int(cs * 0.01)),
                        ],
                        fill=(100, 100, 110, 255),
                        width=max(1, int(cs * 0.005)),
                    )

                # Mysterious smirk
                smirk_y = glass_y + int(cs * 0.045)
                draw.arc(
                    [
                        cx - int(cs * 0.025),
                        smirk_y,
                        cx + int(cs * 0.015),
                        smirk_y + int(cs * 0.015),
                    ],
                    start=0,
                    end=180,
                    fill=(80, 80, 90, 200),
                    width=max(1, int(cs * 0.007)),
                )

                # Collar / coat suggestion
                coat_y = face_y + face_h - int(cs * 0.02)
                draw.polygon(
                    [
                        (cx - int(cs * 0.12), coat_y + int(cs * 0.12)),
                        (cx, coat_y),
                        (cx + int(cs * 0.12), coat_y + int(cs * 0.12)),
                    ],
                    fill=(50, 50, 55, 255),
                    outline=(70, 70, 80, 200),
                    width=1,
                )

                # Mysterious quotes
                quotes = [
                    "I see nothing...",
                    "Your secrets are\nsafe. Maybe.",
                    "No cookies here.\n(wink wink)",
                    "Who? Me? Nobody.",
                    "History? What\nhistory?",
                    "I know everything\nbut I'll deny it.",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.024))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.18), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(130, 130, 145, 200),
                    font=q_font,
                )

            elif style == "rainbow_wheel":
                # ── Mac rainbow spinning wheel — hypnotic rage ────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                cy = int(cs * 0.46)

                # Dark macOS-like bg
                draw.rectangle([0, 0, cs, cs], fill=(30, 30, 35, 245))

                # Spinning wheel
                wheel_r = int(cs * 0.11)
                num_segments = 12
                rainbow_colors = [
                    (255, 59, 48),
                    (255, 149, 0),
                    (255, 204, 0),
                    (76, 217, 100),
                    (0, 199, 190),
                    (90, 200, 250),
                    (0, 122, 255),
                    (88, 86, 214),
                    (175, 82, 222),
                    (255, 45, 85),
                    (255, 59, 48),
                    (255, 149, 0),
                ]
                rotation = i * 6  # degrees per frame
                for seg in range(num_segments):
                    start_angle = seg * (360 / num_segments) + rotation
                    end_angle = start_angle + (360 / num_segments)
                    color = rainbow_colors[seg % len(rainbow_colors)]
                    draw.pieslice(
                        [cx - wheel_r, cy - wheel_r, cx + wheel_r, cy + wheel_r],
                        start=start_angle,
                        end=end_angle,
                        fill=(*color, 255),
                    )
                # Inner circle (hole in the wheel)
                inner_r = int(wheel_r * 0.35)
                draw.ellipse(
                    [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
                    fill=(30, 30, 35, 255),
                )

                # Tiny angry eyes on the inner circle
                eye_r = max(2, int(cs * 0.012))
                eye_y = cy - int(cs * 0.008)
                eye_gap = int(cs * 0.02)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r],
                        fill=(255, 255, 255, 255),
                    )
                    pr = max(1, eye_r // 2)
                    draw.ellipse(
                        [ecx - pr, eye_y - pr, ecx + pr, eye_y + pr],
                        fill=(10, 10, 10, 255),
                    )
                    # Angry brow
                    draw.line(
                        [
                            (ecx - eye_r, eye_y - eye_r - int(cs * 0.005) * side),
                            (ecx + eye_r, eye_y - eye_r + int(cs * 0.005) * side),
                        ],
                        fill=(200, 200, 210, 255),
                        width=max(1, int(cs * 0.006)),
                    )

                # Smug little mouth
                draw.arc(
                    [
                        cx - int(cs * 0.012),
                        cy + int(cs * 0.008),
                        cx + int(cs * 0.012),
                        cy + int(cs * 0.02),
                    ],
                    start=0,
                    end=180,
                    fill=(200, 200, 210, 255),
                    width=max(1, int(cs * 0.005)),
                )

                # Rage quotes
                quotes = [
                    "I'll stop when I want.",
                    "Force Quit won't help.",
                    "Spinning since 2005.",
                    "Cmd+Q? Cute.",
                    "Just 5 more minutes…",
                    "You can't kill me.",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.025))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.18), int(cs * 0.84)),
                    quotes[q_idx],
                    fill=(180, 180, 190, 200),
                    font=q_font,
                )

            elif style == "error_404":
                # ── Error 404 — eternally lost ────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                cy = int(cs * 0.46)

                # White browser-like bg
                draw.rectangle([0, 0, cs, cs], fill=(245, 245, 248, 245))

                # Wandering movement
                wander_x = int(math.sin(i * 0.07) * cs * 0.08)
                wander_y = int(math.cos(i * 0.05) * cs * 0.05)

                # Big "404" text
                try:
                    big_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.12))
                    )
                except OSError:
                    big_font = ImageFont.load_default()
                text_404 = "404"
                bbox = big_font.getbbox(text_404)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                draw.text(
                    (cx - tw // 2 + wander_x, cy - th // 2 + wander_y - int(cs * 0.04)),
                    text_404,
                    fill=(180, 180, 190, 255),
                    font=big_font,
                )

                # Eyes in the zeros
                eye_r = max(3, int(cs * 0.02))
                # Approximate positions of the two 0s in "404"
                zero1_x = cx - int(cs * 0.055) + wander_x
                zero2_x = cx + int(cs * 0.055) + wander_x
                eye_base_y = cy - int(cs * 0.06) + wander_y
                for ecx in [zero1_x, zero2_x]:
                    # Pupil looking around (lost)
                    pr = max(1, eye_r // 2)
                    look_x = int(math.sin(i * 0.12) * cs * 0.01)
                    look_y = int(math.cos(i * 0.09) * cs * 0.008)
                    draw.ellipse(
                        [
                            ecx + look_x - pr,
                            eye_base_y + look_y - pr,
                            ecx + look_x + pr,
                            eye_base_y + look_y + pr,
                        ],
                        fill=(80, 80, 100, 255),
                    )

                # Tiny confused mouth
                mouth_y = cy + int(cs * 0.04) + wander_y
                draw.arc(
                    [
                        cx - int(cs * 0.025) + wander_x,
                        mouth_y,
                        cx + int(cs * 0.025) + wander_x,
                        mouth_y + int(cs * 0.02),
                    ],
                    start=200,
                    end=340,
                    fill=(150, 150, 165, 255),
                    width=max(1, int(cs * 0.006)),
                )

                # Question marks floating around
                try:
                    qm_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.03))
                    )
                except OSError:
                    qm_font = ImageFont.load_default()
                for qm in range(4):
                    qx = cx + int(math.sin(i * 0.04 + qm * 1.6) * cs * 0.18)
                    qy = int(cs * 0.2) + int(math.cos(i * 0.03 + qm * 2) * cs * 0.12)
                    draw.text((qx, qy), "?", fill=(200, 200, 210, 120), font=qm_font)

                # Lost quotes
                quotes = [
                    "Where am I?",
                    "Page Not Found.",
                    "I used to exist…",
                    "Check the URL?",
                    "I'm lost. Again.",
                    "Have you tried /home?",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.024))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.22) + wander_x, int(cs * 0.83)),
                    quotes[q_idx],
                    fill=(150, 150, 165, 200),
                    font=q_font,
                )

            elif style == "google_blob":
                # ── Google blob emoji — melted expressiveness ─────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.02)
                cy = int(cs * 0.48) - bounce

                # Light bg
                draw.rectangle([0, 0, cs, cs], fill=(35, 38, 45, 245))

                # Blob body — wobbly amorphous shape
                blob_r = int(cs * 0.12)
                pts = []
                num_pts = 24
                for p in range(num_pts):
                    angle = p * 2 * math.pi / num_pts
                    wobble = math.sin(angle * 3 + i * 0.15) * cs * 0.015
                    wobble += math.cos(angle * 2 + i * 0.1) * cs * 0.01
                    r = blob_r + int(wobble)
                    bx = cx + int(math.cos(angle) * r)
                    by = cy + int(math.sin(angle) * r * 0.85)
                    pts.append((bx, by))
                # Yellow blob color
                draw.polygon(pts, fill=(255, 205, 50, 255))
                # Lighter outline
                for p_idx in range(len(pts)):
                    draw.line(
                        [pts[p_idx], pts[(p_idx + 1) % len(pts)]],
                        fill=(255, 220, 100, 255),
                        width=max(1, int(cs * 0.004)),
                    )

                # Big expressive eyes
                eye_r = max(4, int(cs * 0.03))
                eye_y = cy - int(cs * 0.02)
                eye_gap = int(cs * 0.045)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    # White sclera
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y - eye_r,
                            ecx + eye_r,
                            eye_y + int(eye_r * 1.2),
                        ],
                        fill=(255, 255, 255, 255),
                    )
                    # Big pupil
                    pr = max(2, int(eye_r * 0.55))
                    look_x = int(math.sin(i * 0.1) * cs * 0.008)
                    draw.ellipse(
                        [
                            ecx + look_x - pr,
                            eye_y + look_x - pr,
                            ecx + look_x + pr,
                            eye_y + look_x + pr,
                        ],
                        fill=(50, 50, 60, 255),
                    )
                    # Gleam
                    gl = max(1, pr // 3)
                    draw.ellipse(
                        [
                            ecx + look_x - pr + gl,
                            eye_y - pr + gl,
                            ecx + look_x - pr + gl * 3,
                            eye_y - pr + gl * 3,
                        ],
                        fill=(255, 255, 255, 200),
                    )

                # Big open smile
                smile_w = int(cs * 0.06)
                smile_y = cy + int(cs * 0.03)
                draw.arc(
                    [cx - smile_w, smile_y, cx + smile_w, smile_y + int(cs * 0.04)],
                    start=0,
                    end=180,
                    fill=(130, 80, 20, 255),
                    width=max(1, int(cs * 0.008)),
                )

                # Nostalgic quotes
                quotes = [
                    "I was EXPRESSIVE!",
                    "Now I'm just a\ncircle. Boring.",
                    "Blob was art.",
                    "Flat design\nkilled me.",
                    "Remember when\nemoji had soul?",
                    "I used to MELT\nwith joy!",
                ]
                q_idx = (i // 42) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.024))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.18), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(255, 210, 80, 200),
                    font=q_font,
                )

            elif style == "bit":
                # ── Binary bit — rigid yes/no ─────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.02)
                cy = int(cs * 0.46) - bounce

                # Terminal green-on-black bg
                draw.rectangle([0, 0, cs, cs], fill=(5, 15, 5, 245))

                # Show alternating 0/1 based on frame
                current_bit = "1" if (i // 20) % 2 == 0 else "0"
                try:
                    bit_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.18))
                    )
                except OSError:
                    bit_font = ImageFont.load_default()
                bbox = bit_font.getbbox(current_bit)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                # Glow effect
                for glow in range(3, 0, -1):
                    draw.text(
                        (cx - tw // 2, cy - th // 2 - int(cs * 0.04)),
                        current_bit,
                        fill=(0, 255, 0, 30 * glow),
                        font=bit_font,
                    )
                draw.text(
                    (cx - tw // 2, cy - th // 2 - int(cs * 0.04)),
                    current_bit,
                    fill=(0, 255, 0, 255),
                    font=bit_font,
                )

                # Eyes embedded in the digit
                eye_r = max(2, int(cs * 0.018))
                eye_y = cy - int(cs * 0.04)
                eye_gap = int(cs * 0.04)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r],
                        fill=(0, 80, 0, 255),
                    )
                    pr = max(1, eye_r // 2)
                    draw.ellipse(
                        [ecx - pr, eye_y - pr, ecx + pr, eye_y + pr],
                        fill=(0, 200, 0, 255),
                    )

                # Stern straight mouth
                draw.line(
                    [
                        (cx - int(cs * 0.03), cy + int(cs * 0.02)),
                        (cx + int(cs * 0.03), cy + int(cs * 0.02)),
                    ],
                    fill=(0, 200, 0, 200),
                    width=max(1, int(cs * 0.006)),
                )

                # Binary rain in background
                try:
                    rain_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.018))
                    )
                except OSError:
                    rain_font = ImageFont.load_default()
                import random as _rng

                rng = _rng.Random(42)
                for col in range(0, cs, int(cs * 0.04)):
                    for row_idx in range(8):
                        ry = (row_idx * int(cs * 0.08) + i * 2) % cs
                        bit_char = str(rng.randint(0, 1))
                        draw.text((col, ry), bit_char, fill=(0, 100, 0, 40), font=rain_font)

                # Rigid quotes
                quotes = [
                    "Yes.",
                    "No.",
                    "True.",
                    "False.",
                    "1.",
                    "0.",
                    "Affirmative.",
                    "Negative.",
                    "Correct.",
                    "Incorrect.",
                ]
                q_idx = (i // 25) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.028))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.30), int(cs * 0.85)),
                    quotes[q_idx],
                    fill=(0, 255, 0, 200),
                    font=q_font,
                )

            elif style == "pc_fan":
                # ── PC fan — screaming cooler ─────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                cy = int(cs * 0.47)

                # Dark case interior bg
                draw.rectangle([0, 0, cs, cs], fill=(20, 22, 28, 245))

                # Fan housing (square frame)
                frame_sz = int(cs * 0.26)
                frame_x = cx - frame_sz // 2
                frame_y = cy - frame_sz // 2
                draw.rounded_rectangle(
                    [frame_x, frame_y, frame_x + frame_sz, frame_y + frame_sz],
                    radius=int(cs * 0.02),
                    fill=(40, 42, 50, 255),
                    outline=(60, 62, 70, 255),
                    width=2,
                )

                # Fan circle
                fan_r = int(frame_sz * 0.42)
                draw.ellipse(
                    [cx - fan_r, cy - fan_r, cx + fan_r, cy + fan_r],
                    fill=(30, 32, 40, 255),
                    outline=(55, 58, 65, 255),
                    width=1,
                )

                # Spinning blades
                num_blades = 7
                rotation = i * (8 + amp * 12)  # speed up with amplitude
                blade_color = (70, 75, 85, 255)
                for b in range(num_blades):
                    angle = math.radians(b * (360 / num_blades) + rotation)
                    # Blade as a curved polygon
                    inner_r = int(fan_r * 0.15)
                    outer_r = int(fan_r * 0.9)
                    angle_w = math.radians(18)
                    pts = [
                        (
                            cx + int(math.cos(angle - angle_w * 0.3) * inner_r),
                            cy + int(math.sin(angle - angle_w * 0.3) * inner_r),
                        ),
                        (
                            cx + int(math.cos(angle - angle_w) * outer_r),
                            cy + int(math.sin(angle - angle_w) * outer_r),
                        ),
                        (
                            cx + int(math.cos(angle) * outer_r),
                            cy + int(math.sin(angle) * outer_r),
                        ),
                        (
                            cx + int(math.cos(angle + angle_w * 0.3) * inner_r),
                            cy + int(math.sin(angle + angle_w * 0.3) * inner_r),
                        ),
                    ]
                    draw.polygon(pts, fill=blade_color)

                # Center hub
                hub_r = int(fan_r * 0.18)
                draw.ellipse(
                    [cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r],
                    fill=(50, 52, 60, 255),
                    outline=(70, 72, 80, 255),
                    width=1,
                )

                # Sticker face on hub
                eye_r = max(2, int(cs * 0.012))
                eye_y = cy - int(cs * 0.006)
                eye_gap = int(cs * 0.015)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r],
                        fill=(200, 200, 210, 255),
                    )
                    pr = max(1, eye_r // 2)
                    draw.ellipse(
                        [ecx - pr, eye_y - pr, ecx + pr, eye_y + pr],
                        fill=(10, 10, 10, 255),
                    )
                # Open screaming mouth
                mouth_r = max(2, int(cs * 0.01 + amp * cs * 0.008))
                draw.ellipse(
                    [
                        cx - mouth_r,
                        cy + int(cs * 0.008) - mouth_r // 2,
                        cx + mouth_r,
                        cy + int(cs * 0.008) + mouth_r,
                    ],
                    fill=(30, 30, 40, 255),
                )

                # Wind lines
                if amp > 0.2:
                    for wl in range(3):
                        wy = cy + int(cs * 0.04) * (wl - 1)
                        wx_start = frame_x + frame_sz + int(cs * 0.02)
                        wx_end = wx_start + int(cs * 0.05 + amp * cs * 0.06)
                        draw.line(
                            [(wx_start, wy), (wx_end, wy)],
                            fill=(80, 130, 200, int(80 + amp * 100)),
                            width=max(1, int(cs * 0.004)),
                        )

                # Screaming quotes
                quotes = [
                    "BRRRRRRRRR!!",
                    "3 Chrome tabs?!\nMAX RPM!",
                    "I CAN'T HEAR YOU\nOVER MY WIND!",
                    "Clean my dust!\nPLEASE!",
                    "Thermal throttle\nin 3… 2… 1…",
                    "WHO OPENED\nAFTER EFFECTS?!",
                ]
                q_idx = (i // 35) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.023))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.16), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(120, 160, 220, 200),
                    font=q_font,
                )

            elif style == "captcha":
                # ── CAPTCHA — twisted illegible challenger ────────────
                import math
                import random

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                cy = int(cs * 0.44)

                # White/grey captcha box bg
                draw.rectangle([0, 0, cs, cs], fill=(240, 240, 242, 245))

                # Captcha box
                box_w = int(cs * 0.32)
                box_h = int(cs * 0.14)
                box_x = cx - box_w // 2
                box_y = cy - box_h // 2
                draw.rectangle(
                    [box_x, box_y, box_x + box_w, box_y + box_h],
                    fill=(255, 255, 255, 255),
                    outline=(180, 180, 185, 255),
                    width=2,
                )

                # Distorted captcha text
                captcha_texts = ["xR7kp2", "w9Mn4Q", "hB3vZf", "Jt8pL5"]
                cap_idx = (i // 60) % len(captcha_texts)
                cap_text = captcha_texts[cap_idx]
                rng = random.Random(i // 60 + 100)
                try:
                    cap_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.035))
                    )
                except OSError:
                    cap_font = ImageFont.load_default()

                # Draw each char with offset/rotation illusion
                char_x = box_x + int(cs * 0.02)
                for ch_idx, ch in enumerate(cap_text):
                    ch_y = (
                        box_y + int(box_h * 0.25) + rng.randint(-int(cs * 0.015), int(cs * 0.015))
                    )
                    char_color = (
                        rng.randint(40, 120),
                        rng.randint(40, 120),
                        rng.randint(40, 120),
                        255,
                    )
                    draw.text((char_x, ch_y), ch, fill=char_color, font=cap_font)
                    char_x += int(cs * 0.045)

                # Strike-through noise lines
                for _ in range(4):
                    lx1 = box_x + rng.randint(0, box_w // 3)
                    ly1 = box_y + rng.randint(int(box_h * 0.2), int(box_h * 0.8))
                    lx2 = box_x + box_w - rng.randint(0, box_w // 3)
                    ly2 = box_y + rng.randint(int(box_h * 0.2), int(box_h * 0.8))
                    draw.line(
                        [(lx1, ly1), (lx2, ly2)],
                        fill=(
                            rng.randint(100, 180),
                            rng.randint(100, 180),
                            rng.randint(100, 180),
                            120,
                        ),
                        width=1,
                    )

                # Eyes above the box (angry)
                eye_r = max(3, int(cs * 0.025))
                eye_y = box_y - int(cs * 0.04)
                eye_gap = int(cs * 0.05)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r],
                        fill=(255, 255, 255, 255),
                        outline=(180, 180, 185, 255),
                        width=1,
                    )
                    pr = max(1, eye_r // 2)
                    draw.ellipse(
                        [ecx - pr, eye_y - pr, ecx + pr, eye_y + pr],
                        fill=(60, 60, 70, 255),
                    )
                    # Angry brows
                    brow_y_pos = eye_y - eye_r - int(cs * 0.008)
                    draw.line(
                        [
                            (ecx - eye_r, brow_y_pos - int(cs * 0.006) * side),
                            (ecx + eye_r, brow_y_pos + int(cs * 0.006) * side),
                        ],
                        fill=(100, 100, 110, 255),
                        width=max(1, int(cs * 0.007)),
                    )

                # Screaming mouth
                mouth_y = box_y - int(cs * 0.01)
                mouth_r = max(3, int(cs * 0.018 + amp * cs * 0.01))
                draw.ellipse(
                    [cx - mouth_r, mouth_y, cx + mouth_r, mouth_y + int(mouth_r * 0.7)],
                    fill=(200, 60, 60, 200),
                )

                # Checkbox area
                cb_sz = int(cs * 0.025)
                cb_x = box_x
                cb_y = box_y + box_h + int(cs * 0.02)
                draw.rectangle(
                    [cb_x, cb_y, cb_x + cb_sz, cb_y + cb_sz],
                    outline=(180, 180, 185, 255),
                    width=1,
                )
                try:
                    cb_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.02))
                    )
                except OSError:
                    cb_font = ImageFont.load_default()
                draw.text(
                    (cb_x + cb_sz + int(cs * 0.01), cb_y),
                    "I'm not a robot",
                    fill=(80, 80, 90, 255),
                    font=cb_font,
                )

                # Angry quotes
                quotes = [
                    "PROVE YOU'RE HUMAN!",
                    "Click the hydrants!",
                    "Am I readable?\nGOOD.",
                    "Select all buses.\nALL OF THEM.",
                    "Wrong! Try again!",
                    "Are traffic lights\nCROSSWALKS? YES!",
                ]
                q_idx = (i // 35) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.023))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.17), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(180, 60, 60, 200),
                    font=q_font,
                )

            elif style == "bluetooth":
                # ── Bluetooth logo — desperate connector ──────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.015)
                cy = int(cs * 0.47) - bounce

                # Dark blue bg
                draw.rectangle([0, 0, cs, cs], fill=(10, 15, 40, 245))

                # Bluetooth symbol (rune ᛒ shape)
                bt_h = int(cs * 0.22)
                bt_w = int(cs * 0.10)
                bt_x = cx
                bt_top = cy - bt_h // 2
                bt_bot = cy + bt_h // 2
                bt_color = (0, 120, 255, 255)
                line_w = max(2, int(cs * 0.008))

                # Vertical line
                draw.line([(bt_x, bt_top), (bt_x, bt_bot)], fill=bt_color, width=line_w)
                # Upper right arrow > shape
                draw.line(
                    [(bt_x, bt_top), (bt_x + bt_w // 2, bt_top + bt_h // 4)],
                    fill=bt_color,
                    width=line_w,
                )
                draw.line(
                    [
                        (bt_x + bt_w // 2, bt_top + bt_h // 4),
                        (bt_x - bt_w // 2, bt_top + bt_h * 3 // 4),
                    ],
                    fill=bt_color,
                    width=line_w,
                )
                # Lower right arrow
                draw.line(
                    [(bt_x, bt_bot), (bt_x + bt_w // 2, bt_bot - bt_h // 4)],
                    fill=bt_color,
                    width=line_w,
                )
                draw.line(
                    [
                        (bt_x + bt_w // 2, bt_bot - bt_h // 4),
                        (bt_x - bt_w // 2, bt_bot - bt_h * 3 // 4),
                    ],
                    fill=bt_color,
                    width=line_w,
                )

                # Glow around symbol
                glow_r = int(cs * 0.14)
                for g in range(3):
                    gr = glow_r + g * int(cs * 0.01)
                    draw.ellipse(
                        [cx - gr, cy - gr, cx + gr, cy + gr],
                        outline=(0, 100, 255, 30 - g * 8),
                        width=max(1, int(cs * 0.003)),
                    )

                # Sad eyes on the symbol
                eye_r = max(2, int(cs * 0.018))
                eye_y = cy - int(cs * 0.01)
                eye_gap = int(cs * 0.03)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r],
                        fill=(150, 180, 255, 255),
                    )
                    pr = max(1, eye_r // 2)
                    draw.ellipse(
                        [ecx - pr, eye_y + 1, ecx + pr, eye_y + pr * 2 + 1],
                        fill=(30, 50, 120, 255),
                    )

                # Sad mouth
                draw.arc(
                    [
                        cx - int(cs * 0.02),
                        cy + int(cs * 0.025),
                        cx + int(cs * 0.02),
                        cy + int(cs * 0.04),
                    ],
                    start=200,
                    end=340,
                    fill=(100, 150, 255, 200),
                    width=max(1, int(cs * 0.006)),
                )

                # Searching waves (pulsing circles)
                pulse_r = int((i % 40) * cs * 0.005)
                pulse_alpha = max(0, 180 - (i % 40) * 5)
                draw.ellipse(
                    [cx - pulse_r, cy - pulse_r, cx + pulse_r, cy + pulse_r],
                    outline=(0, 120, 255, pulse_alpha),
                    width=max(1, int(cs * 0.004)),
                )

                # Desperate quotes
                quotes = [
                    "Searching…",
                    "Pairing failed.",
                    "Device not found.",
                    "Please try again.",
                    "I just want to\nconnect! :(",
                    "Why won't you\npair with me?",
                ]
                q_idx = (i // 42) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.025))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.20), int(cs * 0.83)),
                    quotes[q_idx],
                    fill=(100, 160, 255, 200),
                    font=q_font,
                )

            elif style == "registry_key":
                # ── Windows Registry key — bureaucratic controller ────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                cy = int(cs * 0.46)

                # Windows grey bg
                draw.rectangle([0, 0, cs, cs], fill=(236, 233, 216, 245))

                # Registry tree lines (folder hierarchy)
                tree_x = int(cs * 0.12)
                try:
                    tree_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.016))
                    )
                except OSError:
                    tree_font = ImageFont.load_default()

                tree_items = [
                    "HKEY_LOCAL_MACHINE",
                    "  └─ SOFTWARE",
                    "      └─ Microsoft",
                    "          └─ Windows",
                    "              └─ CurrentVersion",
                    "                  └─ ME ←",
                ]
                # Highlight scrolls
                highlight_idx = (i // 30) % len(tree_items)
                for t_idx, item in enumerate(tree_items):
                    ty = int(cs * 0.12) + t_idx * int(cs * 0.035)
                    color = (0, 0, 150, 255) if t_idx == highlight_idx else (60, 60, 70, 200)
                    if t_idx == highlight_idx:
                        draw.rectangle(
                            [
                                tree_x - 2,
                                ty - 1,
                                tree_x + int(cs * 0.35),
                                ty + int(cs * 0.03),
                            ],
                            fill=(0, 0, 128, 40),
                        )
                    draw.text((tree_x, ty), item, fill=color, font=tree_font)

                # Key icon (folder with key symbol)
                key_sz = int(cs * 0.14)
                key_x = cx - key_sz // 2
                key_y = cy - int(cs * 0.02)
                # Folder shape
                draw.rounded_rectangle(
                    [key_x, key_y, key_x + key_sz, key_y + int(key_sz * 0.8)],
                    radius=int(cs * 0.01),
                    fill=(255, 230, 130, 255),
                    outline=(200, 180, 80, 255),
                    width=1,
                )
                # Tab on folder
                draw.rounded_rectangle(
                    [
                        key_x,
                        key_y - int(cs * 0.015),
                        key_x + int(key_sz * 0.4),
                        key_y + 1,
                    ],
                    radius=int(cs * 0.005),
                    fill=(255, 230, 130, 255),
                )

                # Stern eyes on folder
                eye_r = max(2, int(cs * 0.018))
                eye_y_pos = key_y + int(key_sz * 0.3)
                eye_gap = int(cs * 0.035)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - eye_r,
                            eye_y_pos - eye_r,
                            ecx + eye_r,
                            eye_y_pos + eye_r,
                        ],
                        fill=(255, 255, 255, 255),
                    )
                    pr = max(1, eye_r // 2)
                    draw.ellipse(
                        [ecx - pr, eye_y_pos - pr, ecx + pr, eye_y_pos + pr],
                        fill=(40, 40, 50, 255),
                    )

                # Thin stern mouth
                draw.line(
                    [
                        (cx - int(cs * 0.025), eye_y_pos + int(cs * 0.035)),
                        (cx + int(cs * 0.025), eye_y_pos + int(cs * 0.035)),
                    ],
                    fill=(120, 100, 40, 200),
                    width=max(1, int(cs * 0.006)),
                )

                # Bureaucratic quotes
                quotes = [
                    "Access denied.",
                    "DWORD or QWORD?\nCHOOSE.",
                    "Don't touch\nHKEY_CLASSES_ROOT.",
                    "I control\nEVERYTHING.",
                    "Regedit? I AM\nregedit.",
                    "Invalid key path.",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.023))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.18), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(100, 80, 20, 200),
                    font=q_font,
                )

            elif style == "high_ping":
                # ── High Ping — delayed responder ─────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                cy = int(cs * 0.46)

                # Dark network-ish bg
                draw.rectangle([0, 0, cs, cs], fill=(15, 20, 30, 245))

                # Signal bars (all red/low)
                bars_x = cx - int(cs * 0.08)
                bars_y = cy + int(cs * 0.02)
                for b_idx in range(4):
                    bar_w = max(3, int(cs * 0.025))
                    bar_h = int(cs * 0.03) * (b_idx + 1)
                    bx = bars_x + b_idx * int(cs * 0.04)
                    by = bars_y + int(cs * 0.12) - bar_h
                    bar_color = (255, 60, 60, 255) if b_idx < 1 else (80, 80, 90, 100)
                    draw.rectangle(
                        [bx, by, bx + bar_w, bars_y + int(cs * 0.12)],
                        fill=bar_color,
                    )

                # Ping display
                try:
                    ping_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(8, int(cs * 0.05))
                    )
                except OSError:
                    ping_font = ImageFont.load_default()
                ping_val = 999 + int(math.sin(i * 0.05) * 200)
                ping_text = f"{ping_val}ms"
                bbox = ping_font.getbbox(ping_text)
                tw = bbox[2] - bbox[0]
                draw.text(
                    (cx - tw // 2, cy - int(cs * 0.12)),
                    ping_text,
                    fill=(255, 80, 80, 255),
                    font=ping_font,
                )

                # Face below ping — lagging/frozen
                eye_r = max(3, int(cs * 0.025))
                eye_y = cy - int(cs * 0.04)
                eye_gap = int(cs * 0.05)
                # Eyes frozen/half-closed
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r],
                        fill=(180, 180, 200, 255),
                    )
                    # Horizontal line through eye (buffering)
                    draw.line(
                        [(ecx - eye_r, eye_y), (ecx + eye_r, eye_y)],
                        fill=(80, 80, 100, 200),
                        width=max(1, int(cs * 0.005)),
                    )

                # Straight mouth (expressionless lag)
                draw.line(
                    [
                        (cx - int(cs * 0.03), cy + int(cs * 0.01)),
                        (cx + int(cs * 0.03), cy + int(cs * 0.01)),
                    ],
                    fill=(180, 180, 200, 200),
                    width=max(1, int(cs * 0.006)),
                )

                # Buffering spinner
                spinner_r = int(cs * 0.04)
                spinner_y = cy + int(cs * 0.16)
                arc_start = (i * 8) % 360
                draw.arc(
                    [
                        cx - spinner_r,
                        spinner_y - spinner_r,
                        cx + spinner_r,
                        spinner_y + spinner_r,
                    ],
                    start=arc_start,
                    end=arc_start + 270,
                    fill=(180, 180, 200, 200),
                    width=max(2, int(cs * 0.008)),
                )

                # Delayed quotes (shown with stutter effect)
                quotes = [
                    "Wait… what?",
                    "Sorry I'm late—",
                    "Did you say\nsomething?",
                    "Lag… lag…\nlag…",
                    "Rubber-banding\nagain…",
                    "I was here\n10 sec ago.",
                ]
                q_idx = (i // 50) % len(quotes)
                # Text appears letter by letter (laggy)
                full_text = quotes[q_idx]
                visible = min(len(full_text), (i % 50) // 3)
                shown = full_text[:visible]
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.024))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.20), int(cs * 0.84)),
                    shown,
                    fill=(180, 180, 200, 200),
                    font=q_font,
                )

            elif style == "scratched_cd":
                # ── Scratched CD-ROM — stuttering repeater ────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.01)
                cy = int(cs * 0.47) - bounce

                # Dark bg
                draw.rectangle([0, 0, cs, cs], fill=(25, 20, 30, 245))

                # CD disc
                cd_r = int(cs * 0.14)
                # Rainbow reflection on CD
                for ring in range(cd_r, 0, -2):
                    hue_shift = (ring * 3 + i * 2) % 360
                    # Simple rainbow approx
                    r = int(128 + 60 * math.sin(math.radians(hue_shift)))
                    g = int(128 + 60 * math.sin(math.radians(hue_shift + 120)))
                    b = int(128 + 60 * math.sin(math.radians(hue_shift + 240)))
                    draw.ellipse(
                        [cx - ring, cy - ring, cx + ring, cy + ring],
                        fill=(r, g, b, 200),
                    )

                # Center hole
                hole_r = int(cs * 0.02)
                draw.ellipse(
                    [cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r],
                    fill=(25, 20, 30, 255),
                )

                # Label area (inner ring)
                label_r = int(cs * 0.06)
                draw.ellipse(
                    [cx - label_r, cy - label_r, cx + label_r, cy + label_r],
                    fill=(220, 220, 225, 255),
                )
                # CD text on label
                try:
                    cd_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.015))
                    )
                except OSError:
                    cd_font = ImageFont.load_default()
                draw.text(
                    (cx - int(cs * 0.03), cy - int(cs * 0.02)),
                    "CD-ROM",
                    fill=(100, 100, 110, 200),
                    font=cd_font,
                )

                # Scratches! (diagonal lines across disc)
                scratch_color = (255, 255, 255, 60)
                for s in range(5):
                    angle = s * 0.7 + 0.3
                    sx1 = cx + int(math.cos(angle) * cd_r * 0.3)
                    sy1 = cy + int(math.sin(angle) * cd_r * 0.3)
                    sx2 = cx + int(math.cos(angle) * cd_r * 0.95)
                    sy2 = cy + int(math.sin(angle) * cd_r * 0.95)
                    draw.line(
                        [(sx1, sy1), (sx2, sy2)],
                        fill=scratch_color,
                        width=max(1, int(cs * 0.003)),
                    )

                # Eyes on the label
                eye_r = max(2, int(cs * 0.016))
                eye_y = cy - int(cs * 0.005)
                eye_gap = int(cs * 0.025)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r],
                        fill=(255, 255, 255, 255),
                    )
                    pr = max(1, eye_r // 2)
                    # Vibrating pupils (stuttering)
                    stutter_x = int(math.sin(i * 0.8) * cs * 0.004)
                    draw.ellipse(
                        [
                            ecx + stutter_x - pr,
                            eye_y - pr,
                            ecx + stutter_x + pr,
                            eye_y + pr,
                        ],
                        fill=(40, 40, 50, 255),
                    )

                # Wobbly mouth
                mouth_y = cy + int(cs * 0.018)
                draw.arc(
                    [
                        cx - int(cs * 0.015),
                        mouth_y,
                        cx + int(cs * 0.015),
                        mouth_y + int(cs * 0.01),
                    ],
                    start=0,
                    end=180,
                    fill=(100, 100, 110, 200),
                    width=max(1, int(cs * 0.005)),
                )

                # Stuttering quotes (repeating syllables)
                quotes = [
                    "I-I-I was sa-sa-\nsaying…",
                    "Sk-sk-skip!\nSk-sk-skip!",
                    "Re-re-read error\nat t-t-track 3",
                    "Bur-bur-buffer\nunder-r-r-run",
                    "P-p-please don't\nsc-scratch me!",
                    "640 MB should\nb-b-be enough!",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.023))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.18), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(200, 200, 220, 200),
                    font=q_font,
                )

            elif style == "kermit":
                # ── Kermit — None of My Business ──────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.008)
                cy = int(cs * 0.45) - bounce

                # Swamp-green bg
                draw.rectangle([0, 0, cs, cs], fill=(20, 45, 20, 245))

                # Kermit body (green oval)
                body_h = int(cs * 0.18)
                body_w = int(cs * 0.12)
                draw.ellipse(
                    [cx - body_w, cy - body_h, cx + body_w, cy + body_h],
                    fill=(76, 153, 0, 255),
                )

                # Collar (pointy triangular collar)
                collar_y = cy + int(cs * 0.12)
                collar_w = int(cs * 0.08)
                draw.polygon(
                    [
                        (cx - collar_w, collar_y),
                        (cx, collar_y + int(cs * 0.06)),
                        (cx + collar_w, collar_y),
                    ],
                    fill=(60, 130, 0, 255),
                )

                # Big round eyes (slightly above head)
                eye_r = int(cs * 0.045)
                eye_y = cy - int(cs * 0.14)
                eye_gap = int(cs * 0.055)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    ecy = eye_y
                    draw.ellipse(
                        [ecx - eye_r, ecy - eye_r, ecx + eye_r, ecy + eye_r],
                        fill=(255, 255, 255, 255),
                    )
                    pr = max(2, eye_r // 3)
                    # Looking to the side (sipping tea)
                    draw.ellipse(
                        [
                            ecx + side * pr - pr,
                            ecy - pr,
                            ecx + side * pr + pr,
                            ecy + pr,
                        ],
                        fill=(20, 20, 20, 255),
                    )

                # Mouth (wide frog smile)
                mouth_w = int(cs * 0.07)
                mouth_y = cy - int(cs * 0.04)
                draw.arc(
                    [cx - mouth_w, mouth_y, cx + mouth_w, mouth_y + int(cs * 0.04)],
                    start=0,
                    end=180,
                    fill=(40, 100, 0, 255),
                    width=max(2, int(cs * 0.005)),
                )

                # Tea cup in hand
                cup_x = cx + int(cs * 0.14)
                cup_y = cy + int(cs * 0.02)
                cup_w = int(cs * 0.04)
                cup_h = int(cs * 0.05)
                draw.rectangle(
                    [cup_x, cup_y, cup_x + cup_w, cup_y + cup_h],
                    fill=(255, 255, 240, 255),
                    outline=(200, 180, 140, 255),
                    width=max(1, int(cs * 0.003)),
                )
                # Handle
                draw.arc(
                    [
                        cup_x + cup_w,
                        cup_y + int(cup_h * 0.2),
                        cup_x + cup_w + int(cs * 0.02),
                        cup_y + int(cup_h * 0.8),
                    ],
                    start=270,
                    end=90,
                    fill=(200, 180, 140, 255),
                    width=max(1, int(cs * 0.003)),
                )
                # Steam (animated)
                steam_alpha = int(80 + amp * 80)
                for s in range(3):
                    sx = cup_x + int(cup_w * 0.3) + s * int(cs * 0.012)
                    sy = cup_y - int(cs * 0.02) - int(math.sin(i * 0.15 + s) * cs * 0.01)
                    draw.text((sx, sy), "~", fill=(200, 200, 200, steam_alpha))

                # Quotes
                quotes = [
                    "But that's none of\nmy business…",
                    "I see bugs but\nthat's none of\nmy business.",
                    "*sips tea*\n…interesting.",
                    "Your code has\nno tests but\nthat's fine…",
                    "Deploying on\nFriday? Bold.\n*sips tea*",
                    "The logs say\notherwise…\n*sips*",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.022))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.12), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(180, 220, 160, 200),
                    font=q_font,
                )

            elif style == "this_is_fine":
                # ── This Is Fine dog ──────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.006)
                cy = int(cs * 0.45) - bounce

                # Flames background
                flame_colors = [
                    (255, 80, 0, 180),
                    (255, 140, 0, 160),
                    (255, 200, 0, 140),
                    (255, 60, 0, 200),
                ]
                for f_idx in range(20):
                    fx = int((f_idx * cs * 0.07 + i * 2) % cs)
                    fy = int(cs * 0.3 + math.sin(i * 0.1 + f_idx) * cs * 0.15)
                    fw = int(cs * 0.06 + amp * cs * 0.03)
                    fh = int(cs * 0.2 + amp * cs * 0.1)
                    color = flame_colors[f_idx % len(flame_colors)]
                    draw.ellipse(
                        [fx - fw, fy - fh, fx + fw, fy],
                        fill=color,
                    )

                # Dark smoky top
                draw.rectangle([0, 0, cs, int(cs * 0.15)], fill=(40, 30, 20, 200))

                # Dog body (yellow/tan oval)
                body_w = int(cs * 0.1)
                body_h = int(cs * 0.12)
                draw.ellipse(
                    [cx - body_w, cy - body_h, cx + body_w, cy + body_h],
                    fill=(240, 210, 120, 255),
                )

                # Dog head
                head_r = int(cs * 0.08)
                head_y = cy - int(cs * 0.12)
                draw.ellipse(
                    [cx - head_r, head_y - head_r, cx + head_r, head_y + head_r],
                    fill=(240, 210, 120, 255),
                )

                # Ears (floppy)
                ear_w = int(cs * 0.03)
                ear_h = int(cs * 0.06)
                for side in [-1, 1]:
                    ex = cx + side * int(cs * 0.06)
                    draw.ellipse(
                        [
                            ex - ear_w,
                            head_y - int(cs * 0.04),
                            ex + ear_w,
                            head_y - int(cs * 0.04) + ear_h,
                        ],
                        fill=(200, 170, 90, 255),
                    )

                # Eyes (calm, half-closed)
                eye_y = head_y - int(cs * 0.01)
                eye_gap = int(cs * 0.03)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - int(cs * 0.015),
                            eye_y - int(cs * 0.008),
                            ecx + int(cs * 0.015),
                            eye_y + int(cs * 0.008),
                        ],
                        fill=(20, 20, 20, 255),
                    )

                # Small calm smile
                draw.arc(
                    [
                        cx - int(cs * 0.025),
                        head_y + int(cs * 0.015),
                        cx + int(cs * 0.025),
                        head_y + int(cs * 0.035),
                    ],
                    start=0,
                    end=180,
                    fill=(60, 50, 30, 255),
                    width=max(1, int(cs * 0.004)),
                )

                # Hat (small top hat)
                hat_y = head_y - head_r
                hat_w = int(cs * 0.05)
                hat_h = int(cs * 0.04)
                draw.rectangle(
                    [cx - hat_w, hat_y - hat_h, cx + hat_w, hat_y],
                    fill=(60, 50, 40, 255),
                )
                draw.rectangle(
                    [
                        cx - int(hat_w * 1.3),
                        hat_y - int(cs * 0.005),
                        cx + int(hat_w * 1.3),
                        hat_y + int(cs * 0.005),
                    ],
                    fill=(60, 50, 40, 255),
                )

                # Quotes
                quotes = [
                    "This is fine.",
                    "Everything is\nfine.",
                    "I'm okay with\nthe events.",
                    "This is fine.\n*sips coffee*",
                    "Production is\non fire.\nThis is fine.",
                    "404 errors\neverywhere.\nTotally fine.",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.022))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.15), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(255, 240, 180, 220),
                    font=q_font,
                )

            elif style == "trollface":
                # ── Trollface ─────────────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.01)
                cy = int(cs * 0.45) - bounce

                # Light grey bg
                draw.rectangle([0, 0, cs, cs], fill=(30, 30, 35, 245))

                # Big head shape (wide, slightly squished)
                head_w = int(cs * 0.16)
                head_h = int(cs * 0.14)
                draw.ellipse(
                    [cx - head_w, cy - head_h, cx + head_w, cy + head_h],
                    fill=(255, 255, 255, 255),
                    outline=(180, 180, 180, 255),
                    width=max(1, int(cs * 0.004)),
                )

                # Exaggerated grin (huge, mocking)
                grin_w = int(cs * 0.14)
                grin_y = cy + int(cs * 0.02)
                draw.arc(
                    [
                        cx - grin_w,
                        grin_y - int(cs * 0.03),
                        cx + grin_w,
                        grin_y + int(cs * 0.08),
                    ],
                    start=0,
                    end=180,
                    fill=(80, 80, 80, 255),
                    width=max(2, int(cs * 0.006)),
                )

                # Extended lip corners going up
                for side in [-1, 1]:
                    lip_x = cx + grin_w * side
                    draw.arc(
                        [
                            lip_x - int(cs * 0.02),
                            grin_y - int(cs * 0.04),
                            lip_x + int(cs * 0.02),
                            grin_y,
                        ],
                        start=180 if side == 1 else 0,
                        end=360 if side == 1 else 180,
                        fill=(80, 80, 80, 255),
                        width=max(1, int(cs * 0.004)),
                    )

                # Squinty mischievous eyes
                eye_y = cy - int(cs * 0.04)
                eye_gap = int(cs * 0.06)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    # Narrowed eye shape
                    draw.ellipse(
                        [
                            ecx - int(cs * 0.025),
                            eye_y - int(cs * 0.01),
                            ecx + int(cs * 0.025),
                            eye_y + int(cs * 0.015),
                        ],
                        fill=(20, 20, 20, 255),
                    )
                    # Glint
                    pr = max(1, int(cs * 0.005))
                    draw.ellipse(
                        [
                            ecx + side * int(cs * 0.008) - pr,
                            eye_y - pr,
                            ecx + side * int(cs * 0.008) + pr,
                            eye_y + pr,
                        ],
                        fill=(255, 255, 255, 255),
                    )

                # Raised eyebrows (smug)
                for side in [-1, 1]:
                    bx = cx + eye_gap * side
                    draw.arc(
                        [
                            bx - int(cs * 0.03),
                            eye_y - int(cs * 0.06),
                            bx + int(cs * 0.03),
                            eye_y - int(cs * 0.02),
                        ],
                        start=200,
                        end=340,
                        fill=(120, 120, 120, 255),
                        width=max(1, int(cs * 0.004)),
                    )

                # Chin bump
                chin_y = cy + int(cs * 0.1)
                draw.ellipse(
                    [
                        cx - int(cs * 0.04),
                        chin_y,
                        cx + int(cs * 0.04),
                        chin_y + int(cs * 0.04),
                    ],
                    fill=(250, 250, 250, 255),
                )

                # Quotes
                quotes = [
                    "Problem?",
                    "U mad bro?",
                    "Trolled.\nGet rekt.",
                    "Your test\npassed…\nOR DID IT?",
                    "I moved your\nbutton 1px\nto the left.",
                    "git push\n--force\n*grins*",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.023))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.15), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(200, 200, 210, 200),
                    font=q_font,
                )

            elif style == "no_idea_dog":
                # ── "I Have No Idea What I'm Doing" dog ───────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.007)
                cy = int(cs * 0.42) - bounce

                # Lab/office bg
                draw.rectangle([0, 0, cs, cs], fill=(35, 40, 50, 245))
                # Desk
                desk_y = int(cs * 0.65)
                draw.rectangle(
                    [int(cs * 0.1), desk_y, int(cs * 0.9), desk_y + int(cs * 0.04)],
                    fill=(120, 80, 50, 255),
                )

                # Small laptop on desk
                lap_x = cx - int(cs * 0.06)
                lap_w = int(cs * 0.12)
                lap_h = int(cs * 0.08)
                draw.rectangle(
                    [lap_x, desk_y - lap_h, lap_x + lap_w, desk_y],
                    fill=(60, 60, 70, 255),
                    outline=(80, 80, 90, 255),
                    width=max(1, int(cs * 0.002)),
                )
                # Screen glow
                draw.rectangle(
                    [
                        lap_x + int(cs * 0.01),
                        desk_y - lap_h + int(cs * 0.01),
                        lap_x + lap_w - int(cs * 0.01),
                        desk_y - int(cs * 0.01),
                    ],
                    fill=(100, 140, 200, 200),
                )

                # Golden retriever head
                head_r = int(cs * 0.1)
                head_y = cy - int(cs * 0.06)
                draw.ellipse(
                    [cx - head_r, head_y - head_r, cx + head_r, head_y + head_r],
                    fill=(220, 180, 100, 255),
                )

                # Ears (floppy golden)
                ear_w = int(cs * 0.04)
                ear_h = int(cs * 0.08)
                for side in [-1, 1]:
                    ex = cx + side * int(cs * 0.09)
                    draw.ellipse(
                        [
                            ex - ear_w,
                            head_y - int(cs * 0.02),
                            ex + ear_w,
                            head_y + ear_h,
                        ],
                        fill=(190, 150, 70, 255),
                    )

                # Big friendly eyes (confused)
                eye_r = int(cs * 0.025)
                eye_y = head_y - int(cs * 0.01)
                eye_gap = int(cs * 0.04)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r],
                        fill=(255, 255, 255, 255),
                    )
                    pr = max(2, eye_r // 2)
                    # Looking slightly up
                    draw.ellipse(
                        [
                            ecx - pr,
                            eye_y - pr - int(cs * 0.005),
                            ecx + pr,
                            eye_y + pr - int(cs * 0.005),
                        ],
                        fill=(50, 30, 10, 255),
                    )

                # Nose (black dot)
                nose_r = int(cs * 0.015)
                nose_y = head_y + int(cs * 0.03)
                draw.ellipse(
                    [cx - nose_r, nose_y - nose_r, cx + nose_r, nose_y + nose_r],
                    fill=(30, 20, 15, 255),
                )

                # Tongue out (derpy)
                tongue_w = int(cs * 0.02)
                tongue_h = int(cs * 0.03)
                draw.ellipse(
                    [
                        cx - tongue_w,
                        nose_y + int(cs * 0.01),
                        cx + tongue_w,
                        nose_y + int(cs * 0.01) + tongue_h,
                    ],
                    fill=(220, 100, 100, 255),
                )

                # Quotes
                quotes = [
                    "I have no idea\nwhat I'm doing.",
                    "Is this… code?\nI'm a dog.",
                    "git commit -m\n'no idea what\nthis does'",
                    "Looks like it\nworks… I think?",
                    "*types randomly*\nSomething\nhappened!",
                    "They gave me\nadmin access.\nI'm a dog.",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.022))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.12), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(200, 210, 230, 200),
                    font=q_font,
                )

            elif style == "surprised_pikachu":
                # ── Surprised Pikachu ─────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.012)
                cy = int(cs * 0.45) - bounce

                # Dark bg
                draw.rectangle([0, 0, cs, cs], fill=(30, 25, 40, 245))

                # Yellow body
                body_w = int(cs * 0.13)
                body_h = int(cs * 0.15)
                draw.ellipse(
                    [cx - body_w, cy - body_h, cx + body_w, cy + body_h],
                    fill=(255, 220, 50, 255),
                )

                # Pointed ears
                ear_h = int(cs * 0.1)
                ear_w = int(cs * 0.03)
                for side in [-1, 1]:
                    bx = cx + side * int(cs * 0.08)
                    by = cy - int(cs * 0.12)
                    draw.polygon(
                        [
                            (bx, by),
                            (bx + side * ear_w, by - ear_h),
                            (bx + side * int(ear_w * 0.3), by),
                        ],
                        fill=(255, 220, 50, 255),
                    )
                    # Black ear tips
                    draw.polygon(
                        [
                            (bx + side * int(ear_w * 0.5), by - int(ear_h * 0.5)),
                            (bx + side * ear_w, by - ear_h),
                            (bx + side * int(ear_w * 0.8), by - int(ear_h * 0.6)),
                        ],
                        fill=(40, 30, 20, 255),
                    )

                # Red cheeks
                cheek_r = int(cs * 0.025)
                cheek_y = cy + int(cs * 0.01)
                for side in [-1, 1]:
                    draw.ellipse(
                        [
                            cx + side * int(cs * 0.08) - cheek_r,
                            cheek_y - cheek_r,
                            cx + side * int(cs * 0.08) + cheek_r,
                            cheek_y + cheek_r,
                        ],
                        fill=(220, 50, 50, 200),
                    )

                # Big surprised eyes (wide open)
                eye_r = int(cs * 0.03)
                eye_y = cy - int(cs * 0.04)
                eye_gap = int(cs * 0.045)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r, ecx + eye_r, eye_y + eye_r],
                        fill=(255, 255, 255, 255),
                    )
                    pr = max(2, int(eye_r * 0.5))
                    # Tiny pupils (shock)
                    draw.ellipse(
                        [ecx - pr, eye_y - pr, ecx + pr, eye_y + pr],
                        fill=(20, 20, 30, 255),
                    )

                # Open mouth (big O shape — surprised!)
                mouth_r = int(cs * 0.03 + amp * cs * 0.01)
                mouth_y = cy + int(cs * 0.04)
                draw.ellipse(
                    [cx - mouth_r, mouth_y - mouth_r, cx + mouth_r, mouth_y + mouth_r],
                    fill=(180, 60, 60, 255),
                    outline=(120, 40, 40, 255),
                    width=max(1, int(cs * 0.003)),
                )

                # Lightning bolt near body (animated)
                bolt_alpha = int(60 + amp * 150)
                bolt_x = cx + int(cs * 0.16)
                bolt_y = cy - int(cs * 0.05)
                bolt_sz = int(cs * 0.04)
                draw.polygon(
                    [
                        (bolt_x, bolt_y - bolt_sz),
                        (bolt_x + int(bolt_sz * 0.4), bolt_y),
                        (bolt_x - int(bolt_sz * 0.2), bolt_y + int(bolt_sz * 0.3)),
                        (bolt_x, bolt_y + bolt_sz),
                    ],
                    fill=(255, 255, 100, bolt_alpha),
                )

                # Quotes
                quotes = [
                    ":O\n...wait, what?",
                    "You shipped\nWITHOUT tests?!",
                    "*surprised\nPikachu face*",
                    "It works on the\nfirst try?!",
                    "No merge\nconflicts?!\n:O",
                    "Wait… the bug\nfixed itself?!",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.023))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.15), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(255, 240, 100, 200),
                    font=q_font,
                )

            elif style == "distracted_bf":
                # ── Distracted Boyfriend ──────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.008)
                cy = int(cs * 0.45) - bounce

                # Street bg
                draw.rectangle([0, 0, cs, cs], fill=(45, 40, 50, 245))

                # Male figure (head + torso) — looking back
                head_r = int(cs * 0.06)
                head_y = cy - int(cs * 0.08)
                # Head turned to the right
                draw.ellipse(
                    [cx - head_r, head_y - head_r, cx + head_r, head_y + head_r],
                    fill=(220, 180, 150, 255),
                )

                # Hair (dark, messy)
                draw.ellipse(
                    [
                        cx - int(head_r * 1.1),
                        head_y - int(head_r * 1.2),
                        cx + int(head_r * 0.8),
                        head_y - int(head_r * 0.3),
                    ],
                    fill=(50, 35, 25, 255),
                )

                # Eyes looking away (sideways glance)
                eye_y = head_y - int(cs * 0.005)
                eye_gap = int(cs * 0.025)
                for side_idx, side in enumerate([-1, 1]):
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [
                            ecx - int(cs * 0.012),
                            eye_y - int(cs * 0.01),
                            ecx + int(cs * 0.012),
                            eye_y + int(cs * 0.01),
                        ],
                        fill=(255, 255, 255, 255),
                    )
                    pr = max(1, int(cs * 0.006))
                    # Both eyes looking right (distracted!)
                    draw.ellipse(
                        [
                            ecx + int(cs * 0.005) - pr,
                            eye_y - pr,
                            ecx + int(cs * 0.005) + pr,
                            eye_y + pr,
                        ],
                        fill=(40, 30, 20, 255),
                    )

                # Raised eyebrow
                draw.arc(
                    [
                        cx + eye_gap - int(cs * 0.02),
                        eye_y - int(cs * 0.03),
                        cx + eye_gap + int(cs * 0.02),
                        eye_y - int(cs * 0.01),
                    ],
                    start=200,
                    end=340,
                    fill=(80, 60, 40, 255),
                    width=max(1, int(cs * 0.004)),
                )

                # Slight open mouth (interest)
                draw.ellipse(
                    [
                        cx - int(cs * 0.01),
                        head_y + int(cs * 0.025),
                        cx + int(cs * 0.01),
                        head_y + int(cs * 0.035),
                    ],
                    fill=(180, 100, 90, 255),
                )

                # Torso (red shirt)
                draw.rectangle(
                    [cx - int(cs * 0.07), cy, cx + int(cs * 0.07), cy + int(cs * 0.15)],
                    fill=(180, 40, 40, 255),
                )

                # Arrow pointing right (distraction direction)
                arr_y = cy - int(cs * 0.15)
                arr_x = cx + int(cs * 0.15)
                arr_sz = int(cs * 0.03)
                arr_alpha = int(120 + amp * 100)
                draw.polygon(
                    [
                        (arr_x, arr_y - arr_sz),
                        (arr_x + arr_sz, arr_y),
                        (arr_x, arr_y + arr_sz),
                    ],
                    fill=(255, 100, 100, arr_alpha),
                )
                draw.rectangle(
                    [
                        arr_x - arr_sz,
                        arr_y - int(arr_sz * 0.3),
                        arr_x,
                        arr_y + int(arr_sz * 0.3),
                    ],
                    fill=(255, 100, 100, arr_alpha),
                )

                # Quotes
                quotes = [
                    "*looks at new\nframework*",
                    "But what if\nwe rewrote it\nin Rust?",
                    "Current stack:\n'meh'\nNew stack:\n'SHINY!'",
                    "My backlog vs\nthis cool new\nlibrary…",
                    "*distracted by\nHacker News*",
                    "Deadlines?\nBut look at\nthis side\nproject!",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.022))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.12), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(255, 180, 180, 200),
                    font=q_font,
                )

            elif style == "success_kid":
                # ── Success Kid ───────────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.012)
                cy = int(cs * 0.45) - bounce

                # Victory green bg
                draw.rectangle([0, 0, cs, cs], fill=(20, 50, 30, 245))

                # Radiating success lines
                line_alpha = int(40 + amp * 80)
                for angle_deg in range(0, 360, 30):
                    rad = math.radians(angle_deg + i * 0.5)
                    lx1 = cx + int(math.cos(rad) * cs * 0.2)
                    ly1 = cy + int(math.sin(rad) * cs * 0.2)
                    lx2 = cx + int(math.cos(rad) * cs * 0.4)
                    ly2 = cy + int(math.sin(rad) * cs * 0.4)
                    draw.line(
                        [(lx1, ly1), (lx2, ly2)],
                        fill=(255, 255, 100, line_alpha),
                        width=max(1, int(cs * 0.003)),
                    )

                # Kid figure (stylized — round head + body)
                head_r = int(cs * 0.08)
                head_y = cy - int(cs * 0.06)
                draw.ellipse(
                    [cx - head_r, head_y - head_r, cx + head_r, head_y + head_r],
                    fill=(230, 190, 150, 255),
                )

                # Determined eyes (squinting with determination)
                eye_y = head_y - int(cs * 0.01)
                eye_gap = int(cs * 0.03)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.line(
                        [
                            (ecx - int(cs * 0.015), eye_y),
                            (ecx + int(cs * 0.015), eye_y - int(cs * 0.008)),
                        ],
                        fill=(40, 30, 20, 255),
                        width=max(1, int(cs * 0.004)),
                    )

                # Clenched mouth (determined)
                draw.line(
                    [
                        (cx - int(cs * 0.02), head_y + int(cs * 0.03)),
                        (cx + int(cs * 0.02), head_y + int(cs * 0.025)),
                    ],
                    fill=(60, 40, 30, 255),
                    width=max(1, int(cs * 0.004)),
                )

                # Fist pump! (arm going up)
                fist_x = cx - int(cs * 0.12)
                fist_y = cy - int(cs * 0.15) - bounce
                fist_r = int(cs * 0.03)
                # Arm
                draw.line(
                    [(cx - int(cs * 0.06), cy), (fist_x, fist_y + fist_r)],
                    fill=(230, 190, 150, 255),
                    width=max(2, int(cs * 0.01)),
                )
                # Fist
                draw.ellipse(
                    [
                        fist_x - fist_r,
                        fist_y - fist_r,
                        fist_x + fist_r,
                        fist_y + fist_r,
                    ],
                    fill=(230, 190, 150, 255),
                )

                # Green shirt/body
                draw.rectangle(
                    [cx - int(cs * 0.06), cy, cx + int(cs * 0.06), cy + int(cs * 0.12)],
                    fill=(50, 140, 80, 255),
                )

                # Quotes
                quotes = [
                    "YESSS!\nIt compiled!",
                    "All tests\npassing.\nFIST PUMP!",
                    "Deployed to\nprod. No\nrollback!",
                    "Zero bugs\nfound in\ncode review!",
                    "Merged on\nfirst attempt.\nNailed it!",
                    "Friday deploy\nsurvived the\nweekend!",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.022))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.15), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(150, 255, 150, 200),
                    font=q_font,
                )

            elif style == "expanding_brain":
                # ── Expanding Brain (final luminous stage) ────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.01)
                cy = int(cs * 0.43) - bounce

                # Cosmic dark bg
                draw.rectangle([0, 0, cs, cs], fill=(10, 5, 25, 245))

                # Stars
                for s in range(15):
                    sx = int((s * 97 + i) % cs)
                    sy = int((s * 53) % int(cs * 0.7))
                    sr = max(1, int(cs * 0.003))
                    star_a = int(100 + 80 * math.sin(i * 0.1 + s))
                    draw.ellipse(
                        [sx - sr, sy - sr, sx + sr, sy + sr],
                        fill=(255, 255, 255, star_a),
                    )

                # Glowing head aura (expanding rings)
                head_r = int(cs * 0.09)
                glow_intensity = int(amp * 120)
                for ring in range(5, 0, -1):
                    ring_r = head_r + ring * int(cs * 0.03)
                    ring_alpha = max(10, glow_intensity // ring)
                    hue_shift = (ring * 40 + i * 3) % 360
                    r = int(180 + 75 * math.sin(math.radians(hue_shift)))
                    g = int(180 + 75 * math.sin(math.radians(hue_shift + 120)))
                    b = int(180 + 75 * math.sin(math.radians(hue_shift + 240)))
                    draw.ellipse(
                        [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
                        fill=(r, g, b, ring_alpha),
                    )

                # Head (silhouette with glow)
                draw.ellipse(
                    [cx - head_r, cy - head_r, cx + head_r, cy + head_r],
                    fill=(200, 180, 255, 255),
                )

                # Glowing eyes (beams of light!)
                eye_y = cy - int(cs * 0.02)
                eye_gap = int(cs * 0.035)
                beam_len = int(cs * 0.08 + amp * cs * 0.04)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    # Eye glow
                    draw.ellipse(
                        [
                            ecx - int(cs * 0.015),
                            eye_y - int(cs * 0.012),
                            ecx + int(cs * 0.015),
                            eye_y + int(cs * 0.012),
                        ],
                        fill=(255, 255, 255, 255),
                    )
                    # Light beam
                    beam_alpha = int(100 + amp * 150)
                    draw.polygon(
                        [
                            (ecx - int(cs * 0.01), eye_y),
                            (ecx + side * beam_len, eye_y - int(cs * 0.02)),
                            (ecx + side * beam_len, eye_y + int(cs * 0.02)),
                            (ecx + int(cs * 0.01), eye_y),
                        ],
                        fill=(255, 255, 200, min(255, beam_alpha)),
                    )

                # Small enlightened smile
                draw.arc(
                    [
                        cx - int(cs * 0.025),
                        cy + int(cs * 0.03),
                        cx + int(cs * 0.025),
                        cy + int(cs * 0.05),
                    ],
                    start=0,
                    end=180,
                    fill=(255, 255, 255, 200),
                    width=max(1, int(cs * 0.004)),
                )

                # Energy particles
                for p in range(8):
                    angle = (p * math.pi / 4) + i * 0.05
                    dist = int(cs * 0.2 + math.sin(i * 0.08 + p) * cs * 0.04)
                    px = cx + int(math.cos(angle) * dist)
                    py = cy + int(math.sin(angle) * dist)
                    p_r = max(1, int(cs * 0.005 + amp * cs * 0.003))
                    draw.ellipse(
                        [px - p_r, py - p_r, px + p_r, py + p_r],
                        fill=(255, 255, 200, int(150 + amp * 100)),
                    )

                # Quotes
                quotes = [
                    "Use if/else.\nUse switch.\nUse polymorphism.\nUSE MONADS.",
                    "I have\ntranscended\nthe codebase.",
                    "Your framework\nis just a\ncosmic illusion.",
                    "I see the\nMatrix now.\nIt's all JSON.",
                    "Microservices?\nI AM the\nservice.",
                    "The real bug\nwas inside us\nall along.",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.02))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.12), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(220, 200, 255, 200),
                    font=q_font,
                )

            elif style == "doge":
                # ── Doge (Shiba Inu) ──────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.008)
                cy = int(cs * 0.45) - bounce

                # Warm bg
                draw.rectangle([0, 0, cs, cs], fill=(40, 35, 25, 245))

                # Shiba body (tan)
                body_w = int(cs * 0.12)
                body_h = int(cs * 0.14)
                draw.ellipse(
                    [cx - body_w, cy - body_h, cx + body_w, cy + body_h],
                    fill=(218, 165, 80, 255),
                )

                # White chest patch
                draw.ellipse(
                    [
                        cx - int(cs * 0.06),
                        cy + int(cs * 0.02),
                        cx + int(cs * 0.06),
                        cy + int(cs * 0.12),
                    ],
                    fill=(250, 240, 220, 255),
                )

                # Head (slightly tilted)
                head_r = int(cs * 0.09)
                head_y = cy - int(cs * 0.1)
                draw.ellipse(
                    [cx - head_r, head_y - head_r, cx + head_r, head_y + head_r],
                    fill=(218, 165, 80, 255),
                )

                # White face mask
                draw.ellipse(
                    [
                        cx - int(cs * 0.06),
                        head_y - int(cs * 0.04),
                        cx + int(cs * 0.06),
                        head_y + int(cs * 0.07),
                    ],
                    fill=(250, 240, 220, 255),
                )

                # Pointed ears
                ear_h = int(cs * 0.06)
                for side in [-1, 1]:
                    bx = cx + side * int(cs * 0.06)
                    by = head_y - int(cs * 0.08)
                    draw.polygon(
                        [
                            (bx - int(cs * 0.025), by + ear_h),
                            (bx, by),
                            (bx + int(cs * 0.025), by + ear_h),
                        ],
                        fill=(218, 165, 80, 255),
                    )

                # Squinty happy eyes
                eye_y = head_y - int(cs * 0.015)
                eye_gap = int(cs * 0.035)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.arc(
                        [
                            ecx - int(cs * 0.015),
                            eye_y - int(cs * 0.008),
                            ecx + int(cs * 0.015),
                            eye_y + int(cs * 0.008),
                        ],
                        start=200,
                        end=340,
                        fill=(30, 20, 10, 255),
                        width=max(1, int(cs * 0.004)),
                    )

                # Nose
                nose_r = int(cs * 0.012)
                nose_y = head_y + int(cs * 0.025)
                draw.ellipse(
                    [cx - nose_r, nose_y - nose_r, cx + nose_r, nose_y + nose_r],
                    fill=(30, 20, 15, 255),
                )

                # Mouth — slight smile
                draw.arc(
                    [
                        cx - int(cs * 0.02),
                        nose_y + int(cs * 0.005),
                        cx + int(cs * 0.02),
                        nose_y + int(cs * 0.02),
                    ],
                    start=0,
                    end=180,
                    fill=(30, 20, 10, 255),
                    width=max(1, int(cs * 0.003)),
                )

                # Comic Sans–style floating words (the doge meme!)
                doge_words = [
                    ("such", (255, 100, 100)),
                    ("wow", (100, 255, 100)),
                    ("much", (100, 100, 255)),
                    ("very", (255, 255, 100)),
                    ("amaze", (255, 100, 255)),
                    ("so", (100, 255, 255)),
                ]
                try:
                    word_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.025))
                    )
                except OSError:
                    word_font = ImageFont.load_default()

                for w_idx, (word, color) in enumerate(doge_words):
                    wx = int((w_idx * cs * 0.16 + i * 1.5) % (cs * 0.7)) + int(cs * 0.05)
                    wy = int((w_idx * cs * 0.12 + 20) % (cs * 0.5)) + int(cs * 0.05)
                    w_alpha = int(120 + 80 * math.sin(i * 0.1 + w_idx))
                    draw.text(
                        (wx, wy),
                        word,
                        fill=(*color, w_alpha),
                        font=word_font,
                    )

                # Main context words
                context_words = ["code", "deploy", "API", "crypto", "debug", "PR"]
                c_word = context_words[(i // 50) % len(context_words)]
                draw.text(
                    (int(cs * 0.3), int(cs * 0.85)),
                    f"such {c_word}. much wow.",
                    fill=(255, 255, 200, 200),
                    font=word_font,
                )

            elif style == "wiki_globe":
                # ── Wikipedia Globe with a face ───────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2
                bounce = int(amp * cs * 0.006)
                cy = int(cs * 0.44) - bounce

                # Neutral wiki bg
                draw.rectangle([0, 0, cs, cs], fill=(35, 35, 40, 245))

                # Globe (sphere effect)
                globe_r = int(cs * 0.13)

                # Globe base circle
                draw.ellipse(
                    [cx - globe_r, cy - globe_r, cx + globe_r, cy + globe_r],
                    fill=(200, 200, 210, 255),
                    outline=(160, 160, 170, 255),
                    width=max(1, int(cs * 0.003)),
                )

                # Puzzle piece lines (horizontal)
                for lat in range(-2, 3):
                    ly = cy + lat * int(globe_r * 0.35)
                    half_w = int(math.sqrt(max(0, globe_r**2 - (lat * globe_r * 0.35) ** 2)))
                    draw.line(
                        [(cx - half_w, ly), (cx + half_w, ly)],
                        fill=(160, 160, 170, 150),
                        width=max(1, int(cs * 0.002)),
                    )

                # Puzzle piece lines (vertical, curved)
                for lon in range(-2, 3):
                    lx = cx + lon * int(globe_r * 0.3)
                    for y_step in range(-globe_r, globe_r, int(cs * 0.01)):
                        y1 = cy + y_step
                        y2 = cy + y_step + int(cs * 0.01)
                        dist = abs(lon * globe_r * 0.3)
                        if dist < globe_r:
                            draw.line(
                                [(lx, y1), (lx, min(y2, cy + globe_r))],
                                fill=(160, 160, 170, 100),
                                width=max(1, int(cs * 0.002)),
                            )

                # Missing puzzle piece at top (Wikipedia style)
                miss_x = cx + int(cs * 0.03)
                miss_y = cy - int(globe_r * 0.6)
                miss_sz = int(cs * 0.035)
                draw.rectangle(
                    [miss_x, miss_y, miss_x + miss_sz, miss_y + miss_sz],
                    fill=(35, 35, 40, 255),
                )

                # Face on the globe
                # Eyes (scholarly, with glasses)
                eye_y = cy - int(cs * 0.02)
                eye_gap = int(cs * 0.04)
                glass_r = int(cs * 0.022)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    # Glasses frames
                    draw.ellipse(
                        [
                            ecx - glass_r,
                            eye_y - glass_r,
                            ecx + glass_r,
                            eye_y + glass_r,
                        ],
                        outline=(80, 80, 90, 255),
                        width=max(1, int(cs * 0.003)),
                    )
                    # Eyes inside
                    pr = max(2, int(cs * 0.008))
                    draw.ellipse(
                        [ecx - pr, eye_y - pr, ecx + pr, eye_y + pr],
                        fill=(40, 40, 50, 255),
                    )
                # Bridge of glasses
                draw.line(
                    [(cx - eye_gap + glass_r, eye_y), (cx + eye_gap - glass_r, eye_y)],
                    fill=(80, 80, 90, 255),
                    width=max(1, int(cs * 0.003)),
                )

                # Slight frown (scholarly)
                draw.arc(
                    [
                        cx - int(cs * 0.025),
                        cy + int(cs * 0.03),
                        cx + int(cs * 0.025),
                        cy + int(cs * 0.05),
                    ],
                    start=200,
                    end=340,
                    fill=(120, 120, 130, 255),
                    width=max(1, int(cs * 0.004)),
                )

                # "W" logo below globe
                w_y = cy + globe_r + int(cs * 0.02)
                try:
                    w_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(10, int(cs * 0.03))
                    )
                except OSError:
                    w_font = ImageFont.load_default()
                draw.text(
                    (cx - int(cs * 0.015), w_y),
                    "W",
                    fill=(180, 180, 190, 200),
                    font=w_font,
                )

                # Quotes
                quotes = [
                    "[citation needed]",
                    "According to\nmultiple sources\n[who?]…",
                    "This section\nneeds expansion.\nYou can help.",
                    "Disambiguation:\nDid you mean\nsomething else?",
                    "This article is\na stub. Please\nhelp expand it.",
                    "Neutrality of\nthis section is\ndisputed.",
                ]
                q_idx = (i // 40) % len(quotes)
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", max(8, int(cs * 0.021))
                    )
                except OSError:
                    q_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.12), int(cs * 0.82)),
                    quotes[q_idx],
                    fill=(200, 200, 210, 200),
                    font=q_font,
                )

            # Apply background shape mask (circular/rounded)
            if background_shape in ("circle", "rounded"):
                mask = Image.new("L", (canvas_size, canvas_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                if background_shape == "circle":
                    mask_draw.ellipse([0, 0, canvas_size - 1, canvas_size - 1], fill=255)
                else:  # rounded
                    radius = canvas_size // 5
                    mask_draw.rounded_rectangle(
                        [0, 0, canvas_size - 1, canvas_size - 1],
                        radius=radius,
                        fill=255,
                    )
                # Composite: keep only pixels inside the mask
                alpha = canvas.getchannel("A")
                alpha = ImageChops.multiply(alpha, mask)
                canvas.putalpha(alpha)

            canvas.save(frames_dir / f"frame_{i:05d}.png")

        # Encode frames to video with ffmpeg (VP9 + alpha or H.264)
        out_path = self._output_dir / f"avatar_{self._counter:03d}.webm"
        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "frame_%05d.png"),
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuva420p",  # alpha support
            "-b:v",
            "1M",
            "-an",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("ffmpeg avatar encode failed: %s", result.stderr[-300:])
            # Fallback: H.264 without alpha
            out_path = out_path.with_suffix(".mp4")
            cmd_fallback = [
                "ffmpeg",
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(frames_dir / "frame_%05d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "23",
                "-an",
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
    def _extract_amplitudes(audio: AudioSegment, num_frames: int) -> list[float]:
        """Extract normalized amplitude envelope from audio, one value per frame."""
        samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
        if audio.channels > 1:
            samples = samples[:: audio.channels]  # mono

        chunk_size = max(1, len(samples) // num_frames)
        amplitudes: list[float] = []
        for i in range(num_frames):
            start = i * chunk_size
            end = min(start + chunk_size, len(samples))
            chunk = samples[start:end]
            if len(chunk) == 0:
                amplitudes.append(0.0)
            else:
                rms = np.sqrt(np.mean(chunk**2))
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
    def _load_avatar(image: str | None, size: int) -> _PILImage:
        """Load avatar image from path, URL, or generate a default one."""
        from PIL import Image, ImageDraw, ImageFont

        if image and Path(image).exists():
            img = Image.open(image).convert("RGBA")
            img = img.resize((size, size), Image.LANCZOS)
            return img

        if image and image.startswith(("http://", "https://")):
            import io
            import urllib.request

            cache_dir = Path.home() / ".cache" / "demodsl" / "avatars"
            cache_dir.mkdir(parents=True, exist_ok=True)
            url_hash = hashlib.sha256(image.encode()).hexdigest()[:16]
            cached = cache_dir / f"{url_hash}.png"

            if cached.exists():
                img = Image.open(cached).convert("RGBA")
                img = img.resize((size, size), Image.LANCZOS)
                return img

            logger.info("Downloading avatar image from %s", image)
            req = urllib.request.Request(image, headers={"User-Agent": "demodsl/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                from demodsl.validators import read_with_size_limit

                data = read_with_size_limit(resp, max_bytes=20 * 1024 * 1024)  # 20 MB
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            img = img.resize((size, size), Image.LANCZOS)
            img.save(cached, "PNG")
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
        except OSError:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), char, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((size - tw) / 2, (size - th) / 2 - bbox[1]),
            char,
            fill=(255, 255, 255, 255),
            font=font,
        )
        return img

    @staticmethod
    def _apply_shape(img: _PILImage, shape: str, size: int) -> _PILImage:
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
        self,
        output_dir: Path | None = None,
        api_key: str | None = None,
    ) -> None:
        raw_key = api_key or os.environ.get("D_ID_API_KEY", "")
        # Support ${ENV_VAR} syntax
        if raw_key.startswith("${") and raw_key.endswith("}"):
            raw_key = os.environ.get(raw_key[2:-1], "")
        self._api_key = raw_key
        if not self._api_key:
            raise OSError("D_ID_API_KEY not set. Set the env var or pass api_key in avatar config.")
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
        from demodsl.validators import read_with_size_limit

        with httpx.stream("GET", result_url, timeout=120) as stream:
            stream.raise_for_status()
            data = read_with_size_limit(stream, max_bytes=200 * 1024 * 1024)  # 200 MB
        out_path.write_bytes(data)

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
        self,
        output_dir: Path | None = None,
        api_key: str | None = None,
    ) -> None:
        raw_key = api_key or os.environ.get("HEYGEN_API_KEY", "")
        if raw_key.startswith("${") and raw_key.endswith("}"):
            raw_key = os.environ.get(raw_key[2:-1], "")
        self._api_key = raw_key
        if not self._api_key:
            raise OSError(
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
        from demodsl.validators import read_with_size_limit

        with httpx.stream("GET", result_url, timeout=120) as stream:
            stream.raise_for_status()
            data = read_with_size_limit(stream, max_bytes=200 * 1024 * 1024)  # 200 MB
        out_path.write_bytes(data)

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
                        "talking_photo_url": image
                        if image and image.startswith("http")
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
        self._sadtalker_path = sadtalker_path or os.environ.get("SADTALKER_PATH", "sadtalker")
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
                audio_path,
                image=image,
                size=size,
                style=style,
                shape=shape,
                narration_text=narration_text,
            )

        out_path = self._output_dir / f"avatar_sadtalker_{self._counter:03d}.mp4"

        cmd = [
            "python",
            "-m",
            "sadtalker",
            "--driven_audio",
            str(audio_path),
            "--source_image",
            str(image),
            "--result_dir",
            str(self._output_dir),
            "--enhancer",
            "gfpgan",
        ]
        logger.info("Running SadTalker: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            logger.warning("SadTalker failed: %s", result.stderr[-300:])
            logger.info("Falling back to animated avatar")
            fallback = AnimatedAvatarProvider(output_dir=self._output_dir)
            return fallback.generate(
                audio_path,
                image=image,
                size=size,
                style=style,
                shape=shape,
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
