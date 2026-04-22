# DemoDSL Effects Catalog

Auto-generated from `demodsl/effects/`. All effects with their parameters.

## Browser Effects (JS-injected during capture)

| Effect | Class |
|--------|-------|
| `bubbles` | `BubblesEffect` |
| `callout_arrow` | `CalloutArrowEffect` |
| `confetti` | `ConfettiEffect` |
| `countdown_timer` | `CountdownTimerEffect` |
| `cursor_trail` | `CursorTrailEffect` |
| `cursor_trail_comet` | `CursorTrailCometEffect` |
| `cursor_trail_fire` | `CursorTrailFireEffect` |
| `cursor_trail_glow` | `CursorTrailGlowEffect` |
| `cursor_trail_line` | `CursorTrailLineEffect` |
| `cursor_trail_particles` | `CursorTrailParticlesEffect` |
| `cursor_trail_rainbow` | `CursorTrailRainbowEffect` |
| `emoji_rain` | `EmojiRainEffect` |
| `fireworks` | `FireworksEffect` |
| `frosted_glass` | `FrostedGlassEffect` |
| `glow` | `GlowEffect` |
| `highlight` | `HighlightEffect` |
| `magnetic_hover` | `MagneticHoverEffect` |
| `matrix_rain` | `MatrixRainEffect` |
| `morphing_background` | `MorphingBackgroundEffect` |
| `neon_glow` | `NeonGlowEffect` |
| `party_popper` | `PartyPopperEffect` |
| `progress_bar` | `ProgressBarEffect` |
| `ripple` | `RippleEffect` |
| `shockwave` | `ShockwaveEffect` |
| `snow` | `SnowEffect` |
| `sparkle` | `SparkleEffect` |
| `spotlight` | `SpotlightEffect` |
| `star_burst` | `StarBurstEffect` |
| `success_checkmark` | `SuccessCheckmarkEffect` |
| `text_highlight` | `TextHighlightEffect` |
| `text_scramble` | `TextScrambleEffect` |
| `tooltip_annotation` | `TooltipAnnotationEffect` |
| `typewriter` | `TypewriterEffect` |

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
