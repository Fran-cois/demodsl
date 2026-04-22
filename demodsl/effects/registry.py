"""Effect registry — Strategy pattern for visual effects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from demodsl.effects.js_builder import cleanup_all_js, cleanup_js


class BrowserEffect(ABC):
    """An effect applied in real-time by injecting JS into the page.

    Subclasses **must** set :attr:`effect_id` to a unique short name
    (e.g. ``"spotlight"``).  The default :meth:`cleanup` implementation
    removes all DOM artefacts whose id starts with ``__demodsl_{effect_id}``.
    """

    effect_id: str = ""

    @abstractmethod
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        """Inject JS/CSS into the browser page."""

    def cleanup(self, evaluate_js: Any) -> None:
        """Remove all DOM artefacts injected by this effect."""
        if self.effect_id:
            evaluate_js(cleanup_js(self.effect_id))


class PostEffect(ABC):
    """An effect applied during post-processing on a video clip."""

    @abstractmethod
    def apply(self, clip: Any, params: dict[str, Any]) -> Any:
        """Apply effect to a MoviePy VideoClip and return the modified clip."""


class EffectRegistry:
    """Dual registry: browser effects (JS injection) + post-processing effects."""

    def __init__(self) -> None:
        self._browser: dict[str, BrowserEffect] = {}
        self._post: dict[str, PostEffect] = {}

    # ── Registration ──────────────────────────────────────────────────────

    def register_browser(self, name: str, effect: BrowserEffect) -> None:
        self._browser[name] = effect

    def register_post(self, name: str, effect: PostEffect) -> None:
        self._post[name] = effect

    # ── Lookup ────────────────────────────────────────────────────────────

    def is_browser_effect(self, name: str) -> bool:
        return name in self._browser

    def is_post_effect(self, name: str) -> bool:
        return name in self._post

    def get_browser_effect(self, name: str) -> BrowserEffect:
        if name not in self._browser:
            raise KeyError(f"Unknown browser effect '{name}'")
        return self._browser[name]

    def get_post_effect(self, name: str) -> PostEffect:
        if name not in self._post:
            raise KeyError(f"Unknown post effect '{name}'")
        return self._post[name]

    @property
    def browser_effects(self) -> list[str]:
        return list(self._browser)

    @property
    def post_effects(self) -> list[str]:
        return list(self._post)

    # ── Combo support ─────────────────────────────────────────────────────

    def inject_combo(
        self,
        effects: list[tuple[str, dict[str, Any]]],
        evaluate_js: Any,
    ) -> list[str]:
        """Inject multiple browser effects at once (combo).

        *effects* is a list of ``(effect_name, params)`` tuples.
        Returns the list of effect names that were successfully injected.
        """
        injected: list[str] = []
        for name, params in effects:
            if name in self._browser:
                self._browser[name].inject(evaluate_js, params)
                injected.append(name)
        return injected

    def cleanup_effect(self, name: str, evaluate_js: Any) -> None:
        """Clean up a single browser effect by name."""
        if name in self._browser:
            self._browser[name].cleanup(evaluate_js)

    def cleanup_effects(self, names: list[str], evaluate_js: Any) -> None:
        """Clean up several browser effects by name."""
        for name in names:
            self.cleanup_effect(name, evaluate_js)

    def cleanup_all_browser(self, evaluate_js: Any) -> None:
        """Remove **all** DemoDSL effect artefacts from the page."""
        evaluate_js(cleanup_all_js())
