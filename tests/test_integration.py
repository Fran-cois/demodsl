"""Integration tests — validate example YAML configs and dry-run the engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from demodsl.config_loader import load_config
from demodsl.engine import DemoEngine
from demodsl.models import DemoConfig

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("*.yaml"))


@pytest.mark.integration
class TestExampleValidation:
    """Every example YAML must parse and validate without errors."""

    @pytest.mark.parametrize(
        "yaml_path",
        EXAMPLE_FILES,
        ids=[p.stem for p in EXAMPLE_FILES],
    )
    def test_parse_and_validate(self, yaml_path: Path) -> None:
        raw = load_config(yaml_path)
        config = DemoConfig(**raw)
        assert config.metadata.title


@pytest.mark.integration
class TestDryRunExamples:
    """Dry-run the engine on each example — must complete without errors."""

    @pytest.mark.parametrize(
        "yaml_path",
        EXAMPLE_FILES,
        ids=[p.stem for p in EXAMPLE_FILES],
    )
    def test_dry_run(self, yaml_path: Path, tmp_path: Path) -> None:
        engine = DemoEngine(
            config_path=yaml_path,
            dry_run=True,
            output_dir=tmp_path,
        )
        result = engine.run()
        assert result is None  # dry-run produces no output
