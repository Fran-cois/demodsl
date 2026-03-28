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

            elif style == "pacman":
                # ── Pac-Man arcade ────────────────────────────────────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size

                # Black arcade background
                draw.rounded_rectangle(
                    [2, 2, cs - 3, cs - 3], radius=10,
                    fill=(0, 0, 20, 220),
                )

                # Pac-Man: mouth opens/closes with amplitude
                pac_r = int(cs * 0.18)
                pac_cx = int(cs * 0.32)
                pac_cy = cs // 2
                # Mouth angle: 5° (closed) to 45° (open)
                mouth_angle = 5 + int(amp * 40)
                draw.pieslice(
                    [pac_cx - pac_r, pac_cy - pac_r,
                     pac_cx + pac_r, pac_cy + pac_r],
                    start=mouth_angle, end=360 - mouth_angle,
                    fill=(255, 255, 0, 255),
                )
                # Pac-Man eye
                eye_r = max(2, int(pac_r * 0.15))
                eye_x = pac_cx + int(pac_r * 0.2)
                eye_y = pac_cy - int(pac_r * 0.4)
                draw.ellipse(
                    [eye_x - eye_r, eye_y - eye_r,
                     eye_x + eye_r, eye_y + eye_r],
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
                    (255, 0, 0, 230), (255, 184, 255, 230),
                    (0, 255, 255, 230), (255, 184, 82, 230),
                ]
                gc = ghost_colors[i % len(ghost_colors)]
                ghost_r = int(cs * 0.13)
                ghost_cx = int(cs * 0.78 + math.sin(i * 0.15) * cs * 0.06)
                ghost_cy = int(cs // 2 + math.cos(i * 0.2) * cs * 0.04)
                # Ghost body: top half circle + rectangle bottom
                draw.ellipse(
                    [ghost_cx - ghost_r, ghost_cy - ghost_r,
                     ghost_cx + ghost_r, ghost_cy + int(ghost_r * 0.3)],
                    fill=gc,
                )
                draw.rectangle(
                    [ghost_cx - ghost_r, ghost_cy,
                     ghost_cx + ghost_r, ghost_cy + ghost_r],
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
                        start=0, end=180, fill=gc,
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
                        "/System/Library/Fonts/Courier.dfont", max(10, int(cs * 0.07)))
                except (OSError, IOError):
                    score_font = ImageFont.load_default()
                score = int(progress * 9990)
                draw.text(
                    (int(cs * 0.05), int(cs * 0.06)),
                    f"SCORE {score:04d}",
                    fill=(255, 255, 255, 200), font=score_font,
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
                    [0,0,1,0,0,0,0,0,1,0,0],
                    [0,0,0,1,0,0,0,1,0,0,0],
                    [0,0,1,1,1,1,1,1,1,0,0],
                    [0,1,1,0,1,1,1,0,1,1,0],
                    [1,1,1,1,1,1,1,1,1,1,1],
                    [1,0,1,1,1,1,1,1,1,0,1],
                    [1,0,1,0,0,0,0,0,1,0,1],
                    [0,0,0,1,1,0,1,1,0,0,0],
                ]
                sprite_b = [
                    [0,0,1,0,0,0,0,0,1,0,0],
                    [1,0,0,1,0,0,0,1,0,0,1],
                    [1,0,1,1,1,1,1,1,1,0,1],
                    [1,1,1,0,1,1,1,0,1,1,1],
                    [1,1,1,1,1,1,1,1,1,1,1],
                    [0,1,1,1,1,1,1,1,1,1,0],
                    [0,0,1,0,0,0,0,0,1,0,0],
                    [0,1,0,0,0,0,0,0,0,1,0],
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
                        [missile_x - 1, missile_y,
                         missile_x + 1, missile_y + missile_h],
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
                                [sh_x + sc * px, shield_y + sr * px,
                                 sh_x + (sc + 1) * px - 1,
                                 shield_y + (sr + 1) * px - 1],
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
                    [cs // 2 - barrel_w, cannon_y - cannon_h,
                     cs // 2 + barrel_w, cannon_y],
                    fill=(0, 255, 0, 230),
                )

                # Score
                try:
                    sc_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont", max(9, int(cs * 0.06)))
                except (OSError, IOError):
                    sc_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.05), int(cs * 0.04)),
                    f"SCORE {int((i / max(1, total_frames)) * 1500):04d}",
                    fill=(255, 255, 255, 200), font=sc_font,
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
                    outline=(140, 90, 10, 255), width=max(2, int(cs * 0.015)),
                )

                # Inner darker border
                inset = int(cs * 0.025)
                draw.rounded_rectangle(
                    [block_x + inset, block_y + inset,
                     block_x + block_size - inset,
                     block_y + block_size - inset],
                    radius=3,
                    outline=(180, 110, 20, 200), width=max(1, int(cs * 0.008)),
                )

                # "?" character
                try:
                    q_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc",
                        max(14, int(block_size * 0.55)))
                except (OSError, IOError):
                    q_font = ImageFont.load_default()

                q_bbox = draw.textbbox((0, 0), "?", font=q_font)
                q_w = q_bbox[2] - q_bbox[0]
                q_h = q_bbox[3] - q_bbox[1]
                # Shadow
                draw.text(
                    (block_x + (block_size - q_w) // 2 + 2,
                     block_y + (block_size - q_h) // 2 - q_bbox[1] + 2),
                    "?", fill=(140, 90, 10, 180), font=q_font,
                )
                # "?" in white
                draw.text(
                    (block_x + (block_size - q_w) // 2,
                     block_y + (block_size - q_h) // 2 - q_bbox[1]),
                    "?", fill=(255, 255, 255, 255), font=q_font,
                )

                # Corner rivets
                rivet_r = max(2, int(cs * 0.02))
                rivet_inset = int(cs * 0.04)
                for rx, ry in [
                    (block_x + rivet_inset, block_y + rivet_inset),
                    (block_x + block_size - rivet_inset, block_y + rivet_inset),
                    (block_x + rivet_inset, block_y + block_size - rivet_inset),
                    (block_x + block_size - rivet_inset, block_y + block_size - rivet_inset),
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
                        [coin_x - coin_r, coin_y - coin_r,
                         coin_x + coin_r, coin_y + coin_r],
                        fill=(255, 215, 0, 255),
                        outline=(200, 160, 0, 255), width=2,
                    )
                    # "$" on coin
                    try:
                        coin_font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc",
                            max(8, int(coin_r * 1.1)))
                    except (OSError, IOError):
                        coin_font = ImageFont.load_default()
                    cb = draw.textbbox((0, 0), "$", font=coin_font)
                    cw = cb[2] - cb[0]
                    ch = cb[3] - cb[1]
                    draw.text(
                        (coin_x - cw // 2, coin_y - ch // 2 - cb[1]),
                        "$", fill=(180, 120, 0, 255), font=coin_font,
                    )

                    # Sparkles around coin
                    for sp in range(3):
                        sp_angle = math.pi * 2 * sp / 3 + i * 0.3
                        sp_dist = coin_r + int(amp * cs * 0.06) + sp * 4
                        sp_x = coin_x + int(math.cos(sp_angle) * sp_dist)
                        sp_y = coin_y + int(math.sin(sp_angle) * sp_dist)
                        sp_r = max(1, int(cs * 0.012))
                        draw.ellipse(
                            [sp_x - sp_r, sp_y - sp_r,
                             sp_x + sp_r, sp_y + sp_r],
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
                star_positions = [(int(rng_nc.uniform(0, cs)),
                                   int(rng_nc.uniform(0, cs)))
                                  for _ in range(20)]
                for sx_base, sy in star_positions:
                    sx = (sx_base - i * 3) % cs
                    sr = rng_nc.choice([1, 1, 2])
                    draw.ellipse(
                        [sx - sr, sy - sr, sx + sr, sy + sr],
                        fill=(255, 255, 255, int(rng_nc.uniform(120, 255))),
                    )

                # Rainbow trail (6 bands) flowing left
                rainbow_colors = [
                    (255, 0, 0, 200),    # red
                    (255, 154, 0, 200),  # orange
                    (255, 255, 0, 200),  # yellow
                    (0, 255, 0, 200),    # green
                    (0, 0, 255, 200),    # blue
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
                    outline=(200, 120, 140, 255), width=2,
                )
                # Sprinkles on Pop-Tart
                rng_sprinkle = np.random.default_rng(123)
                sprinkle_colors = [(255,0,100,200), (100,255,100,200),
                                   (100,100,255,200), (255,255,0,200)]
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
                    [face_cx - face_r, face_cy - face_r,
                     face_cx + face_r, face_cy + face_r],
                    fill=(120, 120, 120, 255),
                )
                # Cat ears (triangles)
                ear_size = int(face_r * 0.6)
                for ear_dx in [-int(face_r * 0.5), int(face_r * 0.5)]:
                    ear_cx = face_cx + ear_dx
                    ear_top = face_cy - face_r - ear_size + 2
                    draw.polygon(
                        [(ear_cx - ear_size // 2, face_cy - face_r + 3),
                         (ear_cx + ear_size // 2, face_cy - face_r + 3),
                         (ear_cx, ear_top)],
                        fill=(120, 120, 120, 255),
                    )
                # Cat eyes
                cat_eye_r = max(1, int(face_r * 0.18))
                for edx in [-int(face_r * 0.3), int(face_r * 0.3)]:
                    draw.ellipse(
                        [face_cx + edx - cat_eye_r,
                         face_cy - int(face_r * 0.15) - cat_eye_r,
                         face_cx + edx + cat_eye_r,
                         face_cy - int(face_r * 0.15) + cat_eye_r],
                        fill=(30, 30, 30, 255),
                    )
                # Mouth — opens with audio
                mouth_open = max(1, int(amp * face_r * 0.4))
                draw.ellipse(
                    [face_cx - int(face_r * 0.2),
                     face_cy + int(face_r * 0.1),
                     face_cx + int(face_r * 0.2),
                     face_cy + int(face_r * 0.1) + mouth_open],
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
                    [tail_x - leg_w, cat_cy - leg_w + tail_wave,
                     tail_x, cat_cy + leg_w + tail_wave],
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
                        "/System/Library/Fonts/Courier.dfont",
                        max(8, int(cs * 0.06)))
                except (OSError, IOError):
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

                        char = matrix_chars[
                            int(rng_m.integers(0, len(matrix_chars)))
                        ]
                        draw.text(
                            (col_x, cy_pos), char,
                            fill=color, font=m_font,
                        )

                # Central avatar with green ring
                inner_size = size // 2
                inner_img = avatar_img.resize(
                    (inner_size, inner_size), Image.LANCZOS)
                center = cs // 2
                ix = center - inner_size // 2
                iy = center - inner_size // 2
                # Dark circle behind avatar for contrast
                bg_r = inner_size // 2 + 6
                draw.ellipse(
                    [center - bg_r, center - bg_r,
                     center + bg_r, center + bg_r],
                    fill=(0, 0, 0, 220),
                )
                canvas.paste(inner_img, (ix, iy), inner_img)
                # Green ring
                ring_r = inner_size // 2 + 4
                ring_alpha = int(120 + amp * 135)
                draw.ellipse(
                    [center - ring_r, center - ring_r,
                     center + ring_r, center + ring_r],
                    outline=(0, 255, 70, ring_alpha), width=2,
                )

            elif style == "pickle_rick":
                # ── Pickle Rick — "I turned myself into a pickle!" ────
                import math

                draw = ImageDraw.Draw(canvas)
                cs = canvas_size
                cx = cs // 2

                # Lab / sewer dark background
                draw.rounded_rectangle(
                    [2, 2, cs - 3, cs - 3], radius=10,
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
                    [cx - body_w + sway, cy - body_h,
                     cx + body_w + sway, cy + body_h],
                    fill=body_color,
                    outline=body_outline, width=max(2, int(cs * 0.015)),
                )

                # Darker shading on left side for depth
                shade_w = int(body_w * 0.85)
                draw.ellipse(
                    [cx - body_w + sway, cy - body_h,
                     cx - body_w + shade_w + sway, cy + body_h],
                    fill=body_darker,
                )
                # Re-draw main on top, slightly offset for highlight effect
                draw.ellipse(
                    [cx - body_w + int(cs * 0.02) + sway, cy - body_h + int(cs * 0.01),
                     cx + body_w - int(cs * 0.01) + sway, cy + body_h - int(cs * 0.01)],
                    fill=body_color,
                )

                # Pickle bumps (warts)
                bump_r = max(2, int(cs * 0.018))
                bump_color = (60, 105, 5, 180)
                bump_positions = [
                    (-0.10, -0.06), (0.10, 0.02), (-0.06, 0.14),
                    (0.08, 0.18), (-0.12, 0.08), (0.12, -0.10),
                    (0.04, -0.18), (-0.08, 0.22),
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
                    [(cx - brow_w + sway, brow_y + int(cs * 0.015)),
                     (cx - int(cs * 0.02) + sway, brow_y - int(cs * 0.01)),
                     (cx + int(cs * 0.02) + sway, brow_y - int(cs * 0.01)),
                     (cx + brow_w + sway, brow_y + int(cs * 0.015))],
                    fill=(40, 65, 0, 255), width=brow_thickness,
                )

                # ── Eyes — large, expressive, slightly uneven (Rick-style) ──
                eye_gap = int(cs * 0.05)
                eye_y = face_cy

                # Left eye (slightly bigger)
                le_w = int(cs * 0.065)
                le_h = int(cs * 0.075)
                le_cx = cx - eye_gap - le_w // 2 + sway
                draw.ellipse(
                    [le_cx - le_w, eye_y - le_h,
                     le_cx + le_w, eye_y + le_h],
                    fill=(255, 255, 255, 255),
                    outline=(40, 65, 0, 255), width=2,
                )
                # Right eye (slightly smaller)
                re_w = int(cs * 0.058)
                re_h = int(cs * 0.068)
                re_cx = cx + eye_gap + re_w // 2 + sway
                draw.ellipse(
                    [re_cx - re_w, eye_y - re_h,
                     re_cx + re_w, eye_y + re_h],
                    fill=(255, 255, 255, 255),
                    outline=(40, 65, 0, 255), width=2,
                )

                # Pupils — look around erratically (Rick energy)
                look_x = int(math.sin(i * 0.2) * cs * 0.015)
                look_y = int(math.cos(i * 0.16) * cs * 0.01)
                for ecx in [le_cx, re_cx]:
                    pupil_r = max(3, int(cs * 0.028))
                    draw.ellipse(
                        [ecx + look_x - pupil_r, eye_y + look_y - pupil_r,
                         ecx + look_x + pupil_r, eye_y + look_y + pupil_r],
                        fill=(20, 20, 20, 255),
                    )
                    # Glint
                    gl = max(1, pupil_r // 3)
                    draw.ellipse(
                        [ecx + look_x - pupil_r + 2,
                         eye_y + look_y - pupil_r + 1,
                         ecx + look_x - pupil_r + 2 + gl,
                         eye_y + look_y - pupil_r + 1 + gl],
                        fill=(255, 255, 255, 200),
                    )

                # ── Mouth — wide manic grin / yell ──
                mouth_y = face_cy + int(cs * 0.06)
                mouth_w = int(cs * 0.10)
                mouth_open = max(3, int(amp * cs * 0.07))
                if amp > 0.12:
                    # Open mouth — screaming
                    draw.ellipse(
                        [cx - mouth_w + sway, mouth_y,
                         cx + mouth_w + sway, mouth_y + mouth_open * 2 + 2],
                        fill=(100, 25, 25, 240),
                        outline=(40, 65, 0, 255), width=1,
                    )
                    # Top teeth row
                    teeth_w = int(mouth_w * 0.7)
                    teeth_h = max(2, int(cs * 0.018))
                    draw.rectangle(
                        [cx - teeth_w + sway, mouth_y + 1,
                         cx + teeth_w + sway, mouth_y + teeth_h + 1],
                        fill=(245, 245, 230, 255),
                    )
                    # Bottom teeth
                    if mouth_open > 6:
                        bot_teeth_y = mouth_y + mouth_open * 2 - teeth_h
                        draw.rectangle(
                            [cx - teeth_w + sway, bot_teeth_y,
                             cx + teeth_w + sway, bot_teeth_y + teeth_h],
                            fill=(245, 245, 230, 255),
                        )
                    # Tongue hint
                    tongue_r = int(mouth_w * 0.3)
                    draw.ellipse(
                        [cx - tongue_r + sway,
                         mouth_y + mouth_open,
                         cx + tongue_r + sway,
                         mouth_y + mouth_open * 2],
                        fill=(200, 80, 80, 180),
                    )
                else:
                    # Cocky smirk
                    draw.arc(
                        [cx - mouth_w + sway, mouth_y - int(cs * 0.015),
                         cx + mouth_w + sway, mouth_y + int(cs * 0.035)],
                        start=5, end=175,
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
                draw.line([(la_x1, la_y1), (la_x2, la_y2)],
                          fill=limb_color, width=limb_w)
                # Hand (3 fingers)
                for f_angle in [-0.4, 0.0, 0.4]:
                    fx = la_x2 + int(math.cos(arm_angle + f_angle) * cs * 0.02)
                    fy = la_y2 + int(math.sin(arm_angle + f_angle) * cs * 0.02)
                    draw.line([(la_x2, la_y2), (fx, fy)],
                              fill=limb_color, width=max(1, limb_w - 1))

                # Right arm
                ra_angle = -math.sin(i * 0.18) * 0.3 - 0.4
                ra_x1 = cx + body_w - int(cs * 0.02) + sway
                ra_y1 = cy - int(body_h * 0.08)
                ra_x2 = ra_x1 + int(cs * 0.14 * math.cos(-ra_angle))
                ra_y2 = ra_y1 + int(cs * 0.10 * math.sin(-ra_angle))
                draw.line([(ra_x1, ra_y1), (ra_x2, ra_y2)],
                          fill=limb_color, width=limb_w)
                for f_angle in [-0.4, 0.0, 0.4]:
                    fx = ra_x2 + int(math.cos(-ra_angle + f_angle) * cs * 0.02)
                    fy = ra_y2 + int(math.sin(-ra_angle + f_angle) * cs * 0.02)
                    draw.line([(ra_x2, ra_y2), (fx, fy)],
                              fill=limb_color, width=max(1, limb_w - 1))

                # Legs — dangly rat legs
                for leg_side in [-1, 1]:
                    lx1 = cx + int(body_w * 0.35 * leg_side) + sway
                    ly1 = cy + body_h - 3
                    leg_swing = int(math.sin(i * 0.25 + leg_side * 1.5) * 5)
                    lx2 = lx1 + int(cs * 0.03 * leg_side) + leg_swing
                    ly2 = ly1 + int(cs * 0.10)
                    draw.line([(lx1, ly1), (lx2, ly2)],
                              fill=limb_color, width=limb_w)
                    # Foot
                    foot_w = max(3, int(cs * 0.025))
                    draw.ellipse(
                        [lx2 - foot_w, ly2 - 2,
                         lx2 + foot_w, ly2 + int(cs * 0.015)],
                        fill=limb_color,
                    )

                # ── "I'M PICKLE RICK!" shout when loud ──
                if amp > 0.4:
                    try:
                        shout_font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc",
                            max(9, int(cs * 0.06)))
                    except (OSError, IOError):
                        shout_font = ImageFont.load_default()
                    shout = "I'M PICKLE RICK!"
                    sb = draw.textbbox((0, 0), shout, font=shout_font)
                    sw = sb[2] - sb[0]
                    txt_x = cx - sw // 2
                    txt_y = int(cs * 0.87)
                    # Shadow
                    draw.text(
                        (txt_x + 1, txt_y + 1), shout,
                        fill=(0, 50, 0, 160), font=shout_font,
                    )
                    # Green glow text
                    draw.text(
                        (txt_x, txt_y), shout,
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
                    [0,0,0,0,1,1,1,1,0,0],
                    [0,0,0,0,1,0,1,1,0,0],
                    [0,0,0,0,1,1,1,1,0,0],
                    [0,0,0,1,1,1,1,0,0,0],
                    [1,0,1,1,1,1,1,1,0,0],
                    [1,1,1,1,1,1,0,0,0,0],
                    [0,1,1,1,1,1,0,0,0,0],
                    [0,0,1,0,0,1,0,0,0,0],
                ]
                # Alternate leg frames
                if (i // 4) % 2 == 0:
                    dino_sprite[7] = [0,0,1,0,0,0,1,0,0,0]
                for ry, row in enumerate(dino_sprite):
                    for cx_s, val in enumerate(row):
                        if val:
                            draw.rectangle(
                                [dino_x + cx_s * px, dino_y + ry * px,
                                 dino_x + (cx_s + 1) * px - 1,
                                 dino_y + (ry + 1) * px - 1],
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
                    [cactus_x - cactus_w, sky_h - int(cactus_h * 0.7),
                     cactus_x, sky_h - int(cactus_h * 0.5)],
                    fill=dino_color,
                )
                draw.rectangle(
                    [cactus_x + cactus_w, sky_h - int(cactus_h * 0.5),
                     cactus_x + cactus_w * 2, sky_h - int(cactus_h * 0.3)],
                    fill=dino_color,
                )

                # "NO INTERNET" text
                if amp > 0.3:
                    try:
                        err_font = ImageFont.truetype(
                            "/System/Library/Fonts/Courier.dfont",
                            max(8, int(cs * 0.05)))
                    except (OSError, IOError):
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
                        "/System/Library/Fonts/Courier.dfont",
                        max(8, int(cs * 0.045)))
                except (OSError, IOError):
                    sc_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.7), int(cs * 0.05)),
                    f"{int(i * 3):05d}",
                    fill=(83, 83, 83, 200), font=sc_font,
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
                    fill=head_color, outline=(100, 105, 110, 255), width=2,
                )
                # Head shading (darker left side)
                draw.ellipse(
                    [cx - head_r, cy - head_r,
                     cx - int(head_r * 0.3), cy + head_r],
                    fill=head_dark,
                )

                # ── Visor / face plate — triangular depressed zone ──
                visor_w = int(head_r * 1.2)
                visor_h = int(head_r * 0.6)
                visor_y = cy + int(head_r * 0.05)
                draw.rounded_rectangle(
                    [cx - visor_w // 2, visor_y - visor_h // 2,
                     cx + visor_w // 2, visor_y + visor_h // 2],
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
                        [ecx - eye_r - 2, eye_y - eye_r - 2,
                         ecx + eye_r + 2, eye_y + eye_r + 2],
                        fill=(200, 80, 40, glow_alpha // 2),
                    )
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r,
                         ecx + eye_r, eye_y + eye_r],
                        fill=(200, 100, 50, glow_alpha),
                    )
                    # Droopy brow line (sad)
                    brow_outer = eye_y - eye_r - int(cs * 0.015)
                    brow_inner = brow_outer + int(cs * 0.02)
                    draw.line(
                        [(ecx - eye_r * side, brow_inner),
                         (ecx + eye_r * side, brow_outer)],
                        fill=(80, 85, 90, 255), width=max(2, int(cs * 0.012)),
                    )

                # ── Thin sad mouth line ──
                mouth_y = visor_y + int(visor_h * 0.25)
                mouth_w = int(cs * 0.06)
                # Sad downturned arc
                draw.arc(
                    [cx - mouth_w, mouth_y - int(cs * 0.02),
                     cx + mouth_w, mouth_y + int(cs * 0.03)],
                    start=190, end=350,
                    fill=(200, 100, 50, 200), width=max(2, int(cs * 0.012)),
                )

                # ── Small body below head ──
                body_w = int(cs * 0.15)
                body_top = cy + head_r - 3
                body_bot = body_top + int(cs * 0.18)
                draw.rounded_rectangle(
                    [cx - body_w, body_top, cx + body_w, body_bot],
                    radius=int(cs * 0.03),
                    fill=(160, 165, 170, 255),
                    outline=(100, 105, 110, 255), width=1,
                )

                # Stubby arms (hanging limp, depressed)
                arm_w = max(2, int(cs * 0.018))
                for side in [-1, 1]:
                    ax = cx + body_w * side
                    draw.line(
                        [(ax, body_top + int(cs * 0.03)),
                         (ax + int(cs * 0.08 * side),
                          body_top + int(cs * 0.14 + amp * cs * 0.02))],
                        fill=head_color, width=arm_w,
                    )

                # Stubby legs
                for side in [-1, 1]:
                    lx = cx + int(body_w * 0.5 * side)
                    draw.line(
                        [(lx, body_bot),
                         (lx, body_bot + int(cs * 0.06))],
                        fill=head_color, width=arm_w,
                    )
                    draw.ellipse(
                        [lx - int(cs * 0.02), body_bot + int(cs * 0.05),
                         lx + int(cs * 0.02), body_bot + int(cs * 0.07)],
                        fill=(120, 125, 130, 255),
                    )

                # Depressive quote
                if amp > 0.25:
                    try:
                        q_font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc",
                            max(7, int(cs * 0.04)))
                    except (OSError, IOError):
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
                    [cx - mac_w // 2, cy - mac_h // 2,
                     cx + mac_w // 2, cy + mac_h // 2],
                    radius=int(cs * 0.04),
                    fill=mac_color,
                    outline=mac_border, width=max(2, int(cs * 0.012)),
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
                    outline=(100, 100, 90, 255), width=2,
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
                        [ecx - eye_w // 2, eye_y,
                         ecx + eye_w // 2, eye_y + eye_h],
                        radius=2,
                        fill=(30, 60, 30, 255),
                    )
                    # Inner white
                    draw.rounded_rectangle(
                        [ecx - eye_w // 2 + 2, eye_y + 2,
                         ecx + eye_w // 2 - 2, eye_y + eye_h - 2],
                        radius=1,
                        fill=(200, 230, 200, 255),
                    )
                    # Pupil
                    pr = max(2, int(eye_w * 0.25))
                    draw.ellipse(
                        [ecx + look_x - pr, eye_y + eye_h // 2 + look_y - pr,
                         ecx + look_x + pr, eye_y + eye_h // 2 + look_y + pr],
                        fill=(30, 60, 30, 255),
                    )

                # ── Smile on screen ──
                smile_y = scr_y + int(scr_h * 0.65)
                smile_w = int(scr_w * 0.25)
                mouth_open_h = int(amp * scr_h * 0.15)
                if amp > 0.15:
                    draw.ellipse(
                        [cx - smile_w, smile_y,
                         cx + smile_w, smile_y + mouth_open_h + 3],
                        fill=(30, 60, 30, 230),
                    )
                else:
                    draw.arc(
                        [cx - smile_w, smile_y - int(cs * 0.015),
                         cx + smile_w, smile_y + int(cs * 0.02)],
                        start=10, end=170,
                        fill=(30, 60, 30, 220), width=2,
                    )

                # ── Floppy slot below screen ──
                slot_w = int(mac_w * 0.3)
                slot_h = max(3, int(cs * 0.015))
                slot_y = cy + mac_h // 2 - int(mac_h * 0.15)
                draw.rounded_rectangle(
                    [cx - slot_w // 2, slot_y,
                     cx + slot_w // 2, slot_y + slot_h],
                    radius=1, fill=(140, 135, 120, 255),
                )

                # ── Base/stand ──
                base_w = int(mac_w * 0.5)
                base_h = int(cs * 0.03)
                base_y = cy + mac_h // 2
                draw.rectangle(
                    [cx - base_w // 2, base_y,
                     cx + base_w // 2, base_y + base_h],
                    fill=mac_border,
                )
                # Wider foot
                draw.rectangle(
                    [cx - int(base_w * 0.7), base_y + base_h,
                     cx + int(base_w * 0.7), base_y + base_h + int(cs * 0.015)],
                    fill=mac_border,
                )

                # "hello" text when speaking
                if amp > 0.35:
                    try:
                        hello_font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc",
                            max(8, int(cs * 0.05)))
                    except (OSError, IOError):
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
                    [cx - fl_w // 2, cy - fl_h // 2,
                     cx + fl_w // 2, cy + fl_h // 2],
                    radius=int(cs * 0.02),
                    fill=fl_color,
                    outline=(80, 80, 90, 255), width=2,
                )

                # ── Metal slider at top ──
                slider_w = int(fl_w * 0.45)
                slider_h = int(fl_h * 0.18)
                slider_y = cy - fl_h // 2 + int(fl_h * 0.04)
                draw.rectangle(
                    [cx - slider_w // 2, slider_y,
                     cx + slider_w // 2, slider_y + slider_h],
                    fill=(160, 165, 170, 255),
                    outline=(120, 125, 130, 255), width=1,
                )
                # Slider hole
                hole_w = int(slider_w * 0.25)
                hole_h = int(slider_h * 0.7)
                draw.rectangle(
                    [cx - hole_w // 2 + int(slider_w * 0.15),
                     slider_y + (slider_h - hole_h) // 2,
                     cx + hole_w // 2 + int(slider_w * 0.15),
                     slider_y + (slider_h + hole_h) // 2],
                    fill=(40, 40, 45, 255),
                )

                # ── Label area (white sticker) ──
                label_w = int(fl_w * 0.8)
                label_h = int(fl_h * 0.35)
                label_y = cy + int(fl_h * 0.05)
                draw.rounded_rectangle(
                    [cx - label_w // 2, label_y,
                     cx + label_w // 2, label_y + label_h],
                    radius=3,
                    fill=(240, 235, 220, 255),
                    outline=(200, 195, 180, 255), width=1,
                )

                # Lines on label
                line_color = (180, 175, 165, 200)
                for li in range(4):
                    ly = label_y + int(label_h * 0.2) + li * int(label_h * 0.18)
                    draw.line(
                        [(cx - label_w // 2 + 6, ly),
                         (cx + label_w // 2 - 6, ly)],
                        fill=line_color, width=1,
                    )

                # ── Eyes on the metal slider area ──
                eye_r = max(3, int(cs * 0.032))
                eye_y_pos = slider_y + slider_h + int(fl_h * 0.08)
                eye_gap = int(cs * 0.06)
                look_x = int(math.sin(i * 0.2) * cs * 0.008)

                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y_pos - eye_r,
                         ecx + eye_r, eye_y_pos + eye_r],
                        fill=(255, 255, 255, 255),
                        outline=(80, 80, 90, 255), width=1,
                    )
                    pr = max(1, eye_r // 2)
                    draw.ellipse(
                        [ecx + look_x - pr, eye_y_pos - pr,
                         ecx + look_x + pr, eye_y_pos + pr],
                        fill=(20, 20, 30, 255),
                    )

                # ── Mouth — grumpy ──
                mouth_y_pos = eye_y_pos + int(cs * 0.04)
                mouth_w = int(cs * 0.05)
                if amp > 0.15:
                    draw.ellipse(
                        [cx - mouth_w, mouth_y_pos,
                         cx + mouth_w, mouth_y_pos + int(amp * cs * 0.04) + 2],
                        fill=(200, 80, 80, 200),
                    )
                else:
                    # Grumpy frown
                    draw.arc(
                        [cx - mouth_w, mouth_y_pos,
                         cx + mouth_w, mouth_y_pos + int(cs * 0.03)],
                        start=200, end=340,
                        fill=(200, 100, 100, 200),
                        width=max(2, int(cs * 0.012)),
                    )

                # ── "1.44 MB" label text ──
                try:
                    mb_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont",
                        max(7, int(cs * 0.04)))
                except (OSError, IOError):
                    mb_font = ImageFont.load_default()
                draw.text(
                    (cx - label_w // 2 + 6, label_y + int(label_h * 0.05)),
                    "1.44 MB",
                    fill=(100, 95, 85, 200), font=mb_font,
                )

                # Arms (tiny, floppy-like)
                arm_w = max(2, int(cs * 0.015))
                limb_color = (60, 60, 70, 230)
                for side in [-1, 1]:
                    ax = cx + (fl_w // 2) * side
                    wave = int(math.sin(i * 0.2 + side) * cs * 0.02)
                    draw.line(
                        [(ax, cy + int(fl_h * 0.05)),
                         (ax + int(cs * 0.08 * side),
                          cy + int(fl_h * 0.1) + wave)],
                        fill=limb_color, width=arm_w,
                    )

                # "Save icon!" shout
                if amp > 0.45:
                    try:
                        s_font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc",
                            max(7, int(cs * 0.045)))
                    except (OSError, IOError):
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
                    draw.line([(0, row), (cs, row)],
                              fill=(0, 0, 150, 40), width=1)

                try:
                    bsod_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont",
                        max(7, int(cs * 0.038)))
                except (OSError, IOError):
                    bsod_font = ImageFont.load_default()

                try:
                    title_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont",
                        max(8, int(cs * 0.045)))
                except (OSError, IOError):
                    title_font = bsod_font

                text_color = (255, 255, 255, 255)
                y_pos = int(cs * 0.08)

                # Title bar
                title = " Windows "
                tb = draw.textbbox((0, 0), title, font=title_font)
                tw = tb[2] - tb[0]
                draw.rectangle(
                    [int(cs * 0.15), y_pos,
                     int(cs * 0.15) + tw + 8, y_pos + int(cs * 0.06)],
                    fill=(170, 170, 170, 255),
                )
                draw.text(
                    (int(cs * 0.15) + 4, y_pos + 2), title,
                    fill=(0, 0, 170, 255), font=title_font,
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
                        fill=text_color, font=bsod_font,
                    )

                # Sad emoticon :( — bounces with audio
                sad_y = int(cs * 0.72) - int(amp * cs * 0.05)
                try:
                    sad_font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc",
                        max(20, int(cs * 0.16)))
                except (OSError, IOError):
                    sad_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.35), sad_y), ":(",
                    fill=text_color, font=sad_font,
                )

                # Blinking cursor
                if (i // 15) % 2 == 0:
                    cursor_y = y_pos + visible_lines * int(cs * 0.055)
                    draw.rectangle(
                        [int(cs * 0.06), cursor_y,
                         int(cs * 0.06) + int(cs * 0.03),
                         cursor_y + int(cs * 0.04)],
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
                        fill=(int(200 + t * 30), int(230 + t * 20),
                              int(200 + t * 30), 255),
                    )

                bounce = int(amp * cs * 0.04)
                cy = int(cs * 0.50) - bounce

                # Android green
                ag = (61, 220, 132, 255)  # #3DDC84
                ag_dark = (40, 180, 100, 255)
                ag_outline = (30, 150, 80, 255)

                # ── Head (half-circle on top) ──
                head_w = int(cs * 0.22)
                head_h = int(cs * 0.15)
                head_top = cy - int(cs * 0.18)
                draw.pieslice(
                    [cx - head_w, head_top,
                     cx + head_w, head_top + head_h * 2],
                    start=180, end=0,
                    fill=ag, outline=ag_outline, width=2,
                )

                # ── Antennae ──
                ant_len = int(cs * 0.08)
                ant_w = max(2, int(cs * 0.012))
                for side, angle in [(-1, -30), (1, -30)]:
                    ax = cx + int(head_w * 0.5 * side)
                    ay = head_top + int(head_h * 0.2)
                    tip_x = ax + int(math.sin(math.radians(angle * side)) * ant_len)
                    tip_y = ay - int(math.cos(math.radians(angle * side)) * ant_len)
                    draw.line([(ax, ay), (tip_x, tip_y)],
                              fill=ag, width=ant_w)
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
                        [ecx - eye_r, eye_y - eye_r,
                         ecx + eye_r, eye_y + eye_r],
                        fill=(255, 255, 255, 255),
                    )

                # ── Body (rounded rectangle) ──
                body_w = int(cs * 0.22)
                body_top = head_top + head_h
                body_h = int(cs * 0.22)
                draw.rounded_rectangle(
                    [cx - body_w, body_top,
                     cx + body_w, body_top + body_h],
                    radius=int(cs * 0.03),
                    fill=ag, outline=ag_outline, width=2,
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
                        [ax - arm_w_px // 2 * (1 if side == -1 else 1),
                         arm_top,
                         ax + arm_w_px // 2 * (1 if side == -1 else 1),
                         arm_top + arm_h_px],
                        radius=int(arm_w_px * 0.4),
                        fill=ag,
                    )

                # ── Legs ──
                leg_w_px = int(cs * 0.06)
                leg_h = int(cs * 0.10)
                for side in [-1, 1]:
                    lx = cx + int(body_w * 0.45 * side)
                    draw.rounded_rectangle(
                        [lx - leg_w_px // 2, body_top + body_h - 2,
                         lx + leg_w_px // 2, body_top + body_h + leg_h],
                        radius=int(leg_w_px * 0.4),
                        fill=ag,
                    )

                # ── Mouth (opens with audio) ──
                if amp > 0.2:
                    mouth_w = int(head_w * 0.5)
                    mouth_h = max(2, int(amp * cs * 0.04))
                    mouth_y = eye_y + int(cs * 0.035)
                    draw.rounded_rectangle(
                        [cx - mouth_w, mouth_y,
                         cx + mouth_w, mouth_y + mouth_h],
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
                for (mx, my) in corners:
                    for r in range(marker_size):
                        for c in range(marker_size):
                            is_border = (r == 0 or r == marker_size - 1 or
                                         c == 0 or c == marker_size - 1)
                            is_inner = (1 < r < marker_size - 2 and
                                        1 < c < marker_size - 2)
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
                        for (mx, my) in corners:
                            if mx <= c < mx + marker_size and my <= r < my + marker_size:
                                in_corner = True
                        # Skip center eye zone
                        center_zone = (grid // 2 - 3 <= c <= grid // 2 + 3 and
                                       grid // 2 - 3 <= r <= grid // 2 + 3)
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
                    [cx - eye_gap - eye_bg_r, eye_y - eye_bg_r,
                     cx + eye_gap + eye_bg_r, eye_y + eye_bg_r + int(cs * 0.06)],
                    radius=4, fill=(255, 255, 255, 255),
                )

                look_x = int(math.sin(i * 0.2) * cs * 0.01)
                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y - eye_r,
                         ecx + eye_r, eye_y + eye_r],
                        fill=(255, 255, 255, 255),
                        outline=(0, 0, 0, 255), width=2,
                    )
                    pr = max(2, eye_r // 2)
                    draw.ellipse(
                        [ecx + look_x - pr, eye_y - pr,
                         ecx + look_x + pr, eye_y + pr],
                        fill=(0, 0, 0, 255),
                    )

                # Mouth
                mouth_y = eye_y + int(cs * 0.045)
                mouth_w = int(cs * 0.04)
                if amp > 0.15:
                    draw.ellipse(
                        [cx - mouth_w, mouth_y,
                         cx + mouth_w, mouth_y + int(amp * cs * 0.04) + 2],
                        fill=(0, 0, 0, 200),
                    )
                else:
                    draw.line(
                        [(cx - mouth_w, mouth_y + 2),
                         (cx + mouth_w, mouth_y + 2)],
                        fill=(0, 0, 0, 180), width=2,
                    )

                # "SCAN ME!" text
                if amp > 0.4:
                    try:
                        scan_font = ImageFont.truetype(
                            "/System/Library/Fonts/Helvetica.ttc",
                            max(7, int(cs * 0.045)))
                    except (OSError, IOError):
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
                    outline=(40, 100, 40, 255), width=2,
                )

                # ── GPU cooler/shroud (dark, with fan) ──
                shroud_w = int(pcb_w * 0.85)
                shroud_h = int(pcb_h * 0.75)
                shroud_x = cx - shroud_w // 2
                shroud_y = pcb_y + int(pcb_h * 0.12)
                draw.rounded_rectangle(
                    [shroud_x, shroud_y,
                     shroud_x + shroud_w, shroud_y + shroud_h],
                    radius=int(cs * 0.02),
                    fill=(40, 40, 45, 255),
                    outline=(70, 70, 80, 255), width=1,
                )

                # ── Fan (spinning faster with amplitude) ──
                fan_cx = cx
                fan_cy = shroud_y + shroud_h // 2
                fan_r = int(shroud_h * 0.38)
                # Fan circle
                draw.ellipse(
                    [fan_cx - fan_r, fan_cy - fan_r,
                     fan_cx + fan_r, fan_cy + fan_r],
                    fill=(50, 50, 55, 255),
                    outline=(80, 80, 90, 255), width=1,
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
                        draw.ellipse([bx - 1, by - 1, bx + 1, by + 1],
                                     fill=(90, 90, 100, 200))
                # Fan center cap
                draw.ellipse(
                    [fan_cx - int(fan_r * 0.18), fan_cy - int(fan_r * 0.18),
                     fan_cx + int(fan_r * 0.18), fan_cy + int(fan_r * 0.18)],
                    fill=(60, 60, 65, 255),
                    outline=(100, 100, 110, 255), width=1,
                )

                # ── Eyes on the shroud (above fan) ──
                eye_r = max(2, int(cs * 0.025))
                eye_y_pos = shroud_y + int(shroud_h * 0.12)
                eye_gap = int(cs * 0.06)
                look_x = int(math.sin(i * 0.18) * cs * 0.008)

                for side in [-1, 1]:
                    ecx = cx + eye_gap * side
                    draw.ellipse(
                        [ecx - eye_r, eye_y_pos - eye_r,
                         ecx + eye_r, eye_y_pos + eye_r],
                        fill=(255, 255, 255, 255),
                    )
                    pr = max(1, eye_r // 2)
                    draw.ellipse(
                        [ecx + look_x - pr, eye_y_pos - pr,
                         ecx + look_x + pr, eye_y_pos + pr],
                        fill=(20, 20, 30, 255),
                    )
                    # Worried brows (higher with amp)
                    brow_raise = int(amp * cs * 0.015)
                    brow_y = eye_y_pos - eye_r - int(cs * 0.012) - brow_raise
                    draw.line(
                        [(ecx - eye_r, brow_y + int(cs * 0.008) * side),
                         (ecx + eye_r, brow_y - int(cs * 0.008) * side)],
                        fill=(200, 200, 210, 200),
                        width=max(1, int(cs * 0.01)),
                    )

                # Worried mouth
                mouth_y_pos = shroud_y + shroud_h - int(cs * 0.04)
                mouth_w_px = int(cs * 0.04)
                draw.arc(
                    [cx - mouth_w_px, mouth_y_pos,
                     cx + mouth_w_px, mouth_y_pos + int(cs * 0.025)],
                    start=200, end=340,
                    fill=(200, 200, 210, 200),
                    width=max(1, int(cs * 0.01)),
                )

                # ── PCI-E connector at bottom ──
                pcie_w = int(pcb_w * 0.7)
                pcie_h = max(3, int(cs * 0.02))
                draw.rectangle(
                    [cx - pcie_w // 2, pcb_y + pcb_h,
                     cx + pcie_w // 2, pcb_y + pcb_h + pcie_h],
                    fill=(200, 170, 50, 255),
                )
                # Gold pins
                pin_count = 12
                pin_w = pcie_w // (pin_count * 2)
                for p in range(pin_count):
                    px_pin = cx - pcie_w // 2 + int(p * pcie_w / pin_count) + 2
                    draw.rectangle(
                        [px_pin, pcb_y + pcb_h,
                         px_pin + pin_w, pcb_y + pcb_h + pcie_h],
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
                        [drop_x - drop_r, drop_y,
                         drop_x + drop_r, drop_y + int(drop_r * 1.5)],
                        fill=(100, 180, 255, int(150 + amp * 100)),
                    )
                    # Pointy top
                    draw.polygon(
                        [(drop_x, drop_y - drop_r),
                         (drop_x - drop_r, drop_y + 2),
                         (drop_x + drop_r, drop_y + 2)],
                        fill=(100, 180, 255, int(130 + amp * 80)),
                    )

                # Temperature indicator
                temp = int(40 + amp * 60)
                temp_color = (
                    min(255, int(temp * 2.5)),
                    max(0, int(255 - temp * 2)),
                    50, 220,
                )
                try:
                    t_font = ImageFont.truetype(
                        "/System/Library/Fonts/Courier.dfont",
                        max(7, int(cs * 0.04)))
                except (OSError, IOError):
                    t_font = ImageFont.load_default()
                draw.text(
                    (int(cs * 0.65), int(cs * 0.88)),
                    f"{temp}°C",
                    fill=temp_color, font=t_font,
                )

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
