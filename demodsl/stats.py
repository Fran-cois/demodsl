"""Local usage statistics for DemoDSL.

Stores lightweight counters in JSON so creators can track generated demos
and reuse the numbers for promotion.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_stats_path() -> Path:
    env_path = os.getenv("DEMODSL_STATS_FILE")
    if env_path:
        return Path(env_path).expanduser()
    return Path.home() / ".demodsl" / "stats.json"


@dataclass
class StatsStore:
    path: Path | None = None

    def __post_init__(self) -> None:
        if self.path is None:
            self.path = default_stats_path()

    def _default_data(self) -> dict[str, Any]:
        now = _now_iso()
        return {
            "schema_version": 1,
            "created_at": now,
            "updated_at": now,
            "totals": {
                "demos_created": 0,
                "dry_runs": 0,
                "runs": 0,
            },
            "renderers": {},
            "projects": {},
            "recent": [],
        }

    def load(self) -> dict[str, Any]:
        assert self.path is not None
        if not self.path.exists():
            return self._default_data()
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return self._default_data()

    def save(self, data: dict[str, Any]) -> None:
        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = _now_iso()
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def record_run(
        self,
        *,
        project_title: str,
        config_path: Path,
        renderer: str,
        output: Path | None,
        dry_run: bool,
    ) -> dict[str, Any]:
        data = self.load()

        totals = data.setdefault("totals", {})
        totals["runs"] = int(totals.get("runs", 0)) + 1

        if dry_run:
            totals["dry_runs"] = int(totals.get("dry_runs", 0)) + 1
        if output is not None:
            totals["demos_created"] = int(totals.get("demos_created", 0)) + 1

        renderers = data.setdefault("renderers", {})
        renderers[renderer] = int(renderers.get(renderer, 0)) + 1

        projects = data.setdefault("projects", {})
        projects[project_title] = int(projects.get(project_title, 0)) + 1

        recent = data.setdefault("recent", [])
        recent.append(
            {
                "timestamp": _now_iso(),
                "project_title": project_title,
                "config": str(config_path),
                "renderer": renderer,
                "dry_run": dry_run,
                "output": str(output) if output else None,
            }
        )
        # Keep only recent history window
        if len(recent) > 50:
            data["recent"] = recent[-50:]

        self.save(data)
        return data

    def summary(self) -> dict[str, Any]:
        data = self.load()
        totals = data.get("totals", {})
        projects = data.get("projects", {})
        recent = data.get("recent", [])
        return {
            "path": str(self.path),
            "demos_created": int(totals.get("demos_created", 0)),
            "runs": int(totals.get("runs", 0)),
            "dry_runs": int(totals.get("dry_runs", 0)),
            "unique_projects": len(projects),
            "renderers": data.get("renderers", {}),
            "last_run": recent[-1]["timestamp"] if recent else None,
        }

    def promo_text(self) -> str:
        s = self.summary()
        demos = s["demos_created"]
        projects = s["unique_projects"]
        runs = s["runs"]
        return (
            f"J'ai cree {demos} demos produit avec DemoDSL "
            f"sur {projects} projet(s), en {runs} execution(s) total(es)."
        )
