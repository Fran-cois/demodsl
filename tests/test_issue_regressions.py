"""Regression tests reproducing the reported GitHub issues.

Each class maps to one issue:

* #1 — cursor overlay: a click aborts the render with
  ``window.__demodsl_cursor_click is not a function``.
* #2 — native Playwright video is blank/white in headless mode.
* #3 — SPA renders blank unless the first step is an explicit ``navigate``.
* #4 — ``text`` locator fails on labels containing an em-dash.
* #5 — watermark burn emits a noisy error when ffmpeg lacks ``drawtext``.
* #6 — camera / pointing overlays ignore the scroll offset.
* #7 — ``output.social`` is validated but never executed.
* #8 — CDP recorder's fixed 120 s ffmpeg timeout aborts long recordings.
* #9 — Remotion render has no retry; ``text`` camera targets are dropped.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demodsl.effects.cursor import CursorOverlay
from demodsl.engine import DemoEngine
from demodsl.models import Locator, Viewport
from demodsl.providers.authenticated_browser import PersistentProfileBrowserProvider
from demodsl.providers.browser import PlaywrightBrowserProvider

# ── Issue #1: cursor helper missing must never be fatal ──────────────────────


class TestIssue1CursorClickNonFatal:
    """A missing ``window.__demodsl_cursor_click`` must not kill the render."""

    def test_trigger_click_does_not_raise_when_helper_missing(self) -> None:
        overlay = CursorOverlay({"click_effect": "ripple", "smooth": 0.0})

        def evaluate_js(js: str):
            # Simulates a page that lost the injected helpers after a
            # navigation / SPA re-render: probing says "not a function"
            # and any call to it throws.
            if "typeof" in js:
                return False
            raise RuntimeError(
                "Page.evaluate: TypeError: window.__demodsl_cursor_click is not a function"
            )

        with patch("demodsl.effects.cursor.time"):
            overlay.trigger_click(evaluate_js)  # must NOT raise

    def test_move_to_does_not_raise_when_helper_missing(self) -> None:
        overlay = CursorOverlay({"smooth": 0.0})

        def evaluate_js(js: str):
            if "typeof" in js:
                return False
            raise RuntimeError(
                "Page.evaluate: TypeError: window.__demodsl_cursor_move is not a function"
            )

        with patch("demodsl.effects.cursor.time"):
            overlay.move_to(evaluate_js, 10, 20)  # must NOT raise

    def test_trigger_click_reinjects_when_helper_missing(self) -> None:
        overlay = CursorOverlay({"click_effect": "ripple", "smooth": 0.0})
        calls: list[str] = []

        def evaluate_js(js: str):
            calls.append(js)
            if "typeof" in js:
                return False
            return None

        with patch("demodsl.effects.cursor.time"):
            overlay.trigger_click(evaluate_js)

        # The overlay must re-inject itself before firing the click effect.
        assert any("__demodsl_cursor_style" in js for js in calls)

    def test_call_is_guarded_in_js(self) -> None:
        """Even the direct call must be defensive on the JS side."""
        overlay = CursorOverlay({"click_effect": "ripple", "smooth": 0.0})
        mock_eval = MagicMock(return_value=True)

        with patch("demodsl.effects.cursor.time"):
            overlay.trigger_click(mock_eval)

        last_js = mock_eval.call_args.args[0]
        assert "typeof" in last_js
        assert "__demodsl_cursor_click" in last_js


# ── Issue #2: blank native video when headless ───────────────────────────────


class TestIssue2HeadlessNativeVideo:
    """``record: playwright`` + ``headless: true`` records a blank track."""

    def _launch(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, auth: dict):
        monkeypatch.delenv("DEMODSL_RECORD", raising=False)
        monkeypatch.delenv("DEMODSL_ALLOW_HEADLESS_VIDEO", raising=False)
        monkeypatch.setenv("DEMODSL_USER_DATA_DIR", str(tmp_path / "profile"))
        provider = PersistentProfileBrowserProvider()
        provider.set_auth_config(auth)
        mock_pw = MagicMock()
        mock_context = MagicMock()
        mock_context.pages = [MagicMock()]
        mock_pw.chromium.launch_persistent_context.return_value = mock_context

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            provider.launch_without_recording("chrome", Viewport(width=1280, height=720))

        return provider, mock_pw.chromium.launch_persistent_context.call_args

    def test_headless_disables_native_video(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        provider, call = self._launch(
            monkeypatch, tmp_path, {"record": "playwright", "headless": True}
        )
        # Native video must be disabled (falls back to the CDP recorder)
        # instead of silently producing a blank .webm.
        assert provider._native_video is False
        assert "record_video_dir" not in call.kwargs

    def test_headed_keeps_native_video(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        provider, call = self._launch(
            monkeypatch, tmp_path, {"record": "playwright", "headless": False}
        )
        assert provider._native_video is True
        assert "record_video_dir" in call.kwargs

    def test_env_escape_hatch_keeps_native_video(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("DEMODSL_ALLOW_HEADLESS_VIDEO", "1")
        monkeypatch.setenv("DEMODSL_USER_DATA_DIR", str(tmp_path / "profile"))
        provider = PersistentProfileBrowserProvider()
        provider.set_auth_config({"record": "playwright", "headless": True})
        mock_pw = MagicMock()
        mock_context = MagicMock()
        mock_context.pages = [MagicMock()]
        mock_pw.chromium.launch_persistent_context.return_value = mock_context

        with patch("playwright.sync_api.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.start.return_value = mock_pw
            provider.launch_without_recording("chrome", Viewport(width=1280, height=720))

        assert provider._native_video is True


# ── Issue #3: scenario-level url must be navigated + awaited ─────────────────


def _orchestrator(scenario_dict: dict):
    from demodsl.effects.browser_effects import register_all_browser_effects
    from demodsl.effects.post_effects import register_all_post_effects
    from demodsl.effects.registry import EffectRegistry
    from demodsl.models import DemoConfig
    from demodsl.orchestrators.scenario import ScenarioOrchestrator

    reg = EffectRegistry()
    register_all_browser_effects(reg)
    register_all_post_effects(reg)
    config = DemoConfig(metadata={"title": "T"}, scenarios=[scenario_dict])
    return ScenarioOrchestrator(config, reg), config.scenarios[0]


class TestIssue3PauseFirstScenarioNavigates:
    """A ``pause``-first scenario must still pre-navigate to ``scenario.url``."""

    def _run(self, scenario_dict: dict) -> MagicMock:
        from demodsl.orchestrators.scenario import ScenarioOrchestrator
        from demodsl.pipeline.workspace import Workspace

        orch, scenario = _orchestrator(scenario_dict)
        browser = MagicMock()
        browser.close.return_value = None
        browser._warm_url = None

        with (
            patch.object(ScenarioOrchestrator, "_make_browser", return_value=browser),
            patch.object(ScenarioOrchestrator, "_execute_step"),
            patch.object(ScenarioOrchestrator, "_sleep"),
            Workspace() as ws,
        ):
            orch._execute_scenario(scenario, ws, narration_durations={})
        return browser

    def test_pause_first_step_pre_navigates_to_scenario_url(self) -> None:
        browser = self._run(
            {
                "name": "spa",
                "url": "https://spa.example.com/app",
                "steps": [
                    {"action": "pause", "wait": 1},
                    {"action": "click", "locator": {"type": "css", "value": "#go"}},
                ],
            }
        )
        browser.navigate.assert_any_call("https://spa.example.com/app")

    def test_navigate_first_step_still_uses_step_url(self) -> None:
        browser = self._run(
            {
                "name": "static",
                "url": "https://example.com",
                "steps": [{"action": "navigate", "url": "https://example.com/page"}],
            }
        )
        browser.navigate.assert_any_call("https://example.com/page")


# ── Issue #4: text locator with an em-dash ───────────────────────────────────


def _as_python_regex(selector: str) -> re.Pattern[str]:
    """Translate a Playwright ``text=/…/i`` selector into a Python regex."""
    assert selector.startswith("text=/"), selector
    assert selector.endswith("/i"), selector
    return re.compile(selector[len("text=/") : -len("/i")], re.IGNORECASE)


class TestIssue4TextLocatorEmDash:
    def test_em_dash_label_matches(self) -> None:
        sel = PlaywrightBrowserProvider._resolve_selector(Locator(type="text", value="Foo — Bar"))
        rx = _as_python_regex(sel)
        assert rx.search("Foo — Bar")

    def test_dash_variants_and_whitespace_are_tolerated(self) -> None:
        sel = PlaywrightBrowserProvider._resolve_selector(Locator(type="text", value="Foo — Bar"))
        rx = _as_python_regex(sel)
        for dom_text in (
            "Foo - Bar",  # plain hyphen
            "Foo – Bar",  # en-dash
            "Foo\u00a0—\u00a0Bar",  # non-breaking spaces
            "  Foo   —   Bar  ",  # collapsed whitespace
            "foo — bar",  # case-insensitive
            "Prefix Foo — Bar suffix",  # substring
        ):
            assert rx.search(dom_text), dom_text

    def test_curly_apostrophe_tolerated(self) -> None:
        sel = PlaywrightBrowserProvider._resolve_selector(Locator(type="text", value="It's here"))
        rx = _as_python_regex(sel)
        assert rx.search("It\u2019s here")

    def test_regex_metacharacters_are_escaped(self) -> None:
        sel = PlaywrightBrowserProvider._resolve_selector(
            Locator(type="text", value="Save (draft)")
        )
        rx = _as_python_regex(sel)
        assert rx.search("Save (draft)")
        assert not rx.search("Save draft")

    def test_quoted_value_keeps_exact_playwright_semantics(self) -> None:
        sel = PlaywrightBrowserProvider._resolve_selector(
            Locator(type="text", value='"Exact Label"')
        )
        assert sel == 'text="Exact Label"'


# ── Issue #5: ffmpeg without the drawtext filter ─────────────────────────────


class TestIssue5WatermarkWithoutDrawtext:
    def test_skips_watermark_when_drawtext_missing(self, tmp_path: Path) -> None:
        video = tmp_path / "in.mp4"
        video.write_bytes(b"\x00" * 100)
        output = tmp_path / "out.mp4"

        with (
            patch("demodsl.engine._ffmpeg_has_drawtext", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
            result = DemoEngine._burn_watermark(video, output)

        assert result == video
        mock_run.assert_not_called()

    def test_probe_detects_missing_filter(self) -> None:
        from demodsl.engine import _ffmpeg_has_drawtext

        _ffmpeg_has_drawtext.cache_clear()
        with (
            patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Filters:\n T.. crop  V->V Crop the input video.\n"
                " ... scale V->V Scale the input video size.\n",
                stderr="",
            )
            assert _ffmpeg_has_drawtext() is False
        _ffmpeg_has_drawtext.cache_clear()

    def test_probe_detects_present_filter(self) -> None:
        from demodsl.engine import _ffmpeg_has_drawtext

        _ffmpeg_has_drawtext.cache_clear()
        with (
            patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Filters:\n TS. drawtext V->V Draw text on top of video frames.\n",
                stderr="",
            )
            assert _ffmpeg_has_drawtext() is True
        _ffmpeg_has_drawtext.cache_clear()

    def test_probe_unknown_output_assumes_available(self) -> None:
        """An unparsable probe must not disable the watermark."""
        from demodsl.engine import _ffmpeg_has_drawtext

        _ffmpeg_has_drawtext.cache_clear()
        with (
            patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
            assert _ffmpeg_has_drawtext() is True
        _ffmpeg_has_drawtext.cache_clear()


# ── Issue #6: viewport coords without scroll offset ──────────────────────────


class TestIssue6ScrollOffsetCoordinates:
    """Camera + pointing overlays must work in PAGE coords, not viewport."""

    def _camera_js(self, target=None, **kw) -> list[str]:
        from demodsl.commands import CameraCommand
        from demodsl.models import CameraMove, Step

        browser = MagicMock()
        # Mirror the real provider default: no simulated operator attached.
        browser.humanize = None
        move = CameraMove(target=target, duration=0.0, hold=0.0, **kw)
        with patch("time.sleep"):
            CameraCommand().execute(browser, Step(action="camera", camera=move))
        return [c.args[0] for c in browser.evaluate_js.call_args_list]

    def _effect_js(self, effect, params: dict) -> str:
        mock_eval = MagicMock()
        effect.inject(mock_eval, params)
        return "\n".join(str(c.args[0]) for c in mock_eval.call_args_list)

    def test_locator_origin_is_page_relative(self) -> None:
        bootstrap = self._camera_js(target=Locator(type="css", value="#hero"), zoom=1.5)[0]
        # resolveLocator must add the scroll offsets: transform-origin is
        # expressed in the page coordinate space of <html>.
        assert "window.scrollX" in bootstrap
        assert "window.scrollY" in bootstrap

    def test_normalized_target_origin_is_page_relative(self) -> None:
        scripts = self._camera_js(zoom=2.0, target_x=0.5, target_y=0.5)
        apply_js = scripts[-1]
        assert "window.scrollX" in apply_js
        assert "window.scrollY" in apply_js

    def test_annotation_overlay_uses_absolute_page_coords(self) -> None:
        from demodsl.effects.browser.animated_annotation import AnimatedAnnotationEffect

        js = self._effect_js(AnimatedAnnotationEffect(), {"target_x": 0.5, "target_y": 0.5})
        # position:fixed breaks under the camera transform (the transform
        # establishes a containing block) and ignores the scroll offset.
        assert "position:fixed" not in js.replace(" ", "")
        assert "position:absolute" in js.replace(" ", "")
        assert "window.scrollX" in js
        assert "window.scrollY" in js

    def test_callout_arrow_uses_absolute_page_coords(self) -> None:
        from demodsl.effects.browser.callout_arrow import CalloutArrowEffect

        js = self._effect_js(CalloutArrowEffect(), {"target_x": 0.5, "target_y": 0.5})
        assert "position:fixed" not in js.replace(" ", "")
        assert "position:absolute" in js.replace(" ", "")
        assert "window.scrollX" in js
        assert "window.scrollY" in js


# ── Issue #7: output.social validated but never executed ─────────────────────


class TestIssue7SocialExportIsExecuted:
    def _engine(self, social: list[dict] | None, tmp_path: Path) -> DemoEngine:
        from demodsl.models import DemoConfig, Metadata

        engine = DemoEngine.__new__(DemoEngine)
        output: dict = {"filename": "demo.mp4"}
        if social is not None:
            output["social"] = social
        engine.config = DemoConfig(metadata=Metadata(title="T"), output=output)
        engine._output_dir = tmp_path
        engine._export = MagicMock()
        engine._post = MagicMock(vertical_composition=None)
        return engine

    def test_engine_run_invokes_export_social(self, tmp_path: Path) -> None:
        """``output.social`` must actually reach ``export_social``."""
        engine = self._engine([{"platform": "tiktok", "max_duration": 60}], tmp_path)
        engine._export.export_social.return_value = [tmp_path / "demo_tiktok.mp4"]

        results = engine._run_social_exports(tmp_path / "demo.mp4", None)

        engine._export.export_social.assert_called_once()
        assert results == [tmp_path / "demo_tiktok.mp4"]

    def test_no_social_config_is_a_no_op(self, tmp_path: Path) -> None:
        engine = self._engine(None, tmp_path)
        assert engine._run_social_exports(tmp_path / "demo.mp4", None) == []
        engine._export.export_social.assert_not_called()

    def test_social_failure_never_fails_the_render(self, tmp_path: Path) -> None:
        engine = self._engine([{"platform": "tiktok"}], tmp_path)
        engine._export.export_social.side_effect = RuntimeError("ffmpeg exploded")

        # Must swallow the error: a social export is a bonus, not the render.
        assert engine._run_social_exports(tmp_path / "demo.mp4", None) == []

    def test_run_calls_the_social_hook(self) -> None:
        """Guard against the hook being dropped from ``run()`` again."""
        assert "_run_social_exports" in DemoEngine.run.__code__.co_names

    def test_export_social_produces_platform_file(self, tmp_path: Path) -> None:
        from demodsl.models import DemoConfig, Metadata
        from demodsl.orchestrators.export import ExportOrchestrator

        config = DemoConfig(
            metadata=Metadata(title="Test"),
            output={
                "filename": "demo.mp4",
                "social": [{"platform": "tiktok", "max_duration": 60}],
            },
        )
        orch = ExportOrchestrator(config)
        source = tmp_path / "demo.mp4"
        source.write_bytes(b"\x00" * 100)

        with (
            patch("subprocess.run") as mock_run,
            patch.object(ExportOrchestrator, "verify_video", return_value=True),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            results = orch.export_social(source, tmp_path)

        assert [p.name for p in results] == ["demo_tiktok.mp4"]
        cmd = mock_run.call_args.args[0]
        assert "-t" in cmd and "60" in cmd


# ── Issue #8: fixed 120 s ffmpeg timeout in the CDP recorder ─────────────────


class TestIssue8AssembleTimeoutScalesWithDuration:
    def _assemble(self, tmp_path: Path, *, elapsed: float, frames: int = 120):
        from demodsl.providers.browser import _RawCDPRecorder

        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()
        rec = _RawCDPRecorder(9222, frame_dir, {"width": 1920, "height": 1080}, fps=30)
        rec._frame_count = frames
        rec._start_time = 0.0
        rec._end_time = elapsed

        out = tmp_path / "out.mp4"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            out.write_bytes(b"\x00" * 10)
            rec.assemble(out)
        return mock_run.call_args.kwargs["timeout"]

    def test_long_recording_gets_a_generous_timeout(self, tmp_path: Path) -> None:
        # A 3-minute recording used to die on the fixed 120 s timeout.
        timeout = self._assemble(tmp_path, elapsed=180.0)
        assert timeout > 120
        assert timeout >= 180 * 6

    def test_short_recording_keeps_a_floor(self, tmp_path: Path) -> None:
        timeout = self._assemble(tmp_path, elapsed=5.0)
        assert timeout >= 300


# ── Issue #9: Remotion retry + text camera targets ───────────────────────────


class TestIssue9RemotionRetry:
    def test_retries_once_on_transient_failure(self, tmp_path: Path) -> None:
        from demodsl.providers import remotion_bridge

        output = tmp_path / "out.mp4"
        transient = MagicMock(
            returncode=1,
            stdout="",
            stderr="Timeout (30000ms) exceeded rendering the component at frame 42",
        )
        success = MagicMock(returncode=0, stdout="", stderr="")
        attempts = [transient, success]

        def fake_run(cmd, **kwargs):
            res = attempts.pop(0)
            if res.returncode == 0:
                output.write_bytes(b"\x00" * 10)
            return res

        with patch("subprocess.run", side_effect=fake_run) as mock_run:
            result = remotion_bridge.render_via_remotion({"segments": []}, output)

        assert result == output
        assert mock_run.call_count == 2

    def test_raises_after_two_failures(self, tmp_path: Path) -> None:
        from demodsl.providers import remotion_bridge

        output = tmp_path / "out.mp4"
        failure = MagicMock(returncode=1, stdout="", stderr="boom")

        with patch("subprocess.run", return_value=failure) as mock_run:
            with pytest.raises(RuntimeError, match="Remotion render failed"):
                remotion_bridge.render_via_remotion({"segments": []}, output)

        assert mock_run.call_count == 2

    def test_missing_output_keeps_its_own_error(self, tmp_path: Path) -> None:
        """A clean exit with no file must not be masked by the retry loop."""
        from demodsl.providers import remotion_bridge

        output = tmp_path / "out.mp4"
        clean_but_empty = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=clean_but_empty) as mock_run:
            with pytest.raises(RuntimeError, match="produced no output"):
                remotion_bridge.render_via_remotion({"segments": []}, output)

        assert mock_run.call_count == 2


class TestIssue9TextCameraTarget:
    """`camera.target` of type ``text``/``xpath`` must not be silently dropped."""

    def _origin_js(self, locator: Locator) -> str | None:
        from demodsl.commands import _camera_origin_js

        return _camera_origin_js(locator)

    def test_text_target_is_resolved(self) -> None:
        js = self._origin_js(Locator(type="text", value="Foo — Bar"))
        assert js is not None
        assert "resolveText" in js

    def test_text_target_uses_the_lenient_pattern(self) -> None:
        from demodsl.providers.browser import _text_pattern

        js = self._origin_js(Locator(type="text", value="Foo — Bar"))
        assert js is not None
        # Same normalization as the text locator: a hyphen in the DOM must
        # still match an em-dash in the config.
        pattern = _text_pattern("Foo — Bar")
        rx = re.compile(pattern, re.IGNORECASE)
        assert rx.search("Foo - Bar")
        assert json_escaped(pattern) in js

    def test_xpath_target_is_resolved(self) -> None:
        js = self._origin_js(Locator(type="xpath", value="//button[@id='go']"))
        assert js is not None
        assert "resolveXPath" in js

    def test_css_target_still_uses_query_selector(self) -> None:
        js = self._origin_js(Locator(type="css", value="#hero"))
        assert js is not None
        assert "resolveLocator" in js

    def test_bootstrap_exposes_the_resolvers(self) -> None:
        from demodsl.commands import _CAMERA_BOOTSTRAP_JS

        assert "resolveText:" in _CAMERA_BOOTSTRAP_JS
        assert "resolveXPath:" in _CAMERA_BOOTSTRAP_JS
        assert "XPathResult.FIRST_ORDERED_NODE_TYPE" in _CAMERA_BOOTSTRAP_JS

    def test_camera_command_emits_text_resolution(self) -> None:
        from demodsl.commands import CameraCommand
        from demodsl.models import CameraMove, Step

        browser = MagicMock()
        # Mirror the real provider default: no simulated operator attached.
        browser.humanize = None
        move = CameraMove(
            zoom=1.6,
            target=Locator(type="text", value="Pricing"),
            duration=0.0,
            hold=0.0,
        )
        with patch("time.sleep"):
            CameraCommand().execute(browser, Step(action="camera", camera=move))

        scripts = [c.args[0] for c in browser.evaluate_js.call_args_list]
        assert any("resolveText" in s for s in scripts), (
            "a text camera target degraded to a zoom without a focus point"
        )


def json_escaped(value: str) -> str:
    import json

    return json.dumps(value)[1:-1]


# ── Case-insensitive filesystems: `/library` must not match `/Library` ───────


class TestProjectRootIsCaseExact:
    """A lowercase ``library`` lookup must never match a system ``Library``.

    On macOS/Windows the filesystem is case-insensitive, so the project-root
    walk stopped at ``/`` (matching ``/Library``) and the effect library then
    recursively scanned the whole system tree — ~70 s on *every* engine init.
    """

    def test_capitalised_library_is_not_a_project_root(self, tmp_path: Path) -> None:
        from demodsl.config_loader import _find_project_root

        (tmp_path / "Library").mkdir()
        start = tmp_path / "sub"
        start.mkdir()
        assert _find_project_root(start) != tmp_path

    def test_lowercase_library_is_a_project_root(self, tmp_path: Path) -> None:
        from demodsl.config_loader import _find_project_root

        (tmp_path / "library").mkdir()
        start = tmp_path / "sub"
        start.mkdir()
        assert _find_project_root(start) == tmp_path.resolve()

    def test_deep_path_does_not_walk_up_to_the_filesystem_root(self, tmp_path: Path) -> None:
        """A config outside any project must not resolve the root to ``/``."""
        from demodsl.config_loader import _find_project_root

        start = tmp_path / "a" / "b"
        start.mkdir(parents=True)
        root = _find_project_root(start)
        assert root != Path("/")
        assert root == start.resolve()

    def test_load_directory_refuses_case_folded_path(self, tmp_path: Path) -> None:
        from demodsl.effects.library_registry import EffectLibrary

        (tmp_path / "Library").mkdir()
        lib = EffectLibrary()
        # Would silently scan `Library/` on a case-insensitive filesystem.
        assert lib.load_directory(tmp_path / "library") == 0

    def test_engine_init_does_not_crawl_the_filesystem(self, tmp_path: Path) -> None:
        import time

        import yaml as _yaml

        cfg = tmp_path / "demo.yaml"
        cfg.write_text(
            _yaml.dump(
                {
                    "metadata": {"title": "T", "version": "1"},
                    "scenarios": [
                        {
                            "name": "s",
                            "url": "https://example.com",
                            "steps": [{"action": "pause", "wait": 1}],
                        }
                    ],
                }
            )
        )
        DemoEngine(cfg, dry_run=True)  # warm caches
        start = time.perf_counter()
        DemoEngine(cfg, dry_run=True)
        elapsed = time.perf_counter() - start
        # The full-disk crawl took ~70 s; a sane init is well under a second.
        assert elapsed < 2.0, f"engine init took {elapsed:.1f}s — filesystem crawl regression?"
