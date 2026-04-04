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
| `languages` | LanguagesConfig | null |
| `subtitle` | SubtitleConfig | null |
| `scenarios` | list[Scenario] | `[]` |
| `pipeline` | list[PipelineStage] | `[]` |
| `output` | OutputConfig | null |
| `edit` | EditConfig | null |
| `analytics` | Analytics | null |
| `webinar` | dict | null |

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
| `engine` | `elevenlabs` \| `google` \| `azure` \| `aws_polly` \| `openai` \| `cosyvoice` \| `coqui` \| `piper` \| `local_openai` \| `espeak` \| `gtts` \| `voxtral` \| `custom` | `"elevenlabs"` |
| `voice_id` | str | `"josh"` |
| `speed` | float | `1.0` |
| `pitch` | int | `0` |
| `reference_audio` | str | null |
| `narration_gap` | float | `0.3` |
| `collision_strategy` | `warn` \| `shift` \| `truncate` | `"warn"` |

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
| `min_silence_duration` | float | `0.5` |
| `enhance_clarity` | bool | `false` |
| `enhance_warmth` | bool | `false` |
| `noise_reduction` | bool | `false` |
| `noise_reduction_strength` | `light` \| `moderate` \| `heavy` \| `auto` | `"moderate"` |
| `de_ess` | bool | `false` |
| `de_ess_intensity` | float | `0.5` |

### Compression

| Field | Type | Default |
|-------|------|---------|
| `threshold` | int | `-20` |
| `ratio` | float | `3.0` |
| `attack` | int | `5` |
| `release` | int | `50` |
| `preset` | `voice` \| `podcast` \| `broadcast` \| `gentle` \| `custom` | null |

### AudioEffects

| Field | Type | Default |
|-------|------|---------|
| `eq_preset` | `podcast` \| `warm` \| `bright` \| `telephone` \| `radio` \| `deep` \| `custom` | null |
| `eq_bands` | list[EQBand] | null |
| `reverb_preset` | `none` \| `small_room` \| `large_room` \| `hall` \| `cathedral` \| `plate` | null |
| `compression` | Compression | null |

## DeviceRendering

| Field | Type | Default |
|-------|------|---------|
| `device` | str | `"iphone_15_pro"` |
| `orientation` | `portrait` \| `landscape` | `"portrait"` |
| `quality` | `low` \| `medium` \| `high` \| `cinematic` | `"high"` |
| `render_engine` | `eevee` \| `cycles` | `"eevee"` |
| `camera_animation` | str | `"orbit_smooth"` |
| `lighting` | str | `"studio"` |
| `background_preset` | str | `"space"` |
| `background_color` | str | `"#1a1a1a"` |
| `background_gradient_color` | str | null |
| `background_hdri` | str | null |
| `camera_distance` | float | `1.5` |
| `camera_height` | float | `0.0` |
| `rotation_speed` | float | `1.0` |
| `shadow` | bool | `true` |
| `depth_of_field` | bool | `false` |
| `dof_aperture` | float | `2.8` |
| `motion_blur` | bool | `false` |
| `bloom` | bool | `false` |
| `film_grain` | float | `0.0` |

## VideoConfig

| Field | Type | Default |
|-------|------|---------|
| `intro` | Intro | null |
| `transitions` | Transitions | null |
| `watermark` | Watermark | null |
| `outro` | Outro | null |
| `optimization` | VideoOptimization | null |
| `color_correction` | ColorCorrection | null |
| `pip` | PictureInPicture | null |
| `frame_rate` | int | null |
| `chapters` | list[ChapterMarker] | null |
| `speed` | float | null |

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
| `url` | str | null |
| `browser` | `chrome` \| `firefox` \| `webkit` | `"chrome"` |
| `provider` | `playwright` \| `selenium` | `"playwright"` |
| `viewport` | Viewport | *(factory)* |
| `color_scheme` | `light` \| `dark` \| `no-preference` | null |
| `locale` | str | null |
| `cursor` | CursorConfig | null |
| `glow_select` | GlowSelectConfig | null |
| `popup_card` | PopupCardConfig | null |
| `avatar` | AvatarConfig | null |
| `subtitle` | SubtitleConfig | null |
| `natural` | bool | NaturalConfig | null |
| `mobile` | MobileConfig | null |
| `pre_steps` | list[Step] | null |
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
| `bezier` | bool | `true` |

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
| `style` | str | `"bounce"` |
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
| `action` | `navigate` \| `click` \| `type` \| `scroll` \| `wait_for` \| `screenshot` \| `tap` \| `swipe` \| `pinch` \| `long_press` \| `back` \| `home` \| `notification` \| `app_switch` \| `rotate_device` \| `shake` | **required** |
| `url` | str | null |
| `locator` | Locator | null |
| `value` | str | null |
| `direction` | `up` \| `down` \| `left` \| `right` | null |
| `pixels` | int | null |
| `timeout` | float | null |
| `filename` | str | null |
| `start_x` | float | null |
| `start_y` | float | null |
| `end_x` | float | null |
| `end_y` | float | null |
| `duration_ms` | int | null |
| `pinch_scale` | float | null |
| `orientation` | `portrait` \| `landscape` | null |
| `narration` | str | null |
| `wait` | float | null |
| `effects` | list[Effect] | null |
| `card` | CardContent | null |
| `speed` | float | null |
| `speed_ramp` | SpeedRamp | null |
| `freeze_duration` | float | null |
| `audio_offset` | float | null |
| `stop_if` | list[StopCondition] | null |
| `hover_delay` | float | null |
| `smooth_scroll` | bool | null |
| `char_rate` | float | null |
| `zoom_input` | bool | ZoomInputConfig | null |
| `typing_variance` | float | null |

### Locator

| Field | Type | Default |
|-------|------|---------|
| `type` | `css` \| `id` \| `xpath` \| `text` \| `accessibility_id` \| `class_name` \| `android_uiautomator` \| `ios_predicate` \| `ios_class_chain` | `"css"` |
| `value` | str | **required** |

### Effect

| Field | Type | Default |
|-------|------|---------|
| `type` | `spotlight` \| `highlight` \| `confetti` \| `typewriter` \| `glow` \| `shockwave` \| `sparkle` \| `parallax` \| `cursor_trail` \| `cursor_trail_rainbow` \| `cursor_trail_comet` \| `cursor_trail_glow` \| `cursor_trail_line` \| `cursor_trail_particles` \| `cursor_trail_fire` \| `zoom_pulse` \| `ripple` \| `fade_in` \| `fade_out` \| `glitch` \| `neon_glow` \| `slide_in` \| `success_checkmark` \| `vignette` \| `emoji_rain` \| `fireworks` \| `bubbles` \| `snow` \| `star_burst` \| `party_popper` \| `drone_zoom` \| `ken_burns` \| `zoom_to` \| `dolly_zoom` \| `elastic_zoom` \| `camera_shake` \| `whip_pan` \| `rotate` \| `letterbox` \| `film_grain` \| `color_grade` \| `focus_pull` \| `tilt_shift` \| `text_highlight` \| `text_scramble` \| `magnetic_hover` \| `tooltip_annotation` \| `morphing_background` \| `matrix_rain` \| `frosted_glass` \| `crt_scanlines` \| `chromatic_aberration` \| `vhs_distortion` \| `pixel_sort` \| `bloom` \| `bokeh_blur` \| `light_leak` \| `wipe` \| `iris` \| `dissolve_noise` \| `speed_ramp` \| `freeze_frame` \| `reverse` \| `progress_bar` \| `countdown_timer` \| `callout_arrow` | **required** |
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
| `start_speed` | float | null |
| `end_speed` | float | null |
| `ease` | str | null |
| `freeze_duration` | float | null |

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
| `branding` | bool | `true` |
| `thumbnails` | list[Thumbnail] | null |
| `social` | list[SocialExport] | null |
| `deploy` | DeployConfig | null |

### SocialExport

| Field | Type | Default |
|-------|------|---------|
| `platform` | `youtube` \| `instagram_reels` \| `tiktok` \| `twitter` \| `linkedin` \| `custom` | **required** |
| `resolution` | str | null |
| `bitrate` | str | null |
| `aspect_ratio` | str | null |
| `max_duration` | int | null |
| `max_size_mb` | int | null |
| `crop_mode` | `center` \| `smart` | `"center"` |

### Analytics

| Field | Type | Default |
|-------|------|---------|
| `track_engagement` | bool | `false` |
| `heatmap` | bool | `false` |
| `click_tracking` | bool | `false` |

### Avatar Styles

`ai_hallucinated`, `battery_low`, `bit`, `bluetooth`, `bounce`, `bsod`, `bugdroid`, `captcha`, `chrome_dino`, `clippy`, `cloud`, `cookie`, `cursor_hand`, `distracted_bf`, `doge`, `equalizer`, `error_404`, `esc_key`, `expanding_brain`, `fail_whale`, `firewire`, `floppy_disk`, `google_blob`, `gpu_sweat`, `high_ping`, `hourglass`, `incognito`, `kermit`, `lasso_tool`, `mac128k`, `mario_block`, `marvin`, `matrix`, `modem56k`, `no_idea_dog`, `nokia3310`, `nyan_cat`, `pacman`, `pc_fan`, `pickle_rick`, `pulse`, `qr_code`, `rainbow_wheel`, `registry_key`, `rubber_duck`, `sad_mac`, `scratched_cd`, `server_rack`, `space_invader`, `success_kid`, `surprised_pikachu`, `tamagotchi`, `this_is_fine`, `trollface`, `usb_cable`, `vhs_tape`, `visualizer`, `waveform`, `wifi_low`, `wiki_globe`, `xp_bliss`

### All Effect Types

`spotlight`, `highlight`, `confetti`, `typewriter`, `glow`, `shockwave`, `sparkle`, `parallax`, `cursor_trail`, `cursor_trail_rainbow`, `cursor_trail_comet`, `cursor_trail_glow`, `cursor_trail_line`, `cursor_trail_particles`, `cursor_trail_fire`, `zoom_pulse`, `ripple`, `fade_in`, `fade_out`, `glitch`, `neon_glow`, `slide_in`, `success_checkmark`, `vignette`, `emoji_rain`, `fireworks`, `bubbles`, `snow`, `star_burst`, `party_popper`, `drone_zoom`, `ken_burns`, `zoom_to`, `dolly_zoom`, `elastic_zoom`, `camera_shake`, `whip_pan`, `rotate`, `letterbox`, `film_grain`, `color_grade`, `focus_pull`, `tilt_shift`, `text_highlight`, `text_scramble`, `magnetic_hover`, `tooltip_annotation`, `morphing_background`, `matrix_rain`, `frosted_glass`, `crt_scanlines`, `chromatic_aberration`, `vhs_distortion`, `pixel_sort`, `bloom`, `bokeh_blur`, `light_leak`, `wipe`, `iris`, `dissolve_noise`, `speed_ramp`, `freeze_frame`, `reverse`, `progress_bar`, `countdown_timer`, `callout_arrow`
