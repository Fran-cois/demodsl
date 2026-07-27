"""Interactive authoring session (issue #21).

Today authoring is one-shot and blind: a model emits a whole YAML, then
a render (minutes) tells it whether *any* of it worked. This module turns
demodsl from "a format a model writes" into "an environment a model
operates": the browser stays open across calls, and the model takes one
step at a time — observe, try, undo, commit.

.. code-block:: python

    session = AuthoringSession("https://example.com")
    session.open()
    session.observe()                       # marks + ranked elements
    session.try_step({"action": "hover", "locator": {...}})
    session.undo()                          # the rejected step leaves no residue
    config = session.commit()               # exactly what `demodsl run` replays

``try_step`` is side-effect scoped: nothing is recorded, injected effects
are torn down afterwards, and the page state captured before the step is
restored on ``undo``.
"""

from __future__ import annotations

import base64
import json
import logging
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from demodsl.commands import get_command
from demodsl.models import DemoConfig, Metadata, Scenario, Step, Viewport
from demodsl.observe import candidate_arguments, derive_sections, rank_elements

logger = logging.getLogger(__name__)

__all__ = [
    "SessionExpiredError",
    "TryResult",
    "AuthoringSession",
    "SessionManager",
    "DEFAULT_TTL_SECONDS",
    "MAX_OPEN_SESSIONS",
]

DEFAULT_TTL_SECONDS = 900.0
MAX_OPEN_SESSIONS = 4

_CLEANUP_EFFECTS_JS = r"""
(() => {
  let removed = 0;
  for (const node of document.querySelectorAll('[id^="__demodsl"], [class^="__demodsl"]')) {
    node.remove();
    removed += 1;
  }
  return removed;
})()
"""


class SessionExpiredError(RuntimeError):
    """Raised when a session is used past its TTL or after being closed."""


@dataclass
class TryResult:
    """Exactly what the model needs to decide the next move."""

    ok: bool
    duration_s: float = 0.0
    frame: str | None = None
    resolved_locator: dict[str, Any] | None = None
    effect_anchor: dict[str, float] | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    step: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "duration_s": round(self.duration_s, 3),
            "frame": self.frame,
            "resolved_locator": self.resolved_locator,
            "effect_anchor": self.effect_anchor,
            "warnings": self.warnings,
            "error": self.error,
            "step": self.step,
        }


_RESOLVE_JS = """
((sel, kind) => {
  let nodes = [];
  if (kind === 'css') nodes = Array.from(document.querySelectorAll(sel));
  else if (kind === 'id') { const el = document.getElementById(sel); nodes = el ? [el] : []; }
  else {
    const needle = String(sel).toLowerCase();
    nodes = Array.from(document.querySelectorAll('*')).filter((el) => {
      if (el.children.length) return false;
      return (el.textContent || '').trim().toLowerCase().includes(needle);
    });
  }
  if (!nodes.length) return { matches: 0, bbox: null, visible: false };
  const el = nodes[0];
  const r = el.getBoundingClientRect();
  const cs = getComputedStyle(el);
  return {
    matches: nodes.length,
    bbox: { x: r.left, y: r.top, w: r.width, h: r.height },
    visible: r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none',
    pointer_events: cs.pointerEvents,
  };
})
"""


class AuthoringSession:
    """A stateful, tool-callable authoring session over one live page."""

    def __init__(
        self,
        url: str,
        *,
        provider: Any | None = None,
        viewport: tuple[int, int] = (1920, 1080),
        browser: str = "chrome",
        ttl: float = DEFAULT_TTL_SECONDS,
        title: str = "Interactive session",
        include_frames: bool = True,
    ) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.url = url
        self.viewport = viewport
        self.browser = browser
        self.ttl = ttl
        self.title = title
        self.include_frames = include_frames
        self._provider = provider
        self._owns_provider = provider is None
        self._steps: list[Step] = []
        self._snapshots: list[dict[str, Any]] = []
        self._closed = False
        self._created_at = time.monotonic()
        self._last_used = self._created_at

    # ── Lifecycle ─────────────────────────────────────────────────────────

    @property
    def expired(self) -> bool:
        return self._closed or (time.monotonic() - self._last_used) > self.ttl

    def _touch(self) -> None:
        if self._closed:
            raise SessionExpiredError(f"Session {self.id} is closed")
        if (time.monotonic() - self._last_used) > self.ttl:
            self.close()
            raise SessionExpiredError(f"Session {self.id} expired (TTL {self.ttl:.0f}s)")
        self._last_used = time.monotonic()

    def open(self) -> dict[str, Any]:
        """Launch the browser (no recording) and navigate to the start URL."""
        if self._provider is None:
            import demodsl.providers.browser  # noqa: F401  (registers the provider)
            from demodsl.providers.base import BrowserProviderFactory

            self._provider = BrowserProviderFactory.create("playwright")
            self._provider.launch_without_recording(
                browser_type=self.browser,
                viewport=Viewport(width=self.viewport[0], height=self.viewport[1]),
            )
        self._provider.navigate(self.url)
        self._last_used = time.monotonic()
        return {"session_id": self.id, "url": self.url}

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._provider is not None and self._owns_provider:
            try:
                self._provider.close()
            except Exception:  # pragma: no cover - defensive teardown
                logger.debug("Session %s: provider close failed", self.id, exc_info=True)

    def __enter__(self) -> AuthoringSession:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── Observation ───────────────────────────────────────────────────────

    def observe(self, *, limit: int = 40) -> dict[str, Any]:
        """Screenshot + prominence-ranked element list for the current page."""
        self._touch()
        from demodsl.observe import COLLECT_JS

        payload = self._provider.evaluate_js(COLLECT_JS)
        elements = rank_elements(payload, limit=limit)
        viewport = payload.get("viewport") or {}
        return {
            "session_id": self.id,
            "url": self._current_url(),
            "frame": self._frame(),
            "elements": elements,
            "sections": derive_sections(
                elements,
                page_height=float(payload.get("page_height") or self.viewport[1]),
                viewport_height=float(viewport.get("h") or self.viewport[1]),
            ),
            "candidates": candidate_arguments(elements),
        }

    # ── Try / undo / timeline / commit ────────────────────────────────────

    def try_step(self, step: Step | dict[str, Any]) -> TryResult:
        """Execute exactly ONE step and report what happened.

        Nothing is recorded and any injected effect is torn down, so a
        rejected step leaves no residue on the page.
        """
        self._touch()
        try:
            candidate = step if isinstance(step, Step) else Step(**step)
        except Exception as exc:
            return TryResult(ok=False, error=f"invalid step: {exc}")

        snapshot = self._snapshot()
        resolved = self._resolve(candidate)
        warnings: list[str] = []
        anchor: dict[str, float] | None = None

        if resolved is not None:
            if resolved.get("matches", 0) == 0:
                warnings.append("locator resolves to no element")
            elif resolved.get("matches", 0) > 1:
                warnings.append(f"locator is ambiguous ({resolved['matches']} matches)")
            if resolved.get("matches") and not resolved.get("visible"):
                warnings.append("element is present but not visible")
            if resolved.get("pointer_events") == "none":
                warnings.append("element has pointer-events: none and cannot be hovered")
            anchor = self._anchor(resolved)
            warnings += self._overlay_warnings(candidate, resolved)

        started = time.monotonic()
        error: str | None = None
        try:
            command = get_command(candidate.action, output_dir=Path(tempfile.gettempdir()))
            command.execute(self._provider, candidate)
            ok = True
        except Exception as exc:
            ok = False
            error = str(exc).splitlines()[0][:300]
        duration = time.monotonic() - started

        self._cleanup_effects()

        if ok:
            self._steps.append(candidate)
            self._snapshots.append(snapshot)

        return TryResult(
            ok=ok,
            duration_s=duration,
            frame=self._frame(),
            resolved_locator=resolved,
            effect_anchor=anchor,
            warnings=warnings,
            error=error,
            step=candidate.model_dump(exclude_none=True),
        )

    def undo(self) -> dict[str, Any]:
        """Drop the last accepted step and restore the page state before it."""
        self._touch()
        if not self._steps:
            return {"undone": None, "steps": 0}
        step = self._steps.pop()
        snapshot = self._snapshots.pop()
        self._restore(snapshot)
        self._cleanup_effects()
        return {
            "undone": step.model_dump(exclude_none=True),
            "steps": len(self._steps),
            "restored_url": snapshot.get("url"),
        }

    def timeline(self) -> list[dict[str, Any]]:
        """The steps accepted so far, in order."""
        self._touch()
        return [s.model_dump(exclude_none=True) for s in self._steps]

    def commit(self, *, scenario_name: str = "session") -> DemoConfig:
        """Emit the final validated config — exactly what ``demodsl run`` replays."""
        self._touch()
        steps = list(self._steps)
        if not steps or steps[0].action != "navigate":
            steps.insert(0, Step(action="navigate", url=self.url))
        return DemoConfig(
            metadata=Metadata(title=self.title),
            scenarios=[
                Scenario(
                    name=scenario_name,
                    url=self.url,
                    viewport=Viewport(width=self.viewport[0], height=self.viewport[1]),
                    steps=steps,
                )
            ],
        )

    # ── Internals ─────────────────────────────────────────────────────────

    def _current_url(self) -> str:
        try:
            return str(self._provider.evaluate_js("window.location.href"))
        except Exception:
            return self.url

    def _snapshot(self) -> dict[str, Any]:
        try:
            state = self._provider.evaluate_js(
                "({url: window.location.href, scroll_y: window.scrollY, scroll_x: window.scrollX})"
            )
        except Exception:
            state = {"url": self.url, "scroll_y": 0, "scroll_x": 0}
        return dict(state or {})

    def _restore(self, snapshot: dict[str, Any]) -> None:
        url = snapshot.get("url")
        if url and url != self._current_url():
            try:
                self._provider.navigate(url)
            except Exception:  # pragma: no cover - defensive
                logger.debug("Session %s: restore navigate failed", self.id, exc_info=True)
        try:
            self._provider.evaluate_js(
                f"window.scrollTo({int(snapshot.get('scroll_x', 0) or 0)},"
                f" {int(snapshot.get('scroll_y', 0) or 0)})"
            )
        except Exception:  # pragma: no cover - defensive
            logger.debug("Session %s: restore scroll failed", self.id, exc_info=True)

    def _cleanup_effects(self) -> None:
        try:
            self._provider.evaluate_js(_CLEANUP_EFFECTS_JS)
        except Exception:  # pragma: no cover - defensive
            logger.debug("Session %s: effect cleanup failed", self.id, exc_info=True)

    def _resolve(self, step: Step) -> dict[str, Any] | None:
        if step.locator is None:
            return None
        script = (
            f"{_RESOLVE_JS.strip()}"
            f"({json.dumps(step.locator.value)}, {json.dumps(step.locator.type)})"
        )
        try:
            return dict(self._provider.evaluate_js(script) or {})
        except Exception as exc:
            logger.debug("Session %s: locator probe failed: %s", self.id, exc)
            return {"matches": 0, "bbox": None, "visible": False, "error": str(exc)[:200]}

    def _anchor(self, resolved: dict[str, Any]) -> dict[str, float] | None:
        bbox = resolved.get("bbox")
        if not bbox:
            return None
        vw, vh = self.viewport
        return {
            "x": round(max(0.0, min(1.0, (bbox["x"] + bbox["w"] / 2) / vw)), 4),
            "y": round(max(0.0, min(1.0, (bbox["y"] + bbox["h"] / 2) / vh)), 4),
        }

    def _overlay_warnings(self, step: Step, resolved: dict[str, Any]) -> list[str]:
        """Flag effects that would be drawn partly outside the frame."""
        bbox = resolved.get("bbox")
        if not bbox or not step.effects:
            return []
        vw, vh = self.viewport
        out: list[str] = []
        for effect in step.effects:
            radius = float(getattr(effect, "radius", None) or 0.0) or (bbox["w"] / 2 + 22)
            left = bbox["x"] + bbox["w"] / 2 - radius
            right = bbox["x"] + bbox["w"] / 2 + radius
            if right > vw:
                out.append(f"{effect.type} extends {right - vw:.0f}px past the right edge")
            if left < 0:
                out.append(f"{effect.type} extends {-left:.0f}px past the left edge")
            if bbox["y"] < 0 or bbox["y"] + bbox["h"] > vh:
                out.append(f"{effect.type} target is outside the visible viewport")
        return out

    def _frame(self) -> str | None:
        if not self.include_frames:
            return None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = self._provider.screenshot(Path(tmp) / "frame.png")
                data = Path(path).read_bytes()
            return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
        except Exception:  # pragma: no cover - screenshots are best effort
            logger.debug("Session %s: frame capture failed", self.id, exc_info=True)
            return None


class SessionManager:
    """Registry of open sessions with a TTL and a hard cap on browsers."""

    def __init__(
        self,
        *,
        ttl: float = DEFAULT_TTL_SECONDS,
        max_sessions: int = MAX_OPEN_SESSIONS,
    ) -> None:
        self.ttl = ttl
        self.max_sessions = max_sessions
        self._sessions: dict[str, AuthoringSession] = {}

    def create(self, url: str, **kwargs: Any) -> AuthoringSession:
        self.reap()
        if len(self._sessions) >= self.max_sessions:
            raise RuntimeError(
                f"Too many open authoring sessions ({len(self._sessions)}/"
                f"{self.max_sessions}). Close one first."
            )
        kwargs.setdefault("ttl", self.ttl)
        session = AuthoringSession(url, **kwargs)
        session.open()
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> AuthoringSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown session {session_id!r}")
        if session.expired:
            self.destroy(session_id)
            raise SessionExpiredError(f"Session {session_id} expired")
        return session

    def destroy(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        session.close()
        return True

    def reap(self) -> int:
        """Close every expired session. Returns how many were reaped."""
        expired = [sid for sid, s in self._sessions.items() if s.expired]
        for sid in expired:
            self.destroy(sid)
        return len(expired)

    def __len__(self) -> int:
        return len(self._sessions)

    def close_all(self) -> None:
        for sid in list(self._sessions):
            self.destroy(sid)
