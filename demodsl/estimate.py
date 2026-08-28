"""Narration duration estimation (issue #19).

Every step's ``wait`` is a guess about how long its narration takes to speak.
Guess low and the voice is cut off mid-sentence; guess high and the video
drags — and the truth only shows up inside a 10-minute render.

Two tiers:

* **cheap** — a words-per-second model per TTS engine (instant, offline).
  Enough to catch every gross mismatch;
* **exact** (``synthesize=True``) — actually run the configured TTS once and
  measure the audio, reusing the render's TTS cache so the later render pays
  nothing.

:func:`apply_fix` rewrites the ``wait`` fields of a raw config in place.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from demodsl.humanize import state_for_scenario

if TYPE_CHECKING:  # pragma: no cover
    from demodsl.models import DemoConfig

logger = logging.getLogger(__name__)

__all__ = ["estimate_config", "spoken_seconds", "apply_fix", "WORDS_PER_SECOND"]

#: Measured speaking rate per engine, in words per second at speed 1.0.
#: Neural voices (elevenlabs/openai) breathe; concatenative ones (espeak,
#: gtts) rush. A config paced for one desyncs on another — which is exactly
#: what this table exists to expose.
WORDS_PER_SECOND: dict[str, float] = {
    "elevenlabs": 2.55,
    "openai": 2.70,
    "google": 2.65,
    "azure": 2.65,
    "aws_polly": 2.70,
    "gradium": 2.60,
    "cosyvoice": 2.50,
    "coqui": 2.45,
    "piper": 2.80,
    "local_openai": 2.70,
    "espeak": 3.10,
    "gtts": 2.85,
    "voxtral": 2.60,
    "custom": 2.60,
}
_DEFAULT_WPS = 2.60

#: Tolerance before a wait is called wrong, in seconds.
_SLACK = 0.6

#: Average share a humanised clip gains from its widened pauses, at
#: ``intensity: 1``. Scaled by intensity; the renderer caps each clip at 15 %.
_BREATH_STRETCH = 0.10


def spoken_seconds(text: str, *, engine: str = "elevenlabs", speed: float = 1.0) -> float:
    """Estimate how long *text* takes to speak with *engine* at *speed*."""
    words = len((text or "").split())
    if not words:
        return 0.0
    wps = WORDS_PER_SECOND.get(engine, _DEFAULT_WPS) * max(0.1, speed)
    # Punctuation buys pauses the raw word count does not capture.
    pauses = 0.25 * (text.count(",") + text.count(";")) + 0.4 * (
        text.count(".") + text.count("!") + text.count("?")
    )
    return round(words / wps + pauses, 2)


def _measure(path: Path) -> float | None:
    """Duration of an audio file in seconds, or ``None`` if unmeasurable."""
    import subprocess

    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return round(float(proc.stdout.strip()), 2)
    except Exception:  # pragma: no cover - ffprobe missing / bad file
        return None


def estimate_config(
    config: DemoConfig,
    *,
    synthesize: bool = False,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Per-step narration timing report for *config*.

    With ``synthesize=True`` the configured TTS engine actually renders each
    narration once (into *cache_dir*) and the durations are measured rather
    than modelled.
    """
    voice = config.voice
    engine = voice.engine if voice else "elevenlabs"
    speed = voice.speed if voice else 1.0
    gap = voice.narration_gap if voice else 0.3

    provider = None
    tts_cache = None
    if synthesize:
        provider, tts_cache = _make_provider(config, cache_dir)
        if provider is None:
            logger.warning("TTS provider unavailable — falling back to the modelled estimate")

    out_dir = cache_dir or Path("output") / "estimate"
    steps: list[dict[str, Any]] = []
    total = 0.0
    index = 0
    exact_count = 0
    humanize_total = 0.0

    for scenario in config.scenarios:
        human = state_for_scenario(config, scenario)
        for step in scenario.steps or []:
            overhead = 0.0
            if human is not None and step.humanize is not False:
                human.begin_step(
                    index,
                    override=step.humanize if step.humanize is not True else None,
                )
                overhead = human.expected_overhead(
                    step.action,
                    has_locator=step.locator is not None,
                    value_len=len(step.value or ""),
                    char_rate=step.char_rate,
                    pixels=step.pixels or 0,
                )
                humanize_total += overhead
            narration = step.narration
            if narration:
                dur = None
                if provider is not None:
                    dur = _synthesize_one(provider, tts_cache, config, narration, out_dir, index)
                    if dur is not None:
                        exact_count += 1
                exact = dur is not None
                if dur is None:
                    dur = spoken_seconds(narration, engine=engine, speed=speed)
                if human is not None and step.humanize is not False:
                    # The render widens the clip's internal silences, so the
                    # spoken line really does run longer than the raw synthesis.
                    dur = round(dur * (1.0 + _BREATH_STRETCH * human.intensity_for("voice")), 2)
                wait = float(step.wait) if step.wait is not None else 0.0
                needed = round(dur + gap, 1)
                if not wait:
                    verdict = "unset"
                elif wait < dur + gap - _SLACK:
                    verdict = "too_short"
                elif wait > dur + gap + 3 * _SLACK:
                    verdict = "too_long"
                else:
                    verdict = "ok"
                steps.append(
                    {
                        "index": index,
                        "action": step.action,
                        "words": len(narration.split()),
                        "spoken_seconds": dur,
                        "wait": step.wait,
                        "verdict": verdict,
                        "suggested_wait": needed,
                        "exact": exact,
                        "humanize_overhead": overhead,
                    }
                )
                total += max(wait, dur + gap)
            else:
                total += float(step.wait or 0.0)
            # Human gestures run *before* the step's wait, so they extend the
            # video rather than fitting inside it.
            total += overhead
            index += 1

    if provider is not None:
        try:
            provider.close()
        except Exception:  # pragma: no cover - provider without close
            pass

    # Each junction overlaps two beats, so the rendered video is shorter than
    # the sum of its steps.
    transitions = config.video.transitions if config.video else None
    transition_seconds = 0.0
    if transitions is not None:
        all_steps = [s for scenario in config.scenarios for s in scenario.steps]
        if transitions.between == "scenarios":
            junctions = max(0, len(config.scenarios) - 1)
        elif transitions.between == "navigations":
            junctions = max(0, len(config.scenarios) - 1) + sum(
                1 for step in all_steps[1:] if step.action == "navigate"
            )
        else:
            junctions = max(0, len(all_steps) - 1)
        transition_seconds = round(transitions.duration * junctions, 1)
        total = max(0.0, total - transition_seconds)

    return {
        "voice": {"engine": engine, "speed": speed, "narration_gap": gap},
        "mode": "exact" if exact_count else "modelled",
        "steps": steps,
        "humanize_seconds": round(humanize_total, 1),
        "transition_seconds": transition_seconds,
        "total_seconds": round(total, 1),
    }


def _make_provider(config: DemoConfig, cache_dir: Path | None) -> tuple[Any | None, Any]:
    """Build the configured TTS provider + the shared render TTS cache."""
    from demodsl.providers.base import VoiceProviderFactory
    from demodsl.providers.tts_cache import TTSCache

    voice = config.voice
    if voice is None:
        return None, None
    out_dir = cache_dir or Path("output") / "estimate"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        import demodsl.providers.voice  # noqa: F401  (registers the providers)

        provider = VoiceProviderFactory.create(voice.engine, output_dir=out_dir)
    except Exception as exc:
        logger.warning("Cannot build the '%s' TTS provider: %s", voice.engine, exc)
        return None, None
    return provider, TTSCache()


def _synthesize_one(
    provider: Any,
    tts_cache: Any,
    config: DemoConfig,
    text: str,
    out_dir: Path,
    index: int,
) -> float | None:
    """Render one narration (cache-first) and measure it."""
    voice = config.voice
    voice_id = voice.voice_id if voice else "josh"
    speed = voice.speed if voice else 1.0
    pitch = voice.pitch if voice else 0
    engine = voice.engine if voice else "dummy"
    reference = Path(voice.reference_audio) if voice and voice.reference_audio else None

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"estimate_{index:03d}.mp3"
    key = {
        "engine": engine,
        "text": text,
        "voice_id": voice_id,
        "speed": speed,
        "pitch": pitch,
        "reference_audio": reference,
    }
    if tts_cache is not None:
        try:
            cached = tts_cache.lookup(**key, extra=provider.cache_extra(), dest_path=dest)
        except Exception:  # pragma: no cover - defensive
            cached = None
        if cached is not None:
            return _measure(Path(cached))
    try:
        path = Path(
            provider.generate(
                text=text,
                voice_id=voice_id,
                speed=speed,
                pitch=pitch,
                reference_audio=reference,
            )
        )
    except Exception as exc:
        logger.warning("TTS failed on step %d: %s", index, exc)
        return None
    if tts_cache is not None:
        try:
            tts_cache.store(**key, extra=provider.cache_extra(), generated_path=path)
        except Exception:  # pragma: no cover - defensive
            pass
    return _measure(path)


def apply_fix(raw: dict[str, Any], report: dict[str, Any]) -> int:
    """Rewrite the ``wait`` of every mis-paced step in *raw*. Returns the count."""
    suggestions = {
        step["index"]: step["suggested_wait"]
        for step in report["steps"]
        if step["verdict"] in ("too_short", "too_long", "unset")
    }
    if not suggestions:
        return 0
    changed = 0
    index = 0
    for scenario in raw.get("scenarios") or []:
        for step in scenario.get("steps") or []:
            if index in suggestions:
                step["wait"] = suggestions[index]
                changed += 1
            index += 1
    return changed
