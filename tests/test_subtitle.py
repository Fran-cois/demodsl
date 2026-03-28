"""Tests for demodsl.effects.subtitle — subtitle generation and styles."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.effects.subtitle import (
    SPEED_PRESETS,
    STYLE_PRESETS,
    build_subtitle_entries,
    _format_ass_time,
    _hex_to_ass_color,
    _hex_to_ass_alpha_color,
    _pick_emoji,
    burn_subtitles,
    generate_ass_subtitle,
    get_merged_subtitle_config,
)


class TestHexToAssColor:
    def test_white(self) -> None:
        assert _hex_to_ass_color("#FFFFFF") == "&H00FFFFFF&"

    def test_red(self) -> None:
        assert _hex_to_ass_color("#FF0000") == "&H000000FF&"

    def test_blue(self) -> None:
        assert _hex_to_ass_color("#0000FF") == "&H00FF0000&"

    def test_strips_hash(self) -> None:
        assert _hex_to_ass_color("00FF00") == "&H0000FF00&"


class TestHexToAssAlphaColor:
    def test_rgba_opaque(self) -> None:
        color, alpha = _hex_to_ass_alpha_color("rgba(0,0,0,1.0)")
        assert color == "&H00000000&"
        assert alpha == "&H00&"

    def test_rgba_half_transparent(self) -> None:
        color, alpha = _hex_to_ass_alpha_color("rgba(255,255,255,0.5)")
        assert "&H" in alpha

    def test_hex_fallback(self) -> None:
        color, alpha = _hex_to_ass_alpha_color("#FF0000")
        assert color == "&H000000FF&"
        assert alpha == "&H00&"


class TestFormatAssTime:
    def test_zero(self) -> None:
        assert _format_ass_time(0.0) == "0:00:00.00"

    def test_simple_seconds(self) -> None:
        assert _format_ass_time(5.5) == "0:00:05.50"

    def test_minutes(self) -> None:
        assert _format_ass_time(125.0) == "0:02:05.00"

    def test_hours(self) -> None:
        assert _format_ass_time(3661.0) == "1:01:01.00"


class TestBuildSubtitleEntries:
    def test_basic_entries(self) -> None:
        texts = {0: "Hello world", 1: "Second step here"}
        timestamps = [0.0, 5.0]
        durations = {0: 3.0, 1: 4.0}

        entries = build_subtitle_entries(
            texts,
            timestamps,
            durations,
            speed_wps=2.5,
            max_words_per_line=8,
        )
        assert len(entries) == 2
        assert entries[0]["text"] == "Hello world"
        assert entries[0]["start"] == 0.0
        assert entries[1]["text"] == "Second step here"

    def test_line_splitting(self) -> None:
        long_text = "one two three four five six seven eight nine ten"
        texts = {0: long_text}
        timestamps = [0.0]
        durations = {0: 10.0}

        entries = build_subtitle_entries(
            texts,
            timestamps,
            durations,
            speed_wps=2.5,
            max_words_per_line=4,
        )
        # 10 words / 4 per line = 3 lines
        assert len(entries) == 3
        assert entries[0]["text"] == "one two three four"
        assert entries[1]["text"] == "five six seven eight"
        assert entries[2]["text"] == "nine ten"

    def test_word_level_timing(self) -> None:
        texts = {0: "Hello World"}
        timestamps = [0.0]
        durations = {0: 2.0}

        entries = build_subtitle_entries(
            texts,
            timestamps,
            durations,
            speed_wps=2.5,
        )
        assert len(entries) == 1
        words = entries[0]["words"]
        assert len(words) == 2
        assert words[0]["word"] == "Hello"
        assert words[1]["word"] == "World"
        assert words[0]["start"] == 0.0
        assert words[0]["end"] == pytest.approx(1.0)
        assert words[1]["start"] == pytest.approx(1.0)
        assert words[1]["end"] == pytest.approx(2.0)

    def test_empty_narration(self) -> None:
        entries = build_subtitle_entries({}, [0.0], {}, speed_wps=2.5)
        assert entries == []

    def test_step_beyond_timestamps(self) -> None:
        texts = {5: "Out of range"}
        timestamps = [0.0, 1.0]
        durations = {5: 3.0}

        entries = build_subtitle_entries(texts, timestamps, durations, speed_wps=2.5)
        assert entries == []


class TestGenerateAssSubtitle:
    def test_classic_style(self, tmp_path: Path) -> None:
        entries = [
            {
                "start": 0.0,
                "end": 3.0,
                "text": "Hello World",
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 1.5},
                    {"word": "World", "start": 1.5, "end": 3.0},
                ],
            },
        ]
        config = {
            "style": "classic",
            "font_size": 42,
            "font_family": "Arial",
            "font_color": "#FFFFFF",
            "background_color": "rgba(0,0,0,0.6)",
            "position": "bottom",
        }
        out = tmp_path / "test.ass"
        result = generate_ass_subtitle(entries, config, out)
        assert result.exists()
        content = result.read_text()
        assert "Hello World" in content
        assert "[Script Info]" in content
        assert "Dialogue:" in content

    def test_tiktok_style_word_by_word(self, tmp_path: Path) -> None:
        entries = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Big bold text",
                "words": [
                    {"word": "Big", "start": 0.0, "end": 0.67},
                    {"word": "bold", "start": 0.67, "end": 1.33},
                    {"word": "text", "start": 1.33, "end": 2.0},
                ],
            },
        ]
        config = {
            "style": "tiktok",
            "font_size": 64,
            "font_color": "#FFFFFF",
            "highlight_color": "#FFD700",
            "background_color": "rgba(0,0,0,0)",
            "position": "center",
        }
        out = tmp_path / "test.ass"
        result = generate_ass_subtitle(entries, config, out)
        content = result.read_text()
        # TikTok shows each word separately
        assert content.count("Dialogue:") == 3

    def test_karaoke_style(self, tmp_path: Path) -> None:
        entries = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Karaoke test",
                "words": [
                    {"word": "Karaoke", "start": 0.0, "end": 1.0},
                    {"word": "test", "start": 1.0, "end": 2.0},
                ],
            },
        ]
        config = {
            "style": "karaoke",
            "font_size": 52,
            "font_color": "#AAAAAA",
            "highlight_color": "#FF4444",
            "background_color": "rgba(0,0,0,0.5)",
            "position": "bottom",
        }
        out = tmp_path / "test.ass"
        result = generate_ass_subtitle(entries, config, out)
        content = result.read_text()
        assert "\\kf" in content  # karaoke fill tag

    def test_color_style(self, tmp_path: Path) -> None:
        entries = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Color words",
                "words": [
                    {"word": "Color", "start": 0.0, "end": 1.0},
                    {"word": "words", "start": 1.0, "end": 2.0},
                ],
            },
        ]
        config = {
            "style": "color",
            "font_size": 48,
            "font_color": "#FFFFFF",
            "highlight_color": "#00FF88",
            "background_color": "rgba(0,0,0,0.4)",
            "position": "bottom",
        }
        out = tmp_path / "test.ass"
        result = generate_ass_subtitle(entries, config, out)
        content = result.read_text()
        # Color style shows full line with highlighted word, 2 words = 2 dialogues
        assert content.count("Dialogue:") == 2
        assert "\\c" in content  # color override tag

    def test_typewriter_style(self, tmp_path: Path) -> None:
        entries = [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "Hi",
                "words": [{"word": "Hi", "start": 0.0, "end": 1.0}],
            },
        ]
        config = {
            "style": "typewriter",
            "font_size": 44,
            "font_color": "#00FF00",
            "background_color": "rgba(0,0,0,0.8)",
            "position": "bottom",
        }
        out = tmp_path / "test.ass"
        result = generate_ass_subtitle(entries, config, out)
        content = result.read_text()
        # "Hi" = 2 chars = 2 dialogues
        assert content.count("Dialogue:") == 2

    def test_word_by_word_style(self, tmp_path: Path) -> None:
        entries = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Word by word",
                "words": [
                    {"word": "Word", "start": 0.0, "end": 0.67},
                    {"word": "by", "start": 0.67, "end": 1.33},
                    {"word": "word", "start": 1.33, "end": 2.0},
                ],
            },
        ]
        config = {
            "style": "word_by_word",
            "font_size": 56,
            "font_color": "#FFFFFF",
            "background_color": "rgba(0,0,0,0)",
            "position": "center",
        }
        out = tmp_path / "test.ass"
        result = generate_ass_subtitle(entries, config, out)
        content = result.read_text()
        # word_by_word uses Highlight style, each word separate
        assert content.count("Dialogue:") == 3

    def test_bounce_style(self, tmp_path: Path) -> None:
        entries = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Bounce it",
                "words": [
                    {"word": "Bounce", "start": 0.0, "end": 1.0},
                    {"word": "it", "start": 1.0, "end": 2.0},
                ],
            },
        ]
        config = {
            "style": "bounce",
            "font_size": 60,
            "font_color": "#FFFFFF",
            "highlight_color": "#FFD700",
            "background_color": "rgba(0,0,0,0)",
            "position": "center",
        }
        out = tmp_path / "test.ass"
        result = generate_ass_subtitle(entries, config, out)
        content = result.read_text()
        assert content.count("Dialogue:") == 2
        assert "\\fscx120" in content  # bounce scale animation

    def test_cinema_style(self, tmp_path: Path) -> None:
        entries = [
            {
                "start": 0.0,
                "end": 3.0,
                "text": "An elegant line",
                "words": [
                    {"word": "An", "start": 0.0, "end": 1.0},
                    {"word": "elegant", "start": 1.0, "end": 2.0},
                    {"word": "line", "start": 2.0, "end": 3.0},
                ],
            },
        ]
        config = {
            "style": "cinema",
            "font_size": 38,
            "font_color": "#F5F5DC",
            "background_color": "rgba(0,0,0,0)",
            "position": "bottom",
            "font_family": "Georgia",
        }
        out = tmp_path / "test.ass"
        result = generate_ass_subtitle(entries, config, out)
        content = result.read_text()
        assert content.count("Dialogue:") == 1
        assert "\\i1" in content  # italic tag

    def test_highlight_line_style(self, tmp_path: Path) -> None:
        entries = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Bright line",
                "words": [
                    {"word": "Bright", "start": 0.0, "end": 1.0},
                    {"word": "line", "start": 1.0, "end": 2.0},
                ],
            },
        ]
        config = {
            "style": "highlight_line",
            "font_size": 46,
            "font_color": "#888888",
            "highlight_color": "#FFFFFF",
            "background_color": "rgba(0,0,0,0.5)",
            "position": "bottom",
        }
        out = tmp_path / "test.ass"
        result = generate_ass_subtitle(entries, config, out)
        content = result.read_text()
        # highlight_line: dim + bright = 2 dialogues per entry
        assert content.count("Dialogue:") == 2

    def test_fade_word_style(self, tmp_path: Path) -> None:
        entries = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Fade in words",
                "words": [
                    {"word": "Fade", "start": 0.0, "end": 0.67},
                    {"word": "in", "start": 0.67, "end": 1.33},
                    {"word": "words", "start": 1.33, "end": 2.0},
                ],
            },
        ]
        config = {
            "style": "fade_word",
            "font_size": 50,
            "font_color": "#FFFFFF",
            "background_color": "rgba(0,0,0,0)",
            "position": "center",
        }
        out = tmp_path / "test.ass"
        result = generate_ass_subtitle(entries, config, out)
        content = result.read_text()
        assert content.count("Dialogue:") == 3
        assert "\\fad(" in content  # fade animation tag

    def test_emoji_react_style(self, tmp_path: Path) -> None:
        entries = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Click the button",
                "words": [
                    {"word": "Click", "start": 0.0, "end": 0.67},
                    {"word": "the", "start": 0.67, "end": 1.33},
                    {"word": "button", "start": 1.33, "end": 2.0},
                ],
            },
        ]
        config = {
            "style": "emoji_react",
            "font_size": 52,
            "font_color": "#FFFFFF",
            "highlight_color": "#FFD700",
            "background_color": "rgba(0,0,0,0.4)",
            "position": "bottom",
        }
        out = tmp_path / "test.ass"
        result = generate_ass_subtitle(entries, config, out)
        content = result.read_text()
        assert content.count("Dialogue:") == 1
        assert "👆" in content  # emoji for "click"


class TestBurnSubtitles:
    @patch("demodsl.effects.subtitle.subprocess")
    def test_success(self, mock_subprocess: MagicMock, tmp_path: Path) -> None:
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        video = tmp_path / "input.mp4"
        video.touch()
        sub = tmp_path / "test.ass"
        sub.touch()
        out = tmp_path / "output.mp4"

        result = burn_subtitles(video, sub, out)
        assert result == out
        mock_subprocess.run.assert_called_once()

    @patch("demodsl.effects.subtitle.subprocess")
    def test_failure_returns_original(
        self, mock_subprocess: MagicMock, tmp_path: Path
    ) -> None:
        mock_subprocess.run.return_value = MagicMock(returncode=1, stderr="error")
        video = tmp_path / "input.mp4"
        video.touch()
        sub = tmp_path / "test.ass"
        sub.touch()
        out = tmp_path / "output.mp4"

        result = burn_subtitles(video, sub, out)
        assert result == video  # falls back to original


class TestGetMergedSubtitleConfig:
    def test_classic_defaults(self) -> None:
        config = get_merged_subtitle_config({"style": "classic"})
        assert config["font_size"] == 42
        assert config["position"] == "bottom"

    def test_tiktok_defaults(self) -> None:
        config = get_merged_subtitle_config({"style": "tiktok"})
        assert config["font_size"] == 64
        assert config["position"] == "center"
        assert config["max_words_per_line"] == 3

    def test_user_override(self) -> None:
        config = get_merged_subtitle_config(
            {
                "style": "classic",
                "font_size": 72,
                "position": "top",
            }
        )
        assert config["font_size"] == 72
        assert config["position"] == "top"

    def test_unknown_style_falls_back_to_classic(self) -> None:
        config = get_merged_subtitle_config({"style": "nonexistent"})
        assert config["font_size"] == 42


class TestSpeedPresets:
    def test_all_presets_exist(self) -> None:
        for name in ("slow", "normal", "fast", "tiktok"):
            assert name in SPEED_PRESETS

    def test_speeds_are_increasing(self) -> None:
        assert SPEED_PRESETS["slow"] < SPEED_PRESETS["normal"]
        assert SPEED_PRESETS["normal"] < SPEED_PRESETS["fast"]
        assert SPEED_PRESETS["fast"] < SPEED_PRESETS["tiktok"]


class TestStylePresets:
    def test_all_styles_exist(self) -> None:
        for name in (
            "classic",
            "tiktok",
            "color",
            "word_by_word",
            "typewriter",
            "karaoke",
            "bounce",
            "cinema",
            "highlight_line",
            "fade_word",
            "emoji_react",
        ):
            assert name in STYLE_PRESETS


class TestPickEmoji:
    def test_click_keyword(self) -> None:
        assert _pick_emoji("Click the button") == "👆"

    def test_scroll_keyword(self) -> None:
        assert _pick_emoji("Scroll down to see more") == "📜"

    def test_welcome_keyword(self) -> None:
        assert _pick_emoji("Welcome to the app") == "👋"

    def test_default_emoji(self) -> None:
        assert _pick_emoji("Something random here") == "💬"

    def test_video_keyword(self) -> None:
        assert _pick_emoji("Watch the demo video") == "🎬"

    def test_install_keyword(self) -> None:
        assert _pick_emoji("Install with pip") == "📦"
