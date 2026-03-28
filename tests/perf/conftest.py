"""Performance test infrastructure — SBOM, hardware BOM, timing, result storage."""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

import pytest

# ── BOM collectors ────────────────────────────────────────────────────────────


def collect_hardware_bom() -> dict[str, Any]:
    """Collect hardware/OS information for the current machine."""
    bom: dict[str, Any] = {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count_logical": os.cpu_count() or 0,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
    }
    try:
        import psutil

        mem = psutil.virtual_memory()
        bom["ram_total_gb"] = round(mem.total / (1024**3), 2)
        bom["ram_available_gb"] = round(mem.available / (1024**3), 2)
        bom["cpu_count_physical"] = psutil.cpu_count(logical=False) or 0
        bom["cpu_freq_mhz"] = (
            round(psutil.cpu_freq().current, 0) if psutil.cpu_freq() else None
        )
    except ImportError:
        bom["ram_total_gb"] = None
        bom["cpu_count_physical"] = None
        bom["cpu_freq_mhz"] = None
    return bom


def collect_sbom() -> list[dict[str, str]]:
    """Collect SBOM (Software Bill of Materials) — installed Python packages."""
    packages = []
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name", "unknown")
        version = dist.metadata.get("Version", "unknown")
        packages.append({"name": name, "version": version})
    # Deduplicate and sort
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for pkg in sorted(packages, key=lambda p: p["name"].lower()):
        key = pkg["name"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(pkg)
    return unique


# ── Timer utility ─────────────────────────────────────────────────────────────


@dataclass
class PerfResult:
    """Result of a single performance benchmark."""

    test_name: str
    action: str
    iterations: int
    durations_ms: list[float] = field(default_factory=list)

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.durations_ms) if self.durations_ms else 0.0

    @property
    def median_ms(self) -> float:
        return statistics.median(self.durations_ms) if self.durations_ms else 0.0

    @property
    def min_ms(self) -> float:
        return min(self.durations_ms) if self.durations_ms else 0.0

    @property
    def max_ms(self) -> float:
        return max(self.durations_ms) if self.durations_ms else 0.0

    @property
    def stdev_ms(self) -> float:
        if len(self.durations_ms) < 2:
            return 0.0
        return statistics.stdev(self.durations_ms)

    @property
    def p95_ms(self) -> float:
        if not self.durations_ms:
            return 0.0
        sorted_d = sorted(self.durations_ms)
        idx = int(len(sorted_d) * 0.95)
        return sorted_d[min(idx, len(sorted_d) - 1)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_name": self.test_name,
            "action": self.action,
            "iterations": self.iterations,
            "mean_ms": round(self.mean_ms, 4),
            "median_ms": round(self.median_ms, 4),
            "min_ms": round(self.min_ms, 4),
            "max_ms": round(self.max_ms, 4),
            "stdev_ms": round(self.stdev_ms, 4),
            "p95_ms": round(self.p95_ms, 4),
        }


class PerfTimer:
    """Context-manager based timer for benchmarking a block of code."""

    def __init__(self, result: PerfResult) -> None:
        self._result = result
        self._start: float = 0.0

    def __enter__(self) -> PerfTimer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        elapsed = (time.perf_counter() - self._start) * 1000  # ms
        self._result.durations_ms.append(elapsed)


# ── Session-scoped collector ──────────────────────────────────────────────────


class PerfCollector:
    """Accumulates perf results across all tests in a session."""

    def __init__(self) -> None:
        self.results: list[PerfResult] = []
        self.hardware_bom = collect_hardware_bom()
        self.sbom = collect_sbom()
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def create_result(self, test_name: str, action: str, iterations: int) -> PerfResult:
        result = PerfResult(test_name=test_name, action=action, iterations=iterations)
        self.results.append(result)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": {
                "timestamp": self.timestamp,
                "python_version": platform.python_version(),
                "demodsl_version": self._get_demodsl_version(),
                "python_executable": sys.executable,
                "venv": os.environ.get("VIRTUAL_ENV", None),
            },
            "hardware_bom": self.hardware_bom,
            "sbom": self.sbom,
            "results": [r.to_dict() for r in self.results],
        }

    @staticmethod
    def _get_demodsl_version() -> str:
        try:
            return importlib.metadata.version("demodsl")
        except importlib.metadata.PackageNotFoundError:
            return "dev"

    def write(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = output_dir / f"perf_{ts}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path


# ── Fixtures ──────────────────────────────────────────────────────────────────

PERF_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "perf_results"


@pytest.fixture(scope="session")
def perf_collector() -> Generator[PerfCollector, None, None]:
    """Session-scoped collector; writes results to JSON at teardown."""
    collector = PerfCollector()
    yield collector
    path = collector.write(PERF_OUTPUT_DIR)
    print(f"\n[perf] Results written to {path}")


@pytest.fixture()
def perf_timer(request: pytest.FixtureRequest, perf_collector: PerfCollector):
    """Factory fixture: call perf_timer(action, iterations) to get a PerfResult + PerfTimer."""

    def _factory(action: str, iterations: int = 100) -> tuple[PerfResult, PerfTimer]:
        test_name = request.node.name
        result = perf_collector.create_result(test_name, action, iterations)
        return result, PerfTimer(result)

    return _factory
