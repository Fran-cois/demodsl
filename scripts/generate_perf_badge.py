"""Generate performance badge JSON and summary from latest perf results.

Compares the latest run against the previous baseline to determine
badge colour:
  - green   → no regression (all deltas ≤ +10%)
  - orange  → minor regression (some deltas > +10%, none > +25%)
  - red     → significant regression (any delta > +25%)

Thresholds are configurable via REGRESSION_WARN / REGRESSION_FAIL.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ── Regression thresholds (relative to baseline mean_ms) ─────────────────────
REGRESSION_WARN = 0.10   # >10% slower → orange
REGRESSION_FAIL = 0.25   # >25% slower → red
REGRESSION_MIN_DELTA_MS = 0.5  # ignore deltas below 0.5 ms (sub-ms noise)


def _sanitize(val: str | None) -> str:
    """Strip user home prefix from paths to avoid leaking PII."""
    if val is None:
        return "N/A"
    home = str(Path.home())
    if val.startswith(home):
        return "~" + val[len(home):]
    return val


def load_results(perf_dir: Path) -> tuple[dict, dict | None]:
    """Return (latest, baseline_or_None) from perf result files."""
    files = sorted(perf_dir.glob("perf_*.json"))
    if not files:
        print("No perf result files found", file=sys.stderr)
        sys.exit(1)
    with files[-1].open() as f:
        latest = json.load(f)
    baseline = None
    if len(files) >= 2:
        with files[-2].open() as f:
            baseline = json.load(f)
    return latest, baseline


def _build_baseline_map(baseline: dict) -> dict[str, dict]:
    """Map action → result dict from a baseline run."""
    return {r["action"]: r for r in baseline["results"]}


def _classify_delta(current_ms: float, baseline_ms: float) -> str:
    """Return 'green', 'orange', or 'red' for a single metric."""
    if baseline_ms <= 0:
        return "green"
    abs_delta = current_ms - baseline_ms
    if abs_delta < REGRESSION_MIN_DELTA_MS:
        return "green"
    ratio = abs_delta / baseline_ms
    if ratio > REGRESSION_FAIL:
        return "red"
    if ratio > REGRESSION_WARN:
        return "orange"
    return "green"


def _delta_str(current_ms: float, baseline_ms: float) -> str:
    """Human-readable delta string like '+12.3%' or '-5.1%'."""
    if baseline_ms <= 0:
        return "new"
    pct = ((current_ms - baseline_ms) / baseline_ms) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def _status_icon(color: str) -> str:
    if color == "red":
        return "🔴"
    if color == "orange":
        return "🟠"
    return "🟢"


def compute_overall_status(
    results: list[dict], baseline_map: dict[str, dict] | None
) -> str:
    """Return overall badge color: green, orange, or red."""
    if baseline_map is None:
        return "brightgreen"
    worst = "green"
    for r in results:
        base = baseline_map.get(r["action"])
        if base is None:
            continue
        color = _classify_delta(r["mean_ms"], base["mean_ms"])
        if color == "red":
            return "red"
        if color == "orange":
            worst = "orange"
    return "brightgreen" if worst == "green" else worst


# ── Badge generation ─────────────────────────────────────────────────────────


def generate_badge(
    data: dict, baseline: dict | None, output_path: Path
) -> None:
    """Generate shields.io endpoint badge JSON with regression-aware colour."""
    results = data["results"]
    total = len(results)
    baseline_map = _build_baseline_map(baseline) if baseline else None
    color = compute_overall_status(results, baseline_map)

    label_map = {
        "brightgreen": f"{total} benchmarks ✓ stable",
        "orange": f"{total} benchmarks ⚠ minor regression",
        "red": f"{total} benchmarks ✗ regression",
    }
    badge = {
        "schemaVersion": 1,
        "label": "perf",
        "message": label_map.get(color, f"{total} benchmarks"),
        "color": color,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(badge, indent=2))
    print(f"Badge JSON written to {output_path}  [color={color}]")


# ── Summary generation ───────────────────────────────────────────────────────


def generate_summary(
    data: dict, baseline: dict | None, output_path: Path
) -> None:
    """Generate a Markdown summary table with delta columns when baseline exists."""
    results = data["results"]
    hw = data["hardware_bom"]
    meta = data["metadata"]
    sbom = data["sbom"]
    baseline_map = _build_baseline_map(baseline) if baseline else None

    lines = [
        "# Performance Results",
        "",
        f"**Date**: {meta['timestamp']}  ",
        f"**Python**: {meta['python_version']}  ",
        f"**DemoDSL**: {meta['demodsl_version']}  ",
        f"**Venv**: `{_sanitize(meta.get('venv'))}`  ",
        f"**Executable**: `{_sanitize(meta.get('python_executable'))}`  ",
    ]

    if baseline:
        base_ts = baseline.get("metadata", {}).get("timestamp", "?")
        lines.append(f"**Baseline**: {base_ts}  ")
        lines.append(
            f"**Thresholds**: warn > {REGRESSION_WARN*100:.0f}%, "
            f"fail > {REGRESSION_FAIL*100:.0f}%  "
        )

    lines += [
        "",
        "## Hardware",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| OS | {hw['os']} {hw['os_release']} |",
        f"| Architecture | {hw['architecture']} |",
        f"| CPU | {hw['processor']} ({hw['cpu_count_logical']} logical cores) |",
        f"| RAM | {hw.get('ram_total_gb', '?')} GB |",
        "",
        "## Results",
        "",
    ]

    if baseline_map:
        lines.append(
            "| Status | Action | Mean (ms) | Δ Mean | P95 (ms) | Δ P95 "
            "| Median (ms) | Iterations |"
        )
        lines.append("|:---:|---|---:|---:|---:|---:|---:|---:|")
    else:
        lines.append(
            "| Action | Mean (ms) | Median (ms) | P95 (ms) | Min (ms) "
            "| Max (ms) | Iterations |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|")

    for r in sorted(results, key=lambda x: x["action"]):
        if baseline_map:
            base = baseline_map.get(r["action"])
            if base:
                mean_color = _classify_delta(r["mean_ms"], base["mean_ms"])
                p95_color = _classify_delta(r["p95_ms"], base["p95_ms"])
                # Pick worst status for the row icon
                row_color = (
                    "red" if "red" in (mean_color, p95_color)
                    else "orange" if "orange" in (mean_color, p95_color)
                    else "green"
                )
                mean_delta = _delta_str(r["mean_ms"], base["mean_ms"])
                p95_delta = _delta_str(r["p95_ms"], base["p95_ms"])
            else:
                row_color = "green"
                mean_delta = "new"
                p95_delta = "new"

            lines.append(
                f"| {_status_icon(row_color)} | {r['action']} "
                f"| {r['mean_ms']:.4f} | {mean_delta} "
                f"| {r['p95_ms']:.4f} | {p95_delta} "
                f"| {r['median_ms']:.4f} | {r['iterations']} |"
            )
        else:
            lines.append(
                f"| {r['action']} | {r['mean_ms']:.4f} | {r['median_ms']:.4f} "
                f"| {r['p95_ms']:.4f} | {r['min_ms']:.4f} | {r['max_ms']:.4f} "
                f"| {r['iterations']} |"
            )

    # Regression summary
    if baseline_map:
        regressed = []
        for r in results:
            base = baseline_map.get(r["action"])
            if base and _classify_delta(r["mean_ms"], base["mean_ms"]) != "green":
                regressed.append(
                    (r["action"], r["mean_ms"], base["mean_ms"],
                     _classify_delta(r["mean_ms"], base["mean_ms"]))
                )
        lines += ["", "## Regression Summary", ""]
        if regressed:
            lines.append("| Action | Current (ms) | Baseline (ms) | Delta | Severity |")
            lines.append("|---|---:|---:|---:|:---:|")
            for action, cur, base_v, sev in sorted(regressed, key=lambda x: x[3], reverse=True):
                lines.append(
                    f"| {action} | {cur:.4f} | {base_v:.4f} "
                    f"| {_delta_str(cur, base_v)} | {_status_icon(sev)} {sev} |"
                )
        else:
            lines.append("No regressions detected. All benchmarks within thresholds. 🟢")

    lines += [
        "",
        "## SBOM",
        "",
        f"<details><summary>{len(sbom)} packages</summary>",
        "",
    ]
    for pkg in sbom:
        lines.append(f"- {pkg['name']}=={pkg['version']}")
    lines += ["", "</details>", ""]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"Summary written to {output_path}")


def main() -> None:
    perf_dir = Path(__file__).resolve().parent.parent / "output" / "perf_results"
    docs_dir = Path(__file__).resolve().parent.parent / "docs" / "public" / "perf"
    latest, baseline = load_results(perf_dir)

    # Write to output/ (gitignored, full archive)
    generate_badge(latest, baseline, perf_dir / "badge.json")
    generate_summary(latest, baseline, perf_dir / "PERF_RESULTS.md")

    # Write to docs/public/perf/ (tracked, for badge endpoint)
    generate_badge(latest, baseline, docs_dir / "badge.json")
    generate_summary(latest, baseline, docs_dir / "PERF_RESULTS.md")


if __name__ == "__main__":
    main()
