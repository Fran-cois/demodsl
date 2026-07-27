"""OS-setup usage taxonomy for native mobile demos.

A *simplified vocabulary* that lets a demo author express an OS setup intent —
e.g. ``network.airplane_mode=on`` — instead of hand-writing the concrete
tap/swipe sequence needed to reach and toggle that setting in the device's
Settings app.

The vocabulary is a **dotted namespace** rooted at ``settings.`` (the prefix is
optional):

    settings.network.airplane_mode   → Airplane Mode toggle
    settings.display.dark_mode       → Light/Dark appearance
    settings.battery.low_power_mode  → Low Power / Battery Saver
    settings.general.about           → About screen

Each entry declares a *recipe* per platform (iOS / Android): an ordered list of
navigation hops (cells to open) plus a terminal *control* (a toggle switch, a
segmented choice, or simply a screen to reveal). The recipes are resolved at
**runtime** by :class:`demodsl.commands.OsSettingCommand`, which reads the live
switch state so toggles are idempotent.

Assumption: the demo's ``mobile`` app is the OS Settings app
(``bundle_id: com.apple.Preferences`` on iOS, ``app_package: com.android.settings``
on Android). Navigation labels default to **English**; on a localised device pass
the localised label via the ``labels`` override (see :func:`resolve_recipe`).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Literal

Platform = Literal["ios", "android"]
ControlKind = Literal["toggle", "open", "choice"]

# Value tokens accepted for boolean settings.
_TRUE_TOKENS = frozenset({"on", "true", "1", "yes", "enable", "enabled"})
_FALSE_TOKENS = frozenset({"off", "false", "0", "no", "disable", "disabled"})


# ── Locator dict builders (DSL Locator shape) ────────────────────────────────


def _aid(value: str) -> dict[str, str]:
    """Accessibility id — stable cross-platform identifier."""
    return {"type": "accessibility_id", "value": value}


def _text(value: str) -> dict[str, str]:
    """Visible text / content-desc (converted to a safe XPath by the provider)."""
    return {"type": "text", "value": value}


def _xpath(value: str) -> dict[str, str]:
    return {"type": "xpath", "value": value}


# ── Recipe data model ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Control:
    """The terminal control acted upon once navigation is complete."""

    kind: ControlKind
    # toggle / open target locator (None for pure choice controls)
    locator: dict[str, str] | None = None
    # For toggles: the element attribute holding the current on/off state and
    # the raw attribute values that mean "on". Enables idempotent toggling.
    state_attr: str | None = None
    on_values: tuple[str, ...] = ("1", "true", "on")
    # For choice controls: value token → locator to tap (e.g. on→Dark, off→Light)
    choices: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class Recipe:
    """A per-platform navigation path plus its terminal control."""

    # Ordered navigation hops: each locator is waited-for then tapped.
    path: tuple[dict[str, str], ...]
    control: Control


@dataclass(frozen=True)
class OsSetting:
    """A single entry in the OS usage taxonomy."""

    key: str  # e.g. "network.airplane_mode"
    title: str  # human label, e.g. "Airplane Mode"
    kind: ControlKind  # toggle | open | choice
    description: str = ""
    ios: Recipe | None = None
    android: Recipe | None = None

    def recipe_for(self, platform: Platform) -> Recipe | None:
        return self.ios if platform == "ios" else self.android


# ── Taxonomy registry ────────────────────────────────────────────────────────
# English labels by default; airplane_mode's iOS control is locale-independent
# (first switch on the root screen) so it works on any language.

OS_TAXONOMY: dict[str, OsSetting] = {
    # ── Network ──────────────────────────────────────────────────────────────
    "network.airplane_mode": OsSetting(
        key="network.airplane_mode",
        title="Airplane Mode",
        kind="toggle",
        description="Enable/disable all radios (cellular, Wi-Fi, Bluetooth).",
        ios=Recipe(
            path=(),
            control=Control(
                kind="toggle",
                locator=_xpath("(//XCUIElementTypeSwitch)[1]"),
                state_attr="value",
            ),
        ),
        android=Recipe(
            path=(_text("Network & internet"),),
            control=Control(kind="toggle", locator=_text("Airplane mode")),
        ),
    ),
    "network.wifi": OsSetting(
        key="network.wifi",
        title="Wi-Fi",
        kind="open",
        description="Open the Wi-Fi settings screen.",
        ios=Recipe(path=(), control=Control(kind="open", locator=_aid("Wi-Fi"))),
        android=Recipe(
            path=(_text("Network & internet"),),
            control=Control(kind="open", locator=_text("Internet")),
        ),
    ),
    "network.bluetooth": OsSetting(
        key="network.bluetooth",
        title="Bluetooth",
        kind="open",
        description="Open the Bluetooth settings screen.",
        ios=Recipe(path=(), control=Control(kind="open", locator=_aid("Bluetooth"))),
        android=Recipe(
            path=(_text("Connected devices"),),
            control=Control(kind="open", locator=_text("Connection preferences")),
        ),
    ),
    "network.cellular": OsSetting(
        key="network.cellular",
        title="Cellular / Mobile data",
        kind="open",
        description="Open the cellular / mobile-data settings screen.",
        ios=Recipe(path=(), control=Control(kind="open", locator=_aid("Cellular"))),
        android=Recipe(
            path=(_text("Network & internet"),),
            control=Control(kind="open", locator=_text("SIMs")),
        ),
    ),
    "network.hotspot": OsSetting(
        key="network.hotspot",
        title="Personal Hotspot",
        kind="open",
        description="Open the personal-hotspot / tethering screen.",
        ios=Recipe(path=(), control=Control(kind="open", locator=_aid("Personal Hotspot"))),
        android=Recipe(
            path=(_text("Network & internet"),),
            control=Control(kind="open", locator=_text("Hotspot & tethering")),
        ),
    ),
    "network.vpn": OsSetting(
        key="network.vpn",
        title="VPN",
        kind="open",
        description="Open the VPN configuration screen.",
        ios=Recipe(
            path=(_aid("General"),),
            control=Control(kind="open", locator=_aid("VPN & Device Management")),
        ),
        android=Recipe(
            path=(_text("Network & internet"),),
            control=Control(kind="open", locator=_text("VPN")),
        ),
    ),
    # ── Display ──────────────────────────────────────────────────────────────
    "display.dark_mode": OsSetting(
        key="display.dark_mode",
        title="Dark Mode",
        kind="choice",
        description="Switch the system appearance between Light and Dark.",
        ios=Recipe(
            path=(_aid("Display & Brightness"),),
            control=Control(
                kind="choice",
                choices={"on": _aid("Dark"), "off": _aid("Light")},
            ),
        ),
        android=Recipe(
            path=(_text("Display"),),
            control=Control(kind="toggle", locator=_text("Dark theme")),
        ),
    ),
    "display.brightness": OsSetting(
        key="display.brightness",
        title="Brightness",
        kind="open",
        description="Open the display & brightness screen.",
        ios=Recipe(path=(), control=Control(kind="open", locator=_aid("Display & Brightness"))),
        android=Recipe(path=(), control=Control(kind="open", locator=_text("Display"))),
    ),
    "display.text_size": OsSetting(
        key="display.text_size",
        title="Text Size",
        kind="open",
        description="Open the text-size / font-size screen.",
        ios=Recipe(
            path=(_aid("Display & Brightness"),),
            control=Control(kind="open", locator=_aid("Text Size")),
        ),
        android=Recipe(
            path=(_text("Display"),),
            control=Control(kind="open", locator=_text("Display size and text")),
        ),
    ),
    # ── Sound ────────────────────────────────────────────────────────────────
    "sound.settings": OsSetting(
        key="sound.settings",
        title="Sounds & Haptics",
        kind="open",
        description="Open the sound / haptics screen.",
        ios=Recipe(path=(), control=Control(kind="open", locator=_aid("Sounds & Haptics"))),
        android=Recipe(path=(), control=Control(kind="open", locator=_text("Sound & vibration"))),
    ),
    # ── Battery ──────────────────────────────────────────────────────────────
    "battery.low_power_mode": OsSetting(
        key="battery.low_power_mode",
        title="Low Power Mode",
        kind="toggle",
        description="Enable/disable Low Power Mode (iOS) / Battery Saver (Android).",
        ios=Recipe(
            path=(_aid("Battery"),),
            control=Control(kind="toggle", locator=_aid("Low Power Mode"), state_attr="value"),
        ),
        android=Recipe(
            path=(_text("Battery"),),
            control=Control(kind="open", locator=_text("Battery Saver")),
        ),
    ),
    "battery.settings": OsSetting(
        key="battery.settings",
        title="Battery",
        kind="open",
        description="Open the battery screen.",
        ios=Recipe(path=(), control=Control(kind="open", locator=_aid("Battery"))),
        android=Recipe(path=(), control=Control(kind="open", locator=_text("Battery"))),
    ),
    # ── Focus / Do Not Disturb ───────────────────────────────────────────────
    "focus.do_not_disturb": OsSetting(
        key="focus.do_not_disturb",
        title="Do Not Disturb / Focus",
        kind="open",
        description="Open the Focus / Do-Not-Disturb screen.",
        ios=Recipe(path=(), control=Control(kind="open", locator=_aid("Focus"))),
        android=Recipe(
            path=(_text("Notifications"),),
            control=Control(kind="open", locator=_text("Do Not Disturb")),
        ),
    ),
    # ── Notifications ────────────────────────────────────────────────────────
    "notifications.settings": OsSetting(
        key="notifications.settings",
        title="Notifications",
        kind="open",
        description="Open the notifications screen.",
        ios=Recipe(path=(), control=Control(kind="open", locator=_aid("Notifications"))),
        android=Recipe(path=(), control=Control(kind="open", locator=_text("Notifications"))),
    ),
    # ── Privacy ──────────────────────────────────────────────────────────────
    "privacy.settings": OsSetting(
        key="privacy.settings",
        title="Privacy & Security",
        kind="open",
        description="Open the privacy & security screen.",
        ios=Recipe(path=(), control=Control(kind="open", locator=_aid("Privacy & Security"))),
        android=Recipe(path=(), control=Control(kind="open", locator=_text("Security & privacy"))),
    ),
    "privacy.location": OsSetting(
        key="privacy.location",
        title="Location Services",
        kind="open",
        description="Open the location-services screen.",
        ios=Recipe(
            path=(_aid("Privacy & Security"),),
            control=Control(kind="open", locator=_aid("Location Services")),
        ),
        android=Recipe(
            path=(_text("Location"),),
            control=Control(kind="open", locator=_text("Location services")),
        ),
    ),
    # ── Accessibility ────────────────────────────────────────────────────────
    "accessibility.settings": OsSetting(
        key="accessibility.settings",
        title="Accessibility",
        kind="open",
        description="Open the accessibility screen.",
        ios=Recipe(path=(), control=Control(kind="open", locator=_aid("Accessibility"))),
        android=Recipe(path=(), control=Control(kind="open", locator=_text("Accessibility"))),
    ),
    # ── General / System ─────────────────────────────────────────────────────
    "general.about": OsSetting(
        key="general.about",
        title="About",
        kind="open",
        description="Open the About screen.",
        ios=Recipe(
            path=(_aid("General"),),
            control=Control(kind="open", locator=_aid("About")),
        ),
        android=Recipe(
            path=(_text("About phone"),),
            control=Control(kind="open", locator=_text("About phone")),
        ),
    ),
    "general.software_update": OsSetting(
        key="general.software_update",
        title="Software Update",
        kind="open",
        description="Open the software-update screen.",
        ios=Recipe(
            path=(_aid("General"),),
            control=Control(kind="open", locator=_aid("Software Update")),
        ),
        android=Recipe(
            path=(_text("System"),),
            control=Control(kind="open", locator=_text("System update")),
        ),
    ),
}


# ── Public helpers ───────────────────────────────────────────────────────────


def parse_setting_expr(expr: str) -> tuple[str, str | None]:
    """Parse ``"network.airplane_mode=on"`` → ``("network.airplane_mode", "on")``.

    The leading ``settings.`` namespace is optional and stripped. A bare key
    without ``=`` (e.g. ``"general.about"``) returns ``(key, None)``.
    """
    if not isinstance(expr, str) or not expr.strip():
        raise ValueError("os setting expression must be a non-empty string")
    key_part, sep, value_part = expr.strip().partition("=")
    key = key_part.strip()
    if key.startswith("settings."):
        key = key[len("settings.") :]
    value = value_part.strip() if sep else None
    return key, (value or None)


def normalise_bool(value: str | None) -> bool:
    """Map a value token to a boolean. ``None`` defaults to *on* (enable)."""
    if value is None:
        return True
    token = str(value).strip().lower()
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    raise ValueError(
        f"Invalid boolean value {value!r}. Use one of: "
        f"{', '.join(sorted(_TRUE_TOKENS | _FALSE_TOKENS))}."
    )


def get_setting(key: str) -> OsSetting:
    """Look up a taxonomy entry, raising a helpful error with suggestions."""
    if key.startswith("settings."):
        key = key[len("settings.") :]
    spec = OS_TAXONOMY.get(key)
    if spec is None:
        close = difflib.get_close_matches(key, OS_TAXONOMY.keys(), n=3, cutoff=0.4)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise KeyError(
            f"Unknown OS setting {key!r}. Run 'demodsl os-settings' to list the vocabulary.{hint}"
        )
    return spec


def list_settings() -> list[str]:
    """All setting keys, sorted."""
    return sorted(OS_TAXONOMY.keys())


def resolve_recipe(
    key: str,
    platform: Platform,
    *,
    labels: dict[str, dict[str, str]] | None = None,
) -> Recipe:
    """Return the platform recipe for *key*.

    *labels* optionally overrides a navigation-hop or control locator by the
    canonical accessibility-id/text value, so localised devices can supply their
    own labels without redefining the taxonomy, e.g.
    ``labels={"General": {"type": "text", "value": "Général"}}``.
    """
    spec = get_setting(key)
    recipe = spec.recipe_for(platform)
    if recipe is None:
        raise ValueError(f"OS setting {spec.key!r} has no recipe for platform {platform!r}.")
    if not labels:
        return recipe

    def _swap(loc: dict[str, str] | None) -> dict[str, str] | None:
        if loc is None:
            return None
        return labels.get(loc.get("value", ""), loc)

    new_path = tuple(_swap(hop) or hop for hop in recipe.path)
    ctrl = recipe.control
    new_ctrl = Control(
        kind=ctrl.kind,
        locator=_swap(ctrl.locator),
        state_attr=ctrl.state_attr,
        on_values=ctrl.on_values,
        choices={k: (_swap(v) or v) for k, v in ctrl.choices.items()},
    )
    return Recipe(path=new_path, control=new_ctrl)


def default_narration(key: str, value: str | None) -> str:
    """A human-readable narration line for an OS setting intent."""
    spec = get_setting(key)
    if spec.kind == "open":
        return f"Opening {spec.title} settings."
    state = "on" if normalise_bool(value) else "off"
    return f"Turning {spec.title} {state}."
