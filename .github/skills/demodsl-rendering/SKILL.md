---
name: demodsl-rendering
description: "Generate 3D device rendering configs for DemoDSL. Use when: adding device_rendering to a YAML, choosing a device/camera/lighting/background, debugging Blender render issues, configuring scroll-follow camera sync, picking quality tiers."
argument-hint: "Describe the rendering you want: device, camera effect, background, quality"
---

# DemoDSL 3D Device Rendering — Opinionated DSL

Configure the `device_rendering:` section of a DemoDSL YAML to wrap a browser/mobile recording in a photorealistic 3D device frame rendered by Blender.

## When to Use

- User wants a 3D device mockup around their demo video
- User asks about camera animations, lighting, or backgrounds
- User wants scroll-sync parallax camera effects
- User needs to pick a device (phone, tablet, laptop, monitor)
- User wants to tune quality/performance trade-offs
- User is debugging Blender render issues (camera off-frame, saccaded motion, etc.)

## Golden Rules

1. **Viewport must match device aspect ratio.** Portrait phone → `430×932`. Landscape laptop → `1440×900`. Mismatch = black bars or stretched content.
2. **`smooth_scroll: true` is mandatory with `scroll_follow`.** Without it, scrolls are instant (1-frame jumps) and the camera has nothing to follow.
3. **Quality `low` for iteration, `high` for delivery.** Never use `cinematic` unless the user explicitly asks — it forces Cycles and takes 10–50× longer.
4. **Camera animations are scaled per device category.** Phones have small amplitudes, laptops/monitors have larger geometry. The `scroll_follow` animation auto-scales drift/tilt/lateral by `_camera_scale()`. Don't manually compensate.
5. **Always include `pipeline: [edit_video: {}]`** — the device render replaces the raw video, `edit_video` produces the final output.

## Procedure

### Step 1 — Pick the device

Choose based on the user's intent:

| Intent | Device | Orientation | Viewport |
|--------|--------|-------------|----------|
| Mobile app / phone demo | `iphone_16_pro_max` | `portrait` | `430×932` |
| Mobile landscape | `iphone_16_pro` | `landscape` | `932×430` |
| Web app (16:9) | `macbook_pro_16` | `landscape` | `1440×900` |
| Dashboard / wide UI | `desktop_browser` | `landscape` | `1920×1080` |
| Tablet demo | `ipad_pro_13` | `portrait` or `landscape` | `1024×1366` / `1366×1024` |
| Windows / Surface | `surface_pro_11` | `landscape` | `1440×960` |
| Android demo | `pixel_9_pro` or `galaxy_s25_ultra` | `portrait` | `430×932` |

**Full device catalog:**

| Key | Category | Label | Material | Orientations | Special |
|-----|----------|-------|----------|--------------|---------|
| `iphone_16_pro_max` | phone | iPhone 16 Pro Max | titanium | portrait, landscape | Dynamic Island, triple camera |
| `iphone_16_pro` | phone | iPhone 16 Pro | titanium | portrait, landscape | Dynamic Island, triple camera |
| `iphone_16` | phone | iPhone 16 | aluminum | portrait, landscape | Dynamic Island, dual camera |
| `iphone_15_pro` | phone | iPhone 15 Pro | titanium | portrait, landscape | Dynamic Island, triple camera |
| `pixel_9_pro` | phone | Pixel 9 Pro | aluminum | portrait, landscape | Punch hole, pill camera |
| `galaxy_s25_ultra` | phone | Galaxy S25 Ultra | titanium | portrait, landscape | Punch hole, quad camera |
| `pixel_8` | phone | Pixel 8 | aluminum | portrait, landscape | Punch hole, pill camera |
| `galaxy_s25` | phone | Galaxy S25 | aluminum | portrait, landscape | Punch hole, triple camera |
| `ipad_pro_13` | tablet | iPad Pro 13" M4 | aluminum | portrait, landscape | — |
| `macbook_pro_16` | laptop | MacBook Pro 16" | aluminum | landscape only | Keyboard, notch, hinge 110° |
| `surface_pro_11` | tablet | Surface Pro 11 | aluminum | portrait, landscape | Kickstand |
| `desktop_browser` | monitor | Desktop Browser 27" | plastic | landscape only | Stand |

### Step 2 — Pick camera animation

| Animation | Best For | Key Params |
|-----------|----------|------------|
| `orbit_smooth` | Product showcases, general demos | `rotation_speed` (default 1.0), `camera_distance` |
| `scroll_follow` | **Scroll demos, parallax, website tours** | `camera_distance`, `scroll_data` (auto-captured) |
| `push_in` | Dramatic reveals, feature focus | `camera_distance` |
| `slow_drift` | Subtle background motion | `camera_distance` |
| `zoom_in` | Opening shots, reveal intros | `camera_distance` |
| `zoom_out` | Closing shots, context reveal | `camera_distance` |
| `dolly_zoom` | Hitchcock vertigo effect | `camera_distance` |
| `crane_up` | Low-angle rising reveal | `camera_distance` |
| `fly_around` | Full 360° showcase | `rotation_speed`, `camera_distance` |
| `tilt` | Side-to-side gentle rocking | `camera_distance` |
| `static` | Clean, fixed frame | `camera_distance` |

**`scroll_follow` requirements:**
- Set `smooth_scroll: true` on ALL scroll steps
- The camera automatically captures `scrollY` before/after each scroll step
- Data is smoothed with a moving-average filter (~0.25s window)
- All keyframes use Bézier interpolation with AUTO_CLAMPED handles
- Amplitude scales automatically per device category

### Step 3 — Pick lighting

| Preset | Lights | Character | Best For |
|--------|--------|-----------|----------|
| `studio` | 3× AREA (key + fill + top) | Clean, neutral | Product shots, general demos |
| `dramatic` | SPOT + AREA (hard key + rim) | High contrast, cinematic | Hero shots, marketing |
| `cinematic` | 5× mixed (warm key, cool fill, rim, bounce, kicker) | Film-grade, color contrast | Premium renders |
| `natural` | 1× SUN | Soft, outdoor | Realistic, natural look |

**Default: `studio`**. Use `dramatic` or `cinematic` for marketing material.

### Step 4 — Pick background

| Preset | Look | Best For |
|--------|------|----------|
| `space_dark` | Cinematic starfield + purple/blue nebula | Dark, premium demos |
| `space` | Star field + bright nebula + glow | Sci-fi, tech demos |
| `gradient` | Vertical gradient (customizable colors) | Clean, branded |
| `studio_floor` | Dark top + reflective floor | Product photography |
| `spotlight` | Radial bright center falloff | Focus on device |
| `warm_gradient` | Burgundy → amber | Warm, elegant |
| `cool_gradient` | Navy → steel blue | Corporate, tech |
| `sunset` | Purple → orange → dark blue | Vibrant, creative |
| `abstract_noise` | Procedural Voronoi/Perlin texture | Artistic, unique |
| `solid` | Flat color | Minimal, clean |

**Customize colors** with `background_color` and `background_gradient_color` (hex).
**HDRI overrides everything** if `background_hdri` points to a valid `.hdr`/`.exr` file.

### Step 5 — Pick quality

| Quality | Resolution | Samples | Engine | Speed | Use |
|---------|-----------|---------|--------|-------|-----|
| `low` | 960×540 (50%) | 16 | eevee | ~1 min | **Iteration / testing** |
| `medium` | 1440×810 (75%) | 64 | eevee | ~2 min | Preview |
| `high` | 1920×1080 (100%) | 128 | eevee | ~5 min | **Delivery** |
| `cinematic` | 3840×2160 (4K) | 512 | **cycles** (forced) | 30+ min | Final cut |

**Rule: always start with `low`, switch to `high` for final render.** Never default to `cinematic`.

### Step 6 — Generate the YAML

Assemble `device_rendering:` using the chosen options.

## Templates

### Phone demo (default)
```yaml
device_rendering:
  device: "iphone_16_pro_max"
  orientation: "portrait"
  quality: "low"
  render_engine: "eevee"
  camera_animation: "orbit_smooth"
  lighting: "studio"
  background_preset: "space_dark"
  camera_distance: 1.5
  shadow: true

scenarios:
  - name: "App demo"
    url: "https://example.com"
    viewport:
      width: 430
      height: 932
```

### Scroll parallax (website tour)
```yaml
device_rendering:
  device: "macbook_pro_16"
  orientation: "landscape"
  quality: "low"
  render_engine: "eevee"
  camera_animation: "scroll_follow"
  lighting: "dramatic"
  background_preset: "space_dark"
  camera_distance: 1.4
  shadow: true

scenarios:
  - name: "Website scroll"
    url: "https://example.com"
    viewport:
      width: 1440
      height: 900
    natural: true
    pre_steps:
      - action: "navigate"
        url: "https://example.com"
        wait: 3
    steps:
      - action: "click"
        locator: { type: "text", value: "Accept cookies" }
        wait: 1
      - action: "scroll"
        direction: "down"
        pixels: 400
        smooth_scroll: true
        wait: 0.4
      # ... more scroll steps with smooth_scroll: true
```

### Marketing hero shot
```yaml
device_rendering:
  device: "iphone_16_pro_max"
  orientation: "portrait"
  quality: "high"
  render_engine: "eevee"
  camera_animation: "push_in"
  lighting: "cinematic"
  background_preset: "gradient"
  background_color: "#0f0c29"
  background_gradient_color: "#302b63"
  camera_distance: 1.8
  shadow: true
  bloom: true
  depth_of_field: true
  dof_aperture: 2.0
```

### Dashboard (16:9 widescreen)
```yaml
device_rendering:
  device: "desktop_browser"
  orientation: "landscape"
  quality: "low"
  render_engine: "eevee"
  camera_animation: "orbit_smooth"
  lighting: "studio"
  background_preset: "studio_floor"
  camera_distance: 1.5
  rotation_speed: 0.5
  shadow: true

scenarios:
  - name: "Dashboard demo"
    url: "https://dashboard.example.com"
    viewport:
      width: 1920
      height: 1080
```

### Tablet showcase
```yaml
device_rendering:
  device: "ipad_pro_13"
  orientation: "landscape"
  quality: "low"
  render_engine: "eevee"
  camera_animation: "crane_up"
  lighting: "dramatic"
  background_preset: "cool_gradient"
  camera_distance: 1.4
  shadow: true
```

## All Parameters Reference

```yaml
device_rendering:
  # Device
  device: "iphone_15_pro"              # Device key from catalog
  orientation: "portrait"              # "portrait" | "landscape"

  # Quality
  quality: "high"                      # "low" | "medium" | "high" | "cinematic"
  render_engine: "eevee"               # "eevee" | "cycles" (cinematic forces cycles)

  # Camera
  camera_animation: "orbit_smooth"     # See animation table
  camera_distance: 1.5                 # 0.0 < x ≤ 10.0 (scaled per device)
  camera_height: 0.0                   # -5.0 ≤ x ≤ 5.0
  rotation_speed: 1.0                  # 0.0 < x ≤ 5.0 (orbit/fly_around only)

  # Scene
  lighting: "studio"                   # studio | dramatic | cinematic | natural
  background_preset: "space"           # See background table
  background_color: "#1a1a1a"          # Base color (hex)
  background_gradient_color: null      # Secondary gradient color (hex)
  background_hdri: null                # HDRI path (overrides preset)
  shadow: true                         # Shadow catcher plane

  # Post-effects
  depth_of_field: false                # Bokeh blur
  dof_aperture: 2.8                    # f-stop (0 < x ≤ 22)
  motion_blur: false                   # Frame motion blur
  bloom: false                         # Glow on bright areas
  film_grain: 0.0                      # Noise overlay (0.0–1.0)
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Camera shows only background / edge of device | `scroll_follow` drift not scaled to device | Already fixed — drift auto-scales by `_camera_scale(category)` |
| scrollY always 0 | `overflow-x: hidden` on html/body converts overflow-y to `auto` | Fixed — uses `overflow-x: clip` instead |
| Scroll in video is jerky / instant jumps | Missing `smooth_scroll: true` on scroll steps | Add `smooth_scroll: true` to every scroll step |
| Camera motion is saccaded | Raw scroll data has step discontinuities | Fixed — pre-smoothed with moving-average + Bézier keyframes |
| Render takes forever | `quality: "cinematic"` uses Cycles with 512 samples | Use `low` for testing, `high` for delivery |
| Device not found | Wrong device key | Check catalog table above |
| Black screen on device | Video path invalid or viewport mismatch | Ensure viewport matches device aspect ratio |
| Blender not found | Blender not installed | Install Blender 4.x to `/Applications/Blender.app` (macOS) |

## Validation Checklist

Before generating, verify:
- [ ] `viewport` aspect ratio matches `device` + `orientation`
- [ ] `camera_animation: "scroll_follow"` → all scroll steps have `smooth_scroll: true`
- [ ] `quality: "low"` for testing, `"high"` for final
- [ ] `pipeline` includes `edit_video: {}`
- [ ] `pre_steps` includes `navigate` + cookie dismissal if needed
- [ ] `device` key exists in catalog
- [ ] `orientation` is in device's allowed orientations (e.g. `macbook_pro_16` is landscape only)
