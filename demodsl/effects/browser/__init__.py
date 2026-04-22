"""Browser effects — one file per effect, composable via js_builder."""

from __future__ import annotations

from typing import Any

from demodsl.effects.browser.spotlight import SpotlightEffect
from demodsl.effects.browser.highlight import HighlightEffect
from demodsl.effects.browser.confetti import ConfettiEffect
from demodsl.effects.browser.typewriter import TypewriterEffect
from demodsl.effects.browser.glow import GlowEffect
from demodsl.effects.browser.shockwave import ShockwaveEffect
from demodsl.effects.browser.sparkle import SparkleEffect
from demodsl.effects.browser.cursor_trail import CursorTrailEffect
from demodsl.effects.browser.cursor_trail_rainbow import CursorTrailRainbowEffect
from demodsl.effects.browser.cursor_trail_comet import CursorTrailCometEffect
from demodsl.effects.browser.cursor_trail_glow import CursorTrailGlowEffect
from demodsl.effects.browser.cursor_trail_line import CursorTrailLineEffect
from demodsl.effects.browser.cursor_trail_particles import CursorTrailParticlesEffect
from demodsl.effects.browser.cursor_trail_fire import CursorTrailFireEffect
from demodsl.effects.browser.ripple import RippleEffect
from demodsl.effects.browser.neon_glow import NeonGlowEffect
from demodsl.effects.browser.success_checkmark import SuccessCheckmarkEffect
from demodsl.effects.browser.emoji_rain import EmojiRainEffect
from demodsl.effects.browser.fireworks import FireworksEffect
from demodsl.effects.browser.bubbles import BubblesEffect
from demodsl.effects.browser.snow import SnowEffect
from demodsl.effects.browser.star_burst import StarBurstEffect
from demodsl.effects.browser.party_popper import PartyPopperEffect
from demodsl.effects.browser.text_highlight import TextHighlightEffect
from demodsl.effects.browser.text_scramble import TextScrambleEffect
from demodsl.effects.browser.magnetic_hover import MagneticHoverEffect
from demodsl.effects.browser.tooltip_annotation import TooltipAnnotationEffect
from demodsl.effects.browser.morphing_background import MorphingBackgroundEffect
from demodsl.effects.browser.matrix_rain import MatrixRainEffect
from demodsl.effects.browser.frosted_glass import FrostedGlassEffect
from demodsl.effects.browser.progress_bar import ProgressBarEffect
from demodsl.effects.browser.countdown_timer import CountdownTimerEffect
from demodsl.effects.browser.callout_arrow import CalloutArrowEffect

__all__ = [
    "SpotlightEffect",
    "HighlightEffect",
    "ConfettiEffect",
    "TypewriterEffect",
    "GlowEffect",
    "ShockwaveEffect",
    "SparkleEffect",
    "CursorTrailEffect",
    "CursorTrailRainbowEffect",
    "CursorTrailCometEffect",
    "CursorTrailGlowEffect",
    "CursorTrailLineEffect",
    "CursorTrailParticlesEffect",
    "CursorTrailFireEffect",
    "RippleEffect",
    "NeonGlowEffect",
    "SuccessCheckmarkEffect",
    "EmojiRainEffect",
    "FireworksEffect",
    "BubblesEffect",
    "SnowEffect",
    "StarBurstEffect",
    "PartyPopperEffect",
    "TextHighlightEffect",
    "TextScrambleEffect",
    "MagneticHoverEffect",
    "TooltipAnnotationEffect",
    "MorphingBackgroundEffect",
    "MatrixRainEffect",
    "FrostedGlassEffect",
    "ProgressBarEffect",
    "CountdownTimerEffect",
    "CalloutArrowEffect",
    "register_all_browser_effects",
]

# Explicit mapping: effect name → class (used by register_all_browser_effects)
_BROWSER_EFFECTS: dict[str, type] = {
    "spotlight": SpotlightEffect,
    "highlight": HighlightEffect,
    "confetti": ConfettiEffect,
    "typewriter": TypewriterEffect,
    "glow": GlowEffect,
    "shockwave": ShockwaveEffect,
    "sparkle": SparkleEffect,
    "cursor_trail": CursorTrailEffect,
    "cursor_trail_rainbow": CursorTrailRainbowEffect,
    "cursor_trail_comet": CursorTrailCometEffect,
    "cursor_trail_glow": CursorTrailGlowEffect,
    "cursor_trail_line": CursorTrailLineEffect,
    "cursor_trail_particles": CursorTrailParticlesEffect,
    "cursor_trail_fire": CursorTrailFireEffect,
    "ripple": RippleEffect,
    "neon_glow": NeonGlowEffect,
    "success_checkmark": SuccessCheckmarkEffect,
    "emoji_rain": EmojiRainEffect,
    "fireworks": FireworksEffect,
    "bubbles": BubblesEffect,
    "snow": SnowEffect,
    "star_burst": StarBurstEffect,
    "party_popper": PartyPopperEffect,
    "text_highlight": TextHighlightEffect,
    "text_scramble": TextScrambleEffect,
    "magnetic_hover": MagneticHoverEffect,
    "tooltip_annotation": TooltipAnnotationEffect,
    "morphing_background": MorphingBackgroundEffect,
    "matrix_rain": MatrixRainEffect,
    "frosted_glass": FrostedGlassEffect,
    "progress_bar": ProgressBarEffect,
    "countdown_timer": CountdownTimerEffect,
    "callout_arrow": CalloutArrowEffect,
}


def register_all_browser_effects(registry: Any) -> None:
    """Register all built-in browser effects."""
    for name, cls in _BROWSER_EFFECTS.items():
        registry.register_browser(name, cls())
