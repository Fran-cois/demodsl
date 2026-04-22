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
from demodsl.effects.browser.keyboard_shortcut import KeyboardShortcutEffect
from demodsl.effects.browser.zoom_focus import ZoomFocusEffect
from demodsl.effects.browser.depth_blur import DepthBlurEffect
from demodsl.effects.browser.animated_annotation import AnimatedAnnotationEffect
from demodsl.effects.browser.perspective_tilt import PerspectiveTiltEffect
from demodsl.effects.browser.glassmorphism_float import GlassmorphismFloatEffect
from demodsl.effects.browser.morph_transition import MorphTransitionEffect
from demodsl.effects.browser.scroll_parallax import ScrollParallaxEffect
from demodsl.effects.browser.dark_mode_toggle import DarkModeToggleEffect
from demodsl.effects.browser.click_particles import ClickParticlesEffect
from demodsl.effects.browser.skeleton_loading import SkeletonLoadingEffect
from demodsl.effects.browser.tooltip_pop import TooltipPopEffect
from demodsl.effects.browser.magnifier import MagnifierEffect
from demodsl.effects.browser.drag_drop import DragDropEffect
from demodsl.effects.browser.progress_ring import ProgressRingEffect
from demodsl.effects.browser.device_frame import DeviceFrameEffect
from demodsl.effects.browser.rotation_3d import Rotation3DEffect
from demodsl.effects.browser.split_screen import SplitScreenEffect
from demodsl.effects.browser.directional_blur import DirectionalBlurEffect
from demodsl.effects.browser.notification_toast import NotificationToastEffect
from demodsl.effects.browser.dashboard_timelapse import DashboardTimelapseEffect
from demodsl.effects.browser.click_ripple import ClickRippleEffect
from demodsl.effects.browser.connection_trace import ConnectionTraceEffect
from demodsl.effects.browser.sticky_element import StickyElementEffect
from demodsl.effects.browser.chart_draw import ChartDrawEffect
from demodsl.effects.browser.odometer import OdometerEffect
from demodsl.effects.browser.heatmap import HeatmapEffect
from demodsl.effects.browser.zoom_through import ZoomThroughEffect
from demodsl.effects.browser.infinite_canvas import InfiniteCanvasEffect
from demodsl.effects.browser.tab_swipe import TabSwipeEffect
from demodsl.effects.browser.xray_view import XrayViewEffect
from demodsl.effects.browser.glass_reflection import GlassReflectionEffect
from demodsl.effects.browser.paper_texture import PaperTextureEffect
from demodsl.effects.browser.ui_shimmer import UiShimmerEffect
from demodsl.effects.browser.app_switcher import AppSwitcherEffect

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
    "KeyboardShortcutEffect",
    "ZoomFocusEffect",
    "DepthBlurEffect",
    "AnimatedAnnotationEffect",
    "PerspectiveTiltEffect",
    "GlassmorphismFloatEffect",
    "MorphTransitionEffect",
    "ScrollParallaxEffect",
    "DarkModeToggleEffect",
    "ClickParticlesEffect",
    "SkeletonLoadingEffect",
    "TooltipPopEffect",
    "MagnifierEffect",
    "DragDropEffect",
    "ProgressRingEffect",
    "DeviceFrameEffect",
    "Rotation3DEffect",
    "SplitScreenEffect",
    "DirectionalBlurEffect",
    "NotificationToastEffect",
    "DashboardTimelapseEffect",
    "ClickRippleEffect",
    "ConnectionTraceEffect",
    "StickyElementEffect",
    "ChartDrawEffect",
    "OdometerEffect",
    "HeatmapEffect",
    "ZoomThroughEffect",
    "InfiniteCanvasEffect",
    "TabSwipeEffect",
    "XrayViewEffect",
    "GlassReflectionEffect",
    "PaperTextureEffect",
    "UiShimmerEffect",
    "AppSwitcherEffect",
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
    "keyboard_shortcut": KeyboardShortcutEffect,
    "zoom_focus": ZoomFocusEffect,
    "depth_blur": DepthBlurEffect,
    "animated_annotation": AnimatedAnnotationEffect,
    "perspective_tilt": PerspectiveTiltEffect,
    "glassmorphism_float": GlassmorphismFloatEffect,
    "morph_transition": MorphTransitionEffect,
    "scroll_parallax": ScrollParallaxEffect,
    "dark_mode_toggle": DarkModeToggleEffect,
    "click_particles": ClickParticlesEffect,
    "skeleton_loading": SkeletonLoadingEffect,
    "tooltip_pop": TooltipPopEffect,
    "magnifier": MagnifierEffect,
    "drag_drop": DragDropEffect,
    "progress_ring": ProgressRingEffect,
    "device_frame": DeviceFrameEffect,
    "rotation_3d": Rotation3DEffect,
    "split_screen": SplitScreenEffect,
    "directional_blur": DirectionalBlurEffect,
    "notification_toast": NotificationToastEffect,
    "dashboard_timelapse": DashboardTimelapseEffect,
    "click_ripple": ClickRippleEffect,
    "connection_trace": ConnectionTraceEffect,
    "sticky_element": StickyElementEffect,
    "chart_draw": ChartDrawEffect,
    "odometer": OdometerEffect,
    "heatmap": HeatmapEffect,
    "zoom_through": ZoomThroughEffect,
    "infinite_canvas": InfiniteCanvasEffect,
    "tab_swipe": TabSwipeEffect,
    "xray_view": XrayViewEffect,
    "glass_reflection": GlassReflectionEffect,
    "paper_texture": PaperTextureEffect,
    "ui_shimmer": UiShimmerEffect,
    "app_switcher": AppSwitcherEffect,
}


def register_all_browser_effects(registry: Any) -> None:
    """Register all built-in browser effects."""
    for name, cls in _BROWSER_EFFECTS.items():
        registry.register_browser(name, cls())
