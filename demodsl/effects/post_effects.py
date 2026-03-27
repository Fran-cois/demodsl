"""Post-processing effects applied to video clips via MoviePy."""

from __future__ import annotations

import logging
from typing import Any

from demodsl.effects.registry import PostEffect

logger = logging.getLogger(__name__)


class ParallaxEffect(PostEffect):
    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        depth = params.get("depth", 5)
        scale = 1 + depth * 0.01
        return clip.resized(scale).cropped(
            x_center=clip.w / 2, y_center=clip.h / 2,
            width=clip.w, height=clip.h,
        )


class ZoomPulseEffect(PostEffect):
    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        scale = params.get("scale", 1.2)
        duration = clip.duration

        def zoom(get_frame: Any, t: float) -> Any:
            import numpy as np
            progress = t / duration if duration else 0
            s = 1 + (scale - 1) * abs(np.sin(progress * np.pi))
            frame = get_frame(t)
            from PIL import Image
            img = Image.fromarray(frame)
            w, h = img.size
            nw, nh = int(w * s), int(h * s)
            img = img.resize((nw, nh), Image.LANCZOS)
            left = (nw - w) // 2
            top = (nh - h) // 2
            img = img.crop((left, top, left + w, top + h))
            return np.array(img)

        return clip.transform(zoom)


class FadeInEffect(PostEffect):
    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        duration = params.get("duration", 1.0)
        return clip.with_effects([lambda c: c.crossfadein(duration)])


class FadeOutEffect(PostEffect):
    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        duration = params.get("duration", 1.0)
        return clip.with_effects([lambda c: c.crossfadeout(duration)])


class VignetteEffect(PostEffect):
    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        intensity = params.get("intensity", 0.5)

        def vignette(get_frame: Any, t: float) -> Any:
            import numpy as np
            frame = get_frame(t)
            h, w = frame.shape[:2]
            Y, X = np.ogrid[:h, :w]
            cx, cy = w / 2, h / 2
            r = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
            r_max = np.sqrt(cx ** 2 + cy ** 2)
            mask = 1 - intensity * (r / r_max) ** 2
            mask = np.clip(mask, 0, 1)
            return (frame * mask[..., np.newaxis]).astype(np.uint8)

        return clip.transform(vignette)


class GlitchEffect(PostEffect):
    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        intensity = params.get("intensity", 0.3)

        def glitch(get_frame: Any, t: float) -> Any:
            import numpy as np
            frame = get_frame(t).copy()
            h, w = frame.shape[:2]
            num_slices = int(10 * intensity)
            rng = np.random.default_rng(int(t * 1000) % 2**31)
            for _ in range(num_slices):
                y = rng.integers(0, h)
                height = rng.integers(2, max(3, int(h * 0.05)))
                shift = rng.integers(-int(w * intensity * 0.3), int(w * intensity * 0.3))
                y2 = min(y + height, h)
                frame[y:y2] = np.roll(frame[y:y2], shift, axis=1)
            return frame

        return clip.transform(glitch)


class SlideInEffect(PostEffect):
    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        # Simplified: just a fade-in as a substitute
        duration = params.get("duration", 0.8)
        return clip.with_effects([lambda c: c.crossfadein(duration)])


def register_all_post_effects(registry: Any) -> None:
    """Register all built-in post-processing effects."""
    registry.register_post("parallax", ParallaxEffect())
    registry.register_post("zoom_pulse", ZoomPulseEffect())
    registry.register_post("fade_in", FadeInEffect())
    registry.register_post("fade_out", FadeOutEffect())
    registry.register_post("vignette", VignetteEffect())
    registry.register_post("glitch", GlitchEffect())
    registry.register_post("slide_in", SlideInEffect())
