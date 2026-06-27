"""Synthesise a validated DemoConfig from a discovered trajectory.

The discovered :class:`~demodsl.discover.trajectory.Trajectory` maps almost
one-to-one onto DemoDSL :class:`~demodsl.models.Step` objects.  This module
assembles a plain YAML-shaped ``dict`` (so every model ``before`` validator and
shorthand runs exactly as it would when loading a file) and validates it by
constructing a :class:`~demodsl.models.DemoConfig`.

Authentication is first-class: when discovery ran against an authenticated
session the produced scenario carries the same ``provider`` +
:class:`~demodsl.models.BrowserAuthConfig`, and an optional ``oauth_login``
governance step can be prepended so the rendered demo reproduces the gated flow.
"""

from __future__ import annotations

from typing import Any

from demodsl.discover.actions import AgentAction
from demodsl.discover.trajectory import Trajectory
from demodsl.models import BrowserAuthConfig, DemoConfig, OAuthPolicy

# Effect presets the synthesizer attaches based on the policy's effect hint.
_EFFECT_PRESETS: dict[str, dict[str, Any]] = {
    "spotlight": {"type": "spotlight", "duration": 1.6, "intensity": 0.8},
    "highlight": {"type": "highlight", "duration": 1.4},
    "glow": {"type": "glow", "duration": 1.4},
}


def _locator_dict(action: AgentAction) -> dict[str, str] | None:
    if action.locator is None:
        return None
    return {"type": action.locator.type, "value": action.locator.value}


def _step_from_action(action: AgentAction, *, default_wait: float = 2.5) -> dict[str, Any] | None:
    """Translate one agent action into a DemoDSL step dict (or None to skip)."""
    narration = action.narration or _fallback_narration(action)
    base: dict[str, Any] = {"narration": narration, "wait": default_wait}

    if action.kind == "navigate" and action.url:
        return {"action": "navigate", "url": action.url, **base, "wait": 3.0}
    if action.kind == "click" and action.locator is not None:
        step = {"action": "click", "locator": _locator_dict(action), **base}
        if action.effect_hint in _EFFECT_PRESETS:
            step["effects"] = [dict(_EFFECT_PRESETS[action.effect_hint])]
        return step
    if action.kind == "type" and action.locator is not None:
        return {
            "action": "type",
            "locator": _locator_dict(action),
            "value": action.value or "",
            "char_rate": 18,
            **base,
        }
    if action.kind == "scroll":
        return {
            "action": "scroll",
            "direction": action.direction or "down",
            "pixels": action.pixels or 720,
            "smooth_scroll": True,
            **base,
        }
    if action.kind == "wait_for" and action.locator is not None:
        return {"action": "wait_for", "locator": _locator_dict(action), "timeout": 8.0, **base}
    if action.kind == "hover" and action.locator is not None:
        return {"action": "hover", "locator": _locator_dict(action), **base}
    if action.kind == "press_key" and action.key:
        return {"action": "press_key", "key": action.key, **base}
    return None  # "done" and under-specified actions are not emitted


def _fallback_narration(action: AgentAction) -> str:
    if action.kind == "navigate":
        return "Let's open the page."
    if action.kind == "click":
        return "Now I click here to reveal the feature."
    if action.kind == "type":
        return "I fill in the field."
    if action.kind == "scroll":
        return "Let's scroll down to see more."
    return "Continuing the walkthrough."


def _oauth_login_step(login: dict[str, Any]) -> dict[str, Any]:
    policy = OAuthPolicy(**login)  # validate the governance policy up front
    step: dict[str, Any] = {
        "action": "oauth_login",
        "oauth": policy.model_dump(exclude_none=True),
        "narration": "Signing in to reach the gated feature.",
        "timeout": 90.0,
    }
    return step


def build_config_dict(
    query: str,
    trajectory: Trajectory,
    *,
    provider: str = "playwright",
    auth: BrowserAuthConfig | None = None,
    login: dict[str, Any] | None = None,
    voice_engine: str = "gtts",
    voice_id: str = "en",
    title: str | None = None,
    filename: str = "discovered_demo.mp4",
    feature_reached: bool = True,
) -> dict[str, Any]:
    """Assemble the YAML-shaped config dict for *trajectory*.

    When ``feature_reached`` is ``False`` the discovery could not locate the
    requested feature, so the metadata and opening narration say so instead of
    pretending the walkthrough demonstrates it.
    """
    start_url = trajectory.start_url or _first_url(trajectory)
    steps: list[dict[str, Any]] = []

    # Only successful steps become demo steps: a failed/hallucinated action (e.g.
    # a rejected navigation to a non-existent page) must never be rendered.
    actions = trajectory.successful_actions
    open_narration = (
        f"Let's explore: {query}."
        if feature_reached
        else f"Opening the site — the requested feature ({query}) was not found."
    )
    if not (actions and actions[0].kind == "navigate"):
        if start_url:
            steps.append(
                {
                    "action": "navigate",
                    "url": start_url,
                    "narration": open_narration,
                    "wait": 3.0,
                }
            )

    if login:
        steps.append(_oauth_login_step(login))

    for action in actions:
        step = _step_from_action(action)
        if step is not None:
            steps.append(step)

    scenario: dict[str, Any] = {
        "name": f"Discovered: {query}"[:80],
        "url": start_url,
        "browser": "chrome",
        "provider": provider,
        "natural": True,
        "cursor": {"visible": True, "style": "dot", "color": "#6366F1", "click_effect": "ripple"},
        "steps": steps,
    }
    if auth is not None:
        scenario["auth"] = auth.model_dump(exclude_none=True)

    if feature_reached:
        default_title = f"Demo — {query}"
        description = f"Auto-discovered walkthrough for: {query}"
    else:
        default_title = f"Demo — {query} (feature not found)"
        description = (
            f"Auto-discovered walkthrough for: {query}. "
            "The requested feature could not be located on the site."
        )

    config: dict[str, Any] = {
        "metadata": {
            "title": title or default_title,
            "description": description,
            "version": "2.0.0",
        },
        "voice": {"engine": voice_engine, "voice_id": voice_id, "speed": 1.0},
        "subtitle": {"enabled": True, "style": "classic", "position": "bottom"},
        "scenarios": [scenario],
        "pipeline": [
            {"generate_narration": {}},
            {"edit_video": {}},
            {"burn_subtitles": {}},
        ],
        "output": {"filename": filename, "directory": "output/"},
    }
    return config


def synthesize_config(
    query: str,
    trajectory: Trajectory,
    *,
    provider: str = "playwright",
    auth: BrowserAuthConfig | None = None,
    login: dict[str, Any] | None = None,
    voice_engine: str = "gtts",
    voice_id: str = "en",
    title: str | None = None,
    filename: str = "discovered_demo.mp4",
    feature_reached: bool = True,
) -> tuple[DemoConfig, dict[str, Any]]:
    """Return ``(validated DemoConfig, raw dict)`` for *trajectory*.

    Raises :class:`pydantic.ValidationError` if the assembled config is invalid
    — by construction it should always validate.
    """
    data = build_config_dict(
        query,
        trajectory,
        provider=provider,
        auth=auth,
        login=login,
        voice_engine=voice_engine,
        voice_id=voice_id,
        title=title,
        filename=filename,
        feature_reached=feature_reached,
    )
    config = DemoConfig.model_validate(data)
    return config, data


def _first_url(trajectory: Trajectory) -> str:
    for step in trajectory.steps:
        if step.observation.url:
            return step.observation.url
    return ""
