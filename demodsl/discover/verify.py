"""Render a discovered config into a video as proof of the discovery.

Kept deliberately thin: it writes the synthesised config to a YAML file and
drives the existing :class:`~demodsl.engine.DemoEngine`.  Heavy imports are
deferred so importing the discovery package never pulls in the full render
stack.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def write_config_yaml(config_dict: dict[str, Any], path: Path) -> Path:
    """Serialise *config_dict* to YAML at *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(config_dict, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return path


def verify_config(
    config_dict: dict[str, Any],
    output_dir: Path,
    *,
    config_path: Path | None = None,
    turbo: bool = True,
    skip_voice: bool = False,
    dry_run: bool = False,
) -> Path | None:
    """Render *config_dict*; return the produced media path (or None).

    ``turbo`` defaults to True so the verification pass is fast (no avatars / 3D
    / heavy post-processing).  Set ``dry_run`` to validate + log without
    recording.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = config_path or (output_dir / "discovered_demo.yaml")
    write_config_yaml(config_dict, cfg_path)

    from demodsl.engine import DemoEngine  # deferred: heavy import

    engine = DemoEngine(
        cfg_path,
        dry_run=dry_run,
        skip_voice=skip_voice,
        turbo=turbo,
        output_dir=output_dir,
    )
    result = engine.run()
    if result is not None:
        logger.info("verification render produced %s", result)
    return result
