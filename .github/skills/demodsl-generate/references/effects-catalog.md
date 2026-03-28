# DemoDSL Effects Catalog

Auto-generated from `demodsl/effects/`. All effects with their parameters.

## Browser Effects (JS-injected during capture)

| Effect | Class |
|--------|-------|
| `bubbles` | `BubblesEffect` |
| `confetti` | `ConfettiEffect` |
| `cursor_trail` | `CursorTrailEffect` |
| `cursor_trail_comet` | `CursorTrailCometEffect` |
| `cursor_trail_fire` | `CursorTrailFireEffect` |
| `cursor_trail_glow` | `CursorTrailGlowEffect` |
| `cursor_trail_line` | `CursorTrailLineEffect` |
| `cursor_trail_particles` | `CursorTrailParticlesEffect` |
| `cursor_trail_rainbow` | `CursorTrailRainbowEffect` |
| `emoji_rain` | `EmojiRainEffect` |
| `fireworks` | `FireworksEffect` |
| `glow` | `GlowEffect` |
| `highlight` | `HighlightEffect` |
| `neon_glow` | `NeonGlowEffect` |
| `party_popper` | `PartyPopperEffect` |
| `ripple` | `RippleEffect` |
| `shockwave` | `ShockwaveEffect` |
| `snow` | `SnowEffect` |
| `sparkle` | `SparkleEffect` |
| `spotlight` | `SpotlightEffect` |
| `star_burst` | `StarBurstEffect` |
| `success_checkmark` | `SuccessCheckmarkEffect` |
| `typewriter` | `TypewriterEffect` |

## Post-Processing Effects (applied to video clips)

| Effect | Class |
|--------|-------|
| `camera_shake` | `CameraShakeEffect` |
| `color_grade` | `ColorGradeEffect` |
| `dolly_zoom` | `DollyZoomEffect` |
| `drone_zoom` | `DroneZoomEffect` |
| `elastic_zoom` | `ElasticZoomEffect` |
| `fade_in` | `FadeInEffect` |
| `fade_out` | `FadeOutEffect` |
| `film_grain` | `FilmGrainEffect` |
| `focus_pull` | `FocusPullEffect` |
| `glitch` | `GlitchEffect` |
| `ken_burns` | `KenBurnsEffect` |
| `letterbox` | `LetterboxEffect` |
| `parallax` | `ParallaxEffect` |
| `rotate` | `RotateEffect` |
| `slide_in` | `SlideInEffect` |
| `tilt_shift` | `TiltShiftEffect` |
| `vignette` | `VignetteEffect` |
| `whip_pan` | `WhipPanEffect` |
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
