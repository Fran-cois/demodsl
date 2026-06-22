"""Robust OAuth / social-signup automation with a governance policy.

This module powers the ``oauth_login`` browser action.  The challenge with
automating *"Sign in with Google/Microsoft/GitHub"* is that the consent flow
is **not deterministic** — depending on the SaaS, the account state and the
requested scopes you may hit any of:

* an **account chooser** ("which Google account?"),
* a **credentials** screen (email / password) — when the saved session is not
  actually signed in,
* a **2FA / verification** challenge,
* a **consent** screen listing the permissions the app requests, or
* a straight **redirect** back to the SaaS (already authorised).

Rather than hard-coding ``click(...); sleep(...)`` steps (which break the
moment Google reorders a screen), :class:`OAuthLoginCommand` runs a small
*state machine*: it repeatedly **probes** the page (read-only JS), classifies
the current screen, and reacts.

Governance
----------
The dangerous part of any OAuth signup is the **consent screen** — that is
where you grant an app access to your data.  The :class:`OAuthGovernance`
policy makes the decision *explicit and auditable*:

* ``denied_scopes``  — a veto list.  If any of these substrings appears in the
  consent screen, the flow is **aborted** (reliable; scans the visible text).
* ``allowed_scopes`` — an allowlist.  If set, every permission read from the
  consent screen must match one of these, otherwise the flow is aborted.  If
  the permissions cannot be read at all, the policy **fails closed**.
* ``on_credentials`` / ``on_2fa`` — what to do when a password or 2FA screen
  appears.  The default **never types a password**: we either abort or wait
  for a human.  Passwords are supplied once, out-of-band, via
  ``demodsl setup-login``.

This keeps secrets out of the YAML and makes "what did we just agree to?" a
first-class, reviewable decision.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class OAuthGovernanceError(RuntimeError):
    """Raised when an OAuth flow is refused by the governance policy.

    Distinct from a generic failure so callers can tell "the policy said no"
    apart from "the automation broke".
    """


@dataclass(frozen=True)
class OAuthProviderProfile:
    """Identity-provider-specific selectors and heuristics.

    Kept tiny on purpose — success/abort decisions are host-based (provider
    independent); the profile only tunes screen *classification* and which
    button text counts as "approve consent".
    """

    name: str
    # Regex (JS, case-insensitive) matching the consent/approve button label.
    consent_button_re: str
    # URL substrings that disambiguate the consent screen (optional).
    consent_url_hints: tuple[str, ...] = ()
    # URL substrings that disambiguate the account chooser (optional).
    account_url_hints: tuple[str, ...] = ()


_PROFILES: dict[str, OAuthProviderProfile] = {
    "google": OAuthProviderProfile(
        name="google",
        consent_button_re=(
            r"^(continuer|continue|autoriser|allow|accepter|accept|j'accepte|"
            r"i agree|confirmer|confirm|suivant|next)$"
        ),
        consent_url_hints=("/consent", "/o/oauth2", "signin/oauth"),
        account_url_hints=("accountchooser", "oauthchooseaccount", "selectaccount"),
    ),
    "microsoft": OAuthProviderProfile(
        name="microsoft",
        consent_button_re=r"^(accepter|accept|oui|yes|continuer|continue|allow|autoriser)$",
        consent_url_hints=("/consent", "/oauth2/authorize", "kmsi"),
        account_url_hints=(
            "/account",
            "tile",
        ),
    ),
    "github": OAuthProviderProfile(
        name="github",
        consent_button_re=r"^(authorize|autoriser|continue|continuer|allow|grant)",
        consent_url_hints=("/login/oauth/authorize",),
        account_url_hints=(),
    ),
    "generic": OAuthProviderProfile(
        name="generic",
        consent_button_re=(
            r"^(continuer|continue|allow|autoriser|accept|accepter|authorize|"
            r"agree|confirm|confirmer|yes|oui|next|suivant|grant)"
        ),
        consent_url_hints=("consent", "authorize", "oauth"),
        account_url_hints=("chooseaccount", "accountchooser", "selectaccount"),
    ),
}


def resolve_provider_profile(name: str | None) -> OAuthProviderProfile:
    """Return the provider profile for *name* (defaults to 'generic')."""
    return _PROFILES.get((name or "generic").lower(), _PROFILES["generic"])


# ── Governance ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScopeVerdict:
    """Outcome of evaluating a consent screen against the policy."""

    ok: bool
    reason: str


def check_scopes(
    requested: list[str] | None,
    page_text: str | None,
    allowed: list[str] | None,
    denied: list[str] | None,
) -> ScopeVerdict:
    """Decide whether a consent screen is acceptable.

    Args:
        requested: Best-effort list of permission strings scraped from the
            consent screen (may be empty if the layout could not be parsed).
        page_text: The full visible text of the consent screen — used for the
            reliable *denied* substring scan.
        allowed: Allowlist of permission substrings.  When set, **every**
            scraped permission must match one of these; if nothing could be
            scraped the policy fails closed.
        denied: Denylist of permission substrings — any match vetoes the flow.

    Returns:
        A :class:`ScopeVerdict`.  ``ok=False`` means *do not approve consent*.
    """
    req = [s.strip() for s in (requested or []) if s and s.strip()]
    text = (page_text or "").lower()

    # 1. Denylist veto — reliable: scan the whole visible consent text plus any
    #    parsed permission rows.
    for d in denied or []:
        needle = d.strip().lower()
        if not needle:
            continue
        if needle in text or any(needle in s.lower() for s in req):
            return ScopeVerdict(False, f"denied permission present: {d!r}")

    # 2. Allowlist — only the listed permissions may be granted.
    if allowed:
        if not req:
            return ScopeVerdict(
                False,
                "allowed_scopes is set but no permissions could be read from "
                "the consent screen — refusing to approve blindly (fail-closed)",
            )
        allow = [a.strip().lower() for a in allowed if a and a.strip()]
        for s in req:
            if not any(a in s.lower() for a in allow):
                return ScopeVerdict(False, f"requested permission not in allowlist: {s!r}")

    return ScopeVerdict(True, "ok")


# ── JavaScript probes (read-only) and actions (click) ────────────────────────


def probe_js(profile: OAuthProviderProfile, success_host: str, account_email: str | None) -> str:
    """Build the read-only probe that classifies the current OAuth screen.

    Returns a JS expression evaluating to an object::

        { host, path, url, state, scopes: [...], text }

    ``state`` is one of: ``success``, ``credentials``, ``challenge``,
    ``consent``, ``account``, ``waiting``.
    """
    consent_url = json.dumps(list(profile.consent_url_hints))
    account_url = json.dumps(list(profile.account_url_hints))
    success = json.dumps(success_host or "")
    email = json.dumps(account_email or "")
    return rf"""
(function () {{
  var successHost = {success};
  var consentHints = {consent_url};
  var accountHints = {account_url};
  var host = location.hostname || "";
  var path = location.pathname || "";
  var url = location.href || "";
  var lurl = url.toLowerCase();
  function visible(el) {{ return !!(el && el.offsetParent !== null); }}
  function endsWith(h, suf) {{
    if (!suf) return false;
    h = h.toLowerCase(); suf = suf.toLowerCase();
    return h === suf || h.endsWith("." + suf) || h.endsWith(suf);
  }}
  var onSaas = endsWith(host, successHost);
  // Back on the SaaS and not on a login/auth path => signed in.
  if (onSaas && !/(login|sign-?in|signup|sign-?up|auth)/.test(path)) {{
    return {{ host: host, path: path, url: url, state: "success", scopes: [], text: "" }};
  }}
  if (onSaas) {{
    // Still on the SaaS auth page (e.g. before redirect) — just wait.
    return {{ host: host, path: path, url: url, state: "waiting", scopes: [], text: "" }};
  }}
  // ── On the identity provider ──
  var body = document.body ? (document.body.innerText || "") : "";
  // Credentials screen: a visible password OR email/identifier field.
  var pw = document.querySelector("input[type=password]");
  var idf = document.querySelector("input[type=email], input[name=identifier], input[name=loginfmt], input[autocomplete=username]");
  if (visible(pw) || visible(idf)) {{
    return {{ host: host, path: path, url: url, state: "credentials", scopes: [], text: "" }};
  }}
  // 2FA / verification challenge. Only trust a VISIBLE one-time-code input or a
  // challenge-specific PATH segment — never the query string (OAuth URLs carry
  // redirect_uri/scope params that contain words like "verify").
  var otp = document.querySelector("input[autocomplete='one-time-code'], input[name=totpPin], input[name=otc]");
  var tel = document.querySelector("input[type=tel]");
  var challengePath = /\/challenge\/|\/signin\/v2\/challenge|two-step-verification|\/totp/i.test(path);
  if (visible(otp) || visible(tel) || challengePath) {{
    return {{ host: host, path: path, url: url, state: "challenge", scopes: [], text: "" }};
  }}
  function urlHas(hints) {{
    for (var i = 0; i < hints.length; i++) {{ if (lurl.indexOf(hints[i]) !== -1) return true; }}
    return false;
  }}
  var hasAccountItems = !!document.querySelector("[data-email], [data-identifier]");
  var consentRe = /{profile.consent_button_re}/i;
  var btns = Array.prototype.slice.call(
    document.querySelectorAll("button, div[role=button], span[jsname], a[role=button], input[type=submit]")
  );
  var hasConsentBtn = btns.some(function (b) {{ return consentRe.test(((b.innerText || b.value || "").trim())); }});
  // Account chooser wins when the URL says so or items exist and it's not a consent URL.
  if (urlHas(accountHints) || (hasAccountItems && !urlHas(consentHints))) {{
    return {{ host: host, path: path, url: url, state: "account", scopes: [], text: "" }};
  }}
  // Consent screen: gather best-effort permission rows + the full text.
  if (urlHas(consentHints) || hasConsentBtn) {{
    var scopes = [];
    var seen = {{}};
    var rows = document.querySelectorAll("li, [role=listitem], [data-scope], [aria-label]");
    for (var j = 0; j < rows.length; j++) {{
      var t = (rows[j].innerText || rows[j].getAttribute("aria-label") || "").trim();
      if (t && t.length > 3 && t.length < 220 && !seen[t]) {{ seen[t] = 1; scopes.push(t); }}
      if (scopes.length >= 40) break;
    }}
    return {{ host: host, path: path, url: url, state: "consent", scopes: scopes, text: body.slice(0, 4000) }};
  }}
  return {{ host: host, path: path, url: url, state: "waiting", scopes: [], text: "" }};
}})()
"""


def click_account_js(account_email: str | None) -> str:
    """Build JS that clicks the account-chooser entry (matching email if given)."""
    email = json.dumps(account_email or "")
    return f"""
(function () {{
  var email = {email};
  var items = Array.prototype.slice.call(document.querySelectorAll("[data-email], [data-identifier]"));
  var target = null;
  if (email) {{
    var needle = email.toLowerCase();
    target = items.find(function (e) {{
      var v = (e.getAttribute("data-email") || e.getAttribute("data-identifier") || e.innerText || "").toLowerCase();
      return v.indexOf(needle) !== -1;
    }});
  }}
  target = target || items[0];
  if (target) {{
    target.click();
    return (target.getAttribute("data-email") || target.getAttribute("data-identifier") || (target.innerText || "")).trim().slice(0, 60);
  }}
  return "";
}})()
"""


def click_consent_js(profile: OAuthProviderProfile) -> str:
    """Build JS that clicks the consent/approve button for *profile*."""
    return f"""
(function () {{
  var re = /{profile.consent_button_re}/i;
  var cands = Array.prototype.slice.call(
    document.querySelectorAll("button, div[role=button], span[jsname], a[role=button], input[type=submit]")
  );
  var b = cands.find(function (x) {{ return re.test(((x.innerText || x.value || "").trim())); }});
  if (b) {{ b.click(); return ((b.innerText || b.value || "").trim()).slice(0, 40); }}
  return "";
}})()
"""
