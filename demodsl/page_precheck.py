"""Pre-flight check for main-page accessibility.

Some sites are protected by anti-bot / WAF services that serve a JavaScript
challenge or an outright 403/503/429/451 to non-browser clients.  When we
run a demo against such a site we typically end up recording a "challenge"
page or a blank screen instead of the real content.

Detected protections:
  * Cloudflare (incl. Turnstile / "Just a moment…" interstitial)
  * DataDome
  * Akamai (Bot Manager / "Access Denied" reference page)
  * Imperva / Incapsula
  * AWS WAF (CAPTCHA & request-blocked pages)
  * F5 / Shape Security
  * Sucuri WAF
  * Kasada
  * PerimeterX / HUMAN
  * Generic CAPTCHA gates (hCaptcha, reCAPTCHA, Arkose/FunCaptcha)
  * Generic blocks: HTTP 401/403/429/451/5xx without a friendlier signal

This module probes a URL with a lightweight ``GET`` request and reports:
  * whether the page is reachable at all,
  * whether a known anti-bot service is intercepting the response,
  * a short human-readable reason.

The result is meant to be **advisory** — we never abort the demo, we just
log a clear warning so the demo author knows why the recording is empty.

Detection is heuristic and based on:
  * response status (403 / 503 are strong signals),
  * well-known headers (``cf-ray``, ``cf-mitigated``, ``server: cloudflare``,
    ``x-dd-b``, ``x-datadome``, ``server: AkamaiGHost``…),
  * cookie names set on the response (``__cf_bm``, ``cf_clearance``,
    ``datadome``…),
  * markers in the HTML body for the most common challenge pages.

Network errors are intentionally treated as "accessible" — the demo should
still be allowed to run when the precheck host has no internet access.
"""

from __future__ import annotations

import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5.0
_BODY_SNIFF_BYTES = 16_384  # 16 KB is enough to spot every known challenge page
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Body markers (lower-cased substrings)
_CLOUDFLARE_BODY_MARKERS: tuple[str, ...] = (
    "just a moment",
    "checking your browser before accessing",
    "cf-browser-verification",
    "cf-challenge",
    "challenge-platform",
    "/cdn-cgi/challenge-platform",
    "attention required! | cloudflare",
    "ray id:",
)
_DATADOME_BODY_MARKERS: tuple[str, ...] = (
    "datadome",
    "geo.captcha-delivery.com",
    "captcha-delivery.com",
    "dd_cookie_test",
)
_AKAMAI_BODY_MARKERS: tuple[str, ...] = (
    "access denied",
    "reference&#32;&#35;",
    "you don't have permission to access",
)
_PERIMETERX_BODY_MARKERS: tuple[str, ...] = (
    "px-captcha",
    "perimeterx",
    "_pxcaptcha",
)
_IMPERVA_BODY_MARKERS: tuple[str, ...] = (
    "incapsula incident id",
    "_incapsula_resource",
    "/_incapsula_resource",
    "imperva incident id",
)
_AWS_WAF_BODY_MARKERS: tuple[str, ...] = (
    "aws waf",
    "awswafcaptcha",
    "/aws-waf-token",
    "request blocked. we can&#39;t connect",
)
_F5_BODY_MARKERS: tuple[str, ...] = (
    "f5 networks",
    "the requested url was rejected",
    "tsbocheck",  # F5 Shape JS challenge marker
)
_SUCURI_BODY_MARKERS: tuple[str, ...] = (
    "sucuri website firewall",
    "access denied - sucuri",
    "cloudproxy.sucuri.net",
)
_KASADA_BODY_MARKERS: tuple[str, ...] = (
    "/kpsdk/",
    "kasada",
)
_GENERIC_CAPTCHA_BODY_MARKERS: tuple[str, ...] = (
    "g-recaptcha",
    "h-captcha",
    "hcaptcha.com",
    "challenges.cloudflare.com",  # Turnstile
    "funcaptcha",
    "arkoselabs",
    "please verify you are a human",
    "are you a robot",
)


@dataclass(frozen=True)
class PageProbeResult:
    """Outcome of a single page accessibility probe."""

    url: str
    accessible: bool
    protection: str | None = None  # "cloudflare", "datadome", "akamai", …
    reason: str = ""
    status: int | None = None

    def format_warning(self) -> str:
        bits = [f"{self.url} → not accessible"]
        if self.protection:
            bits.append(f"protected by {self.protection}")
        if self.status is not None:
            bits.append(f"HTTP {self.status}")
        if self.reason:
            bits.append(self.reason)
        return " · ".join(bits)


# ── Header / cookie / body classifiers ────────────────────────────────────────


def _header_value(headers: object, name: str) -> str:
    """Read a header in a case-insensitive way (works for HTTPMessage & dict)."""
    if hasattr(headers, "get"):
        v = headers.get(name)  # type: ignore[call-arg]
        if v is not None:
            return str(v)
    if hasattr(headers, "get_all"):
        try:
            vs = headers.get_all(name)  # type: ignore[call-arg]
            if vs:
                return ", ".join(vs)
        except Exception:  # pragma: no cover
            pass
    return ""


def _all_cookies(headers: object) -> str:
    """Concatenate all ``Set-Cookie`` headers (case-insensitive)."""
    if hasattr(headers, "get_all"):
        try:
            vs = headers.get_all("Set-Cookie")  # type: ignore[call-arg]
            if vs:
                return "; ".join(vs).lower()
        except Exception:  # pragma: no cover
            pass
    if hasattr(headers, "get"):
        v = headers.get("Set-Cookie")  # type: ignore[call-arg]
        if v:
            return str(v).lower()
    return ""


def _classify_protection(
    headers: object, body_lower: str, status: int | None
) -> tuple[str | None, str]:
    """Return ``(protection, reason)`` or ``(None, "")`` if no signal."""
    server = _header_value(headers, "Server").lower()
    cf_ray = _header_value(headers, "cf-ray")
    cf_mitigated = _header_value(headers, "cf-mitigated").lower()
    x_dd = _header_value(headers, "x-dd-b") or _header_value(headers, "x-datadome")
    cookies = _all_cookies(headers)

    # Cloudflare
    if cf_mitigated == "challenge":
        return "cloudflare", "cf-mitigated: challenge"
    if "cloudflare" in server and status in (403, 503):
        return "cloudflare", f"server: cloudflare, HTTP {status}"
    if any(m in body_lower for m in _CLOUDFLARE_BODY_MARKERS):
        return "cloudflare", "challenge page detected in body"
    if cf_ray and status in (403, 503):
        return "cloudflare", f"cf-ray + HTTP {status}"
    if "__cf_bm" in cookies and status in (403, 503):
        return "cloudflare", "__cf_bm cookie + blocked status"

    # DataDome
    if x_dd:
        return "datadome", "x-dd-b / x-datadome header"
    if "datadome=" in cookies:
        return "datadome", "datadome cookie set"
    if any(m in body_lower for m in _DATADOME_BODY_MARKERS):
        return "datadome", "datadome marker in body"

    # Akamai
    if "akamaighost" in server and status in (403, 503):
        return "akamai", f"AkamaiGHost + HTTP {status}"
    if status == 403 and any(m in body_lower for m in _AKAMAI_BODY_MARKERS):
        return "akamai", "Akamai 'Access Denied' page"
    # Akamai Bot Manager sets these cookies
    if "ak_bmsc=" in cookies or "_abck=" in cookies:
        if status in (403, 429):
            return "akamai", f"Akamai Bot Manager cookie + HTTP {status}"

    # Imperva / Incapsula
    if any(m in body_lower for m in _IMPERVA_BODY_MARKERS):
        return "imperva", "Incapsula/Imperva incident page"
    if "visid_incap_" in cookies or "incap_ses_" in cookies:
        if status in (403, 429):
            return "imperva", f"Incapsula cookie + HTTP {status}"
    if _header_value(headers, "X-Iinfo"):
        return "imperva", "X-Iinfo header (Incapsula)"

    # AWS WAF
    if any(m in body_lower for m in _AWS_WAF_BODY_MARKERS):
        return "aws-waf", "AWS WAF challenge / block page"
    if "aws-waf-token=" in cookies:
        return "aws-waf", "aws-waf-token cookie set"
    if _header_value(headers, "x-amzn-waf-action"):
        return "aws-waf", "x-amzn-waf-action header"

    # F5 / Shape Security
    if any(m in body_lower for m in _F5_BODY_MARKERS):
        return "f5-shape", "F5/Shape challenge or rejection page"
    if "bigipserver" in cookies and status in (403, 429):
        return "f5-shape", "BIG-IP cookie + blocked status"

    # Sucuri
    if any(m in body_lower for m in _SUCURI_BODY_MARKERS):
        return "sucuri", "Sucuri WAF block page"
    if "sucuri" in server:
        return "sucuri", f"server: {server}"

    # Kasada
    if any(m in body_lower for m in _KASADA_BODY_MARKERS):
        return "kasada", "Kasada KPSDK challenge"
    if _header_value(headers, "x-kpsdk-ct"):
        return "kasada", "x-kpsdk-ct header"

    # PerimeterX / HUMAN
    if any(m in body_lower for m in _PERIMETERX_BODY_MARKERS):
        return "perimeterx", "PerimeterX/HUMAN challenge in body"
    if "_px3" in cookies or "_pxhd" in cookies:
        if status in (403, 429):
            return "perimeterx", "PerimeterX cookie + blocked status"

    # Generic CAPTCHA gates (hCaptcha / reCAPTCHA / Turnstile / Arkose)
    if any(m in body_lower for m in _GENERIC_CAPTCHA_BODY_MARKERS):
        # Don't fire on pages that legitimately embed reCAPTCHA on a form
        # — only when the gate looks like a full interstitial (small body).
        if len(body_lower) < 8000 or status in (403, 429):
            return "captcha", "CAPTCHA gate detected in body"

    return None, ""


# ── Public probe ──────────────────────────────────────────────────────────────


def _open(url: str, *, method: str, timeout: float):
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310


def probe_page_accessible(url: str, *, timeout: float = _TIMEOUT_SECONDS) -> PageProbeResult:
    """Fetch ``url`` and report whether the page is reachable and unblocked.

    The probe never raises — network errors map to ``accessible=True`` so the
    demo can still proceed (the precheck is only advisory).
    """
    headers: object = {}
    body_lower = ""
    status: int | None = None

    try:
        with _open(url, method="GET", timeout=timeout) as resp:  # noqa: S310
            headers = resp.headers
            status = getattr(resp, "status", None)
            try:
                raw = resp.read(_BODY_SNIFF_BYTES) or b""
                body_lower = raw.decode("utf-8", errors="replace").lower()
            except Exception:  # pragma: no cover
                body_lower = ""
    except urllib.error.HTTPError as exc:
        status = exc.code
        headers = exc.headers if exc.headers is not None else {}
        try:
            raw = exc.read(_BODY_SNIFF_BYTES) if hasattr(exc, "read") else b""
            body_lower = (raw or b"").decode("utf-8", errors="replace").lower()
        except Exception:  # pragma: no cover
            body_lower = ""
    except Exception as exc:
        # DNS / connection failure → treat as advisory pass-through.
        return PageProbeResult(
            url=url,
            accessible=True,
            reason=f"probe skipped ({exc.__class__.__name__}: {exc})",
        )

    protection, reason = _classify_protection(headers, body_lower, status)
    if protection is not None:
        return PageProbeResult(
            url=url,
            accessible=False,
            protection=protection,
            reason=reason,
            status=status,
        )

    if status is not None and status >= 400:
        # Friendlier reason text for the most common "blocked" status codes.
        _STATUS_HINTS = {
            401: "HTTP 401 (authentication required)",
            403: "HTTP 403 (forbidden)",
            404: "HTTP 404 (not found)",
            429: "HTTP 429 (rate limited)",
            451: "HTTP 451 (unavailable for legal reasons)",
            503: "HTTP 503 (service unavailable)",
        }
        return PageProbeResult(
            url=url,
            accessible=False,
            reason=_STATUS_HINTS.get(status, f"HTTP {status}"),
            status=status,
        )

    return PageProbeResult(url=url, accessible=True, status=status)


# ── Convenience helpers ───────────────────────────────────────────────────────


_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _iter_unique_http_urls(urls: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if not u or not _URL_RE.match(u):
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def precheck_urls(
    urls: Iterable[str | None], *, timeout: float = _TIMEOUT_SECONDS
) -> list[PageProbeResult]:
    """Probe a batch of URLs and log a warning for each blocked one.

    Returns the list of :class:`PageProbeResult` (one per unique HTTP URL).
    """
    results: list[PageProbeResult] = []
    for url in _iter_unique_http_urls(urls):
        result = probe_page_accessible(url, timeout=timeout)
        if result.accessible:
            logger.info("[page-precheck] %s OK", url)
        else:
            logger.warning(
                "[page-precheck] %s — the recorded demo is likely to show a "
                "challenge or error page. Consider using a different URL, "
                "a fixture/screenshot, or running the demo on an "
                "allow-listed network.",
                result.format_warning(),
            )
        results.append(result)
    return results
