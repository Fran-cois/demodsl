"""Post-processing effects registry — names only.

Since the v3.0 removal of MoviePy, post-effects are executed by the Remotion
renderer (in TypeScript, see ``remotion/src/components/EffectLayer.tsx``).
On the Python side we only need to know **which effect names are valid**
so the scenario orchestrator can route them through ``step_post_effects``
to Remotion.

The :class:`~demodsl.effects.registry.PostEffect` ``apply()`` method is no
longer invoked at runtime; we expose a sentinel that raises if a caller
tries to use it (which would indicate a leftover MoviePy code path).
"""

from __future__ import annotations

from typing import Any

from demodsl.effects.registry import PostEffect


class _RemotionPostEffect(PostEffect):
    """Sentinel: registered to mark an effect name as a valid post-effect.

    The actual rendering happens client-side in Remotion's
    ``EffectLayer.tsx``. This class exists only so the Python ``EffectRegistry``
    can answer ``is_post_effect(name)`` correctly.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:  # pragma: no cover
        raise NotImplementedError(
            f"Post-effect '{self.name}' has no Python implementation since "
            "MoviePy was removed in v3.0. It is rendered by Remotion in "
            "EffectLayer.tsx. If you see this error, a MoviePy code path "
            "was not removed."
        )


# Canonical list of post-effect names supported by the Remotion EffectLayer.
# Effects marked (no-op) currently render to nothing on the Remotion side
# (kept for forward compatibility — see EffectLayer.tsx).
_POST_EFFECT_NAMES: tuple[str, ...] = (
    # Camera movement
    "parallax",
    "zoom_pulse",
    "drone_zoom",
    "ken_burns",
    "zoom_to",
    "dolly_zoom",
    "elastic_zoom",
    "camera_shake",
    "whip_pan",
    "rotate",
    # Fade / slide
    "fade_in",
    "fade_out",
    "slide_in",
    # Cinematic
    "vignette",
    "letterbox",
    "film_grain",
    "color_grade",
    "focus_pull",
    "tilt_shift",
    # Retro / stylised
    "glitch",
    "crt_scanlines",
    "chromatic_aberration",
    "vhs_distortion",
    "pixel_sort",  # no-op
    # Depth & light
    "bloom",
    "bokeh_blur",
    "light_leak",
    # Transitions
    "wipe",
    "iris",
    "dissolve_noise",
    # Speed / timing (no-op on Remotion path; would need ffmpeg pre-pass)
    "speed_ramp",
    "freeze_frame",
    "reverse",
)


def register_all_post_effects(registry: Any) -> None:
    """Register all built-in post-processing effect names.

    The actual rendering is performed by Remotion's ``EffectLayer.tsx``;
    this only marks the names as known so the scenario orchestrator routes
    them correctly.
    """
    for name in _POST_EFFECT_NAMES:
        registry.register_post(name, _RemotionPostEffect(name))
