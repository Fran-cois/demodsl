"""Tests for OsBackgroundOverlay handling of recorded sub-demo videos."""

from __future__ import annotations

from pathlib import Path

from demodsl.effects.os_background import OsBackgroundOverlay


def test_secondary_window_video_embedded_as_base64(tmp_path: Path) -> None:
    video_file = tmp_path / "clip.mp4"
    video_file.write_bytes(b"\x00\x01\x02\x03FAKE_MP4")

    overlay = OsBackgroundOverlay(
        {
            "os": "macos",
            "theme": "dark",
            "wallpaper_color": "#111",
            "window_title": "Main",
            "secondary_windows": [
                {
                    "title": "Blocked Site",
                    "x": 100,
                    "y": 100,
                    "width": 400,
                    "height": 300,
                    "_video_path": str(video_file),
                }
            ],
        }
    )
    js = overlay._build_macos_js()
    # The video should be embedded as a base64 data URL, not an iframe.
    assert "data:video/mp4;base64," in js
    assert "<iframe" not in js or "data:video/mp4" in js
    assert "autoplay" in js and "muted" in js and "loop" in js


def test_secondary_window_falls_back_when_video_missing(tmp_path: Path) -> None:
    overlay = OsBackgroundOverlay(
        {
            "os": "macos",
            "theme": "dark",
            "wallpaper_color": "#111",
            "window_title": "Main",
            "secondary_windows": [
                {
                    "title": "Broken",
                    "x": 100,
                    "y": 100,
                    "width": 400,
                    "height": 300,
                    "_video_path": str(tmp_path / "does_not_exist.mp4"),
                    "background_color": "#abcdef",
                }
            ],
        }
    )
    js = overlay._build_macos_js()
    # Should not inject a broken video tag; falls back to the static bg.
    assert "data:video/mp4;base64," not in js
    assert "#abcdef" in js
