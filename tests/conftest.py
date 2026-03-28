"""Shared fixtures for the DemoDSL test suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from demodsl.providers.base import BrowserProvider


# ── Minimal config dicts ──────────────────────────────────────────────────────


@pytest.fixture()
def minimal_config_dict() -> dict[str, Any]:
    """Smallest valid DemoConfig as a plain dict."""
    return {"metadata": {"title": "Test Demo"}}


@pytest.fixture()
def full_config_dict() -> dict[str, Any]:
    """Fully populated DemoConfig as a plain dict."""
    return {
        "metadata": {
            "title": "Full Demo",
            "description": "Every field filled",
            "author": "Tester",
            "version": "1.0.0",
        },
        "voice": {
            "engine": "elevenlabs",
            "voice_id": "josh",
            "speed": 1.2,
            "pitch": 5,
        },
        "audio": {
            "background_music": {
                "file": "bg.mp3",
                "volume": 0.5,
                "ducking_mode": "heavy",
                "loop": False,
            },
            "voice_processing": {
                "normalize": True,
                "target_dbfs": -18,
                "remove_silence": True,
                "silence_threshold": -35,
                "enhance_clarity": True,
                "enhance_warmth": True,
                "noise_reduction": True,
            },
            "effects": {
                "eq_preset": "podcast",
                "reverb_preset": "small_room",
                "compression": {
                    "threshold": -15,
                    "ratio": 4.0,
                    "attack": 3,
                    "release": 40,
                },
            },
        },
        "device_rendering": {
            "device": "iphone_15_pro",
            "orientation": "landscape",
            "quality": "medium",
            "render_engine": "cycles",
            "camera_animation": "orbit_smooth",
            "lighting": "studio",
        },
        "video": {
            "intro": {
                "duration": 5.0,
                "type": "fade_in",
                "text": "Welcome",
                "subtitle": "Sub",
                "font_size": 80,
                "font_color": "#FF0000",
                "background_color": "#000000",
            },
            "transitions": {"type": "slide", "duration": 0.8},
            "watermark": {
                "image": "logo.png",
                "position": "top_left",
                "opacity": 0.5,
                "size": 200,
            },
            "outro": {
                "duration": 6.0,
                "type": "fade_out",
                "text": "Thanks",
                "subtitle": "Bye",
                "cta": "Visit us",
            },
            "optimization": {
                "target_size_mb": 50,
                "web_optimized": False,
                "compression_level": "high",
            },
        },
        "scenarios": [
            {
                "name": "Main Scenario",
                "url": "https://example.com",
                "browser": "firefox",
                "viewport": {"width": 1280, "height": 720},
                "steps": [
                    {
                        "action": "navigate",
                        "url": "https://example.com",
                        "narration": "Opening website",
                        "wait": 1.5,
                    },
                    {
                        "action": "click",
                        "locator": {"type": "css", "value": "#btn"},
                        "effects": [{"type": "spotlight", "duration": 0.5, "intensity": 0.9}],
                    },
                    {
                        "action": "type",
                        "locator": {"type": "id", "value": "search"},
                        "value": "hello",
                    },
                    {
                        "action": "scroll",
                        "direction": "down",
                        "pixels": 500,
                    },
                    {
                        "action": "wait_for",
                        "locator": {"type": "xpath", "value": "//div[@id='result']"},
                        "timeout": 10.0,
                    },
                    {
                        "action": "screenshot",
                        "filename": "final.png",
                    },
                ],
            }
        ],
        "pipeline": [
            {"restore_audio": {"denoise": True}},
            {"restore_video": {"stabilize": True}},
            {"apply_effects": {}},
            {"generate_narration": {}},
            {"render_device_mockup": {}},
            {"edit_video": {}},
            {"mix_audio": {}},
            {"optimize": {"format": "mp4", "codec": "h264", "quality": "high"}},
        ],
        "output": {
            "filename": "demo.mp4",
            "directory": "output/",
            "formats": ["mp4", "webm"],
            "thumbnails": [{"timestamp": 5.0}],
            "social": [
                {
                    "platform": "youtube",
                    "resolution": "1080p",
                    "bitrate": "8000k",
                    "aspect_ratio": "16:9",
                    "max_duration": 300,
                    "max_size_mb": 500,
                }
            ],
        },
        "analytics": {
            "track_engagement": True,
            "heatmap": True,
            "click_tracking": True,
        },
    }


# ── Config file fixtures ─────────────────────────────────────────────────────


@pytest.fixture()
def sample_yaml_path(tmp_path: Path, minimal_config_dict: dict[str, Any]) -> Path:
    """Write a minimal YAML config and return the path."""
    p = tmp_path / "test.yaml"
    p.write_text(yaml.dump(minimal_config_dict))
    return p


@pytest.fixture()
def sample_json_path(tmp_path: Path, minimal_config_dict: dict[str, Any]) -> Path:
    """Write a minimal JSON config and return the path."""
    p = tmp_path / "test.json"
    p.write_text(json.dumps(minimal_config_dict))
    return p


@pytest.fixture()
def full_yaml_path(tmp_path: Path, full_config_dict: dict[str, Any]) -> Path:
    """Write a fully populated YAML config and return the path."""
    p = tmp_path / "full.yaml"
    p.write_text(yaml.dump(full_config_dict))
    return p


@pytest.fixture()
def full_json_path(tmp_path: Path, full_config_dict: dict[str, Any]) -> Path:
    """Write a fully populated JSON config and return the path."""
    p = tmp_path / "full.json"
    p.write_text(json.dumps(full_config_dict))
    return p


# ── Mock browser ──────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_browser() -> MagicMock:
    """A MagicMock implementing the BrowserProvider interface."""
    browser = MagicMock(spec=BrowserProvider)
    browser.navigate = MagicMock()
    browser.click = MagicMock()
    browser.type_text = MagicMock()
    browser.scroll = MagicMock()
    browser.wait_for = MagicMock()
    browser.screenshot = MagicMock(return_value=Path("screenshot.png"))
    browser.evaluate_js = MagicMock()
    browser.close = MagicMock(return_value=None)
    return browser
