"""Generate performance badge JSON and summary from latest perf results."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def latest_result(perf_dir: Path) -> dict:
    files = sorted(perf_dir.glob("perf_*.json"))
    if not files:
        print("No perf result files found", file=sys.stderr)
        sys.exit(1)
    with files[-1].open() as f:
        return json.load(f)


def generate_badge(data: dict, output_path: Path) -> None:
    """Generate shields.io endpoint badge JSON."""
    results = data["results"]
    total_tests = len(results)
    all_pass = all(r["mean_ms"] < 200 for r in results)  # generous threshold

    badge = {
        "schemaVersion": 1,
        "label": "perf",
        "message": f"{total_tests} benchmarks passing",
        "color": "brightgreen" if all_pass else "yellow",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(badge, indent=2))
    print(f"Badge JSON written to {output_path}")


def generate_summary(data: dict, output_path: Path) -> None:
    """Generate a Markdown summary table of perf results."""
    results = data["results"]
    hw = data["hardware_bom"]
    meta = data["metadata"]
    sbom = data["sbom"]

    lines = [
        "# Performance Results",
        "",
        f"**Date**: {meta['timestamp']}  ",
        f"**Python**: {meta['python_version']}  ",
        f"**DemoDSL**: {meta['demodsl_version']}  ",
        "",
        "## Hardware",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| OS | {hw['os']} {hw['os_release']} |",
        f"| Architecture | {hw['architecture']} |",
        f"| CPU | {hw['processor']} ({hw['cpu_count_logical']} logical cores) |",
        f"| RAM | {hw.get('ram_total_gb', '?')} GB |",
        "",
        "## Results",
        "",
        "| Action | Mean (ms) | Median (ms) | P95 (ms) | Min (ms) | Max (ms) | Iterations |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sorted(results, key=lambda x: x["action"]):
        lines.append(
            f"| {r['action']} | {r['mean_ms']:.4f} | {r['median_ms']:.4f} "
            f"| {r['p95_ms']:.4f} | {r['min_ms']:.4f} | {r['max_ms']:.4f} "
            f"| {r['iterations']} |"
        )

    lines += [
        "",
        f"## SBOM",
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
    data = latest_result(perf_dir)

    # Write to output/ (gitignored, full archive)
    generate_badge(data, perf_dir / "badge.json")
    generate_summary(data, perf_dir / "PERF_RESULTS.md")

    # Write to docs/public/perf/ (tracked, for badge endpoint)
    generate_badge(data, docs_dir / "badge.json")
    generate_summary(data, docs_dir / "PERF_RESULTS.md")


if __name__ == "__main__":
    main()
