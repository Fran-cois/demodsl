# DemoDSL Schema Reference

Complete field reference — auto-generated from `demodsl/models.py`.

## Root: `DemoConfig`

### DemoConfig

| Field | Type | Default |
|-------|------|---------|
| `metadata` | Metadata | **required** |
| `voice` | VoiceConfig | null |
| `audio` | AudioConfig | null |
| `device_rendering` | DeviceRendering | null |
| `video` | VideoConfig | null |
| `subtitle` | SubtitleConfig | null |
| `scenarios` | list[Scenario] | `[]` |
| `pipeline` | list[PipelineStage] | `[]` |
| `output` | OutputConfig | null |
| `analytics` | Analytics | null |

## Metadata

| Field | Type | Default |
|-------|------|---------|
| `title` | str | **required** |
| `description` | str | null |
| `author` | str | null |
| `version` | str | null |

## VoiceConfig

| Field | Type | Default |
|-------|------|---------|
| `engine` | `elevenlabs` \| `google` \| `azure` \| `aws_polly` \| `openai` \| `cosyvoice` \| `coqui` \| `piper` \| `local_openai` \| `espeak` \| `gtts` \| `custom` | `"elevenlabs"` |
| `voice_id` | str | `"josh"` |
| `speed` | float | `1.0` |
| `pitch` | int | `0` |
| `reference_audio` | str | null |

## AudioConfig

| Field | Type | Default |
|-------|------|---------|
| `background_music` | BackgroundMusic | null |
| `voice_processing` | VoiceProcessing | null |
| `effects` | AudioEffects | null |

### BackgroundMusic

| Field | Type | Default |
|-------|------|---------|
| `file` | str | **required** |
| `volume` | float | `0.3` |
| `ducking_mode` | `none` \| `light` \| `moderate` \| `heavy` | `"moderate"` |
| `loop` | bool | `true` |

### VoiceProcessing

| Field | Type | Default |
|-------|------|---------|
| `normalize` | bool | `true` |
| `target_dbfs` | int | `-20` |
| `remove_silence` | bool | `true` |
| `silence_threshold` | int | `-40` |
| `enhance_clarity` | bool | `false` |
| `enhance_warmth` | bool | `false` |
| `noise_reduction` | bool | `false` |

### Compression

| Field | Type | Default |
|-------|------|---------|
| `threshold` | int | `-20` |
| `ratio` | float | `3.0` |
| `attack` | int | `5` |
| `release` | int | `50` |

### AudioEffects

| Field | Type | Default |
|-------|------|---------|
| `eq_preset` | str | null |
| `reverb_preset` | str | null |
| `compression` | Compression | null |

## DeviceRendering

| Field | Type | Default |
|-------|------|---------|
| `device` | str | `"iphone_15_pro"` |
| `orientation` | `portrait` \| `landscape` | `"portrait"` |
| `quality` | `low` \| `medium` \| `high` | `"high"` |
| `render_engine` | `eevee` \| `cycles` | `"eevee"` |
| `camera_animation` | str | `"orbit_smooth"` |
| `lighting` | str | `"studio"` |

## VideoConfig

| Field | Type | Default |
|-------|------|---------|
| `intro` | Intro | null |
| `transitions` | Transitions | null |
| `watermark` | Watermark | null |
| `outro` | Outro | null |
| `optimization` | VideoOptimization | null |

### Intro

| Field | Type | Default |
|-------|------|---------|
| `duration` | float | `3.0` |
| `type` | str | `"fade_in"` |
| `text` | str | null |
| `subtitle` | str | null |
| `font_size` | int | `60` |
| `font_color` | str | `"#FFFFFF"` |
| `background_color` | str | `"#1a1a1a"` |

### Transitions

| Field | Type | Default |
|-------|------|---------|
| `type` | `crossfade` \| `slide` \| `zoom` \| `dissolve` | `"crossfade"` |
| `duration` | float | `0.5` |

### Watermark

| Field | Type | Default |
|-------|------|---------|
| `image` | str | **required** |
| `position` | `top_left` \| `top_right` \| `bottom_left` \| `bottom_right` \| `center` | `"bottom_right"` |
| `opacity` | float | `0.7` |
| `size` | int | `100` |

### Outro

| Field | Type | Default |
|-------|------|---------|
| `duration` | float | `4.0` |
| `type` | str | `"fade_out"` |
| `text` | str | null |
| `subtitle` | str | null |
| `cta` | str | null |

### VideoOptimization

| Field | Type | Default |
|-------|------|---------|
| `target_size_mb` | int | null |
| `web_optimized` | bool | `true` |
| `compression_level` | `low` \| `balanced` \| `high` | `"balanced"` |

## Scenario

| Field | Type | Default |
|-------|------|---------|
| `name` | str | **required** |
| `url` | str | **required** |
| `browser` | `chrome` \| `firefox` \| `webkit` | `"chrome"` |
| `viewport` | Viewport | *(factory)* |
| `cursor` | CursorConfig | null |
| `glow_select` | GlowSelectConfig | null |
| `popup_card` | PopupCardConfig | null |
| `avatar` | AvatarConfig | null |
| `subtitle` | SubtitleConfig | null |
| `steps` | list[Step] | `[]` |

### Viewport

| Field | Type | Default |
|-------|------|---------|
| `width` | int | `1920` |
| `height` | int | `1080` |

### CursorConfig

| Field | Type | Default |
|-------|------|---------|
| `visible` | bool | `true` |
| `style` | `dot` \| `pointer` | `"dot"` |
| `color` | str | `"#ef4444"` |
| `size` | int | `20` |
| `click_effect` | `ripple` \| `pulse` \| `none` | `"ripple"` |
| `smooth` | float | `0.4` |

### GlowSelectConfig

| Field | Type | Default |
|-------|------|---------|
| `enabled` | bool | `true` |
| `colors` | list[str] | `['#a855f7', '#6366f1', '#ec4899', '#a855f7']` |
| `duration` | float | `0.8` |
| `padding` | int | `8` |
| `border_radius` | int | `12` |
| `intensity` | float | `0.9` |

### AvatarConfig

| Field | Type | Default |
|-------|------|---------|
| `enabled` | bool | `true` |
| `provider` | `animated` \| `d-id` \| `heygen` \| `sadtalker` | `"animated"` |
| `image` | str | null |
| `position` | `bottom-right` \| `bottom-left` \| `top-right` \| `top-left` | `"bottom-right"` |
| `size` | int | `120` |
| `style` | `bounce` \| `waveform` \| `pulse` \| `equalizer` \| `xp_bliss` \| `clippy` \| `visualizer` \| `pacman` \| `space_invader` \| `mario_block` \| `nyan_cat` \| `matrix` \| `pickle_rick` \| `chrome_dino` \| `marvin` \| `mac128k` \| `floppy_disk` \| `bsod` \| `bugdroid` \| `qr_code` \| `gpu_sweat` \| `rubber_duck` \| `fail_whale` \| `server_rack` \| `cursor_hand` \| `vhs_tape` \| `cloud` \| `wifi_low` \| `nokia3310` \| `cookie` \| `modem56k` \| `esc_key` \| `sad_mac` \| `usb_cable` \| `hourglass` \| `firewire` \| `ai_hallucinated` \| `tamagotchi` \| `lasso_tool` \| `battery_low` \| `incognito` | `"bounce"` |
| `shape` | `circle` \| `rounded` \| `square` | `"circle"` |
| `background` | str | `"rgba(0,0,0,0.5)"` |
| `background_shape` | `square` \| `circle` \| `rounded` | `"square"` |
| `api_key` | str | null |
| `show_subtitle` | bool | `false` |
| `subtitle_font_size` | int | `18` |
| `subtitle_font_color` | str | `"#FFFFFF"` |
| `subtitle_bg_color` | str | `"rgba(0,0,0,0.7)"` |

### SubtitleConfig

| Field | Type | Default |
|-------|------|---------|
| `enabled` | bool | `true` |
| `style` | `classic` \| `tiktok` \| `color` \| `word_by_word` \| `typewriter` \| `karaoke` \| `bounce` \| `cinema` \| `highlight_line` \| `fade_word` \| `emoji_react` | `"classic"` |
| `speed` | `slow` \| `normal` \| `fast` \| `tiktok` | `"normal"` |
| `font_size` | int | `48` |
| `font_family` | str | `"Arial"` |
| `font_color` | str | `"#FFFFFF"` |
| `background_color` | str | `"rgba(0,0,0,0.6)"` |
| `position` | `bottom` \| `center` \| `top` | `"bottom"` |
| `highlight_color` | str | `"#FFD700"` |
| `max_words_per_line` | int | `8` |
| `animation` | `none` \| `fade` \| `pop` \| `slide` | `"none"` |

### PopupCardConfig

| Field | Type | Default |
|-------|------|---------|
| `enabled` | bool | `true` |
| `position` | `bottom-right` \| `bottom-left` \| `top-right` \| `top-left` \| `bottom-center` \| `top-center` | `"bottom-right"` |
| `theme` | `glass` \| `dark` \| `light` \| `gradient` | `"glass"` |
| `max_width` | int | `420` |
| `animation` | `slide` \| `fade` \| `scale` | `"slide"` |
| `accent_color` | str | `"#818cf8"` |
| `show_icon` | bool | `true` |
| `show_progress` | bool | `true` |

## Step

| Field | Type | Default |
|-------|------|---------|
| `action` | `navigate` \| `click` \| `type` \| `scroll` \| `wait_for` \| `screenshot` | **required** |
| `url` | str | null |
| `locator` | Locator | null |
| `value` | str | null |
| `direction` | `up` \| `down` \| `left` \| `right` | null |
| `pixels` | int | null |
| `timeout` | float | null |
| `filename` | str | null |
| `narration` | str | null |
| `wait` | float | null |
| `effects` | list[Effect] | null |
| `card` | ForwardRef('CardContent | None') | null |

### Locator

| Field | Type | Default |
|-------|------|---------|
| `type` | `css` \| `id` \| `xpath` \| `text` | `"css"` |
| `value` | str | **required** |

### Effect

| Field | Type | Default |
|-------|------|---------|
| `type` | `spotlight` \| `highlight` \| `confetti` \| `typewriter` \| `glow` \| `shockwave` \| `sparkle` \| `parallax` \| `cursor_trail` \| `cursor_trail_rainbow` \| `cursor_trail_comet` \| `cursor_trail_glow` \| `cursor_trail_line` \| `cursor_trail_particles` \| `cursor_trail_fire` \| `zoom_pulse` \| `ripple` \| `fade_in` \| `fade_out` \| `glitch` \| `neon_glow` \| `slide_in` \| `success_checkmark` \| `vignette` \| `emoji_rain` \| `fireworks` \| `bubbles` \| `snow` \| `star_burst` \| `party_popper` \| `drone_zoom` \| `ken_burns` \| `zoom_to` \| `dolly_zoom` \| `elastic_zoom` \| `camera_shake` \| `whip_pan` \| `rotate` \| `letterbox` \| `film_grain` \| `color_grade` \| `focus_pull` \| `tilt_shift` \| `text_highlight` \| `text_scramble` \| `magnetic_hover` \| `tooltip_annotation` \| `morphing_background` \| `matrix_rain` \| `frosted_glass` \| `crt_scanlines` \| `chromatic_aberration` \| `vhs_distortion` \| `pixel_sort` \| `bloom` \| `bokeh_blur` \| `light_leak` \| `wipe` \| `iris` \| `dissolve_noise` \| `progress_bar` \| `countdown_timer` \| `callout_arrow` | **required** |
| `duration` | float | null |
| `intensity` | float | null |
| `color` | str | null |
| `speed` | float | null |
| `scale` | float | null |
| `depth` | int | null |
| `direction` | str | null |
| `target_x` | float | null |
| `target_y` | float | null |
| `angle` | float | null |
| `ratio` | float | null |
| `preset` | str | null |
| `focus_position` | float | null |
| `threshold` | float | null |
| `line_spacing` | int | null |
| `offset` | int | null |
| `grain_size` | int | null |
| `focus_area` | float | null |
| `radius` | float | null |
| `text` | str | null |
| `position` | str | null |
| `style` | str | null |
| `density` | float | null |
| `colors` | list[str] | null |

### CardContent

| Field | Type | Default |
|-------|------|---------|
| `title` | str | null |
| `body` | str | null |
| `items` | list[str] | null |
| `icon` | str | null |

## Pipeline & Output

### PipelineStage

| Field | Type | Default |
|-------|------|---------|
| `stage_type` | str | **required** |
| `params` | dict | *(factory)* |

### OutputConfig

| Field | Type | Default |
|-------|------|---------|
| `filename` | str | `"output.mp4"` |
| `directory` | str | `"output/"` |
| `formats` | list[str] | `['mp4']` |
| `thumbnails` | list[Thumbnail] | null |
| `social` | list[SocialExport] | null |
| `deploy` | DeployConfig | null |

### SocialExport

| Field | Type | Default |
|-------|------|---------|
| `platform` | str | **required** |
| `resolution` | str | null |
| `bitrate` | str | null |
| `aspect_ratio` | str | null |
| `max_duration` | int | null |
| `max_size_mb` | int | null |

### Analytics

| Field | Type | Default |
|-------|------|---------|
| `track_engagement` | bool | `false` |
| `heatmap` | bool | `false` |
| `click_tracking` | bool | `false` |

### Avatar Styles

`bounce`, `waveform`, `pulse`, `equalizer`, `xp_bliss`, `clippy`, `visualizer`, `pacman`, `space_invader`, `mario_block`, `nyan_cat`, `matrix`, `pickle_rick`, `chrome_dino`, `marvin`, `mac128k`, `floppy_disk`, `bsod`, `bugdroid`, `qr_code`, `gpu_sweat`, `rubber_duck`, `fail_whale`, `server_rack`, `cursor_hand`, `vhs_tape`, `cloud`, `wifi_low`, `nokia3310`, `cookie`, `modem56k`, `esc_key`, `sad_mac`, `usb_cable`, `hourglass`, `firewire`, `ai_hallucinated`, `tamagotchi`, `lasso_tool`, `battery_low`, `incognito`

### All Effect Types

`spotlight`, `highlight`, `confetti`, `typewriter`, `glow`, `shockwave`, `sparkle`, `parallax`, `cursor_trail`, `cursor_trail_rainbow`, `cursor_trail_comet`, `cursor_trail_glow`, `cursor_trail_line`, `cursor_trail_particles`, `cursor_trail_fire`, `zoom_pulse`, `ripple`, `fade_in`, `fade_out`, `glitch`, `neon_glow`, `slide_in`, `success_checkmark`, `vignette`, `emoji_rain`, `fireworks`, `bubbles`, `snow`, `star_burst`, `party_popper`, `drone_zoom`, `ken_burns`, `zoom_to`, `dolly_zoom`, `elastic_zoom`, `camera_shake`, `whip_pan`, `rotate`, `letterbox`, `film_grain`, `color_grade`, `focus_pull`, `tilt_shift`, `text_highlight`, `text_scramble`, `magnetic_hover`, `tooltip_annotation`, `morphing_background`, `matrix_rain`, `frosted_glass`, `crt_scanlines`, `chromatic_aberration`, `vhs_distortion`, `pixel_sort`, `bloom`, `bokeh_blur`, `light_leak`, `wipe`, `iris`, `dissolve_noise`, `progress_bar`, `countdown_timer`, `callout_arrow`
