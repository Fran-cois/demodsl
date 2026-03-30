"""ScenarioOrchestrator — browser recording and step execution."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from demodsl.commands import get_command
from demodsl.effects.cursor import CursorOverlay
from demodsl.effects.glow_select import GlowSelectOverlay
from demodsl.effects.popup_card import PopupCardOverlay
from demodsl.effects.registry import EffectRegistry
from demodsl.effects.sanitize import sanitize_css_selector
from demodsl.models import DemoConfig, DemoStoppedError, Effect, Scenario, Step
from demodsl.orchestrators import RecordingResult
from demodsl.pipeline.workspace import Workspace
from demodsl.providers.base import BrowserProvider, BrowserProviderFactory

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
    ) -> None:
        self.config = config
        self._effects = effects
        # Mutable state populated during recording (kept for backward compat reads)
        self.step_timestamps: list[float] = []
        self.step_post_effects: list[list[tuple[str, dict[str, Any]]]] = []

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

        self.step_timestamps.clear()
        self.step_post_effects.clear()

        videos: list[Path] = []
        video_offset = 0.0
        for scenario in self.config.scenarios:
            pre_count = len(self.step_timestamps)
            video, scenario_duration = self._execute_scenario(
                scenario,
                ws,
                narration_durations=narration_durations or {},
            )
            # Offset timestamps so they are relative to the
            # concatenated video timeline, not per-scenario.
            for i in range(pre_count, len(self.step_timestamps)):
                self.step_timestamps[i] += video_offset
            video_offset += scenario_duration
            if video:
                videos.append(video)

        return RecordingResult(
            raw_videos=videos,
            step_timestamps=list(self.step_timestamps),
            step_post_effects=[list(s) for s in self.step_post_effects],
        )

    # ── Private helpers ───────────────────────────────────────────────────

    def _execute_scenario(
        self,
        scenario: Scenario,
        ws: Workspace,
        *,
        narration_durations: dict[int, float],
    ) -> tuple[Path | None, float]:
        browser: BrowserProvider = BrowserProviderFactory.create("playwright")

        has_pre_steps = bool(scenario.pre_steps)

        if has_pre_steps:
            # Launch without recording to execute warmup steps
            browser.launch_without_recording(
                browser_type=scenario.browser,
                viewport=scenario.viewport,
                color_scheme=scenario.color_scheme,
                locale=scenario.locale,
            )
            logger.info("Running pre_steps for scenario: %s", scenario.name)
            for i, step in enumerate(scenario.pre_steps):  # type: ignore[union-attr]
                logger.info("  Pre-step %d: %s", i + 1, step.action)
                cmd = get_command(step.action, output_dir=ws.frames)
                cmd.execute(browser, step)
                if step.wait and step.wait > 0:
                    time.sleep(step.wait)
            # Restart browser context with recording enabled
            browser.restart_with_recording(video_dir=ws.raw_video)
        else:
            browser.launch(
                browser_type=scenario.browser,
                viewport=scenario.viewport,
                video_dir=ws.raw_video,
                color_scheme=scenario.color_scheme,
                locale=scenario.locale,
            )

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

        t0 = time.monotonic()
        step_offset = len(self.step_timestamps)
        narration_gap = 0.0
        if self.config.voice:
            narration_gap = self.config.voice.narration_gap
        try:
            for i, step in enumerate(scenario.steps):
                logger.info("  Step %d: %s", i + 1, step.action)
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
                )
        finally:
            video_path = browser.close()

        scenario_duration = time.monotonic() - t0

        if video_path:
            logger.info("Recorded video: %s (%.1fs)", video_path, scenario_duration)
        return video_path, scenario_duration

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
    ) -> None:
        if step.effects:
            self._apply_browser_effects(browser, step.effects)
            self._collect_post_effects(step.effects)
        else:
            self.step_post_effects.append([])

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

        if cursor and step.action == "click":
            cursor.trigger_click(browser.evaluate_js)

        cmd = get_command(step.action, output_dir=ws.frames)
        cmd.execute(browser, step)

        self._check_stop_conditions(browser, step, len(self.step_timestamps))

        if glow and step.locator and step.action in ("click", "type"):
            glow.hide(browser.evaluate_js)

        if step.action == "navigate":
            time.sleep(_POST_NAVIGATE_DELAY)
            if cursor:
                cursor.inject(browser.evaluate_js)
            if glow:
                glow.inject(browser.evaluate_js)
            if popup:
                popup.inject(browser.evaluate_js)

        # Record timestamp AFTER effects and navigate delay so that
        # the narration audio aligns with what the viewer actually sees.
        self.step_timestamps.append(time.monotonic() - t0)

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
            )
            if effective_wait > 0:
                time.sleep(effective_wait)

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

        time.sleep(reveal_start)
        for i in range(n):
            popup.reveal_next(browser.evaluate_js)
            if i < n - 1:
                time.sleep(max(0, interval - _REVEAL_ITEM_DELAY))
        elapsed = reveal_start + n * interval
        remaining = total_time - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _apply_browser_effects(
        self, browser: BrowserProvider, effects: list[Effect]
    ) -> None:
        for effect in effects:
            if self._effects.is_browser_effect(effect.type):
                handler = self._effects.get_browser_effect(effect.type)
                params = effect.model_dump(exclude_none=True, exclude={"type"})
                handler.inject(browser.evaluate_js, params)
                if effect.duration:
                    time.sleep(effect.duration)

    def _collect_post_effects(self, effects: list[Effect]) -> None:
        collected: list[tuple[str, dict[str, Any]]] = []
        for effect in effects:
            if self._effects.is_post_effect(effect.type):
                params = effect.model_dump(exclude_none=True, exclude={"type"})
                collected.append((effect.type, params))
        self.step_post_effects.append(collected)

    def _dry_run_scenarios(self) -> list[Path]:
        for scenario in self.config.scenarios:
            logger.info("[DRY-RUN] Scenario: %s", scenario.name)
            if scenario.pre_steps:
                for i, step in enumerate(scenario.pre_steps):
                    cmd = get_command(step.action, output_dir=Path("."))
                    logger.info(
                        "  [DRY-RUN] Pre-step %d (no recording): %s",
                        i + 1,
                        cmd.describe(step),
                    )
            for i, step in enumerate(scenario.steps):
                cmd = get_command(step.action, output_dir=Path("."))
                logger.info("  [DRY-RUN] Step %d: %s", i + 1, cmd.describe(step))
                if step.effects:
                    for e in step.effects:
                        logger.info("    [DRY-RUN] Effect: %s", e.type)
        return []
