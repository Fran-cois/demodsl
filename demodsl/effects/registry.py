"""Effect registry — Strategy pattern for visual effects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BrowserEffect(ABC):
    """An effect applied in real-time by injecting JS into the page."""

    @abstractmethod
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        """Inject JS/CSS into the browser page."""


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

    def register_browser(self, name: str, effect: BrowserEffect) -> None:
        self._browser[name] = effect

    def register_post(self, name: str, effect: PostEffect) -> None:
        self._post[name] = effect

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
