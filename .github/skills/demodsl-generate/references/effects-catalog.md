# DemoDSL Effects Catalog

All 50+ effects available in DemoDSL, organized by category.

## Browser Effects (JS-injected during capture)

These effects are injected as JavaScript during Playwright browser capture. They run in real-time in the browser viewport.

### Visual Overlays

| Effect | Description | Key Params |
|--------|-------------|------------|
| `spotlight` | Dims the page with a spotlight circle following the cursor | `intensity` (0.8), `duration` |
| `highlight` | Adds glowing box-shadow on hovered elements | `color` (#FFD700), `intensity` (0.9), `duration` |
| `glow` | Creates an inner glow around the viewport | `color` (#00FF00), `duration` |
| `neon_glow` | Vivid colored border around the entire page | `color` (#FF00FF), `duration` |
| `success_checkmark` | Displays an animated checkmark overlay | `duration` |

### Particle & Celebration Effects

| Effect | Description | Key Params |
|--------|-------------|------------|
| `confetti` | Colorful confetti particles raining down | `duration` |
| `sparkle` | Sparkling particles effect | `duration` |
| `emoji_rain` | Raining emoji characters | `duration` |
| `fireworks` | Fireworks explosion animation | `duration` |
| `bubbles` | Floating bubble particles | `duration` |
| `snow` | Falling snowflakes | `duration` |
| `star_burst` | Burst of star particles | `duration` |
| `party_popper` | Party popper celebration animation | `duration` |

### Text & Interaction Effects

| Effect | Description | Key Params |
|--------|-------------|------------|
| `typewriter` | Typewriter-style text reveal animation | `duration` |
| `shockwave` | Expanding shockwave ring from center | `duration` |
| `ripple` | Ripple effect on click | `duration` |

### Cursor Trail Effects

| Effect | Description | Key Params |
|--------|-------------|------------|
| `cursor_trail` | Default trail following cursor | `duration` |
| `cursor_trail_rainbow` | Rainbow-colored cursor trail | `duration` |
| `cursor_trail_comet` | Comet tail following cursor | `duration` |
| `cursor_trail_glow` | Glowing trail with customizable color | `color` (#00BFFF), `duration` |
| `cursor_trail_line` | Line trail connecting cursor positions | `duration` |
| `cursor_trail_particles` | Particle spray following cursor | `duration` |
| `cursor_trail_fire` | Fire trail following cursor | `duration` |

## Post-Processing Effects (applied to video clips)

These effects are applied to recorded video clips via MoviePy during the pipeline.

### Basic Video Effects

| Effect | Description | Key Params |
|--------|-------------|------------|
| `parallax` | Simulated depth/parallax motion | `depth` (5) |
| `zoom_pulse` | Rhythmic zoom in and out | `scale` (1.2) |
| `fade_in` | Gradual opacity fade in | `duration` (1.0) |
| `fade_out` | Gradual opacity fade out | `duration` (1.0) |
| `vignette` | Dark edges vignette overlay | `intensity` (0.5) |
| `glitch` | Digital glitch/corruption effect | `intensity` (0.3) |
| `slide_in` | Slide entrance from edge | `duration` (0.8) |

### Camera Movement Effects

| Effect | Description | Key Params |
|--------|-------------|------------|
| `drone_zoom` | Drone-like zoom to a target point | `scale` (1.5), `target_x` (0.5), `target_y` (0.5) |
| `ken_burns` | Ken Burns pan/zoom effect | `scale` (1.15), `direction` (right\|left\|up\|down) |
| `zoom_to` | Smooth zoom to a specific point | `scale` (1.8), `target_x` (0.5), `target_y` (0.5) |
| `dolly_zoom` | Vertigo/dolly zoom distortion | `intensity` (0.3) |
| `elastic_zoom` | Bouncy elastic zoom animation | `scale` (1.3) |
| `camera_shake` | Handheld camera shake effect | `intensity` (0.3), `speed` (8.0) |
| `whip_pan` | Fast whip pan transition | `direction` (right\|left\|up\|down) |
| `rotate` | Gentle rotation oscillation | `angle` (3.0), `speed` (1.0) |

### Cinematic Effects

| Effect | Description | Key Params |
|--------|-------------|------------|
| `letterbox` | Cinema-style black bars | `ratio` (2.35) |
| `film_grain` | Analog film grain overlay | `intensity` (0.3) |
| `color_grade` | Color grading presets | `preset` (warm\|cool\|desaturate\|vintage\|cinematic) |
| `focus_pull` | Simulated rack focus | `direction` (in\|out), `intensity` (0.5) |
| `tilt_shift` | Miniature/tilt-shift blur | `intensity` (0.6), `focus_position` (0.5) |

## Effect Usage in YAML

Effects are added to individual steps:

```yaml
steps:
  - action: "navigate"
    url: "https://example.com"
    effects:
      - type: "spotlight"
        duration: 2.0
        intensity: 0.8
      - type: "confetti"
        duration: 3.0
```

Multiple effects can be stacked on the same step. Browser effects execute during capture; post-processing effects are applied to the recorded clip afterward.

## Common Effect Param Fields

| Param | Type | Description |
|-------|------|-------------|
| `duration` | float | Effect duration in seconds |
| `intensity` | float | Effect strength (0.0 – 1.0) |
| `color` | str | CSS color string (hex, rgba) |
| `speed` | float | Animation speed multiplier |
| `scale` | float | Zoom/scale factor |
| `depth` | int | Parallax depth |
| `direction` | str | Direction (up/down/left/right, in/out) |
| `target_x` | float | Normalized X position (0.0 – 1.0) |
| `target_y` | float | Normalized Y position (0.0 – 1.0) |
| `angle` | float | Rotation angle in degrees |
| `ratio` | float | Aspect ratio |
| `preset` | str | Named preset |
| `focus_position` | float | Focus point (0.0 – 1.0) |
