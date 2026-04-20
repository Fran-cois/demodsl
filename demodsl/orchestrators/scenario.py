"""ScenarioOrchestrator — browser recording and step execution."""

from __future__ import annotations

import logging
import random
import time
from pathlib import Path
from typing import Any

from demodsl.commands import get_command, get_mobile_command
from demodsl.effects.cursor import CursorOverlay
from demodsl.effects.glow_select import GlowSelectOverlay
from demodsl.effects.popup_card import PopupCardOverlay
from demodsl.effects.registry import EffectRegistry
from demodsl.effects.sanitize import sanitize_css_selector
from demodsl.models import (
    DemoConfig,
    DemoStoppedError,
    Effect,
    NaturalConfig,
    Scenario,
    Step,
    ZoomInputConfig,
)
from demodsl.orchestrators import RecordingResult
from demodsl.pipeline.workspace import Workspace
from demodsl.providers.base import (
    BrowserProvider,
    BrowserProviderFactory,
    MobileProvider,
    MobileProviderFactory,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_REVEAL_START_RATIO = 0.15
_REVEAL_END_RATIO = 0.90
_REVEAL_ITEM_DELAY = 0.35
_POST_NAVIGATE_DELAY = 0.3


class ScenarioOrchestrator:
    """Handles browser-based scenario execution and recording."""

    def __init__(
        self,
        config: DemoConfig,
        effects: EffectRegistry,
        *,
        turbo: bool = False,
    ) -> None:
        self.config = config
        self._effects = effects
        self.turbo = turbo
        # Mutable state populated during recording (kept for backward compat reads)
        self.step_timestamps: list[float] = []
        self.step_post_effects: list[list[tuple[str, dict[str, Any]]]] = []

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_natural(scenario: Scenario) -> NaturalConfig | None:
        """Resolve the scenario-level natural config into a NaturalConfig."""
        if scenario.natural is None:
            return None
        if isinstance(scenario.natural, NaturalConfig):
            return scenario.natural if scenario.natural.enabled else None
        # scenario.natural is True
        return NaturalConfig()

    @staticmethod
    def _jittered(value: float, jitter: float) -> float:
        """Return *value* with ±*jitter* random variance."""
        if jitter <= 0 or value <= 0:
            return value
        return value * random.uniform(1.0 - jitter, 1.0 + jitter)

    # Turbo-mode minimum sleep (just enough to avoid racing the browser)
    _TURBO_MIN_SLEEP = 0.05

    def _sleep(self, seconds: float) -> None:
        """Sleep for *seconds*, clamped to a tiny minimum in turbo mode."""
        if seconds <= 0:
            return
        if self.turbo:
            time.sleep(self._TURBO_MIN_SLEEP)
        else:
            time.sleep(seconds)

    # ── Public API ────────────────────────────────────────────────────────

    def run_scenarios(
        self,
        ws: Workspace,
        *,
        narration_durations: dict[int, float] | None = None,
        dry_run: bool = False,
    ) -> RecordingResult:
        if dry_run:
            videos = self._dry_run_scenarios()
            return RecordingResult(raw_videos=videos)

        import demodsl.providers.browser  # noqa: F401

        # Ensure selenium provider is registered when needed
        try:
            import demodsl.providers.selenium_browser  # noqa: F401
        except ImportError:
            pass  # selenium not installed

        self.step_timestamps.clear()
        self.step_post_effects.clear()
        self.scroll_positions: list[tuple[float, int]] = []

        scenarios = self.config.scenarios
        nar = narration_durations or {}

        if len(scenarios) > 1:
            results = self._run_scenarios_parallel(scenarios, ws, nar)
        else:
            results = self._run_scenarios_sequential(scenarios, ws, nar)

        # Merge per-scenario results into the concatenated timeline
        videos: list[Path] = []
        video_offset = 0.0
        for video, duration, timestamps, post_effects, scroll_pos in results:
            for t in timestamps:
                self.step_timestamps.append(t + video_offset)
            self.step_post_effects.extend(post_effects)
            for ts, sy in scroll_pos:
                self.scroll_positions.append((ts + video_offset, sy))
            video_offset += duration
            if video:
                videos.append(video)

        return RecordingResult(
            raw_videos=videos,
            step_timestamps=list(self.step_timestamps),
            step_post_effects=[list(s) for s in self.step_post_effects],
            scroll_positions=list(self.scroll_positions),
        )

    # ── Scenario scheduling helpers ───────────────────────────────────────

    _ScenarioResult = tuple[
        Path | None,  # video path
        float,  # duration
        list[float],  # step timestamps (local)
        list[list[tuple[str, dict[str, Any]]]],  # post effects
        list[tuple[float, int]],  # scroll positions
    ]

    def _record_one_scenario(
        self,
        scenario: Scenario,
        ws: Workspace,
        narration_durations: dict[int, float],
    ) -> _ScenarioResult:
        """Record a single scenario with isolated mutable state."""
        import copy

        isolated = copy.copy(self)
        isolated.step_timestamps = []
        isolated.step_post_effects = []
        isolated.scroll_positions = []

        video, duration = isolated._execute_scenario(
            scenario,
            ws,
            narration_durations=narration_durations,
        )
        return (
            video,
            duration,
            isolated.step_timestamps,
            isolated.step_post_effects,
            isolated.scroll_positions,
        )

    def _run_scenarios_sequential(
        self,
        scenarios: list[Scenario],
        ws: Workspace,
        nar: dict[int, float],
    ) -> list[_ScenarioResult]:
        return [self._record_one_scenario(s, ws, nar) for s in scenarios]

    def _run_scenarios_parallel(
        self,
        scenarios: list[Scenario],
        ws: Workspace,
        nar: dict[int, float],
    ) -> list[_ScenarioResult]:
        import os
        from concurrent.futures import ThreadPoolExecutor

        max_workers = min(len(scenarios), os.cpu_count() or 4)
        logger.info(
            "Recording %d scenarios in parallel (workers=%d)",
            len(scenarios),
            max_workers,
        )

        def _record(scenario: Scenario) -> ScenarioOrchestrator._ScenarioResult:
            return self._record_one_scenario(scenario, ws, nar)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            return list(pool.map(_record, scenarios))

    # ── Private helpers ───────────────────────────────────────────────────

    def _execute_scenario(
        self,
        scenario: Scenario,
        ws: Workspace,
        *,
        narration_durations: dict[int, float],
    ) -> tuple[Path | None, float]:
        # Dispatch to mobile path if scenario has mobile config
        if scenario.mobile:
            return self._execute_mobile_scenario(
                scenario, ws, narration_durations=narration_durations
            )

        browser: BrowserProvider = BrowserProviderFactory.create(scenario.provider)

        # Always launch without recording first so the initial navigate
        # (or pre_steps) happen off-camera.  Recording starts only once the
        # page is visually ready, eliminating blank first frames.
        browser.launch_without_recording(
            browser_type=scenario.browser,
            viewport=scenario.viewport,
            color_scheme=scenario.color_scheme,
            locale=scenario.locale,
        )

        if scenario.pre_steps:
            logger.info("Running pre_steps for scenario: %s", scenario.name)
            for i, step in enumerate(scenario.pre_steps):  # type: ignore[union-attr]
                logger.info("  Pre-step %d: %s", i + 1, step.action)
                cmd = get_command(step.action, output_dir=ws.frames)
                cmd.execute(browser, step)
                if step.wait and step.wait > 0:
                    self._sleep(step.wait)
        elif scenario.steps and scenario.steps[0].action == "navigate":
            # Pre-navigate to the first URL so the page is loaded before
            # recording begins — avoids blank/white initial frames.
            first_url = scenario.steps[0].url
            if first_url:
                logger.info("Pre-navigating to %s (before recording)", first_url)
                browser.navigate(first_url)

        # Start recording with the page already showing content
        browser.restart_with_recording(video_dir=ws.raw_video)

        logger.info("Running scenario: %s", scenario.name)

        cursor: CursorOverlay | None = None
        if scenario.cursor and scenario.cursor.visible:
            cursor = CursorOverlay(scenario.cursor.model_dump())

        glow: GlowSelectOverlay | None = None
        if scenario.glow_select and scenario.glow_select.enabled:
            glow = GlowSelectOverlay(scenario.glow_select.model_dump())

        popup: PopupCardOverlay | None = None
        if scenario.popup_card and scenario.popup_card.enabled:
            popup = PopupCardOverlay(scenario.popup_card.model_dump())

        natural = self._resolve_natural(scenario)

        t0 = time.monotonic()
        step_offset = len(self.step_timestamps)
        narration_gap = 0.0
        if self.config.voice:
            narration_gap = self.config.voice.narration_gap
        try:
            for i, step in enumerate(scenario.steps):
                logger.info(
                    "  [%s] Step %d/%d: %s",
                    scenario.name,
                    i + 1,
                    len(scenario.steps),
                    step.action,
                )
                global_idx = step_offset + i
                nar_dur = narration_durations.get(global_idx, 0.0)
                self._execute_step(
                    browser,
                    step,
                    ws,
                    cursor=cursor,
                    glow=glow,
                    popup=popup,
                    narration_duration=nar_dur,
                    narration_gap=narration_gap if nar_dur > 0 else 0.0,
                    t0=t0,
                    natural=natural,
                )
        finally:
            video_path = browser.close()

        scenario_duration = time.monotonic() - t0

        if video_path and video_path.exists():
            cleaned = self._clean_leading_frames(video_path)
            if cleaned:
                video_path = cleaned

        if video_path:
            logger.info("Recorded video: %s (%.1fs)", video_path, scenario_duration)
        return video_path, scenario_duration

    @staticmethod
    def _clean_leading_frames(video: Path) -> Path | None:
        """Trim the first ~0.4s of the raw video to remove the blank
        frames that Playwright records between context creation and the
        first real paint after navigation.

        Uses stream-copy (``-c copy``) with input-level seeking
        (``-ss`` before ``-i``) to avoid re-encoding the VP8 data,
        since any re-encode at this stage could introduce additional
        compression artefacts.  Keyframe alignment is acceptable here
        because the first keyframe after 0.4s is always a content frame.
        """
        import subprocess

        output = video.with_stem(video.stem + "_clean")
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            "0.4",
            "-i",
            str(video),
            "-c",
            "copy",
            "-an",
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and output.exists():
            logger.debug("Trimmed leading frames: %s", output.name)
            return output
        logger.debug(
            "Leading frame trim skipped: %s",
            result.stderr[-200:] if result.stderr else "unknown",
        )
        return None

    def _execute_step(
        self,
        browser: BrowserProvider,
        step: Step,
        ws: Workspace,
        *,
        cursor: CursorOverlay | None = None,
        glow: GlowSelectOverlay | None = None,
        popup: PopupCardOverlay | None = None,
        narration_duration: float = 0.0,
        narration_gap: float = 0.0,
        t0: float = 0.0,
        natural: NaturalConfig | None = None,
    ) -> None:
        effect_duration = 0.0
        if step.effects:
            effect_duration = self._apply_browser_effects(browser, step.effects)
            self._collect_post_effects(step.effects, step)
        else:
            self._collect_post_effects([], step)

        has_card = popup and step.card
        card_items = (step.card.items or []) if step.card else []
        progressive = bool(card_items) and narration_duration > 0

        if glow and step.locator and step.action in ("click", "type"):
            bbox = browser.get_element_bbox(step.locator)
            if bbox:
                glow.show(browser.evaluate_js, bbox)

        if cursor and step.locator:
            center = browser.get_element_center(step.locator)
            if center:
                cursor.move_to(browser.evaluate_js, center[0], center[1])

        # Hover delay: pause between cursor arrival and click
        hover_delay = step.hover_delay
        if hover_delay is None and natural:
            hover_delay = natural.hover_delay
        if hover_delay and hover_delay > 0 and step.action == "click" and step.locator:
            # Dispatch CSS hover states so :hover styles apply.
            # Only works with CSS/ID locators (querySelector-compatible).
            if step.locator.type in ("css", "id"):
                sel = (
                    step.locator.value
                    if step.locator.type == "css"
                    else f"#{step.locator.value}"
                )
                safe_sel = sel.replace("\\", "\\\\").replace("'", "\\'")
                browser.evaluate_js(
                    f"(() => {{ const el = document.querySelector('{safe_sel}');"
                    " if(el){ el.dispatchEvent(new MouseEvent('mouseenter',{bubbles:true}));"
                    " el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true})); }})()"
                )
            self._sleep(hover_delay)

        if cursor and step.action == "click":
            cursor.trigger_click(browser.evaluate_js)

        # Zoom into the input element if requested
        zoom_active = False
        if step.zoom_input and step.action == "type" and step.locator:
            zoom_cfg = (
                step.zoom_input
                if isinstance(step.zoom_input, ZoomInputConfig)
                else ZoomInputConfig()
            )
            bbox = browser.get_element_bbox(step.locator)
            if bbox:
                self._inject_zoom_input(browser, bbox, zoom_cfg)
                zoom_active = True

        cmd = get_command(step.action, output_dir=ws.frames)

        # Capture scroll position BEFORE the command executes so that
        # the Blender camera holds steady during wait periods and starts
        # moving only when the scroll actually begins.
        if step.action == "scroll":
            try:
                pre_y = browser.evaluate_js(
                    "(window.scrollY || window.pageYOffset || "
                    "document.documentElement.scrollTop || 0)"
                )
                pre_t = time.monotonic() - t0
                self.scroll_positions.append((pre_t, int(pre_y)))
                logger.debug("Scroll pre-capture: t=%.2f scrollY=%s", pre_t, pre_y)
            except Exception:
                pass

        cmd.execute(browser, step)

        self._check_stop_conditions(browser, step, len(self.step_timestamps))

        if glow and step.locator and step.action in ("click", "type"):
            glow.hide(browser.evaluate_js)

        if zoom_active:
            self._remove_zoom_input(browser)

        if step.action == "navigate":
            self._sleep(_POST_NAVIGATE_DELAY)
            if cursor:
                cursor.inject(browser.evaluate_js)
            if glow:
                glow.inject(browser.evaluate_js)
            if popup:
                popup.inject(browser.evaluate_js)

        # Record timestamp AFTER effects and navigate delay so that
        # the narration audio aligns with what the viewer actually sees.
        self.step_timestamps.append(time.monotonic() - t0)

        # Capture scroll position for Blender camera synchronisation
        try:
            scroll_y = browser.evaluate_js(
                "(function(){"
                "  var y = window.scrollY || window.pageYOffset || 0;"
                "  if (y === 0) y = document.documentElement.scrollTop || 0;"
                "  if (y === 0) y = document.body.scrollTop || 0;"
                "  return y;"
                "})()"
            )
            self.scroll_positions.append((self.step_timestamps[-1], int(scroll_y)))
            logger.debug(
                "Scroll capture: t=%.2f scrollY=%s", self.step_timestamps[-1], scroll_y
            )
        except Exception as exc:
            logger.debug("Scroll capture failed: %s", exc)

        if has_card and step.card:
            popup.show(
                browser.evaluate_js,
                title=step.card.title,
                body=step.card.body,
                items=card_items,
                icon=step.card.icon,
                duration=narration_duration,
                progressive=progressive,
            )

        if has_card and progressive and card_items:
            self._reveal_card_items(
                browser,
                popup,
                card_items,
                narration_duration,
                base_wait=step.wait or 0.0,
            )
        else:
            effective_wait = max(
                step.wait or 0.0,
                narration_duration + narration_gap,
                effect_duration,
            )
            if effective_wait > 0:
                jitter = natural.jitter if natural else 0.0
                self._sleep(self._jittered(effective_wait, jitter))

        if has_card:
            popup.hide(browser.evaluate_js)

    def _check_stop_conditions(
        self,
        browser: BrowserProvider,
        step: Step,
        step_index: int,
    ) -> None:
        """Evaluate stop_if conditions; raise DemoStoppedError if any match."""
        if not step.stop_if:
            return
        for cond in step.stop_if:
            triggered = False
            if cond.selector:
                safe_sel = sanitize_css_selector(cond.selector)
                count = browser.evaluate_js(
                    f"document.querySelectorAll({safe_sel!r}).length"
                )
                triggered = bool(count)
            if cond.js:
                result = browser.evaluate_js(cond.js)
                triggered = triggered or bool(result)
            if cond.url_contains:
                current_url = browser.evaluate_js("window.location.href")
                triggered = triggered or cond.url_contains in (current_url or "")
            if triggered:
                msg = f"Step {step_index + 1} ({step.action}): {cond.message}"
                logger.warning("stop_if triggered — %s", msg)
                raise DemoStoppedError(msg)

    def _reveal_card_items(
        self,
        browser: BrowserProvider,
        popup: PopupCardOverlay,
        items: list[str],
        narration_duration: float,
        *,
        base_wait: float = 0.0,
    ) -> None:
        """Progressively reveal list items spaced evenly across the narration."""
        n = len(items)
        total_time = max(narration_duration, base_wait)
        reveal_start = total_time * _REVEAL_START_RATIO
        reveal_end = total_time * _REVEAL_END_RATIO
        interval = (reveal_end - reveal_start) / max(n, 1)

        self._sleep(reveal_start)
        for i in range(n):
            popup.reveal_next(browser.evaluate_js)
            if i < n - 1:
                self._sleep(max(0, interval - _REVEAL_ITEM_DELAY))
        elapsed = reveal_start + n * interval
        remaining = total_time - elapsed
        if remaining > 0:
            self._sleep(remaining)

    def _inject_zoom_input(
        self,
        browser: BrowserProvider,
        bbox: dict[str, float],
        cfg: ZoomInputConfig,
    ) -> None:
        """Apply a CSS zoom centred on the input element's bounding box."""
        cx = bbox["x"] + bbox["width"] / 2
        cy = bbox["y"] + bbox["height"] / 2
        scale = cfg.scale
        browser.evaluate_js(f"""(() => {{
            const s = document.createElement('style');
            s.id = '__demodsl_zoom_input';
            s.textContent = `
                html {{
                    transform: scale({scale});
                    transform-origin: {cx}px {cy}px;
                    transition: transform 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
                }}
            `;
            document.head.appendChild(s);
        }})()""")
        # Small pause for the zoom transition to render
        self._sleep(0.45)

    @staticmethod
    def _remove_zoom_input(browser: BrowserProvider) -> None:
        """Smoothly remove the zoom transform."""
        browser.evaluate_js("""(() => {
            const s = document.getElementById('__demodsl_zoom_input');
            if (s) {
                document.documentElement.style.transition =
                    'transform 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
                document.documentElement.style.transform = 'scale(1)';
                document.documentElement.style.transformOrigin = '';
                setTimeout(() => {
                    s.remove();
                    document.documentElement.style.transition = '';
                    document.documentElement.style.transform = '';
                }, 400);
            }
        })()""")
        import time as _time

        _time.sleep(0.4)

    def _apply_browser_effects(
        self, browser: BrowserProvider, effects: list[Effect]
    ) -> float:
        """Inject browser effects and return the max duration for wait adjustment."""
        # Ensure page nav/header stays above effect overlays (injected once)
        if not getattr(self, "_nav_shield_injected", False):
            browser.evaluate_js("""
            (() => {
                if (document.getElementById('__demodsl_nav_shield')) return;
                const s = document.createElement('style');
                s.id = '__demodsl_nav_shield';
                s.textContent = `
                    nav, header, [role="navigation"],
                    nav *, header * {
                        position: relative !important;
                        z-index: 100000 !important;
                    }
                `;
                document.head.appendChild(s);
            })()
            """)
            self._nav_shield_injected = True
        max_duration = 0.0
        for effect in effects:
            if self._effects.is_browser_effect(effect.type):
                handler = self._effects.get_browser_effect(effect.type)
                params = effect.model_dump(exclude_none=True, exclude={"type"})
                handler.inject(browser.evaluate_js, params)
                if effect.duration:
                    max_duration = max(max_duration, effect.duration)
        return max_duration

    def _collect_post_effects(
        self, effects: list[Effect], step: Step | None = None
    ) -> None:
        collected: list[tuple[str, dict[str, Any]]] = []
        for effect in effects:
            if self._effects.is_post_effect(effect.type):
                params = effect.model_dump(exclude_none=True, exclude={"type"})
                collected.append((effect.type, params))
        # Inject post-effects from step-level speed shorthand fields
        if step is not None:
            if step.speed is not None and step.speed != 1.0:
                collected.append(
                    ("speed_ramp", {"start_speed": step.speed, "end_speed": step.speed})
                )
            if step.speed_ramp is not None:
                collected.append(
                    ("speed_ramp", step.speed_ramp.model_dump(exclude_none=True))
                )
            if step.freeze_duration is not None and step.freeze_duration > 0:
                collected.append(
                    ("freeze_frame", {"freeze_duration": step.freeze_duration})
                )
        self.step_post_effects.append(collected)

    def _dry_run_scenarios(self) -> list[Path]:
        for scenario in self.config.scenarios:
            logger.info("[DRY-RUN] Scenario: %s", scenario.name)
            if scenario.mobile:
                logger.info(
                    "  [DRY-RUN] Mobile: %s on %s",
                    scenario.mobile.platform,
                    scenario.mobile.device_name,
                )
            if scenario.pre_steps:
                for i, step in enumerate(scenario.pre_steps):
                    if scenario.mobile:
                        cmd = get_mobile_command(step.action, output_dir=Path("."))
                    else:
                        cmd = get_command(step.action, output_dir=Path("."))
                    logger.info(
                        "  [DRY-RUN] Pre-step %d (no recording): %s",
                        i + 1,
                        cmd.describe(step),
                    )
            for i, step in enumerate(scenario.steps):
                if scenario.mobile:
                    cmd = get_mobile_command(step.action, output_dir=Path("."))
                else:
                    cmd = get_command(step.action, output_dir=Path("."))
                logger.info("  [DRY-RUN] Step %d: %s", i + 1, cmd.describe(step))
                if step.effects:
                    for e in step.effects:
                        logger.info("    [DRY-RUN] Effect: %s", e.type)
        return []

    # ── Mobile scenario execution ─────────────────────────────────────────

    def _execute_mobile_scenario(
        self,
        scenario: Scenario,
        ws: Workspace,
        *,
        narration_durations: dict[int, float],
    ) -> tuple[Path | None, float]:
        """Execute a scenario using a mobile (Appium) provider."""
        import demodsl.providers.mobile  # noqa: F401 — register AppiumMobileProvider

        mobile: MobileProvider = MobileProviderFactory.create("appium")
        mobile.launch(scenario.mobile, video_dir=ws.raw_video)  # type: ignore[arg-type]

        logger.info("Running mobile scenario: %s", scenario.name)

        # Warn if all steps are passive (screenshot/wait only)
        _PASSIVE_ACTIONS = {"screenshot", "wait"}
        if all(step.action in _PASSIVE_ACTIONS for step in scenario.steps):
            logger.warning(
                "Scenario '%s' has only screenshot/wait actions. "
                "The output will be a static slideshow, not a live recording. "
                "Add tap/swipe/scroll steps for a real demo.",
                scenario.name,
            )

        # Pre-steps (no separate recording toggle needed — Appium records
        # continuously from launch)
        if scenario.pre_steps:
            logger.info("Running mobile pre_steps for scenario: %s", scenario.name)
            for i, step in enumerate(scenario.pre_steps):
                logger.info("  Mobile pre-step %d: %s", i + 1, step.action)
                try:
                    cmd = get_mobile_command(step.action, output_dir=ws.frames)
                    cmd.execute(mobile, step)
                except Exception as exc:
                    # Take a debug screenshot before re-raising
                    debug_path = ws.frames / f"pre_step_{i + 1}_failure.png"
                    try:
                        mobile.screenshot(debug_path)
                        logger.error(
                            "Mobile pre-step %d (%s) failed: %s  "
                            "— debug screenshot saved to %s",
                            i + 1,
                            step.action,
                            exc,
                            debug_path,
                        )
                    except Exception:
                        logger.error(
                            "Mobile pre-step %d (%s) failed: %s  "
                            "— could not capture debug screenshot",
                            i + 1,
                            step.action,
                            exc,
                        )
                    raise
                if step.wait and step.wait > 0:
                    self._sleep(step.wait)

        t0 = time.monotonic()
        step_offset = len(self.step_timestamps)
        narration_gap = 0.0
        if self.config.voice:
            narration_gap = self.config.voice.narration_gap

        try:
            for i, step in enumerate(scenario.steps):
                logger.info("  Mobile step %d: %s", i + 1, step.action)
                global_idx = step_offset + i
                nar_dur = narration_durations.get(global_idx, 0.0)
                try:
                    self._execute_mobile_step(
                        mobile,
                        step,
                        ws,
                        narration_duration=nar_dur,
                        narration_gap=narration_gap if nar_dur > 0 else 0.0,
                        t0=t0,
                    )
                except Exception as exc:
                    # Take a debug screenshot on step failure
                    debug_path = ws.frames / f"step_{i + 1}_failure.png"
                    try:
                        mobile.screenshot(debug_path)
                        logger.error(
                            "Mobile step %d (%s) failed: %s  "
                            "— debug screenshot saved to %s",
                            i + 1,
                            step.action,
                            exc,
                            debug_path,
                        )
                    except Exception:
                        logger.error(
                            "Mobile step %d (%s) failed: %s",
                            i + 1,
                            step.action,
                            exc,
                        )
                    raise
        finally:
            video_path = mobile.close()

        scenario_duration = time.monotonic() - t0

        if video_path:
            logger.info(
                "Mobile recorded video: %s (%.1fs)", video_path, scenario_duration
            )
        return video_path, scenario_duration

    def _execute_mobile_step(
        self,
        mobile: MobileProvider,
        step: Step,
        ws: Workspace,
        *,
        narration_duration: float = 0.0,
        narration_gap: float = 0.0,
        t0: float = 0.0,
    ) -> None:
        """Execute a single step in a mobile scenario."""
        # Post effects: collect any that apply (no browser effects for mobile)
        if step.effects:
            self._collect_post_effects(step.effects, step)
        else:
            self._collect_post_effects([], step)

        cmd = get_mobile_command(step.action, output_dir=ws.frames)
        cmd.execute(mobile, step)

        # Record timestamp
        self.step_timestamps.append(time.monotonic() - t0)

        # Wait for narration duration or explicit wait
        effective_wait = max(
            step.wait or 0.0,
            narration_duration + narration_gap,
        )
        if effective_wait > 0:
            self._sleep(effective_wait)
