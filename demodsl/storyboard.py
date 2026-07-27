"""`demodsl storyboard` — one frame per step, in seconds (issue #17).

An authoring agent ships a config it has never *seen*: the only feedback loop
is a full render (browser recording + TTS + composition), far too slow to
iterate on. So nobody iterates, and quality plateaus at "first draft".

:func:`storyboard` drives the page through the steps **without recording and
without TTS**: it applies each step's camera framing, injects its effects,
takes one screenshot, and writes

* ``step-000.png … step-NNN.png``
* ``storyboard.png`` — a contact sheet of every frame
* ``storyboard.json`` — per step: action, narration, effects, camera, the
  resolved anchor, and the layout **warnings** a multimodal reviewer would
  otherwise have to spot by eye (mark off-screen, mark under the subtitle
  band, two consecutive beats marking the same region).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from demodsl.models import DemoConfig, Step
    from demodsl.providers.base import BrowserProvider

logger = logging.getLogger(__name__)

__all__ = ["storyboard", "frame_warnings", "contact_sheet"]

#: Fraction of the frame height reserved for burned-in subtitles.
SUBTITLE_BAND = 0.82
#: Two anchors closer than this (normalized distance) mark "the same thing".
_SAME_REGION = 0.06
#: Actions a storyboard pass can safely execute (no side effects, no waiting).
_DRIVE_ACTIONS = frozenset({"navigate", "scroll", "hover", "click", "type", "wait_for"})


def frame_warnings(
    anchor: tuple[float, float] | None,
    *,
    previous_anchor: tuple[float, float] | None = None,
    effects: list[str] | None = None,
    narration: str | None = None,
    wait: float | None = None,
) -> list[str]:
    """Layout problems visible on a single storyboard frame.

    Pure function of the frame's metadata so it can be unit-tested without a
    browser.
    """
    out: list[str] = []
    effects = effects or []
    if anchor is not None:
        x, y = anchor
        if not (0.0 <= x <= 1.0) or not (0.0 <= y <= 1.0):
            out.append("mark falls outside the frame")
        else:
            if x > 0.94 or x < 0.06:
                out.append("mark extends past the horizontal edge")
            if y > SUBTITLE_BAND and narration:
                out.append("mark sits under the subtitle band")
        if previous_anchor is not None:
            dx = abs(previous_anchor[0] - x)
            dy = abs(previous_anchor[1] - y)
            if dx < _SAME_REGION and dy < _SAME_REGION:
                out.append("marks the same region as the previous step")
    elif effects:
        out.append("pointing effect without a resolved anchor")
    if narration and wait:
        from demodsl.estimate import spoken_seconds

        if spoken_seconds(narration) > wait + 0.6:
            out.append("narration is longer than the step wait")
    return out


def contact_sheet(frames: list[Path], dest: Path, *, columns: int = 4, width: int = 480) -> Path:
    """Tile *frames* into a single contact sheet image."""
    from PIL import Image

    if not frames:
        raise ValueError("no frames to tile")
    thumbs = []
    for frame in frames:
        with Image.open(frame) as img:
            ratio = width / img.width
            thumbs.append(img.convert("RGB").resize((width, max(1, int(img.height * ratio)))))
    cols = max(1, min(columns, len(thumbs)))
    rows = (len(thumbs) + cols - 1) // cols
    cell_h = max(t.height for t in thumbs)
    sheet = Image.new("RGB", (cols * width, rows * cell_h), (18, 18, 22))
    for i, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((i % cols) * width, (i // cols) * cell_h))
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest)
    return dest


def storyboard(
    config: DemoConfig,
    *,
    output_dir: Path,
    viewport: tuple[int, int] = (1920, 1080),
    browser: str = "chrome",
    sheet: bool = True,
) -> dict[str, Any]:
    """Render one screenshot per step and report the layout warnings."""
    import demodsl.providers.browser  # noqa: F401  (registers the provider)
    from demodsl.effects.browser_effects import register_all_browser_effects
    from demodsl.effects.registry import EffectRegistry
    from demodsl.models import Viewport
    from demodsl.providers.base import BrowserProviderFactory

    output_dir.mkdir(parents=True, exist_ok=True)
    registry = EffectRegistry()
    register_all_browser_effects(registry)

    provider = BrowserProviderFactory.create("playwright")
    provider.launch_without_recording(
        browser_type=browser,
        viewport=Viewport(width=viewport[0], height=viewport[1]),
    )

    entries: list[dict[str, Any]] = []
    frames: list[Path] = []
    previous_anchor: tuple[float, float] | None = None
    index = 0
    try:
        for scenario in config.scenarios:
            if scenario.mobile is not None:
                index += len(scenario.steps or [])
                continue
            if scenario.url:
                _safe(provider.navigate, scenario.url)
            for step in scenario.steps or []:
                entry, anchor, frame = _shoot_step(
                    provider, registry, step, index, output_dir, viewport, previous_anchor
                )
                entries.append(entry)
                if frame is not None:
                    frames.append(frame)
                if anchor is not None:
                    previous_anchor = anchor
                index += 1
    finally:
        provider.close()

    report: dict[str, Any] = {
        "title": config.metadata.title,
        "viewport": {"width": viewport[0], "height": viewport[1]},
        "steps": entries,
        "warnings": sum(len(e["warnings"]) for e in entries),
    }
    if sheet and frames:
        try:
            report["contact_sheet"] = str(contact_sheet(frames, output_dir / "storyboard.png"))
        except Exception as exc:  # pragma: no cover - Pillow missing/odd frames
            logger.warning("Contact sheet skipped: %s", exc)
    (output_dir / "storyboard.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _shoot_step(
    provider: BrowserProvider,
    registry: Any,
    step: Step,
    index: int,
    output_dir: Path,
    viewport: tuple[int, int],
    previous_anchor: tuple[float, float] | None,
) -> tuple[dict[str, Any], tuple[float, float] | None, Path | None]:
    """Drive one step, inject its effects and capture a single frame."""
    errors: list[str] = []
    if step.action in _DRIVE_ACTIONS:
        try:
            _drive(provider, step)
        except Exception as exc:
            errors.append(f"{step.action} failed: {exc}")

    anchor = _anchor(provider, step, viewport)
    effect_names = [e.type for e in (step.effects or [])]
    for effect in step.effects or []:
        if not registry.is_browser_effect(effect.type):
            continue
        params = effect.model_dump(exclude_none=True, exclude={"type"})
        if anchor is not None:
            params.setdefault("target_x", anchor[0])
            params.setdefault("target_y", anchor[1])
        try:
            registry.get_browser_effect(effect.type).inject(provider.evaluate_js, params)
        except Exception as exc:
            errors.append(f"effect '{effect.type}' failed: {exc}")

    frame: Path | None = None
    try:
        frame = provider.screenshot(output_dir / f"step-{index:03d}.png")
    except Exception as exc:
        errors.append(f"screenshot failed: {exc}")

    warnings = frame_warnings(
        anchor,
        previous_anchor=previous_anchor,
        effects=effect_names,
        narration=step.narration,
        wait=step.wait,
    )
    entry = {
        "index": index,
        "action": step.action,
        "frame": frame.name if frame else None,
        "narration": step.narration,
        "effects": effect_names,
        "camera": step.camera.model_dump(exclude_none=True) if step.camera else None,
        "anchored_at": {"x": anchor[0], "y": anchor[1]} if anchor else None,
        "warnings": warnings + errors,
    }
    return entry, anchor, frame


def _drive(provider: BrowserProvider, step: Step) -> None:
    action = step.action
    if action == "navigate" and step.url:
        provider.navigate(step.url)
    elif action == "scroll":
        provider.scroll(step.direction or "down", step.pixels or 600, smooth=False)
    elif action in ("hover", "click") and step.locator is not None:
        scroll_fn = getattr(provider, "scroll_into_view", None)
        if scroll_fn:
            scroll_fn(step.locator)
        provider.hover(step.locator)
    elif action == "type" and step.locator is not None and step.value is not None:
        provider.type_text(step.locator, step.value)
    elif action == "wait_for" and step.locator is not None:
        provider.wait_for(step.locator, min(step.timeout or 5.0, 5.0))


def _anchor(
    provider: BrowserProvider, step: Step, viewport: tuple[int, int]
) -> tuple[float, float] | None:
    """Normalized centre of the element this step points at, if any."""
    if step.locator is None:
        return None
    explicit = next(
        (e for e in (step.effects or []) if e.target_x is not None and e.target_y is not None),
        None,
    )
    if explicit is not None:
        return (float(explicit.target_x), float(explicit.target_y))  # type: ignore[arg-type]
    try:
        bbox = provider.get_element_bbox(step.locator)
    except Exception:
        return None
    if not bbox:
        return None
    vw, vh = getattr(provider, "viewport_size", viewport) or viewport
    if not vw or not vh:
        return None
    return (
        round((bbox["x"] + bbox["width"] / 2) / vw, 4),
        round((bbox["y"] + bbox["height"] / 2) / vh, 4),
    )


def _safe(fn: Any, *args: Any) -> None:
    try:
        fn(*args)
    except Exception as exc:  # pragma: no cover - navigation failure
        logger.warning("storyboard: %s", exc)
