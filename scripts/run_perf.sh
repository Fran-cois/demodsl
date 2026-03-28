#!/usr/bin/env bash
# run_perf.sh — Run perf benchmarks in a dedicated, isolated virtual environment.
#
# Usage:
#   ./scripts/run_perf.sh              # create venv, run benchmarks, generate badge
#   ./scripts/run_perf.sh --keep-venv  # reuse existing venv if present
#
# The dedicated venv ensures the SBOM only captures project dependencies,
# not unrelated packages from the developer's global environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv-perf"
KEEP_VENV=false

for arg in "$@"; do
    case "$arg" in
        --keep-venv) KEEP_VENV=true ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

# ── 1. Create dedicated venv ────────────────────────────────────────────────

if [ "$KEEP_VENV" = false ] || [ ! -d "$VENV_DIR" ]; then
    echo "▸ Creating dedicated perf venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "▸ Python: $(python --version) at $(which python)"

# ── 2. Install project + test deps ──────────────────────────────────────────

echo "▸ Installing demodsl + test dependencies"
pip install --quiet --upgrade pip
pip install --quiet -e "$PROJECT_ROOT[dev]"
# psutil is optional but useful for hardware BOM
pip install --quiet psutil 2>/dev/null || true

echo "▸ Installed packages: $(pip list --format=columns | tail -n +3 | wc -l | tr -d ' ') packages"

# ── 3. Run perf benchmarks ──────────────────────────────────────────────────

echo "▸ Running performance benchmarks"
python -m pytest "$PROJECT_ROOT/tests/perf/" -m perf -v --tb=short

# ── 4. Generate badge + summary ─────────────────────────────────────────────

echo "▸ Generating badge and summary"
python "$PROJECT_ROOT/scripts/generate_perf_badge.py"

# ── 5. Deactivate venv ──────────────────────────────────────────────────────

deactivate

echo ""
echo "✓ Perf run complete. Results in:"
echo "    output/perf_results/       (gitignored, full archive)"
echo "    docs/public/perf/          (tracked, for badge endpoint)"
