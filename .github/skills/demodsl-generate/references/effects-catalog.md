# DemoDSL Effects Catalog

Auto-generated from `demodsl/effects/`. All effects with their parameters.

## Browser Effects (JS-injected during capture)

### UI / Overlay Effects

| Effect | Parameters | Description |
|--------|-----------|-------------|
| `spotlight` | `duration`(2), `intensity`(0.7) | Radial gradient spotlight overlay, darkens edges. |
| `highlight` | `duration`(2), `color`(#FFD700), `intensity`(0.8) | Glowing box-shadow on hovered elements. |
| `frosted_glass` | `duration`(3), `intensity`(0.5) | Frosted glass blur overlay. |
| `glow` | `duration`(2), `color`(#6366f1) | Inner box-shadow glow around the viewport. |
| `neon_glow` | `duration`(2), `color`(#FF00FF) | Neon-colored glow border around the viewport. |
| `morphing_background` | `duration`(5), `colors`([list]) | Animated gradient background morphing through colors. |
| `progress_bar` | `duration`(3), `color`(#4CAF50), `position`(top), `intensity`(4) | Animated progress bar filling horizontally. |
| `countdown_timer` | `duration`(5), `color`(#333), `position`(center) | Countdown circle timer overlay. |

### Text Effects

| Effect | Parameters | Description |
|--------|-----------|-------------|
| `typewriter` | `duration`(2), `caret_color`(#333), `blink_speed`(0.7), `bg_color`, `text_color`, `font_size`(18), `label`("Typing") | Blinking caret animation on input fields. |
| `text_highlight` | `duration`(2), `color`(#FFD700) | Highlighted text background animation. |
| `text_scramble` | `duration`(2), `speed`(50) | Text scramble/decode animation. |
| `tooltip_annotation` | `duration`(3), `text`(""), `color`(#333) | Tooltip annotation popup. |
| `callout_arrow` | `duration`(3), `text`(""), `color`(#FF6B6B), `target_x`(0.5), `target_y`(0.5) | Arrow callout pointing to coordinates. |

### Interactive Effects

| Effect | Parameters | Description |
|--------|-----------|-------------|
| `magnetic_hover` | `duration`(3), `intensity`(0.5) | Magnetic attraction effect on hover. |
| `ripple` | `duration`(0.6), `color`(#4FC3F7), `glow_color`(rgba(79,195,247,0.4)), `border_width`(3), `max_size`(200), `glow`(12) | Click ripple ring animation. |
| `shockwave` | `duration`(0.8), `color`(#FF5722), `glow_color`(rgba(255,87,34,0.5)), `border_width`(4), `max_size`(600), `glow`(15) | Expanding shockwave ring from center. |
| `success_checkmark` | `duration`(1.2), `color`(#4CAF50), `size`(140), `glow`(20), `symbol`(✓) | Animated checkmark overlay. |

### Cursor Trail Effects

| Effect | Parameters | Description |
|--------|-----------|-------------|
| `cursor_trail` | `duration`(3), `color`(#a855f7), `size`(22), `glow`(14), `fade_duration`(1.2), `max_dots`(80) | Basic trailing dots following cursor. |
| `cursor_trail_comet` | `duration`(3), `color`(rgba(168,85,247,1)), `glow_color`(rgba(168,85,247,0.3)), `layers`(4), `size`(22), `size_step`(3), `fade_duration`(0.8) | Comet tail with size gradient. |
| `cursor_trail_fire` | `duration`(3), `sparks`(5), `min_size`(10), `size_range`(12), `glow`(10), `hue_base`(10), `hue_range`(40), `fade_delay`(300), `lifetime`(1500) | Fire sparks rising and fading. |
| `cursor_trail_particles` | `duration`(3), `count`(6), `min_size`(8), `size_range`(6), `spread`(35), `hue_base`(180), `hue_range`(60), `glow`(8), `fade_delay`(200), `lifetime`(1400) | Particle burst on each mouse move. |
| `cursor_trail_rainbow` | `duration`(3), `size`(18), `hue_step`(12), `glow`(12), `fade_duration`(1.4), `lifetime`(2200) | Rainbow-colored dots cycling through hues. |
| `cursor_trail_glow` | `duration`(3), `color`(#00BFFF), `size`(36), `glow_inner`(24), `glow_outer`(48), `fade_duration`(1.5), `lifetime`(2000), `scale_end`(2.5) | Soft glowing trail with radial gradient. |
| `cursor_trail_line` | `duration`(3), `color`(rgba(168,85,247,1)), `max_points`(60), `min_width`(2), `max_width`(7) | Connected SVG line segments following cursor. |

### Fun / Celebration Effects

| Effect | Parameters | Description |
|--------|-----------|-------------|
| `confetti` | `duration`(3), `count`(150), `colors`([list of 6 hex]), `speed_min`(1.5), `speed_range`(3.0) | Animated falling confetti particles. |
| `emoji_rain` | `duration`(4), `count`(60), `min_size`(22), `size_range`(20), `speed_min`(1.5), `speed_range`(2.5), `emojis`([🎉,🔥,❤️,⭐,🚀,💯]) | Rain of emojis falling from top. |
| `bubbles` | `duration`(4), `count`(45), `min_radius`(10), `max_radius`(35), `speed_min`(0.5), `speed_range`(1.5), `hue_base`(180), `hue_range`(60) | Translucent bubbles rising with wobble. |
| `snow` | `duration`(5), `count`(120), `min_radius`(3), `max_radius`(8), `color`(rgba(200,230,255,0.85)), `glow_color`(rgba(180,220,255,0.6)), `glow`(4), `speed_min`(0.8), `speed_max`(2.8) | Snowflakes drifting down with wind. |
| `sparkle` | `duration`(3), `count`(80), `color`(#FFD700), `min_size`(2), `max_size`(8) | Random sparkling golden dots. |
| `star_burst` | `duration`(3), `count`(80), `speed_min`(2), `speed_range`(5), `hue_base`(40), `hue_range`(60), `decay`(0.006) | 5-pointed stars exploding from center. |
| `party_popper` | `duration`(3), `count`(55), `colors`([list of 8 hex]), `min_size`(8), `size_range`(10), `speed_min`(4), `speed_range`(7), `gravity`(0.12), `fade_rate`(0.003) | Confetti shapes from both bottom corners. |
| `fireworks` | `duration`(3), `initial_rockets`(8), `launch_interval`(1200), `particles_per_rocket`(50), `particle_speed_min`(1.5), `particle_speed_range`(4), `gravity`(0.05), `fade_rate`(0.012) | Rockets launching and exploding. |

### Code / Digital Effects

| Effect | Parameters | Description |
|--------|-----------|-------------|
| `matrix_rain` | `duration`(5), `color`(#00FF41), `density`(0.05), `speed`(1.0) | Matrix-style falling green characters. |

## Post-Processing Effects (applied to video clips)

| Effect | Parameters | Description |
|--------|-----------|-------------|
| `bloom` | `duration`, `intensity` | Bloom/glow on bright areas. |
| `bokeh_blur` | `duration`, `intensity` | Bokeh-style background blur. |
| `camera_shake` | `duration`, `intensity` | Camera shake/vibration. |
| `chromatic_aberration` | `duration`, `intensity` | RGB channel split. |
| `color_grade` | `duration`, `preset` | Color grading preset. |
| `crt_scanlines` | `duration`, `intensity` | CRT scanline overlay. |
| `dissolve_noise` | `duration` | Noise dissolve transition. |
| `dolly_zoom` | `duration`, `scale` | Dolly zoom (Vertigo effect). |
| `drone_zoom` | `duration`, `scale` | Smooth drone-style zoom. |
| `elastic_zoom` | `duration`, `scale` | Elastic bounce zoom. |
| `fade_in` | `duration` | Fade in from black. |
| `fade_out` | `duration` | Fade out to black. |
| `film_grain` | `duration`, `intensity` | Film grain overlay. |
| `focus_pull` | `duration`, `focus_position` | Rack focus pull. |
| `freeze_frame` | `duration` | Freeze frame. |
| `glitch` | `duration`, `intensity` | Random horizontal slice displacement. |
| `iris` | `duration`, `direction` | Iris open/close transition. |
| `ken_burns` | `duration`, `scale`, `direction` | Ken Burns pan & zoom. |
| `letterbox` | `duration`, `ratio` | Cinematic letterbox bars. |
| `light_leak` | `duration`, `intensity` | Light leak overlay. |
| `parallax` | `duration`, `depth` | Subtle zoom depth illusion. |
| `pixel_sort` | `duration`, `intensity` | Pixel sorting effect. |
| `reverse` | `duration` | Reverse playback. |
| `rotate` | `duration`, `angle` | Rotation animation. |
| `slide_in` | `duration`, `direction` | Slide-in entrance. |
| `speed_ramp` | `duration`, `speed` | Speed ramp (slow-mo / fast). |
| `tilt_shift` | `duration`, `focus_position` | Tilt-shift miniature blur. |
| `vhs_distortion` | `duration`, `intensity` | VHS tracking distortion. |
| `vignette` | `duration`, `intensity` | Dark vignette border. |
| `whip_pan` | `duration`, `direction` | Whip pan blur transition. |
| `wipe` | `duration`, `direction` | Wipe transition. |
| `zoom_pulse` | `duration`, `scale` | Pulsing zoom sine wave. |
| `zoom_to` | `duration`, `scale`, `target_x`, `target_y` | Zoom to specific point. |

## Usage Examples

```yaml
# Customized confetti with more particles and custom colors
effects:
  - type: "confetti"
    duration: 4.0
    count: 250
    colors: ["#FF0000", "#00FF00", "#0000FF", "#FFFF00"]
    speed_min: 2.0
    speed_range: 4.0

# Fire cursor trail with larger sparks
effects:
  - type: "cursor_trail_fire"
    sparks: 8
    min_size: 15
    size_range: 18
    hue_base: 0
    hue_range: 50

# Custom snow effect
effects:
  - type: "snow"
    duration: 8.0
    count: 200
    min_radius: 2
    max_radius: 12
    color: "rgba(255,255,255,0.9)"
    speed_min: 0.5
    speed_max: 3.5

# Fireworks with more rockets
effects:
  - type: "fireworks"
    duration: 6.0
    initial_rockets: 12
    particles_per_rocket: 80
    launch_interval: 800

# Shockwave with custom color
effects:
  - type: "shockwave"
    duration: 1.0
    color: "#FF00FF"
    max_size: 800
    glow: 20
```
