"""Subtitle overlay — burns styled subtitles into video via ffmpeg drawtext."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Speed presets: words per second displayed
SPEED_PRESETS: dict[str, float] = {
    "slow": 1.5,
    "normal": 2.5,
    "fast": 4.0,
    "tiktok": 6.0,
}

# Style presets with default overrides
STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "classic": {
        "font_size": 42,
        "font_color": "#FFFFFF",
        "background_color": "rgba(0,0,0,0.6)",
        "position": "bottom",
        "animation": "none",
    },
    "tiktok": {
        "font_size": 64,
        "font_color": "#FFFFFF",
        "background_color": "rgba(0,0,0,0)",
        "position": "center",
        "highlight_color": "#FFD700",
        "animation": "pop",
        "max_words_per_line": 3,
    },
    "color": {
        "font_size": 48,
        "font_color": "#FFFFFF",
        "background_color": "rgba(0,0,0,0.4)",
        "position": "bottom",
        "highlight_color": "#00FF88",
        "animation": "fade",
    },
    "word_by_word": {
        "font_size": 56,
        "font_color": "#FFFFFF",
        "background_color": "rgba(0,0,0,0)",
        "position": "center",
        "animation": "pop",
        "max_words_per_line": 1,
    },
    "typewriter": {
        "font_size": 44,
        "font_color": "#00FF00",
        "background_color": "rgba(0,0,0,0.8)",
        "position": "bottom",
        "animation": "none",
    },
    "karaoke": {
        "font_size": 52,
        "font_color": "#AAAAAA",
        "background_color": "rgba(0,0,0,0.5)",
        "position": "bottom",
        "highlight_color": "#FF4444",
        "animation": "fade",
    },
    "bounce": {
        "font_size": 60,
        "font_color": "#FFFFFF",
        "background_color": "rgba(0,0,0,0)",
        "position": "center",
        "animation": "pop",
        "max_words_per_line": 4,
    },
    "cinema": {
        "font_size": 38,
        "font_color": "#F5F5DC",
        "background_color": "rgba(0,0,0,0)",
        "position": "bottom",
        "animation": "fade",
        "font_family": "Georgia",
    },
    "highlight_line": {
        "font_size": 46,
        "font_color": "#888888",
        "background_color": "rgba(0,0,0,0.5)",
        "position": "bottom",
        "highlight_color": "#FFFFFF",
        "animation": "none",
    },
    "fade_word": {
        "font_size": 50,
        "font_color": "#FFFFFF",
        "background_color": "rgba(0,0,0,0)",
        "position": "center",
        "animation": "fade",
        "max_words_per_line": 5,
    },
    "emoji_react": {
        "font_size": 52,
        "font_color": "#FFFFFF",
        "background_color": "rgba(0,0,0,0.4)",
        "position": "bottom",
        "highlight_color": "#FFD700",
        "animation": "pop",
    },
}


def _hex_to_ass_color(hex_color: str) -> str:
    """Convert #RRGGBB to ASS color format &HBBGGRR&."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H00{b}{g}{r}&"
    return "&H00FFFFFF&"


def _hex_to_ass_alpha_color(rgba: str) -> tuple[str, str]:
    """Convert rgba() or hex to ASS color + alpha.

    Returns (color, alpha) in ASS format.
    """
    if rgba.startswith("rgba("):
        parts = rgba[5:-1].split(",")
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        a = float(parts[3])
        alpha = format(int((1 - a) * 255), "02X")
        color = f"&H00{b:02X}{g:02X}{r:02X}&"
        return color, f"&H{alpha}&"
    return _hex_to_ass_color(rgba), "&H00&"


def _pick_emoji(text: str) -> str:
    """Pick a contextual emoji based on keywords in the text."""
    lower = text.lower()
    mapping = [
        (["welcome", "hello", "hi ", "hey"], "👋"),
        (["click", "button", "press", "tap"], "👆"),
        (["scroll", "swipe"], "📜"),
        (["install", "setup", "pip", "npm"], "📦"),
        (["fast", "speed", "quick", "instant"], "⚡"),
        (["feature", "powerful", "capability"], "✨"),
        (["code", "yaml", "json", "config"], "💻"),
        (["video", "demo", "watch", "record"], "🎬"),
        (["voice", "narration", "speak", "audio"], "🎙️"),
        (["effect", "visual", "animation"], "🎨"),
        (["export", "output", "save", "file"], "💾"),
        (["error", "fail", "bug", "fix"], "🐛"),
        (["success", "done", "complete", "finish"], "✅"),
        (["star", "review", "rate"], "⭐"),
        (["love", "great", "awesome", "amazing"], "🔥"),
    ]
    for keywords, emoji in mapping:
        if any(kw in lower for kw in keywords):
            return emoji
    return "💬"


def build_subtitle_entries(
    narration_texts: dict[int, str],
    step_timestamps: list[float],
    narration_durations: dict[int, float],
    *,
    speed_wps: float = 2.5,
    max_words_per_line: int = 8,
    style_name: str = "classic",
) -> list[dict[str, Any]]:
    """Build a list of subtitle entries with timing.

    Each entry: {start, end, text, words} where words is list of
    {word, start, end} for word-level timing.
    """
    entries: list[dict[str, Any]] = []

    for step_idx, text in sorted(narration_texts.items()):
        if step_idx >= len(step_timestamps):
            continue

        start_t = step_timestamps[step_idx]
        duration = narration_durations.get(step_idx, len(text.split()) / speed_wps)
        start_t + duration

        words = text.split()
        if not words:
            continue

        # Split into lines
        lines: list[list[str]] = []
        for i in range(0, len(words), max_words_per_line):
            lines.append(words[i : i + max_words_per_line])

        # Distribute time across lines
        total_words = len(words)
        word_duration = duration / total_words if total_words else duration

        current_t = start_t
        for line_words in lines:
            line_start = current_t
            line_dur = len(line_words) * word_duration
            line_end = line_start + line_dur

            word_entries = []
            wt = line_start
            for w in line_words:
                w_end = wt + word_duration
                word_entries.append({"word": w, "start": wt, "end": w_end})
                wt = w_end

            entries.append(
                {
                    "start": line_start,
                    "end": line_end,
                    "text": " ".join(line_words),
                    "words": word_entries,
                }
            )
            current_t = line_end

    return entries


def clamp_subtitle_entries(
    entries: list[dict[str, Any]],
    *,
    gap: float = 0.05,
) -> list[dict[str, Any]]:
    """Clamp subtitle entries so none overlap the next one.

    For each consecutive pair, if entry[i].end > entry[i+1].start - gap,
    the end time (and its word timings) are compressed to fit.

    Args:
        entries: Subtitle entries from build_subtitle_entries.
        gap: Minimum gap in seconds between consecutive entries.

    Returns:
        The same list, mutated in place, with clamped timings.
    """
    if len(entries) <= 1:
        return entries

    for i in range(len(entries) - 1):
        cur = entries[i]
        nxt = entries[i + 1]
        max_end = nxt["start"] - gap

        if cur["end"] <= max_end:
            continue

        original_end = cur["end"]
        cur["end"] = max(max_end, cur["start"] + 0.05)

        logger.debug(
            "Clamped subtitle end %.2fs → %.2fs (next starts %.2fs)",
            original_end,
            cur["end"],
            nxt["start"],
        )

        # Recompute word timings to fit the clamped duration
        words = cur.get("words", [])
        if words:
            new_dur = cur["end"] - cur["start"]
            old_dur = original_end - cur["start"]
            if old_dur > 0:
                ratio = new_dur / old_dur
                for w in words:
                    w["start"] = cur["start"] + (w["start"] - cur["start"]) * ratio
                    w["end"] = cur["start"] + (w["end"] - cur["start"]) * ratio

    return entries


def _format_ass_time(seconds: float) -> str:
    """Format seconds as H:MM:SS.cc (ASS format)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    cs = int((s - int(s)) * 100)
    return f"{h}:{m:02d}:{int(s):02d}.{cs:02d}"


def generate_ass_subtitle(
    entries: list[dict[str, Any]],
    config: dict[str, Any],
    output_path: Path,
) -> Path:
    """Generate an ASS subtitle file with styled entries.

    Args:
        entries: Subtitle entries from build_subtitle_entries.
        config: Merged subtitle config (style preset + user overrides).
        output_path: Where to write the .ass file.

    Returns:
        Path to the generated .ass file.
    """
    style_name = config.get("style", "classic")
    font_size = config.get("font_size", 48)
    font_family = config.get("font_family", "Arial")
    font_color = _hex_to_ass_color(config.get("font_color", "#FFFFFF"))
    highlight_color = _hex_to_ass_color(config.get("highlight_color", "#FFD700"))
    bg_color, bg_alpha = _hex_to_ass_alpha_color(config.get("background_color", "rgba(0,0,0,0.6)"))
    position = config.get("position", "bottom")

    # ASS alignment: bottom-center=2, center=5, top-center=8
    alignment = {"bottom": 2, "center": 5, "top": 8}.get(position, 2)

    # Margin from edge
    margin_v = 40 if position == "bottom" else (40 if position == "top" else 0)

    bold = -1 if style_name in ("tiktok", "word_by_word", "bounce", "emoji_react") else 0

    # Border style: 3 = opaque box, 1 = outline+shadow
    border_style = 3 if style_name in ("classic", "typewriter", "karaoke", "highlight_line") else 1
    outline = 2 if border_style == 1 else 0
    shadow = 1 if style_name == "cinema" else 0

    ass_header = f"""[Script Info]
Title: DemoDSL Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_family},{font_size},{font_color},{highlight_color},&H00000000&,{bg_color},{bold},0,0,0,100,100,0,0,{border_style},{outline},{shadow},{alignment},30,30,{margin_v},1
Style: Highlight,{font_family},{font_size},{highlight_color},{font_color},&H00000000&,{bg_color},{bold},0,0,0,100,100,0,0,{border_style},{outline},{shadow},{alignment},30,30,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines: list[str] = []

    for entry in entries:
        start = _format_ass_time(entry["start"])
        end = _format_ass_time(entry["end"])

        if style_name == "karaoke":
            # Karaoke: progressive color fill word by word
            kara_text = ""
            for w in entry["words"]:
                w_dur_cs = int((w["end"] - w["start"]) * 100)
                kara_text += f"{{\\kf{w_dur_cs}}}{w['word']} "
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{kara_text.strip()}")

        elif style_name in ("tiktok", "word_by_word"):
            # Word-by-word highlight: each word briefly highlighted
            for w in entry["words"]:
                w_start = _format_ass_time(w["start"])
                w_end = _format_ass_time(w["end"])
                lines.append(f"Dialogue: 0,{w_start},{w_end},Highlight,,0,0,0,,{w['word']}")

        elif style_name == "color":
            # Color: show full line but highlight current word
            for i, w in enumerate(entry["words"]):
                w_start = _format_ass_time(w["start"])
                w_end = _format_ass_time(w["end"])
                parts = []
                for j, ww in enumerate(entry["words"]):
                    if j == i:
                        parts.append(f"{{\\c{highlight_color}}}{ww['word']}{{\\c{font_color}}}")
                    else:
                        parts.append(ww["word"])
                colored_text = " ".join(parts)
                lines.append(f"Dialogue: 0,{w_start},{w_end},Default,,0,0,0,,{colored_text}")

        elif style_name == "typewriter":
            # Typewriter: progressive character reveal
            text = entry["text"]
            total_dur = entry["end"] - entry["start"]
            char_dur = total_dur / max(len(text), 1)
            for ci in range(1, len(text) + 1):
                c_start = _format_ass_time(entry["start"] + (ci - 1) * char_dur)
                c_end = _format_ass_time(entry["start"] + ci * char_dur)
                partial = text[:ci]
                lines.append(f"Dialogue: 0,{c_start},{c_end},Default,,0,0,0,,{partial}")

        elif style_name == "bounce":
            # Bounce: words appear one at a time with scale animation
            for w in entry["words"]:
                w_start = _format_ass_time(w["start"])
                w_end = _format_ass_time(w["end"])
                # ASS \t transform: scale from 120% to 100% for a bounce feel
                bounce_text = f"{{\\fscx120\\fscy120\\t(0,150,\\fscx100\\fscy100)}}{w['word']}"
                lines.append(f"Dialogue: 0,{w_start},{w_end},Highlight,,0,0,0,,{bounce_text}")

        elif style_name == "cinema":
            # Cinema: elegant italic timed lines, letterbox feel
            text = entry["text"]
            cinema_text = f"{{\\i1}}{text}"
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{cinema_text}")

        elif style_name == "highlight_line":
            # Highlight line: dim full text, bright current line
            # Show all lines dimmed, then overlay the bright current line
            text = entry["text"]
            dim_text = f"{{\\c{font_color}}}{text}"
            bright_text = f"{{\\c{highlight_color}}}{text}"
            # Dim version for the whole entry duration
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{dim_text}")
            # Bright overlay on top (layer 1)
            lines.append(f"Dialogue: 1,{start},{end},Default,,0,0,0,,{bright_text}")

        elif style_name == "fade_word":
            # Fade word: each word fades in with alpha animation
            for w in entry["words"]:
                w_start = _format_ass_time(w["start"])
                w_end = _format_ass_time(w["end"])
                fade_dur_ms = 200
                fade_text = f"{{\\fad({fade_dur_ms},0)}}{w['word']}"
                lines.append(f"Dialogue: 0,{w_start},{w_end},Highlight,,0,0,0,,{fade_text}")

        elif style_name == "emoji_react":
            # Emoji react: subtitle line with a contextual emoji prefix
            text = entry["text"]
            emoji = _pick_emoji(text)
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{emoji} {text}")

        else:
            # Classic: simple timed subtitle
            text = entry["text"]
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    ass_content = ass_header + "\n".join(lines) + "\n"
    output_path.write_text(ass_content, encoding="utf-8")
    logger.info("Generated ASS subtitle file: %s (%d entries)", output_path.name, len(entries))
    return output_path


def burn_subtitles(
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
) -> Path:
    """Burn ASS subtitles into a video using ffmpeg.

    Args:
        video_path: Source video.
        subtitle_path: ASS subtitle file.
        output_path: Where to write the output.

    Returns:
        Path to the video with burned subtitles.
    """
    # Escape paths for ffmpeg filter (colons and backslashes)
    sub_escaped = str(subtitle_path).replace("\\", "/").replace(":", "\\:")

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"ass={sub_escaped}",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-c:a",
        "copy",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]

    logger.info("Burning subtitles: %s → %s", video_path.name, output_path.name)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("ffmpeg subtitle burn failed: %s", result.stderr[-300:])
        return video_path

    logger.info("Subtitles burned successfully: %s", output_path.name)
    return output_path


def get_merged_subtitle_config(config: dict[str, Any]) -> dict[str, Any]:
    """Merge style preset defaults with user-provided overrides.

    Args:
        config: Raw subtitle config dict from the model.

    Returns:
        Merged config with style preset defaults filled in.
    """
    style = config.get("style", "classic")
    preset = STYLE_PRESETS.get(style, STYLE_PRESETS["classic"]).copy()
    # User overrides take precedence
    for k, v in config.items():
        if v is not None:
            preset[k] = v
    return preset
