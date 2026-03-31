"""Tests for Blender bridge, provider, DeviceRendering model, and device manifest."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from demodsl.models import DeviceRendering
from demodsl.providers.blender_bridge import (
    build_blender_params,
    check_blender_available,
    render_via_blender,
)

# Path to the device manifest
_MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent / "blender" / "devices" / "manifest.json"
)


# ── Device manifest validation ────────────────────────────────────────────────

_REQUIRED_KEYS = {
    "category",
    "label",
    "body_mm",
    "screen_mm",
    "screen_px",
    "corner_radius_mm",
    "bezel_mm",
    "notch",
    "material",
    "orientations",
    "blend_file",
}


class TestDeviceManifest:
    @pytest.fixture()
    def manifest(self) -> dict:
        assert _MANIFEST_PATH.exists(), f"manifest not found at {_MANIFEST_PATH}"
        with open(_MANIFEST_PATH) as fh:
            data = json.load(fh)
        return data.get("devices", {})

    def test_manifest_loads(self, manifest: dict) -> None:
        assert len(manifest) >= 12, f"expected ≥12 devices, got {len(manifest)}"

    @pytest.mark.parametrize(
        "device_id",
        [
            "iphone_16_pro_max",
            "iphone_16_pro",
            "iphone_16",
            "iphone_15_pro",
            "pixel_9_pro",
            "galaxy_s25_ultra",
            "pixel_8",
            "galaxy_s25",
            "ipad_pro_13",
            "macbook_pro_16",
            "surface_pro_11",
            "desktop_browser",
        ],
    )
    def test_device_present(self, manifest: dict, device_id: str) -> None:
        assert device_id in manifest, f"{device_id} missing from manifest"

    @pytest.mark.parametrize(
        "device_id",
        [
            "iphone_16_pro_max",
            "iphone_15_pro",
            "pixel_9_pro",
            "galaxy_s25_ultra",
            "ipad_pro_13",
            "macbook_pro_16",
            "desktop_browser",
        ],
    )
    def test_device_has_required_keys(self, manifest: dict, device_id: str) -> None:
        spec = manifest[device_id]
        missing = _REQUIRED_KEYS - set(spec.keys())
        assert not missing, f"{device_id} missing keys: {missing}"

    def test_body_dimensions_positive(self, manifest: dict) -> None:
        for did, spec in manifest.items():
            for dim in ("w", "h", "d"):
                assert spec["body_mm"][dim] > 0, f"{did} body_mm.{dim} not positive"

    def test_screen_smaller_than_body(self, manifest: dict) -> None:
        for did, spec in manifest.items():
            assert spec["screen_mm"]["w"] < spec["body_mm"]["w"], (
                f"{did} screen_mm.w >= body_mm.w"
            )
            assert spec["screen_mm"]["h"] < spec["body_mm"]["h"], (
                f"{did} screen_mm.h >= body_mm.h"
            )

    def test_categories_valid(self, manifest: dict) -> None:
        valid = {"phone", "tablet", "laptop", "monitor"}
        for did, spec in manifest.items():
            assert spec["category"] in valid, f"{did} has invalid category"

    def test_materials_valid(self, manifest: dict) -> None:
        valid = {"titanium", "aluminum", "plastic", "glass"}
        for did, spec in manifest.items():
            assert spec["material"] in valid, f"{did} has invalid material"

    def test_notch_valid(self, manifest: dict) -> None:
        valid = {"dynamic_island", "punch_hole", "notch_top", "none"}
        for did, spec in manifest.items():
            assert spec["notch"] in valid, f"{did} has invalid notch type"

    def test_laptop_has_hinge_angle(self, manifest: dict) -> None:
        for did, spec in manifest.items():
            if spec["category"] == "laptop":
                assert "hinge_angle_deg" in spec, (
                    f"{did} laptop missing hinge_angle_deg"
                )

    def test_all_devices_accepted_by_bridge(self, manifest: dict) -> None:
        """Every manifest device can be passed to build_blender_params."""
        for device_id in manifest:
            params = build_blender_params(
                video_path=Path("/tmp/v.mp4"),
                device=device_id,
            )
            assert params["device"] == device_id


# ── DeviceRendering model — new fields ────────────────────────────────────────


class TestDeviceRenderingNewFields:
    def test_new_defaults(self) -> None:
        dr = DeviceRendering()
        assert dr.background_preset == "solid"
        assert dr.background_color == "#1a1a1a"
        assert dr.background_gradient_color is None
        assert dr.background_hdri is None
        assert dr.camera_distance == 1.5
        assert dr.camera_height == 0.0
        assert dr.rotation_speed == 1.0
        assert dr.shadow is True

    def test_custom_values(self) -> None:
        dr = DeviceRendering(
            background_preset="gradient",
            background_color="#FF0000",
            background_gradient_color="#00FF00",
            camera_distance=3.0,
            camera_height=1.5,
            rotation_speed=2.0,
            shadow=False,
        )
        assert dr.background_preset == "gradient"
        assert dr.background_color == "#FF0000"
        assert dr.background_gradient_color == "#00FF00"
        assert dr.camera_distance == 3.0
        assert dr.camera_height == 1.5
        assert dr.rotation_speed == 2.0
        assert dr.shadow is False

    def test_invalid_background_color(self) -> None:
        with pytest.raises(ValidationError):
            DeviceRendering(background_color="not-a-color")

    def test_invalid_gradient_color(self) -> None:
        with pytest.raises(ValidationError):
            DeviceRendering(background_gradient_color="not-a-color")

    def test_invalid_background_preset(self) -> None:
        with pytest.raises(ValidationError, match="Invalid background_preset"):
            DeviceRendering(background_preset="neon_rainbow")

    @pytest.mark.parametrize(
        "preset",
        [
            "solid",
            "gradient",
            "studio_floor",
            "spotlight",
            "warm_gradient",
            "cool_gradient",
            "sunset",
            "abstract_noise",
        ],
    )
    def test_all_presets_accepted(self, preset: str) -> None:
        dr = DeviceRendering(background_preset=preset)
        assert dr.background_preset == preset

    def test_camera_distance_bounds(self) -> None:
        with pytest.raises(ValidationError):
            DeviceRendering(camera_distance=0)  # gt=0
        with pytest.raises(ValidationError):
            DeviceRendering(camera_distance=11)  # le=10.0

    def test_rotation_speed_bounds(self) -> None:
        with pytest.raises(ValidationError):
            DeviceRendering(rotation_speed=0)  # gt=0
        with pytest.raises(ValidationError):
            DeviceRendering(rotation_speed=6)  # le=5.0

    def test_hdri_path_traversal_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DeviceRendering(background_hdri="../../etc/passwd")


# ── check_blender_available ───────────────────────────────────────────────────


class TestCheckBlenderAvailable:
    def test_blender_missing(self) -> None:
        with patch("demodsl.providers.blender_bridge._find_blender", return_value=None):
            assert check_blender_available() is False

    def test_script_missing(self) -> None:
        with (
            patch(
                "demodsl.providers.blender_bridge.shutil.which",
                return_value="/usr/bin/blender",
            ),
            patch(
                "demodsl.providers.blender_bridge._BLENDER_DIR",
                Path("/nonexistent"),
            ),
        ):
            assert check_blender_available() is False

    def test_all_present(self, tmp_path: Path) -> None:
        script = tmp_path / "render_device.py"
        script.touch()
        with (
            patch(
                "demodsl.providers.blender_bridge.shutil.which",
                return_value="/usr/bin/blender",
            ),
            patch("demodsl.providers.blender_bridge._BLENDER_DIR", tmp_path),
        ):
            assert check_blender_available() is True


# ── build_blender_params ──────────────────────────────────────────────────────


class TestBuildBlenderParams:
    def test_default_params(self, tmp_path: Path) -> None:
        video = tmp_path / "recording.mp4"
        video.touch()
        params = build_blender_params(video_path=video)
        assert params["video_path"] == str(video)
        assert params["device"] == "iphone_15_pro"
        assert params["orientation"] == "portrait"
        assert params["render_engine"] == "eevee"
        assert params["camera_animation"] == "orbit_smooth"
        assert params["lighting"] == "studio"
        assert params["background_preset"] == "solid"
        assert params["background_color"] == "#1a1a1a"
        assert params["background_gradient_color"] is None
        assert params["shadow"] is True
        # high quality defaults
        assert params["resolution_percentage"] == 100
        assert params["samples"] == 128

    def test_low_quality(self, tmp_path: Path) -> None:
        params = build_blender_params(
            video_path=tmp_path / "v.mp4",
            quality="low",
        )
        assert params["resolution_percentage"] == 50
        assert params["samples"] == 16

    def test_custom_fields(self, tmp_path: Path) -> None:
        params = build_blender_params(
            video_path=tmp_path / "v.mp4",
            device="pixel_8",
            orientation="landscape",
            render_engine="cycles",
            background_preset="gradient",
            background_gradient_color="#AABBCC",
            camera_distance=3.0,
            camera_height=1.0,
            rotation_speed=2.5,
            shadow=False,
            background_hdri="/tmp/sky.hdr",
        )
        assert params["device"] == "pixel_8"
        assert params["orientation"] == "landscape"
        assert params["render_engine"] == "cycles"
        assert params["background_preset"] == "gradient"
        assert params["background_gradient_color"] == "#AABBCC"
        assert params["camera_distance"] == 3.0
        assert params["camera_height"] == 1.0
        assert params["rotation_speed"] == 2.5
        assert params["shadow"] is False
        assert params["background_hdri"] == "/tmp/sky.hdr"


# ── render_via_blender ────────────────────────────────────────────────────────


class TestRenderViaBlender:
    def test_unavailable_raises(self, tmp_path: Path) -> None:
        with patch(
            "demodsl.providers.blender_bridge.check_blender_available",
            return_value=False,
        ):
            with pytest.raises(RuntimeError, match="not available"):
                render_via_blender(
                    {"video_path": "/tmp/v.mp4"},
                    tmp_path / "out.mp4",
                )

    def test_successful_render(self, tmp_path: Path) -> None:
        output = tmp_path / "out.mp4"

        def fake_run(cmd, **kwargs):
            # Simulate Blender creating the output file
            output.write_bytes(b"fake-mp4")
            return MagicMock(returncode=0, stdout="OK", stderr="")

        with (
            patch(
                "demodsl.providers.blender_bridge.check_blender_available",
                return_value=True,
            ),
            patch(
                "demodsl.providers.blender_bridge.subprocess.run", side_effect=fake_run
            ),
        ):
            result = render_via_blender({"video_path": "/tmp/v.mp4"}, output)
            assert result == output
            assert output.exists()

    def test_nonzero_exit_raises(self, tmp_path: Path) -> None:
        mock_result = MagicMock(returncode=1, stdout="", stderr="Segfault")
        with (
            patch(
                "demodsl.providers.blender_bridge.check_blender_available",
                return_value=True,
            ),
            patch(
                "demodsl.providers.blender_bridge.subprocess.run",
                return_value=mock_result,
            ),
        ):
            with pytest.raises(RuntimeError, match="Blender render failed"):
                render_via_blender(
                    {"video_path": "/tmp/v.mp4"},
                    tmp_path / "out.mp4",
                )

    def test_no_output_file_raises(self, tmp_path: Path) -> None:
        mock_result = MagicMock(returncode=0, stdout="OK", stderr="")
        with (
            patch(
                "demodsl.providers.blender_bridge.check_blender_available",
                return_value=True,
            ),
            patch(
                "demodsl.providers.blender_bridge.subprocess.run",
                return_value=mock_result,
            ),
        ):
            with pytest.raises(RuntimeError, match="produced no output"):
                render_via_blender(
                    {"video_path": "/tmp/v.mp4"},
                    tmp_path / "out.mp4",
                )

    def test_temp_params_cleaned_up(self, tmp_path: Path) -> None:
        """The temp JSON params file should be deleted after render."""
        output = tmp_path / "out.mp4"

        created_files: list[Path] = []

        def spy_run(cmd, **kwargs):
            # Find the --params arg to track the temp file
            if "--params" in cmd:
                idx = cmd.index("--params") + 1
                created_files.append(Path(cmd[idx]))
            output.write_bytes(b"data")
            return MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch(
                "demodsl.providers.blender_bridge.check_blender_available",
                return_value=True,
            ),
            patch(
                "demodsl.providers.blender_bridge.subprocess.run", side_effect=spy_run
            ),
        ):
            render_via_blender({"video_path": "/tmp/v.mp4"}, output)

        assert len(created_files) == 1
        assert not created_files[0].exists(), "temp params file should be cleaned up"


# ── HeadlessBlenderProvider ───────────────────────────────────────────────────


class TestHeadlessBlenderProvider:
    def test_registered_in_factory(self) -> None:
        import demodsl.providers.blender  # noqa: F401 — registration side effect

        from demodsl.providers.base import BlenderProviderFactory

        provider = BlenderProviderFactory.create("headless")
        assert provider is not None

    def test_render_delegates_to_bridge(self, tmp_path: Path) -> None:
        import demodsl.providers.blender  # noqa: F401

        from demodsl.providers.base import BlenderProviderFactory

        provider = BlenderProviderFactory.create("headless")
        config = DeviceRendering()
        video = tmp_path / "input.mp4"
        video.touch()
        output = tmp_path / "output.mp4"

        with patch(
            "demodsl.providers.blender.render_via_blender",
            return_value=output,
        ) as mock_render:
            result = provider.render(video, config, output)
            assert result == output
            mock_render.assert_called_once()
            call_params = mock_render.call_args[0][0]
            assert call_params["device"] == "iphone_15_pro"
            assert call_params["render_engine"] == "eevee"

    def test_render_rejects_wrong_config_type(self, tmp_path: Path) -> None:
        import demodsl.providers.blender  # noqa: F401

        from demodsl.providers.base import BlenderProviderFactory

        provider = BlenderProviderFactory.create("headless")
        with pytest.raises(TypeError, match="Expected DeviceRendering"):
            provider.render(tmp_path / "v.mp4", {"not": "right"}, tmp_path / "o.mp4")


# ── Engine Pass 2.75 integration ──────────────────────────────────────────────


class TestEngineDeviceRendering:
    def test_apply_device_rendering_fallback_when_unavailable(
        self, tmp_path: Path
    ) -> None:
        """When Blender is not available, the original video is returned."""
        from demodsl.engine import DemoEngine

        video = tmp_path / "raw.mp4"
        video.write_bytes(b"raw-video")
        config = DeviceRendering()

        with patch(
            "demodsl.providers.blender.check_blender_available",
            return_value=False,
        ):
            result = DemoEngine._apply_device_rendering(
                video, config, tmp_path / "rendered.mp4"
            )
        assert result == video

    def test_apply_device_rendering_fallback_on_error(self, tmp_path: Path) -> None:
        """On unexpected errors, fallback to raw video."""
        from demodsl.engine import DemoEngine

        video = tmp_path / "raw.mp4"
        video.write_bytes(b"raw-video")
        config = DeviceRendering()

        with (
            patch(
                "demodsl.providers.blender.render_via_blender",
                side_effect=RuntimeError("boom"),
            ),
            patch(
                "demodsl.providers.blender.check_blender_available",
                return_value=True,
            ),
        ):
            result = DemoEngine._apply_device_rendering(
                video, config, tmp_path / "rendered.mp4"
            )
        assert result == video
