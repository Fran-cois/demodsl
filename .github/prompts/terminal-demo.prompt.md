---
description: "Generate a DemoDSL terminal recording demo. Use when: creating a terminal demo, recording CLI commands, showcasing a build/deploy workflow in a terminal, generating a terminal screencast with macOS desktop background."
mode: "agent"
tools: ["run_in_terminal", "create_file", "read_file"]
---

# Terminal Demo Generator for DemoDSL

Generate a complete DemoDSL YAML configuration that records a **terminal session** — typed commands with animated output — rendered in a browser via Playwright and exported as MP4 video.

## Context

DemoDSL supports `terminal` scenarios alongside browser and mobile scenarios. A terminal scenario renders a self-contained HTML terminal emulator in a headless browser, types commands character-by-character, displays output with configurable delays, and records the result as a high-quality MP4 video.

On macOS, dock icons are extracted natively from installed `.app` bundles at runtime (Finder, Safari, Terminal, VS Code, etc.) with SVG fallbacks.

## YAML Schema

### Terminal config (`terminal:` on a scenario)

```yaml
terminal:
  shell: "zsh"                 # Shell name shown in title bar (cosmetic)
  prompt: "~/project $ "       # Prompt string before each command
  theme: "dracula"             # dark | light | dracula | monokai | solarized
  font_family: "'SF Mono', 'Fira Code', monospace"
  font_size: 18                # 10–48
  line_height: 1.5             # 1.0–3.0
  cols: 100                    # 40–300
  rows: 28                     # 10–80
  title: "Terminal — my-project"
  window_chrome: true          # macOS-style traffic lights + title bar
  typing_speed: 14             # chars/sec (>0, ≤200)
  output_delay: 0.35           # seconds before output appears (0–5)
```

### macOS desktop background (`background:` on a scenario, optional)

```yaml
background:
  os: "macos"
  theme: "dark"
  wallpaper_color: "#1a1a2e"
  window_title: "Terminal"
  show_dock: true
  show_menu_bar: true
  apps:                        # Dock icons (real macOS icons if app is installed)
    - name: "Finder"
    - name: "Safari"
    - name: "Terminal"
    - name: "VS Code"
    - name: "Slack"
    - name: "Music"
```

Available dock app names (auto-resolved from `/Applications/`):
Finder, Safari, Terminal, VS Code, Slack, Music, Notes, Messages, Mail, Settings, Photos, Chrome, Firefox, Discord, Spotify, GitHub Desktop.

### Terminal step actions

| Action           | Required fields          | Optional fields                    | Description                                    |
| ---------------- | ------------------------ | ---------------------------------- | ---------------------------------------------- |
| `terminal_run`   | `command`                | `output` (str or list[str]), `wait`, `narration` | Type a command + display output        |
| `terminal_clear` | —                        | `wait`, `narration`                | Clear the terminal screen                      |
| `terminal_zoom`  | —                        | `zoom_level` (float, default 1.5), `zoom_duration` (float, default 0.8), `wait`, `narration` | Zoom in/out on terminal content |

### Rules

1. A terminal scenario uses `terminal:` instead of `url:` — **no URL is needed**.
2. `terminal_run`, `terminal_clear`, `terminal_zoom` are only valid in terminal scenarios.
3. `output` can be a single string or a list of strings (one per line).
4. To create a zoom effect: first `terminal_zoom` with `zoom_level: 1.5` (zoom in), then `terminal_zoom` with `zoom_level: 1.0` (zoom back out).
5. Emoji characters (🚀, ✅, ❌) are automatically stripped to avoid Chromium rendering crashes on macOS ARM — they will silently disappear from the recorded video. Use plain text symbols (✓, ✗, →, ★) instead for safe rendering.
6. Always set `viewport` to `1920x1080` for best quality.
7. `metadata.version` is always `"2.0.0"`.

## Full Example

```yaml
metadata:
  title: "Terminal on macOS"
  version: "2.0.0"

scenarios:
  - name: "macOS Terminal"
    terminal:
      shell: "zsh"
      prompt: "~/project $ "
      theme: "dracula"
      font_size: 18
      typing_speed: 14
      output_delay: 0.35
      window_chrome: true
      title: "Terminal — my-project"
    background:
      os: "macos"
      theme: "dark"
      wallpaper_color: "#1a1a2e"
      window_title: "Terminal"
      show_dock: true
      show_menu_bar: true
      apps:
        - name: "Finder"
        - name: "Safari"
        - name: "Terminal"
        - name: "VS Code"
    viewport:
      width: 1920
      height: 1080
    steps:
      - action: terminal_run
        command: "echo 'Hello, World!'"
        output: "Hello, World!"
        wait: 1.5

      - action: terminal_run
        command: "npm run build"
        output:
          - "> myapp@1.0.0 build"
          - "> tsc && vite build"
          - ""
          - "vite v5.2.0 building for production..."
          - "dist/index.html          0.46 kB"
          - "dist/assets/index.js   142.35 kB"
          - "Done in 1.82s"
        wait: 1.5

      - action: terminal_zoom
        zoom_level: 1.6
        zoom_duration: 0.8
        wait: 2.0

      - action: terminal_zoom
        zoom_level: 1.0
        zoom_duration: 0.6
        wait: 1.0

      - action: terminal_clear
        wait: 0.5

      - action: terminal_run
        command: "echo 'Build complete'"
        output: "Build complete"
        wait: 2.0

pipeline:
  - edit_video: {}
```

## Running the Demo

```bash
demodsl run <file>.yaml --force --no-run-cache --skip-voice
```

Output goes to `output/output.mp4`.

## Procedure

1. Ask the user what commands/workflow to demo (or infer from context).
2. Generate a YAML file following the schema above.
3. Save it to `examples/` or a user-specified path.
4. Optionally run it with `demodsl run`.
