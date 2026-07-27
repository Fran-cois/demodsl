"""Opinionated "house style" for a good demo — demodsl's own opinion.

Any generator (LLM pipeline, template, hand-written script) can produce a
*correct* config; this module is where demodsl says what a **good** one looks
like, so callers inherit the craft instead of re-inventing it:

- **One idea per step.** Each beat spotlights exactly one on-page argument;
  the camera zooms onto what the narration talks about, then pulls back.
- **Narration sets the clock.** ``pace()`` derives each step's ``wait`` from
  the spoken word count (≈2.6 words/s TTS + a visual settle margin), clamped —
  no more fixed 6-second guesses that clip long lines or drag short ones.
- **Natural motion.** Bézier cursor, smooth scrolling, hover delays and a
  glow on the element under the cursor — the demo reads as a human tour.
- **Framed like a video, not a screencast.** 1920×1080 viewport, branded
  intro card, crossfade transitions, closing CTA outro.
- **Effects budget.** At most one effect per step (a spotlight on the
  argument); a finale zoom-pulse on the CTA beat only. More is noise.

Usage::

    from demodsl.recipe import walkthrough

    cfg = walkthrough(
        company="Acme", url="https://acme.com",
        intro="Welcome to this tour of Acme.",
        beats=[
            {"locator": {"type": "css", "value": "h1"},
             "narration": "The hero promises effortless invoicing."},
            {"locator": {"type": "text", "value": "Start free"},
             "narration": "One clear call to action seals the pitch.",
             "role": "cta"},
        ],
        verdict="A crisp page overall — 4 out of 5.",
    )   # → dict, already validated against DemoConfig

Every returned config validates against :class:`demodsl.models.DemoConfig`.
"""

from __future__ import annotations

import re
from typing import Any

from demodsl.models import DemoConfig

# ── the numbers behind the opinion ───────────────────────────────────────────
WORDS_PER_SECOND = 2.6  # comfortable TTS pace (gTTS/openai voices ≈ 2.4-2.8)
SETTLE = 1.2  # visual settle margin per step (anim + page paint)
MIN_WAIT, MAX_WAIT = 3.0, 12.0
ACCENT = "#6366F1"  # house accent (cursor, glow, intro card)
HERO_ZOOM = 1.35  # frame the hero without losing page context
BEAT_ZOOM = 1.55  # tighter on smaller arguments (metrics, CTAs, logos)
CAMERA_EASE = "ease-in-out"


def pace(narration: str | None, *, floor: float = MIN_WAIT) -> float:
    """Seconds a step should hold so its narration fits, plus settle margin."""
    words = len((narration or "").split())
    return round(min(MAX_WAIT, max(floor, words / WORDS_PER_SECOND + SETTLE)), 1)


def _spotlight() -> dict[str, Any]:
    return {"type": "spotlight", "duration": 1.8, "intensity": 0.85}


# Role → how an expert reviewer physically points at that kind of argument.
# animated_annotation / callout_arrow auto-anchor to the step's locator at
# runtime (orchestrator fills target_x/y + radius from the element bbox), so
# the circle is drawn around the REAL element — the "circle what you talk
# about" move of a human reviewer.
ANNOTATE_RED = "#EF4444"


def _role_effects(
    role: str, note: str | None = None, duration: float | None = None
) -> list[dict[str, Any]]:
    hold = round(min(10.0, duration or 3.0), 1)  # effect param clamp is 10s
    if role == "hero":
        # The editor's opening gesture: a highlighter sweep under the headline.
        return [{"type": "marker_underline", "color": ACCENT, "duration": hold}]
    if role in ("proof", "metric", "social_proof"):
        return [
            {
                "type": "animated_annotation",
                "color": ANNOTATE_RED,
                "duration": hold,
                **({"text": note} if note else {}),
            }
        ]
    if role == "cta":
        return [
            {
                "type": "callout_arrow",
                "color": ANNOTATE_RED,
                "duration": hold,
                **({"text": note} if note else {}),
            },
            {"type": "zoom_pulse", "duration": 2.0},
        ]
    # standard argument: circle it, no label
    return [{"type": "animated_annotation", "color": ACCENT, "duration": hold}]


def scenario_defaults() -> dict[str, Any]:
    """The house look-and-feel every walkthrough scenario starts from."""
    return {
        "browser": "chrome",
        "provider": "playwright",
        "viewport": {"width": 1920, "height": 1080},
        "natural": {
            "enabled": True,
            "hover_delay": 0.25,
            "smooth_scroll": True,
            "bezier_cursor": True,
        },
        "cursor": {
            "visible": True,
            "style": "dot",
            "color": ACCENT,
            "click_effect": "ripple",
        },
        "glow_select": {"enabled": True, "colors": [ACCENT], "intensity": 0.6},
    }


# The default human face of a DemoBro review — override via walkthrough(reviewer=…).
DEFAULT_REVIEWER: dict[str, Any] = {
    "enabled": True,
    "name": "Alex Rivera",
    "title": "Senior CRO Reviewer",
    "company": "DemoBro",
    "accent": ACCENT,
    "position": "bottom-left",
    "size": 88,
}


# The audio-reactive presenter bubble (bottom-right) — flat-vector, no
# uncanny valley. Override via walkthrough(live_avatar=…), {"enabled": False}
# to remove.
DEFAULT_LIVE_AVATAR: dict[str, Any] = {
    "enabled": True,
    "accent": ACCENT,
    "position": "bottom-right",
    "size": 168,
}


def video_defaults(
    company: str,
    *,
    cta: str | None = None,
    reviewer: dict[str, Any] | None = None,
    live_avatar: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Branded intro card, crossfades, closing CTA outro — plus the reviewer
    badge and the live presenter bubble, so the viewer always sees the human
    behind the narration."""
    return {
        "intro": {
            "duration": 2.5,
            "type": "fade_in",
            "text": company,
            "subtitle": "A guided tour",
            "background_color": "#0B1224",
            "font_color": "#FFFFFF",
        },
        "transitions": {"type": "crossfade", "duration": 0.5},
        "reviewer": {**DEFAULT_REVIEWER, **(reviewer or {})},
        "live_avatar": {**DEFAULT_LIVE_AVATAR, **(live_avatar or {})},
        "progress_bar": {"enabled": True, "accent": ACCENT, "position": "top", "height": 6},
        "outro": {
            "duration": 3.5,
            "type": "fade_out",
            "text": company,
            "cta": cta or "See it for yourself",
        },
    }


def _beat_step(beat: dict[str, Any], *, first: bool) -> dict[str, Any]:
    """One argument → one hover step: camera frames it, the expert marks it."""
    loc = beat["locator"]
    narration = str(beat.get("narration") or "").strip()
    role = beat.get("role") or ("hero" if first else "argument")
    zoom = HERO_ZOOM if role == "hero" else BEAT_ZOOM
    wait = pace(narration)
    effects = _role_effects(role, beat.get("note"), duration=wait)
    sentiment = str(beat.get("sentiment") or "").lower()
    if sentiment in ("good", "bad"):
        # The reviewer's verdict on THIS argument — a ✓ or ✗ dropped in the
        # margin next to the element (auto-anchored to its top-right corner).
        effects.append(
            {
                "type": "hand_mark",
                "style": "check" if sentiment == "good" else "cross",
                "duration": round(min(10.0, wait), 1),
            }
        )
    return {
        "action": "hover",
        "locator": dict(loc),
        "camera": {
            "zoom": zoom,
            "target": dict(loc),
            "duration": 0.7,
            "ease": CAMERA_EASE,
        },
        "narration": narration,
        "wait": wait,
        "effects": effects,
    }


def _camera_reset(duration: float = 0.6) -> dict[str, Any]:
    return {"action": "camera_reset", "camera": {"reset": True, "duration": duration}}


def expand_beat(data: dict[str, Any]) -> dict[str, Any]:
    """Expand a semantic ``beat:`` step (issue #20) into concrete step fields.

    ``data`` is the raw step mapping, e.g.::

        {"beat": "cta", "locator": {...}, "narration": "…"}
        {"beat": {"role": "proof", "sentiment": "good", "note": "4.9/5"},
         "locator": {...}, "narration": "…"}

    The role picks the camera framing and the pointing gesture, the narration
    sets the pacing. Anything the author already spelled out (``action``,
    ``camera``, ``effects``, ``wait``) is left untouched — a beat only fills
    the blanks.
    """
    step = dict(data)
    beat = step["beat"]
    if isinstance(beat, str):
        beat = {"role": beat.strip().lower()}
        step["beat"] = beat
    if not isinstance(beat, dict):
        return step  # let pydantic report the type error

    locator = step.get("locator")
    narration = str(step.get("narration") or "").strip()
    role = str(beat.get("role") or "argument").lower()
    wait = step.get("wait")
    if wait is None:
        wait = pace(narration)
        step["wait"] = wait

    if not step.get("action"):
        step["action"] = "hover" if locator else "pause"

    if locator and step.get("camera") is None and step["action"] != "navigate":
        step["camera"] = {
            "zoom": HERO_ZOOM if role == "hero" else BEAT_ZOOM,
            "target": dict(locator),
            "duration": 0.7,
            "ease": CAMERA_EASE,
        }

    if step.get("effects") is None:
        effects = _role_effects(role, beat.get("note"), duration=float(wait))
        sentiment = str(beat.get("sentiment") or "").lower()
        if sentiment in ("good", "bad"):
            effects.append(
                {
                    "type": "hand_mark",
                    "style": "check" if sentiment == "good" else "cross",
                    "duration": round(min(10.0, float(wait)), 1),
                }
            )
        step["effects"] = effects
    return step


_SCORE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:/|sur|out of)\s*(5|10)", re.IGNORECASE)


def extract_score(verdict: str | None) -> str | None:
    """Pull a "3/5"-style score out of a verdict sentence, if present."""
    if not verdict:
        return None
    m = _SCORE_RE.search(verdict)
    if not m:
        return None
    num = m.group(1).replace(",", ".")
    num = num.rstrip("0").rstrip(".") if "." in num else num
    return f"{num}/{m.group(2)}"


def walkthrough(
    *,
    company: str,
    url: str,
    beats: list[dict[str, Any]],
    intro: str | None = None,
    verdict: str | None = None,
    title: str | None = None,
    description: str | None = None,
    voice: dict[str, Any] | None = None,
    reviewer: dict[str, Any] | None = None,
    live_avatar: dict[str, Any] | None = None,
    shorts: bool = True,
    filename: str | None = None,
    directory: str = "output/",
    scenario_name: str = "Guided walkthrough",
) -> dict[str, Any]:
    """Build demodsl's opinionated guided-tour config from raw beats.

    ``beats`` items: ``{"locator": {...}, "narration": str, "role": str?,
    "note": str?}``. ``role`` shapes the expert's gesture — ``"hero"`` (default
    for the first beat) gets a highlighter underline sweep,
    ``"proof"``/``"metric"``/``"social_proof"`` a hand-drawn red circle on the
    element, ``"cta"`` a red callout arrow + finale pulse, anything else a
    subtle accent circle. ``note`` is an optional 2-4 word on-screen label
    next to the mark. ``sentiment`` (``"good"``/``"bad"``) drops a hand-drawn
    ✓ or ✗ in the margin next to the element. Beats **without** a locator
    become narrated smooth scrolls (never a dead hover on an element that
    might not resolve). A score in the verdict ("… 3 out of 5", "… 8/10")
    is stamped onto the page during the wrap-up.
    ``reviewer`` overrides the default DemoBro reviewer badge (the persistent
    human presence in the corner); pass ``{"enabled": False}`` to remove it.

    Returns a plain dict that has already been validated against
    :class:`~demodsl.models.DemoConfig`.
    """
    if not beats:
        raise ValueError(
            "a walkthrough needs at least one beat — a good demo shows at least one argument"
        )
    steps: list[dict[str, Any]] = [
        {
            "action": "navigate",
            "url": url,
            "narration": (intro or f"Let's take a guided tour of {company}.").strip(),
            "wait": pace(intro, floor=5.0),  # first paint needs the extra floor
        }
    ]
    for i, beat in enumerate(beats):
        narration = str(beat.get("narration") or "").strip()
        if beat.get("locator"):
            steps.append(_beat_step(beat, first=(i == 0)))
            steps.append(_camera_reset())
        else:
            steps.append(
                {
                    "action": "scroll",
                    "direction": "down",
                    "pixels": 360,
                    "smooth_scroll": True,
                    "narration": narration,
                    "wait": pace(narration),
                }
            )
    closing = (verdict or f"That's {company} — a focused page with a clear next step.").strip()
    closing_wait = pace(closing, floor=5.0)
    closing_step: dict[str, Any] = {
        "action": "scroll",
        "direction": "down",
        "pixels": 320,
        "smooth_scroll": True,
        "narration": closing,
        "wait": closing_wait,
    }
    score = extract_score(closing)
    if score:
        # The reviewer's final gesture: the score stamped onto the page.
        closing_step["effects"] = [
            {
                "type": "verdict_stamp",
                "text": score,
                "color": ANNOTATE_RED,
                "style": "REVIEW SCORE",
                "duration": round(min(10.0, closing_wait), 1),
            }
        ]
    steps.append(closing_step)

    cfg: dict[str, Any] = {
        "metadata": {
            "title": title or f"{company} — Guided Tour",
            "description": description or f"An opinionated demodsl walkthrough of {company}.",
            "version": "2.0.0",
        },
        "voice": voice or {"engine": "gtts", "voice_id": "en", "speed": 1.0},
        "subtitle": {"enabled": True, "style": "classic", "position": "bottom"},
        "video": video_defaults(company, reviewer=reviewer, live_avatar=live_avatar),
        "scenarios": [
            {
                "name": scenario_name,
                "url": url,
                **scenario_defaults(),
                "steps": steps,
            }
        ],
        "pipeline": [
            {"generate_narration": {}},
            {"edit_video": {}},
            {"burn_subtitles": {}},
        ],
        "output": {
            "filename": filename or "walkthrough.mp4",
            "directory": directory,
            # A vertical short falls out of every render for free: blurred
            # 9:16 canvas, sharp full-width video, first 60 s (hook + hero).
            **(
                {"social": [{"platform": "tiktok", "crop_mode": "blur_pad", "max_duration": 60}]}
                if shorts
                else {}
            ),
        },
    }
    DemoConfig(**cfg)  # the recipe never emits an invalid config
    return cfg


__all__ = [
    "ACCENT",
    "MAX_WAIT",
    "MIN_WAIT",
    "pace",
    "scenario_defaults",
    "video_defaults",
    "walkthrough",
]
