#!/usr/bin/env bash
# Regenerate ALL documentation videos with improved quality (deblock filter).
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv-perf/bin/activate

VIDEOS_DIR="docs/public/videos"
LOG_DIR="output/_regen_logs"
mkdir -p "$LOG_DIR"

echo "=== DemoDSL: Regenerating ALL doc videos ==="
echo ""

# ─── 1. Core feature demos (via demodsl CLI) ───────────────────────────
CORE_DEMOS=(
  demo_navigate_scroll
  demo_click
  demo_cursor
  demo_glow_select
  demo_locators
  demo_popup_card
  demo_tab_switch
  demo_waitfor
  demo_multi_scenario
  demo_mobile_screenshot
  demo_browser_effects
  demo_voice_narration
)

echo "── Phase 1: Core feature demos (${#CORE_DEMOS[@]} demos) ──"
PASS=0
FAIL=0
for demo in "${CORE_DEMOS[@]}"; do
  echo -n "  ▸ $demo ... "
  if python -m demodsl.cli run "examples/${demo}.yaml" \
       --skip-voice -o "$VIDEOS_DIR" --no-run-cache \
       > "$LOG_DIR/${demo}.log" 2>&1; then
    echo "✓"
    ((PASS++))
  else
    echo "✗ (see $LOG_DIR/${demo}.log)"
    ((FAIL++))
  fi
done
echo "  Core demos done: $PASS passed, $FAIL failed"
echo ""

# ─── 2. Avatar demos (script) ─────────────────────────────────────────
echo "── Phase 2: Avatar demos (63 styles) ──"
if python scripts/generate_avatar_demos.py > "$LOG_DIR/avatar_demos.log" 2>&1; then
  echo "  ✓ Avatar demos generated"
else
  echo "  ✗ Avatar demos failed (see $LOG_DIR/avatar_demos.log)"
fi
echo ""

# ─── 3. Browser effect demos (script) ─────────────────────────────────
echo "── Phase 3: Browser effect demos (23 effects) ──"
if python scripts/generate_effect_demos.py > "$LOG_DIR/effect_demos.log" 2>&1; then
  echo "  ✓ Effect demos generated"
else
  echo "  ✗ Effect demos failed (see $LOG_DIR/effect_demos.log)"
fi
echo ""

# ─── 4. Subtitle demos (script) ───────────────────────────────────────
echo "── Phase 4: Subtitle demos (11 styles) ──"
if python scripts/generate_subtitle_demos.py > "$LOG_DIR/subtitle_demos.log" 2>&1; then
  echo "  ✓ Subtitle demos generated"
else
  echo "  ✗ Subtitle demos failed (see $LOG_DIR/subtitle_demos.log)"
fi
echo ""

# ─── 5. Camera / cinematic demos (script) ─────────────────────────────
echo "── Phase 5: Camera & cinematic demos (13 effects) ──"
if python scripts/generate_camera_demos.py > "$LOG_DIR/camera_demos.log" 2>&1; then
  echo "  ✓ Camera demos generated"
else
  echo "  ✗ Camera demos failed (see $LOG_DIR/camera_demos.log)"
fi
echo ""

echo "=== All phases complete ==="
echo "Videos in: $VIDEOS_DIR"
echo "Logs in:   $LOG_DIR"
