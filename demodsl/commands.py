"""Command pattern for browser actions."""

from __future__ import annotations

import difflib
import json
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from demodsl.models import Step
from demodsl.providers.base import BrowserProvider, MobileProvider
from demodsl.validators import _validate_url

logger = logging.getLogger(__name__)


class BrowserCommand(ABC):
    """Base class for all browser action commands."""

    @abstractmethod
    def execute(self, browser: BrowserProvider, step: Step) -> Any:
        """Execute the action against the browser."""

    @abstractmethod
    def describe(self, step: Step) -> str:
        """Human-readable description (used for dry-run logging)."""


class NavigateCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if step.url is None:
            raise ValueError("NavigateCommand requires 'url'")
        _validate_url(step.url)
        browser.navigate(step.url)

    def describe(self, step: Step) -> str:
        return f"Navigate to {step.url}"


class ClickCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if step.locator is None:
            raise ValueError("ClickCommand requires 'locator'")
        browser.click(step.locator)

    def describe(self, step: Step) -> str:
        loc = step.locator
        return f"Click on [{loc.type}] {loc.value}" if loc else "Click (no locator)"


class TypeCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if step.locator is None or step.value is None:
            raise ValueError("TypeCommand requires 'locator' and 'value'")
        if step.char_rate is not None:
            browser.type_text_organic(
                step.locator,
                step.value,
                step.char_rate,
                variance=step.typing_variance or 0.0,
            )
        else:
            browser.type_text(step.locator, step.value)

    def describe(self, step: Step) -> str:
        loc = step.locator
        target = f"[{loc.type}] {loc.value}" if loc else "?"
        rate = f" @{step.char_rate}ch/s" if step.char_rate else ""
        return f"Type '{step.value}' into {target}{rate}"


class ScrollCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        direction = step.direction or "down"
        pixels = step.pixels or 300
        browser.scroll(direction, pixels, smooth=bool(step.smooth_scroll))

    def describe(self, step: Step) -> str:
        smooth = " (smooth)" if step.smooth_scroll else ""
        return f"Scroll {step.direction or 'down'} {step.pixels or 300}px{smooth}"


class PauseCommand(BrowserCommand):
    """No-op action — holds the current page without scrolling."""

    def execute(self, browser: BrowserProvider, step: Step) -> None:
        pass  # intentionally does nothing

    def describe(self, step: Step) -> str:
        return "Pause (no action)"


class WaitForCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if step.locator is None:
            raise ValueError("WaitForCommand requires 'locator'")
        timeout = step.timeout or 5.0
        browser.wait_for(step.locator, timeout)

    def describe(self, step: Step) -> str:
        loc = step.locator
        target = f"[{loc.type}] {loc.value}" if loc else "?"
        return f"Wait for {target} (timeout={step.timeout or 5.0}s)"


class ScreenshotCommand(BrowserCommand):
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def execute(self, browser: BrowserProvider, step: Step) -> Path:
        filename = step.filename or "screenshot.png"
        path = self._output_dir / filename
        return browser.screenshot(path)

    def describe(self, step: Step) -> str:
        return f"Screenshot → {step.filename or 'screenshot.png'}"


class ShortcutCommand(BrowserCommand):
    """Execute a keyboard shortcut and display an overlay badge."""

    # Display duration for the shortcut badge (seconds)
    _DISPLAY_SECONDS = 1.5

    @staticmethod
    def _format_label(keys: str) -> str:
        """Convert Playwright-style keys ('Meta+f') to display label ('⌘ F')."""
        _SYMBOLS = {
            "Meta": "⌘",
            "Command": "⌘",
            "Control": "Ctrl",
            "Shift": "⇧",
            "Alt": "⌥",
            "Option": "⌥",
            "Enter": "↵",
            "Escape": "Esc",
            "Backspace": "⌫",
            "Delete": "⌦",
            "Tab": "⇥",
            "ArrowUp": "↑",
            "ArrowDown": "↓",
            "ArrowLeft": "←",
            "ArrowRight": "→",
        }
        parts = keys.split("+")
        return " ".join(_SYMBOLS.get(p, p.upper()) for p in parts)

    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if not step.keys:
            raise ValueError("ShortcutCommand requires 'keys'")
        label = self._format_label(step.keys)
        # Inject the visual overlay *before* pressing so it's visible on camera
        browser.evaluate_js(self._overlay_js(label, self._DISPLAY_SECONDS))
        import time

        time.sleep(0.15)  # brief pause so overlay is rendered before key press
        browser.press_keys(step.keys)

    def describe(self, step: Step) -> str:
        return f"Shortcut {step.keys}"

    @staticmethod
    def _overlay_js(label: str, duration: float) -> str:
        # json.dumps yields a properly-quoted JS string literal — safe
        # against quote/backslash/newline injection from scenario YAML.
        # ensure_ascii=False keeps Unicode (⌘, emoji…) human-readable.
        safe_label = json.dumps(label, ensure_ascii=False)
        ms = int(duration * 1000)
        return f"""
        (() => {{
            const existing = document.getElementById('__demodsl_shortcut');
            if (existing) existing.remove();
            const badge = document.createElement('div');
            badge.id = '__demodsl_shortcut';
            badge.style.cssText = `
                position: fixed;
                bottom: 48px;
                left: 50%;
                transform: translateX(-50%) scale(0.85);
                display: inline-flex;
                gap: 6px;
                padding: 10px 22px;
                background: rgba(24, 24, 27, 0.88);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.35);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 18px;
                font-weight: 600;
                letter-spacing: 0.04em;
                color: #f4f4f5;
                z-index: 999999;
                pointer-events: none;
                opacity: 0;
                transition: opacity 0.25s ease, transform 0.25s ease;
            `;
            const parts = {safe_label}.split(' ');
            parts.forEach((part, i) => {{
                const key = document.createElement('span');
                key.textContent = part;
                key.style.cssText = `
                    display: inline-block;
                    padding: 4px 10px;
                    background: rgba(255,255,255,0.10);
                    border: 1px solid rgba(255,255,255,0.18);
                    border-radius: 7px;
                    font-size: 16px;
                    line-height: 1.3;
                    min-width: 28px;
                    text-align: center;
                `;
                badge.appendChild(key);
            }});
            document.body.appendChild(badge);
            requestAnimationFrame(() => {{
                badge.style.opacity = '1';
                badge.style.transform = 'translateX(-50%) scale(1)';
            }});
            setTimeout(() => {{
                badge.style.opacity = '0';
                badge.style.transform = 'translateX(-50%) scale(0.85)';
                setTimeout(() => badge.remove(), 350);
            }}, {ms});
        }})()
        """


# ── Command Registry ─────────────────────────────────────────────────────────


class HoverCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if step.locator is None:
            raise ValueError("HoverCommand requires 'locator'")
        browser.hover(step.locator)

    def describe(self, step: Step) -> str:
        loc = step.locator
        return f"Hover over [{loc.type}] {loc.value}" if loc else "Hover (no locator)"


class DragCommand(BrowserCommand):
    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if step.locator is None:
            raise ValueError("DragCommand requires 'locator' (source)")
        browser.drag_and_drop(
            step.locator,
            target=step.target_locator,
            target_x=step.end_x,
            target_y=step.end_y,
        )

    def describe(self, step: Step) -> str:
        src = f"[{step.locator.type}]{step.locator.value}" if step.locator else "?"
        if step.target_locator:
            tgt = f"[{step.target_locator.type}]{step.target_locator.value}"
        elif step.end_x is not None and step.end_y is not None:
            tgt = f"({step.end_x},{step.end_y})"
        else:
            tgt = "?"
        return f"Drag {src} → {tgt}"


class PressKeyCommand(BrowserCommand):
    """Press a single key (Enter, Escape, Tab, ArrowDown, etc.)."""

    def execute(self, browser: BrowserProvider, step: Step) -> None:
        if not step.key:
            raise ValueError("PressKeyCommand requires 'key'")
        browser.press_keys(step.key)

    def describe(self, step: Step) -> str:
        return f"Press key '{step.key}'"


# ── Virtual camera ───────────────────────────────────────────────────────────


_CAMERA_BOOTSTRAP_JS = r"""
(function () {
  if (window.__demodslCamera) return;
  const html = document.documentElement;
  // Preserve existing transform-origin / transform so we can restore on reset.
  const prev = {
    origin: html.style.transformOrigin,
    transform: html.style.transform,
    transition: html.style.transition,
    overflow: html.style.overflow,
  };
  // Prevent the page from growing a scrollbar when we zoom in (transform
  // doesn't change layout, but some pages animate body padding on resize).
  html.style.overflow = html.style.overflow || "hidden";
  window.__demodslCamera = {
    prev: prev,
    state: { zoom: 1, ox: 0, oy: 0, panX: 0, panY: 0, rot: 0 },
    apply: function (next, durationMs, ease) {
      const s = Object.assign({}, this.state, next);
      this.state = s;
      const html = document.documentElement;
      html.style.transformOrigin = s.ox + "px " + s.oy + "px";
      html.style.transition =
        "transform " + Math.max(0, durationMs) + "ms " + (ease || "ease-in-out");
      html.style.transform =
        "translate(" + s.panX + "px, " + s.panY + "px) " +
        "scale(" + s.zoom + ") " +
        "rotate(" + s.rot + "deg)";
    },
    reset: function (durationMs, ease) {
      this.state = { zoom: 1, ox: 0, oy: 0, panX: 0, panY: 0, rot: 0 };
      const html = document.documentElement;
      html.style.transition =
        "transform " + Math.max(0, durationMs) + "ms " + (ease || "ease-in-out");
      html.style.transform = "translate(0,0) scale(1) rotate(0deg)";
    },
    resolveLocator: function (sel) {
      let el = null;
      try { el = document.querySelector(sel); } catch (e) { el = null; }
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    },
  };
})();
"""


def _camera_locator_to_css(loc: Any) -> str | None:
    """Best-effort conversion of a Locator into a CSS selector for in-page JS."""
    if loc is None:
        return None
    if loc.type == "css":
        return loc.value
    if loc.type == "id":
        # Escape any embedded quotes — id values are rarely exotic in practice.
        return f"#{loc.value}"
    if loc.type == "text":
        # Best-effort: cannot use :has-text in vanilla CSS, fall back to None.
        # Camera supports normalized targets / locators of type css|id only.
        return None
    if loc.type == "xpath":
        return None
    return None


class CameraCommand(BrowserCommand):
    """Animate the virtual camera (zoom / pan / rotate) on the recorded page.

    Works by injecting a small JS controller that mutates the CSS
    ``transform`` of ``<html>``. The transition is recorded by the browser
    video capture so no post-processing is needed.
    """

    def execute(self, browser: BrowserProvider, step: Step) -> None:
        # ``camera_reset`` action does not require step.camera — synthesize one.
        if step.action == "camera_reset":
            move = step.camera
            if move is None:
                from demodsl.models import CameraMove

                move = CameraMove(reset=True)
        else:
            if step.camera is None:
                raise ValueError("CameraCommand requires 'camera' field")
            move = step.camera

        browser.evaluate_js(_CAMERA_BOOTSTRAP_JS)

        duration_ms = int(round(move.duration * 1000))
        ease = "cubic-bezier(.34,1.56,.64,1)" if move.ease == "spring" else move.ease

        if move.reset:
            browser.evaluate_js(f"window.__demodslCamera.reset({duration_ms}, {json.dumps(ease)});")
        else:
            # Resolve focus point in page-pixel coords.
            origin_js = "null"
            target_css = _camera_locator_to_css(move.target)
            if target_css is not None:
                origin_js = f"window.__demodslCamera.resolveLocator({json.dumps(target_css)})"
            elif move.target_x is not None or move.target_y is not None:
                tx = move.target_x if move.target_x is not None else 0.5
                ty = move.target_y if move.target_y is not None else 0.5
                origin_js = (
                    "(function(){"
                    "var w=window.innerWidth, h=window.innerHeight;"
                    f"return {{x: w * {tx}, y: h * {ty}}};"
                    "})()"
                )

            zoom = move.zoom if move.zoom is not None else "null"
            pan_x = move.pan_x if move.pan_x is not None else "null"
            pan_y = move.pan_y if move.pan_y is not None else "null"
            rot = move.rotation if move.rotation is not None else "null"

            script = (
                "(function(){"
                f"var origin = {origin_js};"
                "var cam = window.__demodslCamera;"
                "var next = {};"
                "if (origin) { next.ox = origin.x; next.oy = origin.y; }"
                f"var z = {zoom}; if (z !== null) next.zoom = z;"
                f"var px = {pan_x}; if (px !== null) next.panX = px;"
                f"var py = {pan_y}; if (py !== null) next.panY = py;"
                f"var r = {rot}; if (r !== null) next.rot = r;"
                f"cam.apply(next, {duration_ms}, {json.dumps(ease)});"
                "})();"
            )
            browser.evaluate_js(script)

        # Block until the transition + optional hold complete so the recorded
        # video captures the full move.
        import time as _time

        _time.sleep(move.duration + move.hold)

    def describe(self, step: Step) -> str:
        m = step.camera
        if step.action == "camera_reset" or (m is not None and m.reset):
            return "Camera reset"
        if m is None:
            return "Camera (no move)"
        parts: list[str] = []
        if m.zoom is not None:
            parts.append(f"zoom={m.zoom}")
        if m.target is not None:
            parts.append(f"target=[{m.target.type}]{m.target.value}")
        elif m.target_x is not None or m.target_y is not None:
            parts.append(f"focus=({m.target_x},{m.target_y})")
        if m.pan_x or m.pan_y:
            parts.append(f"pan=({m.pan_x or 0},{m.pan_y or 0})")
        if m.rotation:
            parts.append(f"rot={m.rotation}°")
        return "Camera " + ", ".join(parts) + f" ({m.duration}s {m.ease})"


class EmailVerifyCommand(BrowserCommand):
    """Wait for a registration/validation email and act on it.

    Connects to the scenario's IMAP mailbox, waits for the newest message
    matching the (optional) subject/from filters, then either:
      - ``email_extract='link'`` (default): follows the confirmation link by
        navigating the recorded browser to it; or
      - ``email_extract='code'``: types the verification code into ``locator``.

    Mailbox credentials come from the scenario ``mailbox:`` block with a
    ``DEMODSL_IMAP_*`` env fallback (see demodsl.mailbox.resolve_mailbox_config).
    The poll budget is ``step.timeout`` seconds (default 60).
    """

    def __init__(self, mailbox: dict | None = None) -> None:
        self._mailbox = mailbox

    def execute(self, browser: BrowserProvider, step: Step) -> str | None:
        from demodsl.mailbox import (
            MailboxClient,
            extract_code,
            extract_link,
            message_text,
            resolve_mailbox_config,
        )

        cfg = resolve_mailbox_config(self._mailbox)
        timeout = step.timeout if step.timeout is not None else 60.0
        extract = step.email_extract or "link"

        logger.info(
            "await_email: waiting up to %.0fs for email (subject~%r, from~%r) -> %s",
            timeout,
            step.email_subject,
            step.email_from,
            extract,
        )

        with MailboxClient(**cfg) as mailbox:
            msg = mailbox.wait_for_message(
                subject_contains=step.email_subject,
                from_contains=step.email_from,
                timeout=timeout,
            )

        body = message_text(msg)

        if extract == "code":
            code = extract_code(body, step.email_code_pattern)
            if not code:
                raise RuntimeError(
                    "await_email: no verification code found in the email "
                    f"(pattern={step.email_code_pattern or 'default 4-8 digits'})."
                )
            if step.locator is None:  # guarded at parse time, defensive here
                raise ValueError("await_email email_extract='code' requires 'locator'")
            logger.info("await_email: filling verification code into target field")
            browser.type_text(step.locator, code)
            return code

        link = extract_link(body, step.email_link_contains)
        if not link:
            raise RuntimeError(
                "await_email: no confirmation link found in the email "
                f"(link_contains={step.email_link_contains!r})."
            )
        _validate_url(link)
        logger.info("await_email: following confirmation link")
        browser.navigate(link)
        return link

    def describe(self, step: Step) -> str:
        what = step.email_extract or "link"
        filt = []
        if step.email_subject:
            filt.append(f"subject~{step.email_subject!r}")
        if step.email_from:
            filt.append(f"from~{step.email_from!r}")
        suffix = (" " + ", ".join(filt)) if filt else ""
        return f"Await validation email, extract {what}{suffix}"


class OAuthLoginCommand(BrowserCommand):
    """Drive a *"Sign in with Google/Microsoft/GitHub"* flow robustly.

    Instead of hard-coded ``click; sleep`` steps (which break whenever the
    provider reorders a screen), this runs a small state machine: it probes
    the page read-only, classifies the current screen (account chooser /
    credentials / 2FA / consent / redirect) and reacts according to the
    scenario's :class:`~demodsl.models.OAuthPolicy`.

    Governance is enforced on the **consent** screen: the requested
    permissions are checked against ``allowed_scopes`` / ``denied_scopes``
    *before* the approve button is clicked. Passwords are never auto-typed —
    the identity comes from the saved session (``demodsl setup-login``).

    Usage in YAML::

        - action: oauth_login
          locator: { type: text, value: "Continue with Google" }
          timeout: 120
          oauth:
            provider: google
            account_email: me@example.com
            success_host: app.acme.com
            denied_scopes: ["Drive", "delete", "manage your contacts"]
    """

    def execute(self, browser: BrowserProvider, step: Step) -> str:
        import time

        from demodsl.models import OAuthPolicy
        from demodsl.oauth import (
            OAuthGovernanceError,
            check_scopes,
            click_account_js,
            click_consent_js,
            probe_js,
            resolve_provider_profile,
        )

        policy = step.oauth or OAuthPolicy()
        profile = resolve_provider_profile(policy.provider)
        timeout = step.timeout if step.timeout is not None else 120.0
        poll = policy.poll

        # The SaaS host we expect to land back on. Captured before starting the
        # flow unless the policy pins it explicitly.
        success_host = policy.success_host
        if not success_host:
            success_host = (browser.evaluate_js("location.hostname") or "").strip()
        logger.info(
            "oauth_login: provider=%s success_host=%r account=%r (timeout=%.0fs)",
            policy.provider,
            success_host,
            policy.account_email,
            timeout,
        )

        # Kick off the flow by clicking the social button, if provided.
        if step.locator is not None:
            browser.click(step.locator)

        probe = probe_js(profile, success_host, policy.account_email)
        account_clicks = 0
        deadline = time.monotonic() + timeout
        last_state: str | None = None

        while time.monotonic() < deadline:
            info = browser.evaluate_js(probe) or {}
            state = info.get("state", "waiting")
            url = info.get("url", "")
            if state != last_state:
                logger.info("oauth_login: state=%s host=%s", state, info.get("host", ""))
                last_state = state

            if state == "success":
                logger.info("oauth_login: signed in -> %s", url[:120])
                return url

            if state == "credentials":
                if policy.on_credentials == "abort":
                    raise OAuthGovernanceError(
                        "oauth_login: a credentials (email/password) screen appeared — "
                        "the saved session is not signed in. Run `demodsl setup-login` "
                        "first. Passwords are never auto-typed."
                    )
                logger.warning(
                    "oauth_login: credentials screen — waiting for a human to sign in ..."
                )

            elif state == "challenge":
                if policy.on_2fa == "abort":
                    raise OAuthGovernanceError(
                        "oauth_login: a 2FA/verification challenge appeared and on_2fa='abort'."
                    )
                logger.warning("oauth_login: 2FA/verification challenge — waiting for a human ...")

            elif state == "consent":
                scopes = info.get("scopes") or []
                verdict = check_scopes(
                    scopes, info.get("text", ""), policy.allowed_scopes, policy.denied_scopes
                )
                if not verdict.ok:
                    raise OAuthGovernanceError(
                        f"oauth_login: consent refused by governance policy — {verdict.reason}. "
                        f"Permissions read: {scopes!r}"
                    )
                if not policy.auto_consent:
                    logger.warning(
                        "oauth_login: consent screen approved by policy but "
                        "auto_consent=false — waiting for a human to click ..."
                    )
                else:
                    clicked = browser.evaluate_js(click_consent_js(profile))
                    logger.info("oauth_login: consent approved (scopes ok) -> clicked %r", clicked)

            elif state == "account":
                if account_clicks >= 5:
                    raise OAuthGovernanceError(
                        "oauth_login: stuck on the account chooser (clicked 5x). "
                        f"No account matched account_email={policy.account_email!r}."
                    )
                clicked = browser.evaluate_js(click_account_js(policy.account_email))
                account_clicks += 1
                logger.info("oauth_login: picked account -> %r", clicked or "(none)")

            time.sleep(poll)

        raise TimeoutError(
            f"oauth_login: did not reach {success_host!r} within {timeout:.0f}s "
            f"(last state={last_state!r})."
        )

    def describe(self, step: Step) -> str:
        prov = step.oauth.provider if step.oauth else "google"
        bits = [f"OAuth login via {prov}"]
        if step.oauth:
            if step.oauth.account_email:
                bits.append(f"account~{step.oauth.account_email!r}")
            if step.oauth.denied_scopes:
                bits.append(f"deny={step.oauth.denied_scopes}")
            if step.oauth.allowed_scopes:
                bits.append(f"allow={step.oauth.allowed_scopes}")
        return ", ".join(bits)


_COMMANDS: dict[str, type[BrowserCommand]] = {
    "navigate": NavigateCommand,
    "click": ClickCommand,
    "type": TypeCommand,
    "scroll": ScrollCommand,
    "pause": PauseCommand,
    "wait_for": WaitForCommand,
    "shortcut": ShortcutCommand,
    "hover": HoverCommand,
    "drag": DragCommand,
    "press_key": PressKeyCommand,
    "camera": CameraCommand,
    "camera_reset": CameraCommand,
    "oauth_login": OAuthLoginCommand,
    # "screenshot" handled separately because it needs output_dir
    # "await_email" handled separately because it needs the mailbox config
}


def get_command(action: str, **kwargs: Any) -> BrowserCommand:
    """Instantiate the appropriate command for *action*."""
    if action == "screenshot":
        output_dir = kwargs.get("output_dir", Path("."))
        return ScreenshotCommand(output_dir=output_dir)
    if action == "await_email":
        return EmailVerifyCommand(mailbox=kwargs.get("mailbox"))
    cls = _COMMANDS.get(action)
    if cls is None:
        valid = sorted(list(_COMMANDS.keys()) + ["screenshot"])
        close = difflib.get_close_matches(action, valid, n=3, cutoff=0.5)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise ValueError(
            f"Unknown browser action '{action}'. Valid browser actions: {', '.join(valid)}.{hint}"
        )
    return cls()


# ── Mobile Command Pattern ───────────────────────────────────────────────────


class MobileCommand(ABC):
    """Base class for all mobile action commands."""

    @abstractmethod
    def execute(self, mobile: MobileProvider, step: Step) -> Any:
        """Execute the action against the mobile provider."""

    @abstractmethod
    def describe(self, step: Step) -> str:
        """Human-readable description (used for dry-run logging)."""


class TapCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.tap(
            locator=step.locator,
            x=step.start_x,
            y=step.start_y,
            duration_ms=step.duration_ms,
        )

    def describe(self, step: Step) -> str:
        if step.locator:
            return f"Tap [{step.locator.type}] {step.locator.value}"
        return f"Tap at ({step.start_x}, {step.start_y})"


class SwipeCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.swipe(
            start_x=step.start_x or 0,
            start_y=step.start_y or 0,
            end_x=step.end_x or 0,
            end_y=step.end_y or 0,
            duration_ms=step.duration_ms or 800,
        )

    def describe(self, step: Step) -> str:
        return f"Swipe ({step.start_x}, {step.start_y}) → ({step.end_x}, {step.end_y})"


class PinchCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.pinch(
            locator=step.locator,
            scale=step.pinch_scale or 0.5,
            duration_ms=step.duration_ms or 500,
        )

    def describe(self, step: Step) -> str:
        return f"Pinch scale={step.pinch_scale}"


class LongPressCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.long_press(
            locator=step.locator,
            x=step.start_x,
            y=step.start_y,
            duration_ms=step.duration_ms or 1000,
        )

    def describe(self, step: Step) -> str:
        if step.locator:
            return f"Long press [{step.locator.type}] {step.locator.value}"
        return f"Long press at ({step.start_x}, {step.start_y})"


class BackCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.back()

    def describe(self, step: Step) -> str:
        return "Press back button"


class HomeCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.home()

    def describe(self, step: Step) -> str:
        return "Press home button"


class NotificationCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.open_notifications()

    def describe(self, step: Step) -> str:
        return "Open notifications"


class AppSwitchCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.app_switch()

    def describe(self, step: Step) -> str:
        return "Open app switcher"


class RotateDeviceCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.rotate(step.orientation or "portrait")

    def describe(self, step: Step) -> str:
        return f"Rotate to {step.orientation}"


class ShakeCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        mobile.shake()

    def describe(self, step: Step) -> str:
        return "Shake device"


class MobileScrollCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        direction = step.direction or "down"
        pixels = step.pixels or 300
        mobile.scroll(direction, pixels)

    def describe(self, step: Step) -> str:
        return f"Scroll {step.direction or 'down'} {step.pixels or 300}px"


class MobileTypeCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        if step.locator is None or step.value is None:
            raise ValueError("MobileTypeCommand requires 'locator' and 'value'")
        mobile.type_text(step.locator, step.value)

    def describe(self, step: Step) -> str:
        loc = step.locator
        target = f"[{loc.type}] {loc.value}" if loc else "?"
        return f"Type '{step.value}' into {target}"


class MobileClickCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        if step.locator is None:
            raise ValueError("MobileClickCommand requires 'locator'")
        mobile.click(step.locator)

    def describe(self, step: Step) -> str:
        loc = step.locator
        return f"Tap [{loc.type}] {loc.value}" if loc else "Tap (no locator)"


class MobileWaitForCommand(MobileCommand):
    def execute(self, mobile: MobileProvider, step: Step) -> None:
        if step.locator is None:
            raise ValueError("MobileWaitForCommand requires 'locator'")
        timeout = step.timeout or 5.0
        mobile.wait_for(step.locator, timeout)

    def describe(self, step: Step) -> str:
        loc = step.locator
        target = f"[{loc.type}] {loc.value}" if loc else "?"
        return f"Wait for {target} (timeout={step.timeout or 5.0}s)"


class MobileScreenshotCommand(MobileCommand):
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def execute(self, mobile: MobileProvider, step: Step) -> Path:
        filename = step.filename or "mobile_screenshot.png"
        path = self._output_dir / filename
        return mobile.screenshot(path)

    def describe(self, step: Step) -> str:
        return f"Screenshot → {step.filename or 'mobile_screenshot.png'}"


# ── Mobile Command Registry ──────────────────────────────────────────────────

_MOBILE_COMMANDS: dict[str, type[MobileCommand]] = {
    "tap": TapCommand,
    "swipe": SwipeCommand,
    "pinch": PinchCommand,
    "long_press": LongPressCommand,
    "back": BackCommand,
    "home": HomeCommand,
    "notification": NotificationCommand,
    "app_switch": AppSwitchCommand,
    "rotate_device": RotateDeviceCommand,
    "shake": ShakeCommand,
    # Shared actions mapped to mobile variants
    "scroll": MobileScrollCommand,
    "type": MobileTypeCommand,
    "click": MobileClickCommand,
    "wait_for": MobileWaitForCommand,
}


def get_mobile_command(action: str, **kwargs: Any) -> MobileCommand:
    """Instantiate the appropriate mobile command for *action*."""
    if action == "screenshot":
        output_dir = kwargs.get("output_dir", Path("."))
        return MobileScreenshotCommand(output_dir=output_dir)
    cls = _MOBILE_COMMANDS.get(action)
    if cls is None:
        valid = sorted(list(_MOBILE_COMMANDS.keys()) + ["screenshot"])
        if action == "navigate":
            raise ValueError(
                "Unknown mobile action 'navigate'. "
                "Mobile scenarios launch the app automatically via "
                "bundle_id/app_package — no 'navigate' step is needed. "
                "Did you mean to use a browser scenario (with 'url' instead of 'mobile')?"
            )
        # fuzzy suggestion
        close = difflib.get_close_matches(action, valid, n=3, cutoff=0.5)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise ValueError(
            f"Unknown mobile action '{action}'. Valid mobile actions: {', '.join(valid)}.{hint}"
        )
    return cls()


# ── Terminal Command Pattern ─────────────────────────────────────────────────

# Playwright-bundled Chromium crashes (BUS_ADRALN) when rendering characters
# with Emoji_Presentation=Yes on macOS ARM.  Text-presentation symbols like
# ✓ (U+2713) are safe.  We target exactly the Unicode Emoji_Presentation=Yes
# BMP codepoints plus the entire SMP (U+10000+).
_EMOJI_RE = re.compile(
    "["
    # --- BMP chars with Emoji_Presentation=Yes (crash Chromium) ---
    "\u231a\u231b"  # watch, hourglass
    "\u23e9-\u23ec"  # fast-forward/rewind
    "\u23f0"  # alarm clock
    "\u23f3"  # hourglass flowing
    "\u25fd\u25fe"  # medium squares
    "\u2614\u2615"  # umbrella, hot beverage
    "\u2648-\u2653"  # zodiac signs
    "\u267f"  # wheelchair
    "\u2693"  # anchor
    "\u26a1"  # high voltage
    "\u26aa\u26ab"  # circles
    "\u26bd\u26be"  # soccer, baseball
    "\u26c4\u26c5"  # snowman, sun behind cloud
    "\u26ce"  # ophiuchus
    "\u26d4"  # no entry
    "\u26ea"  # church
    "\u26f2\u26f3"  # fountain, golf
    "\u26f5"  # sailboat
    "\u26fa"  # tent
    "\u26fd"  # fuel pump
    "\u2705"  # ✅ white heavy check mark
    "\u270a-\u270d"  # raised fist → writing hand
    "\u270f"  # pencil
    "\u2712"  # black nib
    "\u2714"  # heavy check mark (emoji)
    "\u2716"  # heavy multiplication
    "\u271d"  # latin cross
    "\u2721"  # star of david
    "\u2728"  # sparkles
    "\u2733\u2734"  # eight-spoked asterisks
    "\u2744"  # snowflake
    "\u2747"  # sparkle
    "\u274c"  # ❌ cross mark
    "\u274e"  # cross mark negative squared
    "\u2753-\u2755"  # question/exclamation ornaments
    "\u2757"  # heavy exclamation mark
    "\u2763\u2764"  # heart exclamation, red heart
    "\u2795-\u2797"  # heavy plus/minus/divide
    "\u27a1"  # right arrow
    "\u27b0"  # curly loop
    "\u27bf"  # double curly loop
    "\u2934\u2935"  # right arrow curving up/down
    "\u2b05-\u2b07"  # left/up/down arrows
    "\u2b1b\u2b1c"  # black/white large squares
    "\u2b50"  # star
    "\u2b55"  # heavy large circle
    "\u3030"  # wavy dash
    "\u303d"  # part alternation mark
    "\u3297"  # circled ideograph congratulation
    "\u3299"  # circled ideograph secret
    # --- SMP catch-all (all emoji/symbols above BMP) ---
    "\U00010000-\U0001ffff"
    # --- Modifiers / joiners ---
    "\ufe00-\ufe0f"  # variation selectors
    "\u200d"  # zero width joiner
    "]+",
)


def _strip_emoji(text: str) -> str:
    """Remove emoji characters that crash headless Chromium."""
    return _EMOJI_RE.sub("", text)


class TerminalCommand(ABC):
    """Base class for terminal action commands."""

    @abstractmethod
    def execute(
        self, browser: BrowserProvider, step: Step, *, typing_speed: float, output_delay: float
    ) -> None:
        """Execute the terminal action via Playwright JS calls."""

    @abstractmethod
    def describe(self, step: Step) -> str:
        """Human-readable description."""


class TerminalRunCommand(TerminalCommand):
    """Type a command in the terminal and optionally display output."""

    def execute(
        self, browser: BrowserProvider, step: Step, *, typing_speed: float, output_delay: float
    ) -> None:
        import json
        import time

        if not step.command:
            raise ValueError("TerminalRunCommand requires 'command'")

        # Type the command character-by-character
        # Use JSON encoding to safely pass Unicode (emojis, special chars)
        safe_cmd = json.dumps(_strip_emoji(step.command))
        # Use void() to fire-and-forget the async typeCommand — avoids
        # blocking Playwright's CDP connection for the full animation
        # duration, which would conflict with the CDP screen recorder.
        browser.evaluate_js(f"void(typeCommand({safe_cmd}, {typing_speed}))")

        # Wait for typing to finish (approximate)
        typing_duration = len(step.command) / typing_speed
        time.sleep(typing_duration + 0.2)

        # Show output if provided
        if step.output is not None:
            time.sleep(output_delay)
            if isinstance(step.output, list):
                output_text = "\n".join(step.output)
            else:
                output_text = step.output
            safe_output = json.dumps(_strip_emoji(output_text))
            browser.evaluate_js(f"showOutput({safe_output})")
            time.sleep(0.1)

        # Show a new prompt
        browser.evaluate_js("showPrompt()")

    def describe(self, step: Step) -> str:
        out = " (with output)" if step.output else ""
        return f"Terminal: $ {step.command}{out}"


class TerminalClearCommand(TerminalCommand):
    """Clear the terminal screen."""

    def execute(
        self, browser: BrowserProvider, step: Step, *, typing_speed: float, output_delay: float
    ) -> None:
        browser.evaluate_js("clearTerminal()")

    def describe(self, step: Step) -> str:
        return "Terminal: clear"


class TerminalZoomCommand(TerminalCommand):
    """Zoom in or out on the terminal content."""

    def execute(
        self, browser: BrowserProvider, step: Step, *, typing_speed: float, output_delay: float
    ) -> None:
        import time

        scale = step.zoom_level if step.zoom_level is not None else 1.5
        duration_s = step.zoom_duration if step.zoom_duration is not None else 0.8
        duration_ms = int(duration_s * 1000)
        browser.evaluate_js(f"void(zoomTerminal({scale}, {duration_ms}))")
        time.sleep(duration_s + 0.1)

    def describe(self, step: Step) -> str:
        scale = step.zoom_level if step.zoom_level is not None else 1.5
        return f"Terminal: zoom {scale}x"


_TERMINAL_COMMANDS: dict[str, type[TerminalCommand]] = {
    "terminal_run": TerminalRunCommand,
    "terminal_clear": TerminalClearCommand,
    "terminal_zoom": TerminalZoomCommand,
}


def get_terminal_command(action: str) -> TerminalCommand:
    """Instantiate the appropriate terminal command for *action*."""
    cls = _TERMINAL_COMMANDS.get(action)
    if cls is None:
        valid = sorted(_TERMINAL_COMMANDS.keys())
        close = difflib.get_close_matches(action, valid, n=3, cutoff=0.5)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise ValueError(
            f"Unknown terminal action '{action}'. Valid terminal actions: {', '.join(valid)}.{hint}"
        )
    return cls()
