"""Pre-flight check for iframe embeddability of secondary_windows URLs.

Sites can block iframe embedding via two mechanisms:
  - ``X-Frame-Options: DENY`` or ``SAMEORIGIN``
  - ``Content-Security-Policy: frame-ancestors 'none'`` (or a restrictive list)

This module probes a URL with a short HEAD/GET request and reports whether
it can be safely embedded.  The result is used by the engine to strip the
``url`` from any blocked ``SecondaryWindow`` so the demo falls back to the
window's ``background_color``/``screenshot`` instead of showing an empty
frame.
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 4.0
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass(frozen=True)
class IframeProbeResult:
    url: str
    embeddable: bool
    reason: str = ""


def _csp_blocks_embedding(csp: str) -> bool:
    """Return True if a CSP header's ``frame-ancestors`` directive blocks us.

    We consider the frame blocked when ``frame-ancestors`` is present AND
    does not include ``*`` (wildcard) or ``http:``/``https:`` scheme sources.
    """
    directives = [d.strip().lower() for d in csp.split(";") if d.strip()]
    for d in directives:
        if not d.startswith("frame-ancestors"):
            continue
        values = d.split(None, 1)[1].strip() if " " in d else ""
        if not values or "'none'" in values:
            return True
        # If wildcard or scheme-only source is allowed, we're fine.
        if "*" in values.split():
            return False
        if "https:" in values.split() or "http:" in values.split():
            return False
        # Any other non-empty value = site restricts to specific origins.
        return True
    return False


def probe_url_embeddable(
    url: str, *, timeout: float = _TIMEOUT_SECONDS
) -> IframeProbeResult:
    """Fetch only headers for ``url`` and decide if it may be iframed."""
    req = urllib.request.Request(
        url, method="HEAD", headers={"User-Agent": _USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            headers = resp.headers
    except urllib.error.HTTPError as exc:
        # Some servers reject HEAD (405); retry with GET.
        if exc.code in (405, 403, 501):
            try:
                req2 = urllib.request.Request(
                    url, method="GET", headers={"User-Agent": _USER_AGENT}
                )
                with urllib.request.urlopen(req2, timeout=timeout) as resp:  # noqa: S310
                    headers = resp.headers
            except Exception as exc2:  # pragma: no cover - network flakiness
                return IframeProbeResult(url, False, f"request failed: {exc2}")
        else:
            return IframeProbeResult(url, False, f"HTTP {exc.code}")
    except Exception as exc:  # pragma: no cover - network flakiness
        # Unreachable → let it through; iframe will show blank but demo goes on.
        return IframeProbeResult(url, True, f"probe skipped ({exc})")

    xfo = (headers.get("X-Frame-Options") or "").strip().upper()
    if xfo in ("DENY", "SAMEORIGIN"):
        return IframeProbeResult(url, False, f"X-Frame-Options: {xfo}")

    csp = headers.get("Content-Security-Policy") or ""
    if csp and _csp_blocks_embedding(csp):
        return IframeProbeResult(url, False, "CSP frame-ancestors restriction")

    return IframeProbeResult(url, True)


def sanitize_secondary_windows(windows: list[dict] | None) -> list[dict] | None:
    """Mutate ``windows`` in-place, stripping unembeddable URLs.

    Returns the same list (or ``None``) for chaining.  A warning is logged
    for each URL that is stripped.
    """
    if not windows:
        return windows
    for w in windows:
        url = w.get("url")
        if not url:
            continue
        result = probe_url_embeddable(url)
        if not result.embeddable:
            logger.warning(
                "[iframe-precheck] '%s' cannot be embedded (%s) — falling back "
                "to static background for window '%s'",
                url,
                result.reason,
                w.get("title", "?"),
            )
            w["url"] = None
        else:
            logger.info("[iframe-precheck] '%s' OK (embeddable)", url)
    return windows


def auto_record_blocked_urls(
    windows: list[dict] | None,
    *,
    cache_dir=None,
    enabled: bool = True,
) -> list[dict] | None:
    """Probe each window's URL; record a sub-demo video for blocked URLs.

    For each window:
      * If the URL is iframe-embeddable → keep ``url`` untouched.
      * If the URL is blocked AND ``enabled`` is True → record a short
        headless clip of the page and stash the file path in the private
        ``_video_path`` field.  The overlay renderer picks this up and
        injects a looping ``<video>`` element instead of an iframe.
      * If recording fails or ``enabled`` is False → strip ``url`` and
        fall back to the window's static background/screenshot.

    Side effects fully under control:
      * The sub-recorder runs in its own Playwright process, isolated
        from the main demo's browser, monitor plugin and narration.
      * Recordings are muted and looped in-page — they never interfere
        with the main demo's subtitles or audio track.
      * Results are cached on disk (keyed by URL + dimensions), so
        repeat runs are fast.

    Mutates ``windows`` in place; returns it for chaining.
    """
    if not windows:
        return windows

    # Import lazily — avoids pulling Playwright into CLI help/validate paths.
    try:
        from demodsl.sub_recorder import record_sub_demo
    except Exception:  # pragma: no cover
        record_sub_demo = None  # type: ignore[assignment]

    for w in windows:
        url = w.get("url")
        if not url:
            continue
        result = probe_url_embeddable(url)
        if result.embeddable:
            logger.info("[iframe-precheck] '%s' OK (embeddable)", url)
            continue

        # Blocked site — try to record a clip as a fallback
        logger.warning(
            "[iframe-precheck] '%s' cannot be embedded (%s) — window '%s'",
            url,
            result.reason,
            w.get("title", "?"),
        )
        video_path = None
        if enabled and record_sub_demo is not None:
            try:
                video_path = record_sub_demo(
                    url,
                    width=int(w.get("width", 600)),
                    height=int(w.get("height", 400)),
                    cache_dir=cache_dir,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "[iframe-precheck] sub-recording failed for %s: %s", url, exc
                )
        if video_path is not None:
            logger.info(
                "[iframe-precheck] using recorded clip for '%s' → %s",
                w.get("title", "?"),
                video_path.name,
            )
            w["_video_path"] = str(video_path)
            # Keep url set to None so the overlay renderer branches to video
            w["url"] = None
        else:
            logger.info(
                "[iframe-precheck] no clip recorded — falling back to static "
                "background for window '%s'",
                w.get("title", "?"),
            )
            w["url"] = None
    return windows
