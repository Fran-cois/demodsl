"""Determinism contract for renders (issue #26).

Without determinism there is no measurement: two runs of the same config
differ because several subsystems are stochastic (hand-drawn wobble,
avatar blink/saccade schedules, natural timing jitter, particle
emitters). ``seed:`` at config level makes every one of them derive from
a single root, and ``--deterministic`` additionally freezes timing
jitter and the capture rate.

The derivation is a stable hash rather than ``random.seed`` so that
adding a subsystem never shifts the stream of an existing one.
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "derive_seed",
    "seeded_random",
    "apply_determinism",
    "deterministic_enabled",
    "DETERMINISTIC_ENV",
    "DETERMINISTIC_FRAME_RATE",
]

DETERMINISTIC_ENV = "DEMODSL_DETERMINISTIC"
#: Fixed capture rate used in deterministic mode so frame counts match.
DETERMINISTIC_FRAME_RATE = 30

_SEED_MASK = 2**31 - 1


def derive_seed(root: int | None, namespace: str, index: int = 0) -> int:
    """Derive a stable sub-seed for *namespace* / *index* from *root*.

    ``derive_seed(1234, "particles", 2)`` always returns the same value,
    and is independent of how many other subsystems asked for a seed
    first — the property that makes seeds survive refactors.
    """
    if root is None:
        return random.randrange(_SEED_MASK)
    payload = f"{int(root)}:{namespace}:{int(index)}".encode()
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:4], "big") & _SEED_MASK


def seeded_random(root: int | None, namespace: str, index: int = 0) -> random.Random:
    """A ``random.Random`` bound to the derived sub-seed."""
    return random.Random(derive_seed(root, namespace, index))


def deterministic_enabled() -> bool:
    """Whether ``--deterministic`` (or its env var) is active."""
    return os.environ.get(DETERMINISTIC_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def apply_determinism(config: Any, *, strict: bool | None = None) -> dict[str, Any]:
    """Push ``config.seed`` into every stochastic subsystem.

    * particle emitters and fractal-noise layers get a derived ``seed``
      unless the author pinned one;
    * with *strict* (``--deterministic``) the natural-motion jitter is
      zeroed and the frame rate pinned, so two runs produce the same
      number of frames at the same instants.

    Returns a report of what was pinned — used by ``--explain-cache`` and
    by the eval harness to certify that a run was reproducible.
    """
    if strict is None:
        strict = deterministic_enabled()

    root = getattr(config, "seed", None)
    report: dict[str, Any] = {
        "seed": root,
        "strict": bool(strict),
        "pinned": [],
        "jitter_disabled": [],
    }
    if root is None and not strict:
        return report

    counter = 0

    def pin_layers(layers: Any, path: str) -> None:
        nonlocal counter
        for idx, layer in enumerate(layers or []):
            if not hasattr(layer, "seed"):
                continue
            if "seed" in getattr(layer, "model_fields_set", set()):
                continue
            layer.seed = derive_seed(root, "layer", counter)
            layer.model_fields_set.add("seed")
            report["pinned"].append(f"{path}[{idx}].seed={layer.seed}")
            counter += 1

    for s_idx, scenario in enumerate(getattr(config, "scenarios", []) or []):
        timeline = getattr(scenario, "timeline", None)
        if timeline is not None:
            pin_layers(getattr(timeline, "layers", None), f"scenarios[{s_idx}].timeline.layers")
            precomps = getattr(timeline, "precomps", None) or {}
            for name, precomp in sorted(precomps.items()):
                pin_layers(
                    getattr(precomp, "layers", None),
                    f"scenarios[{s_idx}].timeline.precomps[{name}].layers",
                )

        if strict:
            natural = getattr(scenario, "natural", None)
            if natural is not None and hasattr(natural, "jitter") and natural.jitter:
                natural.jitter = 0.0
                report["jitter_disabled"].append(f"scenarios[{s_idx}].natural.jitter")

    if strict:
        video = getattr(config, "video", None)
        if video is not None and getattr(video, "frame_rate", None) is None:
            video.frame_rate = DETERMINISTIC_FRAME_RATE
            report["pinned"].append(f"video.frame_rate={DETERMINISTIC_FRAME_RATE}")

    if report["pinned"] or report["jitter_disabled"]:
        logger.debug("Determinism: %s", report)
    return report
