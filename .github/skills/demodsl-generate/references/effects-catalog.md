# DemoDSL Effects Catalog

Auto-generated from `demodsl/effects/`. All effects with their parameters.

## Browser Effects (JS-injected during capture)

| Effect | Class |
|--------|-------|
| `animated_annotation` | `AnimatedAnnotationEffect` |
| `app_switcher` | `AppSwitcherEffect` |
| `bubbles` | `BubblesEffect` |
| `callout_arrow` | `CalloutArrowEffect` |
| `chart_draw` | `ChartDrawEffect` |
| `click_particles` | `ClickParticlesEffect` |
| `click_ripple` | `ClickRippleEffect` |
| `confetti` | `ConfettiEffect` |
| `connection_trace` | `ConnectionTraceEffect` |
| `countdown_timer` | `CountdownTimerEffect` |
| `cursor_trail` | `CursorTrailEffect` |
| `cursor_trail_comet` | `CursorTrailCometEffect` |
| `cursor_trail_fire` | `CursorTrailFireEffect` |
| `cursor_trail_glow` | `CursorTrailGlowEffect` |
| `cursor_trail_line` | `CursorTrailLineEffect` |
| `cursor_trail_particles` | `CursorTrailParticlesEffect` |
| `cursor_trail_rainbow` | `CursorTrailRainbowEffect` |
| `dark_mode_toggle` | `DarkModeToggleEffect` |
| `dashboard_timelapse` | `DashboardTimelapseEffect` |
| `depth_blur` | `DepthBlurEffect` |
| `device_frame` | `DeviceFrameEffect` |
| `directional_blur` | `DirectionalBlurEffect` |
| `drag_drop` | `DragDropEffect` |
| `emoji_rain` | `EmojiRainEffect` |
| `fireworks` | `FireworksEffect` |
| `frosted_glass` | `FrostedGlassEffect` |
| `glass_reflection` | `GlassReflectionEffect` |
| `glassmorphism_float` | `GlassmorphismFloatEffect` |
| `glow` | `GlowEffect` |
| `heatmap` | `HeatmapEffect` |
| `highlight` | `HighlightEffect` |
| `infinite_canvas` | `InfiniteCanvasEffect` |
| `keyboard_shortcut` | `KeyboardShortcutEffect` |
| `magnetic_hover` | `MagneticHoverEffect` |
| `magnifier` | `MagnifierEffect` |
| `matrix_rain` | `MatrixRainEffect` |
| `morph_transition` | `MorphTransitionEffect` |
| `morphing_background` | `MorphingBackgroundEffect` |
| `neon_glow` | `NeonGlowEffect` |
| `notification_toast` | `NotificationToastEffect` |
| `odometer` | `OdometerEffect` |
| `paper_texture` | `PaperTextureEffect` |
| `party_popper` | `PartyPopperEffect` |
| `perspective_tilt` | `PerspectiveTiltEffect` |
| `progress_bar` | `ProgressBarEffect` |
| `progress_ring` | `ProgressRingEffect` |
| `ripple` | `RippleEffect` |
| `rotation_3d` | `Rotation3DEffect` |
| `scroll_parallax` | `ScrollParallaxEffect` |
| `shockwave` | `ShockwaveEffect` |
| `skeleton_loading` | `SkeletonLoadingEffect` |
| `snow` | `SnowEffect` |
| `sparkle` | `SparkleEffect` |
| `split_screen` | `SplitScreenEffect` |
| `spotlight` | `SpotlightEffect` |
| `star_burst` | `StarBurstEffect` |
| `sticky_element` | `StickyElementEffect` |
| `success_checkmark` | `SuccessCheckmarkEffect` |
| `tab_swipe` | `TabSwipeEffect` |
| `text_highlight` | `TextHighlightEffect` |
| `text_scramble` | `TextScrambleEffect` |
| `tooltip_annotation` | `TooltipAnnotationEffect` |
| `tooltip_pop` | `TooltipPopEffect` |
| `typewriter` | `TypewriterEffect` |
| `ui_shimmer` | `UiShimmerEffect` |
| `xray_view` | `XrayViewEffect` |
| `zoom_focus` | `ZoomFocusEffect` |
| `zoom_through` | `ZoomThroughEffect` |

## Post-Processing Effects (applied to video clips)

| Effect | Class |
|--------|-------|
| `bloom` | `BloomEffect` |
| `bokeh_blur` | `BokehBlurEffect` |
| `camera_shake` | `CameraShakeEffect` |
| `chromatic_aberration` | `ChromaticAberrationEffect` |
| `color_grade` | `ColorGradeEffect` |
| `crt_scanlines` | `CrtScanlinesEffect` |
| `dissolve_noise` | `DissolveNoiseEffect` |
| `dolly_zoom` | `DollyZoomEffect` |
| `drone_zoom` | `DroneZoomEffect` |
| `elastic_zoom` | `ElasticZoomEffect` |
| `fade_in` | `FadeInEffect` |
| `fade_out` | `FadeOutEffect` |
| `film_grain` | `FilmGrainEffect` |
| `focus_pull` | `FocusPullEffect` |
| `freeze_frame` | `FreezeFrameEffect` |
| `glitch` | `GlitchEffect` |
| `iris` | `IrisEffect` |
| `ken_burns` | `KenBurnsEffect` |
| `letterbox` | `LetterboxEffect` |
| `light_leak` | `LightLeakEffect` |
| `parallax` | `ParallaxEffect` |
| `pixel_sort` | `PixelSortEffect` |
| `reverse` | `ReverseEffect` |
| `rotate` | `RotateEffect` |
| `slide_in` | `SlideInEffect` |
| `speed_ramp` | `SpeedRampEffect` |
| `tilt_shift` | `TiltShiftEffect` |
| `vhs_distortion` | `VhsDistortionEffect` |
| `vignette` | `VignetteEffect` |
| `whip_pan` | `WhipPanEffect` |
| `wipe` | `WipeEffect` |
| `zoom_pulse` | `ZoomPulseEffect` |
| `zoom_to` | `ZoomToEffect` |

## Common Effect Parameters

| Param | Type | Description |
|-------|------|-------------|
| `duration` | float | Effect duration in seconds |
| `intensity` | float | Effect strength (0.0–1.0) |
| `color` | str | CSS color (hex, rgba) |
| `speed` | float | Animation speed multiplier |
| `scale` | float | Zoom/scale factor |
| `depth` | int | Parallax depth |
| `direction` | str | Direction (up/down/left/right, in/out) |
| `target_x` | float | Normalized X position (0.0–1.0) |
| `target_y` | float | Normalized Y position (0.0–1.0) |
| `angle` | float | Rotation angle in degrees |
| `ratio` | float | Aspect ratio |
| `preset` | str | Named preset |
| `focus_position` | float | Focus point (0.0–1.0) |
