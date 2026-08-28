"""Runtime state of the simulated operator — the part that must stay *coherent*.

Two rules make the difference between "human" and "sloppy", and both live
here rather than in the individual effects:

* **Correlation.** Every imperfection derives from one persona, aged by the
  time already spent recording, so a demo drifts the way a real session does.
* **Budget.** Imperfections are rationed (:meth:`allow_imperfection`): at most
  a handful per demo, never twice in a row, never on a step the author marked
  critical. Unbudgeted randomness is what turns a human-feeling demo into an
  amateur one.

Randomness is drawn from :func:`demodsl.determinism.seeded_random` on a
per-channel, per-step stream, so inserting a step never shifts the noise of
the other channels.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from demodsl.determinism import seeded_random
from demodsl.humanize.keyboard import bigram_factor
from demodsl.humanize.persona import OperatorProfile, get_profile

logger = logging.getLogger(__name__)

__all__ = ["HumanState", "build_state", "CHANNELS"]

#: Independent noise streams. One per subsystem so they stay decorrelated.
CHANNELS = ("cursor", "keyboard", "scroll", "camera", "video", "voice", "timing")


class HumanState:
    """Mutable per-scenario operator state, advanced once per step."""

    def __init__(
        self,
        profile: OperatorProfile,
        *,
        intensity: float = 0.6,
        seed: int | None = None,
        fatigue_ramp: bool = True,
        max_imperfections: int = 3,
        keyboard_layout: str = "qwerty",
        handheld: bool = True,
        film_look: bool = False,
        channels: dict[str, float] | None = None,
    ) -> None:
        self.base_profile = profile
        self.intensity = max(0.0, min(1.0, intensity))
        self.seed = seed
        self.fatigue_ramp = fatigue_ramp
        self.max_imperfections = max(0, max_imperfections)
        self.keyboard_layout = keyboard_layout
        self.handheld = handheld
        self.film_look = film_look
        self.channels = dict(channels or {})
        self._step_index = 0
        self._critical = False
        self._spent = 0
        self._last_imperfection_step = -99
        self._last_detour_step = -99
        self._t0 = time.monotonic()
        self._streams: dict[str, Any] = {}
        # Per-step dials, reset by begin_step; the budget is never overridable.
        self._step_intensity: float | None = None
        self._step_channels: dict[str, float] = {}

    # ── lifecycle ────────────────────────────────────────────────────────

    def begin_step(
        self,
        index: int,
        *,
        critical: bool = False,
        override: Any | None = None,
    ) -> None:
        """Advance to step *index*; *critical* steps never get an imperfection.

        *override* is the step's own ``humanize`` block (a ``StepHumanize``):
        it retunes intensity and channels for this step only.
        """
        self._step_index = index
        self._critical = critical
        if override is not None and not getattr(override, "enabled", True):
            self._step_intensity = 0.0
            self._step_channels = {}
        else:
            self._step_intensity = getattr(override, "intensity", None)
            self._step_channels = dict(getattr(override, "channels", None) or {})
        # Streams are per-step by construction: entering a step restarts them,
        # so replaying a step reproduces it exactly.
        self._streams.clear()

    def intensity_for(self, channel: str) -> float:
        """How human *channel* should behave right now.

        Resolution order: the step's channel dial, the step's intensity, the
        scenario's channel dial, the scenario's intensity. A channel set to 0
        is off — that is how a demo keeps a locked-off camera while its typing
        stays fully human.
        """
        if channel in self._step_channels:
            return self._step_channels[channel]
        if self._step_intensity is not None:
            return self._step_intensity
        return self.scenario_intensity_for(channel)

    def scenario_intensity_for(self, channel: str) -> float:
        """Same, ignoring the per-step dials.

        Whole-clip treatments must read this one: a per-step override switching
        them off would make them blink between beats, which reads as a
        rendering glitch rather than a camera.
        """
        if channel in self.channels:
            return self.channels[channel]
        return self.intensity

    @property
    def profile(self) -> OperatorProfile:
        """The persona as it stands right now (fatigue applied)."""
        if not self.fatigue_ramp:
            return self.base_profile
        return self.base_profile.with_fatigue((time.monotonic() - self._t0) / 60.0)

    def rng(self, channel: str) -> Any:
        """A ``random.Random`` bound to (*seed*, *channel*, current step).

        Cached until the next :meth:`begin_step`, so repeated calls within a
        step keep advancing one stream instead of replaying the same first draw.
        """
        stream = self._streams.get(channel)
        if stream is None:
            stream = seeded_random(self.seed, f"humanize.{channel}", self._step_index)
            self._streams[channel] = stream
        return stream

    # ── budget ───────────────────────────────────────────────────────────

    def allow_imperfection(self, probability: float, *, channel: str = "timing") -> bool:
        """Whether a visible mistake may happen now.

        Guards, in order: intensity, budget exhausted, back-to-back steps,
        critical step. Only then is the persona-weighted dice rolled.
        """
        if self.max_imperfections <= 0:
            return False
        if self.intensity_for(channel) <= 0:
            return False
        if self._critical:
            return False
        if self._spent >= self.max_imperfections:
            return False
        if self._step_index - self._last_imperfection_step < 2:
            return False
        if self.rng(channel).random() >= probability * self.intensity_for(channel):
            return False
        self._spent += 1
        self._last_imperfection_step = self._step_index
        logger.debug(
            "humanize: imperfection %d/%d on step %d (%s)",
            self._spent,
            self.max_imperfections,
            self._step_index,
            channel,
        )
        return True

    # ── derived motor parameters ─────────────────────────────────────────

    def wants_detour(self) -> bool:
        """Whether the cursor brushes something on its way to the target.

        Rationed separately from :meth:`allow_imperfection`: looking around is
        curiosity, not a mistake, and it costs the demo nothing but a beat.
        """
        if self.intensity_for("cursor") <= 0 or self._critical:
            return False
        if self._step_index - self._last_detour_step < 3:
            return False
        if self.rng("cursor").random() >= 0.35 * self.profile.curiosity * self.intensity_for(
            "cursor"
        ):
            return False
        self._last_detour_step = self._step_index
        return True

    def _sloppiness_for(self, channel: str) -> float:
        """0 = robot, 1 = maximally imprecise, for one subsystem."""
        return (1.0 - self.profile.precision) * self.intensity_for(channel)

    def cursor_params(self) -> dict[str, float]:
        """Overshoot / resting-drift parameters for the cursor overlay."""
        # Every amplitude is scaled by the channel: even a perfectly precise
        # persona has a baseline overshoot, and a channel dialled to 0 has to
        # mean a genuinely locked-off cursor, not a slightly calmer one.
        k = self.intensity_for("cursor")
        sloppy = self._sloppiness_for("cursor")
        return {
            # Fraction of the travel distance the cursor sails past the target.
            "overshoot_ratio": round(k * (0.02 + 0.06 * sloppy), 4),
            "overshoot_max": round(k * (4.0 + 14.0 * sloppy), 2),
            # Time spent coming back — a correction is always faster than the move.
            "settle_ms": round(k * (90 + 90 * sloppy), 1),
            # Micro-movement while "resting" on the target.
            "drift_px": round(k * (0.6 + 2.6 * sloppy), 2),
            "drift_period_ms": round(1400 - 400 * sloppy, 1),
        }

    def pre_click_pause(self) -> float:
        """Extra hesitation between cursor arrival and click, in seconds."""
        k = self.intensity_for("timing")
        if k <= 0:
            return 0.0
        p = self.profile
        base = (1.0 - p.confidence) * 0.5 * k
        return round(base * self.rng("timing").uniform(0.6, 1.4), 3)

    def aim_miss(self, width: float, height: float) -> tuple[float, float] | None:
        """Where the cursor lands when it *just* misses an element.

        Returns an offset from the element's centre that falls a few pixels
        outside its box, or ``None`` when no miss should happen. Only the
        approach misses — the click itself is still dispatched on the real
        element, so a near-miss can never navigate somewhere unintended.
        """
        if not self.allow_imperfection(0.55, channel="cursor"):
            return None
        rng = self.rng("cursor")
        overshoot = rng.uniform(6.0, 18.0) * (0.5 + self._sloppiness_for("cursor"))
        if rng.random() < 0.5:
            dx = (width / 2 + overshoot) * rng.choice([-1, 1])
            dy = rng.uniform(-height / 3, height / 3)
        else:
            dx = rng.uniform(-width / 3, width / 3)
            dy = (height / 2 + overshoot) * rng.choice([-1, 1])
        return round(dx, 1), round(dy, 1)

    def typo_rate(self) -> float:
        """Per-character probability of hitting a neighbouring key."""
        return round(min(0.08, 0.09 * self._sloppiness_for("keyboard")), 4)

    def typing_tempo(self) -> float:
        """Multiplier applied to the authored ``char_rate``."""
        k = self.intensity_for("keyboard")
        if k <= 0:
            return 1.0
        return round(1.0 - (1.0 - self.profile.tempo) * k, 3)

    def keystroke_delays(self, value: str, base_delay: float) -> list[float]:
        """Per-character delay for *value*, in seconds.

        Three things make typed text read as a person rather than a metronome:
        the hand alternation pulse (:func:`bigram_factor`), a pause where the
        eye has to think (an ``@``, a digit, the start of a long word), and
        bursts — a run of fast keys followed by a beat of reading back what
        was just typed.
        """
        k = self.intensity_for("keyboard")
        if k <= 0 or not value:
            return [base_delay] * len(value)
        rng = self.rng("keyboard")
        words = value.split(" ")
        long_word_starts = set()
        pos = 0
        for w in words:
            if len(w) > 8:
                long_word_starts.add(pos)
            pos += len(w) + 1

        delays: list[float] = []
        burst_left = rng.randint(6, 13)
        prev = ""
        for i, ch in enumerate(value):
            factor = bigram_factor(prev, ch, self.keyboard_layout) if prev else 1.0
            if ch in " \t\n":
                factor *= 1.6
            elif ch in ".,;:!?'\"()-":
                factor *= 1.9
            elif ch == "@" or (ch.isdigit() and prev.isalpha()):
                factor *= 2.4  # the eye stops on a symbol/number boundary
            if i in long_word_starts:
                factor *= 1.5
            factor = 1.0 + (factor - 1.0) * k
            factor *= rng.uniform(1.0 - 0.25 * k, 1.0 + 0.25 * k)

            burst_left -= 1
            if burst_left <= 0 and i < len(value) - 1:
                # Read back what was just typed before pressing on.
                factor += rng.uniform(2.5, 6.0) * k
                burst_left = rng.randint(6, 13)
            delays.append(base_delay * max(factor, 0.2))
            prev = ch
        return delays

    def camera_miss(self, zoom: float | None) -> tuple[float | None, float, float] | None:
        """How an operator lands a camera move: slightly off, then corrected.

        Returns ``(first_zoom, origin_jitter_px, correction_seconds)``, or
        ``None`` when the move should be played exactly as authored. Nobody
        frames a shot perfectly on the first push.
        """
        if self.intensity_for("camera") <= 0:
            return None
        rng = self.rng("camera")
        sloppy = self._sloppiness_for("camera")
        if rng.random() > 0.55 + 0.4 * sloppy:
            return None
        first = None
        if zoom is not None and zoom > 0:
            # Undershoot or overshoot the zoom, but always by enough that the
            # correction is visible — a miss of 0.1 % is just noise.
            delta = rng.uniform(-0.09, 0.09) * (0.4 + sloppy)
            if abs(delta) < 0.02:
                delta = 0.02 if delta >= 0 else -0.02
            first = round(zoom * (1.0 + delta), 3)
            if first <= 0:
                first = None
        jitter = round(rng.uniform(10.0, 55.0) * (0.4 + sloppy), 1)
        return first, jitter, round(rng.uniform(0.28, 0.55), 3)

    def camera_reaction_delay(self) -> float:
        """Seconds the operator lags behind the beat before moving the camera.

        A person reacts to what is happening; a script anticipates it, and that
        anticipation is one of the tells.
        """
        k = self.intensity_for("camera")
        if k <= 0:
            return 0.0
        return round(
            self.rng("camera").uniform(0.05, 0.3) * k * (1.4 - self.profile.tempo),
            3,
        )

    def scroll_plan(self, pixels: int) -> list[int]:
        """Split a scroll into the uneven bursts a real wheel/trackpad makes.

        The last burst overshoots and is followed by a negative correction —
        the single most recognisable "a human did this" scroll gesture.
        """
        k = self.intensity_for("scroll")
        if k <= 0 or pixels <= 0:
            return [pixels]
        rng = self.rng("scroll")
        p = self.profile
        # More curiosity / less tempo → more, smaller flicks.
        bursts = 1 + int(round((0.8 + p.curiosity - p.tempo) * k * 2.2))
        bursts = max(1, min(4, bursts))
        if bursts == 1 and rng.random() > 0.5 * k:
            return [pixels]

        overshoot = int(pixels * (0.05 + 0.18 * p.curiosity * k))
        overshoot = max(0, min(140, overshoot))
        total = pixels + overshoot

        # Uneven split: real flicks decay, they are not equal slices.
        weights = [rng.uniform(0.6, 1.5) for _ in range(bursts)]
        scale = total / sum(weights)
        plan = [int(w * scale) for w in weights]
        plan[-1] += total - sum(plan)  # absorb rounding into the last flick
        if overshoot > 0:
            plan.append(-overshoot)
        return plan

    def video_finish(self) -> list[tuple[str, dict[str, Any]]]:
        """Post-effects that make the capture look *recorded* rather than rendered.

        Applied identically to every step — a handheld drift that switched on
        and off between beats would read as a rendering glitch, not a camera.
        """
        # Scenario-level on purpose: a per-step override must never make the
        # whole-clip finish blink between beats.
        k = self.scenario_intensity_for("video")
        if k <= 0:
            return []
        out: list[tuple[str, dict[str, Any]]] = []
        p = self.base_profile
        if self.handheld:
            out.append(
                (
                    "handheld",
                    {
                        # Steadier hands hold the frame tighter.
                        "intensity": round(0.12 + 0.5 * (1.0 - p.precision) * k, 3),
                        "speed": round(0.35 + 0.5 * p.curiosity, 3),
                        # Fixed per scenario: a per-step phase would jump on cuts.
                        "seed": (self.seed or 0) % 360,
                    },
                )
            )
        if self.film_look:
            out.append(("film_grain", {"intensity": round(0.05 + 0.09 * k, 3)}))
            out.append(("vignette", {"intensity": round(0.14 + 0.16 * k, 3)}))
        return out

    # ── planning ─────────────────────────────────────────────────────────

    def expected_overhead(
        self,
        action: str,
        *,
        has_locator: bool = False,
        value_len: int = 0,
        char_rate: float | None = None,
        pixels: int = 0,
    ) -> float:
        """Seconds this step gains from being performed by a human.

        An *expected* value (no dice rolled), because it is used by
        ``demodsl estimate`` to keep the declared timeline honest: hesitation,
        corrections and extra scroll flicks happen **before** the step's
        ``wait``, so they add to the video length instead of fitting inside it.

        Rationed one-offs (a near-miss, a curious detour) are deliberately not
        modelled: capped at a handful per scenario, they land well inside the
        slack the narration estimate already carries, and a bad model of them
        would be worse than none.
        """
        p = self.profile
        extra = 0.0
        if has_locator:
            extra += self.cursor_params()["settle_ms"] / 1000.0
        if action == "click":
            extra += (1.0 - p.confidence) * 0.5 * self.intensity_for("timing")  # mean hesitation
        elif action == "type" and value_len and char_rate:
            base = value_len / char_rate
            tempo = self.typing_tempo()
            extra += base / tempo - base if tempo > 0 else 0.0
            candidates = max(0, value_len - 1)
            odds = min(1.0, self.typo_rate() * candidates) * self.intensity_for("keyboard")
            extra += odds * 7.0 / char_rate  # slip + pause + backspaces + retype
        elif action == "scroll" and pixels:
            bursts = len([b for b in self.scroll_plan(pixels) if b])
            extra += max(0, bursts - 1) * 0.25
        elif action in ("camera", "camera_reset"):
            # Mean reaction lag, plus the reframe (played twice: the miss and
            # its correction) weighted by how often the framing misses.
            extra += 0.175 * self.intensity_for("camera") * (1.4 - p.tempo)
            p_miss = min(1.0, 0.55 + 0.4 * self._sloppiness_for("camera"))
            extra += p_miss * 2 * 0.415
        return round(extra, 3)


def build_state(cfg: Any, *, root_seed: int | None = None) -> HumanState | None:
    """Turn a ``HumanizeConfig`` (or ``True``) into a live :class:`HumanState`.

    Returns ``None`` when humanisation is off, so callers can keep the
    existing robot code path untouched.
    """
    if cfg is None or cfg is False:
        return None
    if cfg is True:
        return HumanState(get_profile(None), seed=root_seed)
    if not getattr(cfg, "enabled", True):
        return None
    intensity = float(getattr(cfg, "intensity", 0.6))
    channels = dict(getattr(cfg, "channels", None) or {})
    # A zero global intensity still leaves a live operator when a channel was
    # dialled up on its own — that is the point of per-subsystem plugging.
    if intensity <= 0 and not any(v > 0 for v in channels.values()):
        return None
    return HumanState(
        get_profile(getattr(cfg, "persona", None)),
        intensity=intensity,
        seed=getattr(cfg, "seed", None) if getattr(cfg, "seed", None) is not None else root_seed,
        fatigue_ramp=bool(getattr(cfg, "fatigue_ramp", True)),
        max_imperfections=int(getattr(cfg, "max_imperfections", 3)),
        keyboard_layout=str(getattr(cfg, "keyboard_layout", "qwerty")),
        handheld=bool(getattr(cfg, "handheld", True)),
        film_look=bool(getattr(cfg, "film_look", False)),
        channels=channels,
    )


def state_for_scenario(config: Any, scenario: Any) -> HumanState | None:
    """The operator driving *scenario*, honouring the config-level default.

    A scenario's own ``humanize`` wins outright (including ``false``, which
    opts that one scenario out of a config-wide operator).
    """
    cfg = scenario.humanize if scenario.humanize is not None else getattr(config, "humanize", None)
    return build_state(cfg, root_seed=getattr(config, "seed", None))
