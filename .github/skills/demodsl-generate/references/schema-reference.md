# DemoDSL Schema Reference

Complete field reference extracted from `demodsl/models.py`.

## Root: `DemoConfig`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `metadata` | Metadata | **yes** | — |
| `voice` | VoiceConfig | no | null |
| `audio` | AudioConfig | no | null |
| `device_rendering` | DeviceRendering | no | null |
| `video` | VideoConfig | no | null |
| `subtitle` | SubtitleConfig | no | null |
| `scenarios` | list[Scenario] | no | [] |
| `pipeline` | list[PipelineStage] | no | [] |
| `output` | OutputConfig | no | null |
| `analytics` | Analytics | no | null |

## Metadata

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `title` | str | **yes** | — |
| `description` | str | no | null |
| `author` | str | no | null |
| `version` | str | no | null |

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

### AudioEffects

| Field | Type | Default |
|-------|------|---------|
| `eq_preset` | str | null |
| `reverb_preset` | str | null |
| `compression` | Compression | null |

### Compression

| Field | Type | Default |
|-------|------|---------|
| `threshold` | int | `-20` |
| `ratio` | float | `3.0` |
| `attack` | int | `5` |
| `release` | int | `50` |

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
| `viewport` | Viewport | `{width: 1920, height: 1080}` |
| `cursor` | CursorConfig | null |
| `glow_select` | GlowSelectConfig | null |
| `popup_card` | PopupCardConfig | null |
| `avatar` | AvatarConfig | null |
| `subtitle` | SubtitleConfig | null |
| `steps` | list[Step] | [] |

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
| `colors` | list[str] | `["#a855f7", "#6366f1", "#ec4899", "#a855f7"]` |
| `duration` | float | `0.8` |
| `padding` | int | `8` |
| `border_radius` | int | `12` |
| `intensity` | float | `0.9` |

### AvatarConfig

| Field | Type | Default |
|-------|------|---------|
| `enabled` | bool | `true` |
| `provider` | `animated` \| `d-id` \| `heygen` \| `sadtalker` | `"animated"` |
| `image` | str | null | Path, URL (http/https), or preset name (`"default"`, `"robot"`, `"circle"`). URLs are downloaded and cached. |
| `position` | `bottom-right` \| `bottom-left` \| `top-right` \| `top-left` | `"bottom-right"` |
| `size` | int | `120` |
| `style` | see styles list below | `"bounce"` |
| `shape` | `circle` \| `rounded` \| `square` | `"circle"` |
| `background` | str | `"rgba(0,0,0,0.5)"` |
| `api_key` | str | null |
| `show_subtitle` | bool | `false` |
| `subtitle_font_size` | int | `18` |
| `subtitle_font_color` | str | `"#FFFFFF"` |
| `subtitle_bg_color` | str | `"rgba(0,0,0,0.7)"` |

**Avatar styles:** `bounce`, `waveform`, `pulse`, `equalizer`, `xp_bliss`, `clippy`, `visualizer`, `pacman`, `space_invader`, `mario_block`, `nyan_cat`, `matrix`, `pickle_rick`, `chrome_dino`, `marvin`, `mac128k`, `floppy_disk`, `bsod`, `bugdroid`, `qr_code`, `gpu_sweat`, `rubber_duck`, `fail_whale`, `server_rack`, `cursor_hand`, `vhs_tape`, `cloud`, `wifi_low`, `nokia3310`, `cookie`, `modem56k`, `esc_key`, `sad_mac`, `usb_cable`, `hourglass`, `firewire`, `ai_hallucinated`, `tamagotchi`, `lasso_tool`, `battery_low`, `incognito`

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

| Field | Type | Default | Used with actions |
|-------|------|---------|-------------------|
| `action` | `navigate` \| `click` \| `type` \| `scroll` \| `wait_for` \| `screenshot` | **required** | all |
| `url` | str | null | navigate |
| `locator` | Locator | null | click, type, wait_for |
| `value` | str | null | type |
| `direction` | `up` \| `down` \| `left` \| `right` | null | scroll |
| `pixels` | int | null | scroll |
| `timeout` | float | null | wait_for |
| `filename` | str | null | screenshot |
| `narration` | str | null | all (optional) |
| `wait` | float | null | all (optional) |
| `effects` | list[Effect] | null | all (optional) |
| `card` | CardContent | null | all (optional) |

### Locator

| Field | Type | Default |
|-------|------|---------|
| `type` | `css` \| `id` \| `xpath` \| `text` | `"css"` |
| `value` | str | **required** |

### CardContent

| Field | Type | Default |
|-------|------|---------|
| `title` | str | null |
| `body` | str | null |
| `items` | list[str] | null |
| `icon` | str | null |

## PipelineStage

Written as a single-key dict in YAML:
```yaml
pipeline:
  - stage_name: {param1: value1}
```

Available stages: `restore_audio`, `restore_video`, `apply_effects`, `generate_narration`, `render_device_mockup`, `composite_avatar`, `edit_video`, `burn_subtitles`, `mix_audio`, `optimize`

### optimize params

| Field | Type | Default |
|-------|------|---------|
| `format` | str | `"mp4"` |
| `codec` | str | `"h264"` |
| `quality` | str | `"high"` |
| `target_size_mb` | int | null |

## OutputConfig

| Field | Type | Default |
|-------|------|---------|
| `filename` | str | `"output.mp4"` |
| `directory` | str | `"output/"` |
| `formats` | list[str] | `["mp4"]` |
| `thumbnails` | list[Thumbnail] | null |
| `social` | list[SocialExport] | null |

### SocialExport

| Field | Type | Default |
|-------|------|---------|
| `platform` | str | **required** |
| `resolution` | str | null |
| `bitrate` | str | null |
| `aspect_ratio` | str | null |
| `max_duration` | int | null |
| `max_size_mb` | int | null |
