"""Glow-select overlay — Apple Intelligence-style animated glow around elements."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class GlowSelectOverlay:
    """Injects a reusable animated gradient glow overlay around targeted elements.

    Mimics the Apple Intelligence highlight: an animated gradient border
    (purple → indigo → pink → purple) that smoothly appears around the
    element bounding box, pulses once, then fades out.

    JS globals injected:
    * ``window.__demodsl_glow_show(x, y, w, h)`` — show glow at rect
    * ``window.__demodsl_glow_hide()``            — fade out and remove
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.enabled = config.get("enabled", True)
        self.colors: list[str] = config.get(
            "colors", ["#a855f7", "#6366f1", "#ec4899", "#a855f7"]
        )
        self.duration = config.get("duration", 0.8)
        self.padding = config.get("padding", 8)
        self.border_radius = config.get("border_radius", 12)
        self.intensity = config.get("intensity", 0.9)

    def inject(self, evaluate_js: Any) -> None:
        """Inject the glow overlay element, keyframes, and JS helper functions."""
        if not self.enabled:
            return

        gradient_stops = ", ".join(self.colors)
        dur_s = f"{self.duration}s"
        pad = self.padding
        br = self.border_radius

        evaluate_js(f"""(() => {{
            // Cleanup previous
            document.getElementById('__demodsl_glow_overlay')?.remove();
            document.getElementById('__demodsl_glow_style')?.remove();

            const style = document.createElement('style');
            style.id = '__demodsl_glow_style';
            style.textContent = `
                @keyframes __demodsl_glow_rotate {{
                    0%   {{ filter: hue-rotate(0deg); }}
                    100% {{ filter: hue-rotate(360deg); }}
                }}
                @keyframes __demodsl_glow_fadein {{
                    0%   {{ opacity: 0; transform: scale(0.95); }}
                    100% {{ opacity: 1; transform: scale(1); }}
                }}
                @keyframes __demodsl_glow_pulse {{
                    0%, 100% {{ opacity: {self.intensity}; }}
                    50%      {{ opacity: {max(0.4, self.intensity - 0.3)}; }}
                }}
                @keyframes __demodsl_glow_fadeout {{
                    0%   {{ opacity: 1; }}
                    100% {{ opacity: 0; }}
                }}
            `;
            document.head.appendChild(style);

            const overlay = document.createElement('div');
            overlay.id = '__demodsl_glow_overlay';
            overlay.style.cssText = `
                position: fixed; z-index: 199997; pointer-events: none;
                opacity: 0; display: none;
                border-radius: {br}px;
                background: transparent;
                box-shadow:
                    0 0 15px 4px {self.colors[0]}80,
                    0 0 30px 8px {self.colors[1] if len(self.colors) > 1 else self.colors[0]}50,
                    inset 0 0 15px 2px {self.colors[0]}30;
                border: 2px solid;
                border-image: linear-gradient(135deg, {gradient_stops}) 1;
                animation: __demodsl_glow_rotate {dur_s} linear infinite;
            `;
            document.body.appendChild(overlay);

            window.__demodsl_glow_show = function(x, y, w, h) {{
                overlay.style.left   = (x - {pad}) + 'px';
                overlay.style.top    = (y - {pad}) + 'px';
                overlay.style.width  = (w + {pad * 2}) + 'px';
                overlay.style.height = (h + {pad * 2}) + 'px';
                overlay.style.display = 'block';
                overlay.style.opacity = '1';
                overlay.style.animation = `
                    __demodsl_glow_fadein 0.25s ease-out,
                    __demodsl_glow_rotate {dur_s} linear infinite,
                    __demodsl_glow_pulse 1.2s ease-in-out infinite 0.25s
                `;
            }};

            window.__demodsl_glow_hide = function() {{
                overlay.style.animation = '__demodsl_glow_fadeout 0.3s ease-in forwards';
                setTimeout(() => {{
                    overlay.style.display = 'none';
                    overlay.style.opacity = '0';
                }}, 350);
            }};
        }})()""")
        logger.debug("Glow-select overlay injected")

    def show(self, evaluate_js: Any, bbox: dict[str, float]) -> None:
        """Show the glow around the given bounding box and wait for the entrance."""
        if not self.enabled:
            return
        evaluate_js(
            f"window.__demodsl_glow_show("
            f"{bbox['x']}, {bbox['y']}, {bbox['width']}, {bbox['height']})"
        )
        time.sleep(0.3)  # wait for fadein

    def hide(self, evaluate_js: Any) -> None:
        """Fade out the glow overlay."""
        if not self.enabled:
            return
        evaluate_js("window.__demodsl_glow_hide()")
        time.sleep(0.35)
