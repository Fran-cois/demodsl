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


# ── Camera movement effects ───────────────────────────────────────────────────


class DroneZoomEffect(PostEffect):
    """Smooth progressive zoom towards a target point — simulates a drone descent."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        max_scale = params.get("scale", 1.5)
        tx = params.get("target_x", 0.5)
        ty = params.get("target_y", 0.5)
        duration = clip.duration

        def drone(get_frame: Any, t: float) -> Any:
            import numpy as np
            from PIL import Image

            progress = t / duration if duration else 0
            # Ease-in-out curve
            p = progress * progress * (3 - 2 * progress)
            s = 1 + (max_scale - 1) * p
            frame = get_frame(t)
            img = Image.fromarray(frame)
            w, h = img.size
            nw, nh = int(w * s), int(h * s)
            img = img.resize((nw, nh), Image.LANCZOS)
            # Offset towards target
            left = int((nw - w) * tx)
            top = int((nh - h) * ty)
            img = img.crop((left, top, left + w, top + h))
            return np.array(img)

        return clip.transform(drone)


class KenBurnsEffect(PostEffect):
    """Classic documentary pan + zoom (slow push with lateral drift)."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        max_scale = params.get("scale", 1.15)
        direction = params.get("direction", "right")
        duration = clip.duration

        def ken_burns(get_frame: Any, t: float) -> Any:
            import numpy as np
            from PIL import Image

            progress = t / duration if duration else 0
            s = 1 + (max_scale - 1) * progress
            frame = get_frame(t)
            img = Image.fromarray(frame)
            w, h = img.size
            nw, nh = int(w * s), int(h * s)
            img = img.resize((nw, nh), Image.LANCZOS)
            # Pan direction
            if direction == "right":
                left = int((nw - w) * progress)
                top = (nh - h) // 2
            elif direction == "left":
                left = int((nw - w) * (1 - progress))
                top = (nh - h) // 2
            elif direction == "up":
                left = (nw - w) // 2
                top = int((nh - h) * (1 - progress))
            else:  # down
                left = (nw - w) // 2
                top = int((nh - h) * progress)
            img = img.crop((left, top, left + w, top + h))
            return np.array(img)

        return clip.transform(ken_burns)


class ZoomToEffect(PostEffect):
    """Zoom to a specific point and hold — great for highlighting UI elements."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        max_scale = params.get("scale", 1.8)
        tx = params.get("target_x", 0.5)
        ty = params.get("target_y", 0.5)
        duration = clip.duration

        def zoom_to(get_frame: Any, t: float) -> Any:
            import numpy as np
            from PIL import Image

            progress = t / duration if duration else 0
            # Fast ease-out: zoom in quickly, hold
            p = 1 - (1 - min(progress * 2, 1)) ** 3
            s = 1 + (max_scale - 1) * p
            frame = get_frame(t)
            img = Image.fromarray(frame)
            w, h = img.size
            nw, nh = int(w * s), int(h * s)
            img = img.resize((nw, nh), Image.LANCZOS)
            left = int((nw - w) * tx)
            top = int((nh - h) * ty)
            img = img.crop((left, top, left + w, top + h))
            return np.array(img)

        return clip.transform(zoom_to)


class DollyZoomEffect(PostEffect):
    """Vertigo / dolly-zoom: zoom in while widening the crop (or reverse)."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        intensity = params.get("intensity", 0.3)
        duration = clip.duration

        def dolly(get_frame: Any, t: float) -> Any:
            import numpy as np
            from PIL import Image

            progress = t / duration if duration else 0
            # Zoom increases while crop area widens — opposing motions
            zoom = 1 + intensity * progress
            crop_expand = 1 - intensity * 0.5 * progress
            frame = get_frame(t)
            img = Image.fromarray(frame)
            w, h = img.size
            nw, nh = int(w * zoom), int(h * zoom)
            img = img.resize((nw, nh), Image.LANCZOS)
            # Crop a slightly different region to create the vertigo feel
            cw = int(w * crop_expand)
            ch = int(h * crop_expand)
            left = (nw - cw) // 2
            top = (nh - ch) // 2
            img = img.crop((left, top, left + cw, top + ch))
            img = img.resize((w, h), Image.LANCZOS)
            return np.array(img)

        return clip.transform(dolly)


class ElasticZoomEffect(PostEffect):
    """Zoom with elastic overshoot bounce (ease-out-back)."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        max_scale = params.get("scale", 1.3)
        duration = clip.duration

        def elastic(get_frame: Any, t: float) -> Any:
            import numpy as np
            from PIL import Image

            progress = t / duration if duration else 0
            # Ease-out-back: overshoot then settle
            c1 = 1.70158
            c3 = c1 + 1
            p = min(progress * 2, 1)  # zoom in first half
            ease = 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2
            s = 1 + (max_scale - 1) * max(ease, 0)
            frame = get_frame(t)
            img = Image.fromarray(frame)
            w, h = img.size
            nw, nh = int(w * s), int(h * s)
            nw = max(nw, w)
            nh = max(nh, h)
            img = img.resize((nw, nh), Image.LANCZOS)
            left = (nw - w) // 2
            top = (nh - h) // 2
            img = img.crop((left, top, left + w, top + h))
            return np.array(img)

        return clip.transform(elastic)


class CameraShakeEffect(PostEffect):
    """Subtle camera shake / handheld feel."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        intensity = params.get("intensity", 0.3)
        speed = params.get("speed", 8.0)
        duration = clip.duration

        def shake(get_frame: Any, t: float) -> Any:
            import numpy as np
            from PIL import Image

            frame = get_frame(t)
            img = Image.fromarray(frame)
            w, h = img.size
            max_shift = int(w * 0.01 * intensity * 10)
            if max_shift < 1:
                return frame
            # Deterministic pseudo-random from time
            dx = int(max_shift * np.sin(t * speed * 2 * np.pi))
            dy = int(max_shift * np.cos(t * speed * 2.7 * np.pi))
            # Scale up slightly to allow shifting without black borders
            s = 1 + 0.02 * intensity
            nw, nh = int(w * s), int(h * s)
            img = img.resize((nw, nh), Image.LANCZOS)
            cx = (nw - w) // 2 + dx
            cy = (nh - h) // 2 + dy
            cx = max(0, min(cx, nw - w))
            cy = max(0, min(cy, nh - h))
            img = img.crop((cx, cy, cx + w, cy + h))
            return np.array(img)

        return clip.transform(shake)


class WhipPanEffect(PostEffect):
    """Fast horizontal/vertical pan with motion blur — great for transitions."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        direction = params.get("direction", "right")
        duration = clip.duration

        def whip(get_frame: Any, t: float) -> Any:
            import numpy as np
            from PIL import Image, ImageFilter

            progress = t / duration if duration else 0
            frame = get_frame(t)
            # Apply blur only during the middle of the clip (20%-80%)
            blur_zone = max(0, min(1, (progress - 0.2) / 0.6))
            blur_amount = 20 * np.sin(blur_zone * np.pi)  # peak in middle

            if blur_amount < 1:
                return frame

            img = Image.fromarray(frame)
            w, h = img.size
            if direction in ("right", "left"):
                img = img.filter(ImageFilter.BoxBlur((blur_amount, 0)))
            else:
                img = img.filter(ImageFilter.BoxBlur((0, blur_amount)))

            # Shift offset during blur
            shift = int(w * 0.05 * np.sin(blur_zone * np.pi))
            if direction in ("right", "down"):
                shift = -shift

            result = np.array(img)
            if direction in ("right", "left"):
                result = np.roll(result, shift, axis=1)
            else:
                result = np.roll(result, shift, axis=0)
            return result

        return clip.transform(whip)


class RotateEffect(PostEffect):
    """Gentle animated rotation — subtle tilt for dynamic feel."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        max_angle = params.get("angle", 3.0)
        speed = params.get("speed", 1.0)
        duration = clip.duration

        def rotate(get_frame: Any, t: float) -> Any:
            import numpy as np
            from PIL import Image

            progress = t / duration if duration else 0
            angle = max_angle * np.sin(progress * speed * 2 * np.pi)
            frame = get_frame(t)
            img = Image.fromarray(frame)
            w, h = img.size
            # Rotate with slight upscale to avoid black corners
            s = 1.05
            nw, nh = int(w * s), int(h * s)
            img = img.resize((nw, nh), Image.LANCZOS)
            img = img.rotate(angle, Image.BICUBIC, expand=False)
            left = (nw - w) // 2
            top = (nh - h) // 2
            img = img.crop((left, top, left + w, top + h))
            return np.array(img)

        return clip.transform(rotate)


# ── Cinematic effects ─────────────────────────────────────────────────────────


class LetterboxEffect(PostEffect):
    """Cinematic black bars (e.g. 2.35:1 cinemascope)."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        ratio = params.get("ratio", 2.35)

        def letterbox(get_frame: Any, t: float) -> Any:
            import numpy as np

            frame = get_frame(t).copy()
            h, w = frame.shape[:2]
            target_h = int(w / ratio)
            if target_h >= h:
                return frame
            bar = (h - target_h) // 2
            frame[:bar] = 0
            frame[h - bar:] = 0
            return frame

        return clip.transform(letterbox)


class FilmGrainEffect(PostEffect):
    """Analog film grain overlay."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        intensity = params.get("intensity", 0.3)

        def grain(get_frame: Any, t: float) -> Any:
            import numpy as np

            frame = get_frame(t).copy()
            h, w = frame.shape[:2]
            rng = np.random.default_rng(int(t * 1000) % 2**31)
            noise = rng.integers(-50, 50, size=(h, w), dtype=np.int16)
            noise = (noise * intensity).astype(np.int16)
            # Add noise to all channels
            result = frame.astype(np.int16) + noise[..., np.newaxis]
            return np.clip(result, 0, 255).astype(np.uint8)

        return clip.transform(grain)


class ColorGradeEffect(PostEffect):
    """Color grading presets: warm, cool, desaturate, vintage, cinematic."""

    PRESETS = {
        "warm": (1.1, 1.0, 0.9),
        "cool": (0.9, 1.0, 1.1),
        "desaturate": None,  # special handling
        "vintage": (1.1, 0.95, 0.8),
        "cinematic": (0.95, 1.05, 1.1),
    }

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        preset = params.get("preset", "cinematic")
        multipliers = self.PRESETS.get(preset, self.PRESETS["cinematic"])

        def grade(get_frame: Any, t: float) -> Any:
            import numpy as np

            frame = get_frame(t).copy()

            if preset == "desaturate":
                gray = np.mean(frame, axis=2, keepdims=True)
                frame = (frame * 0.4 + gray * 0.6).astype(np.uint8)
            else:
                r, g, b = multipliers  # type: ignore[misc]
                result = frame.astype(np.float32)
                result[:, :, 0] = result[:, :, 0] * r
                result[:, :, 1] = result[:, :, 1] * g
                result[:, :, 2] = result[:, :, 2] * b
                frame = np.clip(result, 0, 255).astype(np.uint8)
            return frame

        return clip.transform(grade)


class FocusPullEffect(PostEffect):
    """Rack focus: transition from sharp to blurry (or reverse)."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        direction = params.get("direction", "out")
        intensity = params.get("intensity", 0.5)
        duration = clip.duration

        def focus(get_frame: Any, t: float) -> Any:
            from PIL import Image, ImageFilter

            import numpy as np

            progress = t / duration if duration else 0
            if direction == "in":
                blur = intensity * 15 * (1 - progress)
            else:
                blur = intensity * 15 * progress

            frame = get_frame(t)
            if blur < 0.5:
                return frame
            img = Image.fromarray(frame)
            img = img.filter(ImageFilter.GaussianBlur(radius=blur))
            return np.array(img)

        return clip.transform(focus)


class TiltShiftEffect(PostEffect):
    """Miniature / tilt-shift: sharp band in center, blurred top and bottom."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        intensity = params.get("intensity", 0.6)
        focus_pos = params.get("focus_position", 0.5)

        def tilt(get_frame: Any, t: float) -> Any:
            import numpy as np
            from PIL import Image, ImageFilter

            frame = get_frame(t)
            img = Image.fromarray(frame)
            blurred = img.filter(ImageFilter.GaussianBlur(radius=intensity * 12))
            h, w = frame.shape[:2]

            # Create gradient mask: sharp band around focus_pos
            Y = np.linspace(0, 1, h)
            dist = np.abs(Y - focus_pos)
            # Smooth transition: sharp within 15% of focus, blur outside
            mask = np.clip((dist - 0.15) / 0.2, 0, 1)
            mask = mask[:, np.newaxis, np.newaxis]

            # Blend sharp and blurred
            result = frame * (1 - mask) + np.array(blurred) * mask
            return result.astype(np.uint8)

        return clip.transform(tilt)


# ── Retro / stylised effects ─────────────────────────────────────────────────


class CrtScanlinesEffect(PostEffect):
    """CRT monitor scanlines + slight darkening between lines."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        intensity = params.get("intensity", 0.4)
        line_spacing = params.get("line_spacing", 3)

        def scanlines(get_frame: Any, t: float) -> Any:
            import numpy as np

            frame = get_frame(t).copy()
            h, w = frame.shape[:2]
            # Dark every Nth row
            for y in range(0, h, line_spacing):
                frame[y] = (frame[y].astype(np.float32) * (1 - intensity)).astype(np.uint8)
            return frame

        return clip.transform(scanlines)


class ChromaticAberrationEffect(PostEffect):
    """RGB channel offset on edges — classic lens distortion."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        offset = params.get("offset", 3)

        def aberration(get_frame: Any, t: float) -> Any:
            import numpy as np

            frame = get_frame(t).copy()
            h, w = frame.shape[:2]
            result = np.zeros_like(frame)
            # Red channel shifted right
            result[:, offset:, 0] = frame[:, :w - offset, 0]
            # Green channel centered
            result[:, :, 1] = frame[:, :, 1]
            # Blue channel shifted left
            result[:, :w - offset, 2] = frame[:, offset:, 2]
            return result

        return clip.transform(aberration)


class VhsDistortionEffect(PostEffect):
    """VHS tape distortion: scanlines + noise + horizontal jitter."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        intensity = params.get("intensity", 0.4)

        def vhs(get_frame: Any, t: float) -> Any:
            import numpy as np

            frame = get_frame(t).copy()
            h, w = frame.shape[:2]
            rng = np.random.default_rng(int(t * 1000) % 2**31)
            # Scanlines
            for y in range(0, h, 2):
                frame[y] = (frame[y].astype(np.float32) * (1 - intensity * 0.3)).astype(np.uint8)
            # Random horizontal jitter on a few rows
            num_jitter = int(5 * intensity)
            for _ in range(num_jitter):
                y = rng.integers(0, h)
                shift = rng.integers(-int(w * intensity * 0.02), int(w * intensity * 0.02))
                frame[y] = np.roll(frame[y], shift, axis=0)
            # Noise
            noise = rng.integers(-int(20 * intensity), int(20 * intensity), size=(h, w), dtype=np.int16)
            result = frame.astype(np.int16) + noise[..., np.newaxis]
            return np.clip(result, 0, 255).astype(np.uint8)

        return clip.transform(vhs)


class PixelSortEffect(PostEffect):
    """Sort pixels by brightness on selected rows for a glitch-art look."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        threshold = params.get("threshold", 0.5)
        direction = params.get("direction", "horizontal")

        def pixel_sort(get_frame: Any, t: float) -> Any:
            import numpy as np

            frame = get_frame(t).copy()
            h, w = frame.shape[:2]
            rng = np.random.default_rng(int(t * 1000) % 2**31)
            # Sort ~20% of rows/cols
            if direction == "horizontal":
                indices = rng.choice(h, size=max(1, h // 5), replace=False)
                for y in indices:
                    row = frame[y]
                    brightness = np.mean(row, axis=1)
                    mask = brightness > threshold * 255
                    if mask.sum() < 2:
                        continue
                    positions = np.where(mask)[0]
                    start, end = positions[0], positions[-1] + 1
                    segment = row[start:end]
                    order = np.argsort(np.mean(segment, axis=1))
                    frame[y, start:end] = segment[order]
            else:
                indices = rng.choice(w, size=max(1, w // 5), replace=False)
                for x in indices:
                    col = frame[:, x]
                    brightness = np.mean(col, axis=1)
                    mask = brightness > threshold * 255
                    if mask.sum() < 2:
                        continue
                    positions = np.where(mask)[0]
                    start, end = positions[0], positions[-1] + 1
                    segment = col[start:end]
                    order = np.argsort(np.mean(segment, axis=1))
                    frame[start:end, x] = segment[order]
            return frame

        return clip.transform(pixel_sort)


# ── Depth & light effects ────────────────────────────────────────────────────


class BloomEffect(PostEffect):
    """Light bloom / glow around bright areas."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        threshold_val = params.get("threshold", 0.7)
        radius = params.get("radius", 10.0)
        intensity = params.get("intensity", 0.6)

        def bloom(get_frame: Any, t: float) -> Any:
            import numpy as np
            from PIL import Image, ImageFilter

            frame = get_frame(t)
            img = Image.fromarray(frame)
            # Extract bright pixels
            arr = frame.astype(np.float32) / 255.0
            brightness = np.mean(arr, axis=2)
            mask = (brightness > threshold_val).astype(np.float32)
            # Create glow layer: bright pixels only, then blur
            bright = (arr * mask[..., np.newaxis] * 255).astype(np.uint8)
            glow = Image.fromarray(bright).filter(ImageFilter.GaussianBlur(radius=radius))
            # Additive blend
            result = np.clip(
                frame.astype(np.float32) + np.array(glow).astype(np.float32) * intensity,
                0, 255,
            ).astype(np.uint8)
            return result

        return clip.transform(bloom)


class BokehBlurEffect(PostEffect):
    """Depth-of-field with sharp center focus and blurred surroundings."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        focus_area = params.get("focus_area", 0.3)
        radius = params.get("radius", 8.0)

        def bokeh(get_frame: Any, t: float) -> Any:
            import numpy as np
            from PIL import Image, ImageFilter

            frame = get_frame(t)
            img = Image.fromarray(frame)
            blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
            h, w = frame.shape[:2]
            # Circular mask: sharp in center, blurred outside
            Y, X = np.ogrid[:h, :w]
            cx, cy = w / 2, h / 2
            r = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
            r_max = np.sqrt(cx ** 2 + cy ** 2) * focus_area
            mask = np.clip((r - r_max) / (r_max * 0.5), 0, 1)
            mask = mask[..., np.newaxis]
            result = frame * (1 - mask) + np.array(blurred) * mask
            return result.astype(np.uint8)

        return clip.transform(bokeh)


class LightLeakEffect(PostEffect):
    """Warm animated light leak sweeping across the frame."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        color = params.get("color", "#FF8C00")
        intensity = params.get("intensity", 0.35)
        speed = params.get("speed", 1.0)
        duration = clip.duration

        def light_leak(get_frame: Any, t: float) -> Any:
            import numpy as np

            frame = get_frame(t).copy()
            h, w = frame.shape[:2]
            progress = (t * speed / duration) % 1.0 if duration else 0
            # Parse color
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            # Gaussian-shaped sweep across width
            X = np.linspace(0, 1, w)
            center = progress
            leak = np.exp(-((X - center) ** 2) / (2 * 0.08 ** 2))
            leak = leak[np.newaxis, :, np.newaxis]
            tint = np.array([r, g, b], dtype=np.float32) / 255.0
            overlay = leak * tint * intensity * 255
            result = np.clip(frame.astype(np.float32) + overlay, 0, 255)
            return result.astype(np.uint8)

        return clip.transform(light_leak)


# ── Transition effects ───────────────────────────────────────────────────────


class WipeEffect(PostEffect):
    """Wipe transition: progressive reveal from one direction."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        direction = params.get("direction", "left")
        style = params.get("style", "hard")
        duration = clip.duration

        def wipe(get_frame: Any, t: float) -> Any:
            import numpy as np

            frame = get_frame(t).copy()
            h, w = frame.shape[:2]
            progress = t / duration if duration else 0
            if direction == "left":
                edge = int(w * progress)
                if style == "soft" and edge > 0:
                    grad = np.linspace(0, 1, min(40, edge))
                    for i, a in enumerate(grad):
                        col = max(0, edge - len(grad) + i)
                        frame[:, col] = (frame[:, col].astype(np.float32) * a).astype(np.uint8)
                frame[:, edge:] = 0
            elif direction == "right":
                edge = int(w * (1 - progress))
                frame[:, :edge] = 0
            elif direction == "down":
                edge = int(h * progress)
                frame[edge:, :] = 0
            else:  # up
                edge = int(h * (1 - progress))
                frame[:edge, :] = 0
            return frame

        return clip.transform(wipe)


class IrisEffect(PostEffect):
    """Circular iris open/close — classic cinema transition."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        direction = params.get("direction", "in")
        duration = clip.duration

        def iris(get_frame: Any, t: float) -> Any:
            import numpy as np

            frame = get_frame(t).copy()
            h, w = frame.shape[:2]
            progress = t / duration if duration else 0
            if direction == "out":
                progress = 1 - progress
            Y, X = np.ogrid[:h, :w]
            cx, cy = w / 2, h / 2
            r = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
            r_max = np.sqrt(cx ** 2 + cy ** 2)
            threshold = r_max * progress
            mask = (r <= threshold).astype(np.float32)
            frame = (frame * mask[..., np.newaxis]).astype(np.uint8)
            return frame

        return clip.transform(iris)


class DissolveNoiseEffect(PostEffect):
    """Noise-based dissolve: pixels appear/disappear based on noise pattern."""

    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        grain_size = params.get("grain_size", 4)
        duration = clip.duration

        def dissolve(get_frame: Any, t: float) -> Any:
            import numpy as np

            frame = get_frame(t).copy()
            h, w = frame.shape[:2]
            progress = t / duration if duration else 0
            # Generate block noise pattern (deterministic per grain_size)
            rng = np.random.default_rng(42)
            small_h = h // grain_size + 1
            small_w = w // grain_size + 1
            noise = rng.random((small_h, small_w))
            # Upscale noise to frame size
            noise = np.repeat(np.repeat(noise, grain_size, axis=0), grain_size, axis=1)[:h, :w]
            mask = (noise < progress).astype(np.float32)
            frame = (frame * mask[..., np.newaxis]).astype(np.uint8)
            return frame

        return clip.transform(dissolve)


def register_all_post_effects(registry: Any) -> None:
    """Register all built-in post-processing effects."""
    registry.register_post("parallax", ParallaxEffect())
    registry.register_post("zoom_pulse", ZoomPulseEffect())
    registry.register_post("fade_in", FadeInEffect())
    registry.register_post("fade_out", FadeOutEffect())
    registry.register_post("vignette", VignetteEffect())
    registry.register_post("glitch", GlitchEffect())
    registry.register_post("slide_in", SlideInEffect())
    # Camera movement effects
    registry.register_post("drone_zoom", DroneZoomEffect())
    registry.register_post("ken_burns", KenBurnsEffect())
    registry.register_post("zoom_to", ZoomToEffect())
    registry.register_post("dolly_zoom", DollyZoomEffect())
    registry.register_post("elastic_zoom", ElasticZoomEffect())
    registry.register_post("camera_shake", CameraShakeEffect())
    registry.register_post("whip_pan", WhipPanEffect())
    registry.register_post("rotate", RotateEffect())
    # Cinematic effects
    registry.register_post("letterbox", LetterboxEffect())
    registry.register_post("film_grain", FilmGrainEffect())
    registry.register_post("color_grade", ColorGradeEffect())
    registry.register_post("focus_pull", FocusPullEffect())
    registry.register_post("tilt_shift", TiltShiftEffect())
    # Retro / stylised effects
    registry.register_post("crt_scanlines", CrtScanlinesEffect())
    registry.register_post("chromatic_aberration", ChromaticAberrationEffect())
    registry.register_post("vhs_distortion", VhsDistortionEffect())
    registry.register_post("pixel_sort", PixelSortEffect())
    # Depth & light effects
    registry.register_post("bloom", BloomEffect())
    registry.register_post("bokeh_blur", BokehBlurEffect())
    registry.register_post("light_leak", LightLeakEffect())
    # Transition effects
    registry.register_post("wipe", WipeEffect())
    registry.register_post("iris", IrisEffect())
    registry.register_post("dissolve_noise", DissolveNoiseEffect())
