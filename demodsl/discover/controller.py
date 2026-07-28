"""Web environment abstraction + live browser controller.

The discovery loop talks to a :class:`WebEnvironment` — a tiny protocol that
both the **live Playwright controller** (:class:`BrowserController`) and the
offline **simulated site** (used by the benchmark) implement.  Keeping the loop
environment-agnostic means the exact same policy / observation / search code is
exercised online and offline, which is what makes the benchmark a fair ablation.

``BrowserController`` reuses the project's existing providers — including the
**authenticated-browser** providers added in the latest version
(``playwright-cdp`` and ``playwright-persistent``) — so gated features can be
discovered against a real signed-in session.  Authentication is configured with
a :class:`~demodsl.models.BrowserAuthConfig`, applied through the provider's
``set_auth_config`` hook exactly like :class:`ScenarioOrchestrator` does.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from demodsl.models import BrowserAuthConfig, Locator, Viewport
from demodsl.providers.base import BrowserProvider, BrowserProviderFactory

logger = logging.getLogger(__name__)


def _ensure_browser_providers_registered() -> None:
    """Import the concrete provider modules so they self-register.

    The controller only imports :mod:`demodsl.providers.base`, whose registry
    starts empty; each concrete provider registers itself at import time via a
    module-level ``BrowserProviderFactory.register(...)`` call.  We trigger the
    same imports :class:`ScenarioOrchestrator` does, otherwise
    ``BrowserProviderFactory.create('playwright')`` — and the authenticated
    ``playwright-persistent`` / ``playwright-cdp`` providers — would raise
    ``Unknown browser provider ... Available: []``.
    """
    import demodsl.providers.browser  # noqa: F401

    try:
        import demodsl.providers.authenticated_browser  # noqa: F401
    except ImportError:
        pass  # playwright extras not installed
    try:
        import demodsl.providers.selenium_browser  # noqa: F401
    except ImportError:
        pass  # selenium not installed


@runtime_checkable
class WebEnvironment(Protocol):
    """Minimal surface the discovery loop needs from a web environment."""

    def extract_elements(self) -> list[dict[str, Any]]:
        """Return raw interactive-element records (see ``_ELEMENT_EXTRACT_JS``)."""

    def current_url(self) -> str: ...

    def title(self) -> str: ...

    def navigate(self, url: str) -> None: ...

    def click(self, locator: Locator) -> None: ...

    def type_text(self, locator: Locator, value: str) -> None: ...

    def scroll(self, direction: str, pixels: int) -> None: ...

    def wait_for(self, locator: Locator, timeout: float = 5.0) -> None: ...

    def close(self) -> None: ...


# JavaScript behind ``page_content()`` (issue #29). DOM order is not argument
# order, and a modern hero is often a ``div``/``span``, never an ``h1``. So the
# candidate set is "headings + price-ish labels + anything rendered in the top
# decile of the page's font sizes", filtered on *real* visibility and ranked by
# rendered weight, fold position and whether the node lives inside a decorative
# product mockup. ``__LIMIT__`` is substituted by the caller.
# Returned shape per candidate:
#   {text, tag, fontSizePx, bbox:{x,y,w,h}, viewportY, insideMockup,
#    furniture, score}
_PAGE_CONTENT_JS = r"""
(() => {
  const LIMIT = __LIMIT__;
  const MAXLEN = 90;
  const vw = window.innerWidth || 1280, vh = window.innerHeight || 800;
  const scrollY = window.scrollY || 0;
  // Classes that decorate rather than argue: product screenshots, fake app
  // chrome, device frames, carousels rotating out of view.
  const MOCK = /(mockup|screenshot|screen-shot|preview|device|phone|browser|app-frame|window-frame|carousel|marquee|ticker|slider)/i;
  const FURN = /(footer|nav|menu|breadcrumb|cookie|legal|copyright)/i;
  const SKIP = /^(script|style|noscript|svg|path|option|iframe|template)$/i;
  const PRICE = /(price|plan|tier)/i;

  const classOf = (el) => {
    const c = el.className;
    const s = (c && typeof c === 'object' && 'baseVal' in c) ? c.baseVal : (c || '');
    return String(s) + ' ' + (el.id || '');
  };
  // Only the element's OWN text: without this every ancestor container
  // re-reports the same sentence and the ranking is meaningless.
  const ownText = (el) => {
    let t = '';
    for (const n of el.childNodes) if (n.nodeType === 3) t += n.nodeValue;
    return t.replace(/\s+/g, ' ').trim();
  };

  const nodes = [];
  const all = document.body ? document.body.querySelectorAll('*') : [];
  for (const el of all) {
    if (SKIP.test(el.tagName)) continue;
    const text = ownText(el);
    if (!text || text.length > MAXLEN) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (parseFloat(cs.opacity || '1') < 0.1) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) continue;
    if (r.right <= 0 || r.left >= vw) continue;  // off-canvas carousel slide
    try { if (el.closest('[aria-hidden="true"]')) continue; } catch (e) {}
    nodes.push({ el: el, text: text, r: r, size: parseFloat(cs.fontSize) || 0 });
  }
  if (!nodes.length) return [];

  const sizes = nodes.map((n) => n.size).sort((a, b) => a - b);
  const decile = sizes[Math.floor(sizes.length * 0.9)] || 0;

  const out = [];
  const seen = new Set();
  for (const n of nodes) {
    const tag = n.el.tagName.toLowerCase();
    const heading = /^h[1-3]$/.test(tag);
    const cls = classOf(n.el);
    const priceish = PRICE.test(cls);
    if (!heading && !priceish && n.size < decile) continue;
    if (seen.has(n.text)) continue;
    seen.add(n.text);

    const absTop = n.r.top + scrollY;
    const viewportY = absTop / vh;

    let insideMockup = false;
    for (let p = n.el.parentElement, d = 0; p && d < 8; p = p.parentElement, d++) {
      if (MOCK.test(classOf(p))) { insideMockup = true; break; }
      const tr = getComputedStyle(p).transform;
      if (tr && tr !== 'none' && /matrix3d|perspective/.test(tr)) { insideMockup = true; break; }
    }
    let furniture = FURN.test(cls);
    try { furniture = furniture || !!n.el.closest('footer,nav'); } catch (e) {}

    let score = n.size;                       // rendered weight is the base signal
    if (heading) score += tag === 'h1' ? 24 : (tag === 'h2' ? 10 : 4);
    if (priceish) score += 6;
    score -= Math.min(40, Math.max(0, viewportY) * 12);  // below the fold argues less
    if (insideMockup) score -= 45;            // decoration, not argument
    if (furniture) score -= 60;               // footer/nav is not an argument

    out.push({
      text: n.text,
      tag: tag,
      fontSizePx: Math.round(n.size * 10) / 10,
      bbox: { x: Math.round(n.r.left), y: Math.round(absTop),
              w: Math.round(n.r.width), h: Math.round(n.r.height) },
      viewportY: Math.round(viewportY * 100) / 100,
      insideMockup: insideMockup,
      furniture: furniture,
      score: Math.round(score * 10) / 10,
    });
  }
  out.sort((a, b) => b.score - a.score);
  return out.slice(0, LIMIT);
})()
"""


def pick_hero(candidates: list[dict[str, Any]]) -> str:
    """The hero out of ranked :meth:`BrowserController.page_content` candidates.

    Highest-scoring candidate that is above the fold and *not* inside a
    decorative mockup; falls back to the highest-scoring one overall. Kept as a
    free function so callers holding a serialised graph can re-rank without a
    live browser.
    """
    for cand in candidates:
        if cand.get("insideMockup") or cand.get("furniture"):
            continue
        try:
            if float(cand.get("viewportY", 1e9)) < 1.0:
                return str(cand.get("text") or "")
        except (TypeError, ValueError):
            continue
    return str(candidates[0].get("text") or "") if candidates else ""


# JavaScript that walks the DOM and returns a compact list of interactive
# elements, each with a *robust* locator chosen with the same priority ladder as
# the recorder Chrome extension (data-testid > id > role+aria > text > css path).
# Returned shape per element:
#   {tag, role, name, text, editable, in_viewport, bbox:{x,y,width,height},
#    locator:{type, value}, attrs}
_ELEMENT_EXTRACT_JS = r"""
(() => {
  const MAX = 220;
  const vw = window.innerWidth, vh = window.innerHeight;
  const out = [];
  const seen = new Set();

  const clean = (t) => (t || '').replace(/\s+/g, ' ').trim().slice(0, 140);
  const isUnique = (sel) => {
    try { return document.querySelectorAll(sel).length === 1; } catch (e) { return false; }
  };
  const implicitRole = (el) => {
    const tag = el.tagName.toLowerCase();
    if (tag === 'a' && el.hasAttribute('href')) return 'link';
    if (tag === 'button') return 'button';
    if (tag === 'select') return 'combobox';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'input') {
      const t = (el.getAttribute('type') || 'text').toLowerCase();
      if (['button','submit','reset','image'].includes(t)) return 'button';
      if (t === 'checkbox') return 'checkbox';
      if (t === 'radio') return 'radio';
      if (t === 'search') return 'searchbox';
      return 'textbox';
    }
    if (/^h[1-6]$/.test(tag)) return 'heading';
    return el.getAttribute('role') || 'generic';
  };
  const accName = (el) => {
    const aria = el.getAttribute('aria-label');
    if (aria) return clean(aria);
    const labelledby = el.getAttribute('aria-labelledby');
    if (labelledby) {
      const ref = document.getElementById(labelledby);
      if (ref) return clean(ref.textContent);
    }
    if (el.id) {
      const lab = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (lab) return clean(lab.textContent);
    }
    const ph = el.getAttribute('placeholder');
    if (ph) return clean(ph);
    const val = el.getAttribute('value');
    const txt = clean(el.textContent);
    if (txt) return txt;
    if (val) return clean(val);
    return clean(el.getAttribute('title') || el.getAttribute('name') || '');
  };
  const cssPath = (el) => {
    if (el.id && isUnique('#' + CSS.escape(el.id))) return '#' + CSS.escape(el.id);
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 5) {
      let sel = node.tagName.toLowerCase();
      if (node.id) { sel = '#' + CSS.escape(node.id); parts.unshift(sel); break; }
      const parent = node.parentElement;
      if (parent) {
        const sibs = Array.from(parent.children).filter(c => c.tagName === node.tagName);
        if (sibs.length > 1) sel += ':nth-of-type(' + (sibs.indexOf(node) + 1) + ')';
      }
      parts.unshift(sel);
      node = node.parentElement;
    }
    return parts.join(' > ');
  };
  // Flatten grounding-relevant attributes so the harness can match elements
  // identified by metadata rather than visible text (Mind2Web-style grounding).
  const ATTRS = ['aria-label','placeholder','title','name','type','value','alt','role'];
  const attrsText = (el) => {
    const out = [];
    for (const a of ATTRS) {
      const v = el.getAttribute(a);
      if (v) out.push(clean(v));
    }
    if (el.id) out.push(el.id);
    return out.join(' ').slice(0, 200);
  };
  // Resolve a link element's destination to an absolute URL so the harness can
  // ground navigation in *real* page links (and reject hallucinated targets).
  const hrefFor = (el) => {
    const raw = el.getAttribute('href');
    if (!raw) return null;
    const t = raw.trim();
    if (!t || t.toLowerCase().startsWith('javascript:')) return null;
    try {
      return new URL(t, location.href).href;
    } catch (e) {
      return null;
    }
  };
  const locatorFor = (el) => {
    const testid = el.getAttribute('data-testid') || el.getAttribute('data-test');
    if (testid) {
      const sel = '[data-testid="' + testid + '"]';
      if (isUnique(sel)) return { type: 'css', value: sel };
      const sel2 = '[data-test="' + testid + '"]';
      if (isUnique(sel2)) return { type: 'css', value: sel2 };
    }
    if (el.id && isUnique('#' + CSS.escape(el.id))) return { type: 'id', value: el.id };
    const role = el.getAttribute('role') || implicitRole(el);
    const aria = el.getAttribute('aria-label');
    if (role && aria) return { type: 'accessibility_id', value: role + ':' + clean(aria) };
    const txt = clean(el.textContent);
    if (txt && txt.length <= 40) {
      try {
        const matches = Array.from(document.querySelectorAll(el.tagName.toLowerCase()))
          .filter(e => clean(e.textContent) === txt);
        if (matches.length === 1) return { type: 'text', value: txt };
      } catch (e) {}
    }
    return { type: 'css', value: cssPath(el) };
  };

  const SEL = 'a[href],button,input,select,textarea,[role=button],[role=link],' +
    '[role=tab],[role=checkbox],[role=switch],[role=menuitem],[role=radio],' +
    '[onclick],[tabindex]:not([tabindex="-1"])';
  const nodes = document.querySelectorAll(SEL);
  for (const el of nodes) {
    if (out.length >= MAX) break;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none' || parseFloat(style.opacity) === 0)
      continue;
    if (el.disabled) continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;
    const tag = el.tagName.toLowerCase();
    const role = implicitRole(el);
    const name = accName(el);
    const key = role + '|' + name + '|' + Math.round(r.left) + '|' + Math.round(r.top);
    if (seen.has(key)) continue;
    seen.add(key);
    const editable = tag === 'textarea' ||
      (tag === 'input' && !['button','submit','reset','checkbox','radio','image'].includes(
        (el.getAttribute('type') || 'text').toLowerCase()));
    const inView = r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw;
    out.push({
      tag, role, name, text: clean(el.textContent),
      editable, in_viewport: inView,
      bbox: { x: r.left, y: r.top, width: r.width, height: r.height },
      locator: locatorFor(el),
      attrs: attrsText(el),
      href: hrefFor(el),
    });
  }
  return out;
})()
"""


class BrowserController(WebEnvironment):
    """Live :class:`WebEnvironment` backed by a real DemoDSL browser provider.

    Supports authenticated discovery by accepting a *provider* name
    (``playwright`` / ``playwright-cdp`` / ``playwright-persistent``) and an
    optional :class:`~demodsl.models.BrowserAuthConfig`.
    """

    def __init__(
        self,
        *,
        provider: str = "playwright",
        auth: BrowserAuthConfig | None = None,
        browser: str = "chrome",
        viewport: Viewport | None = None,
    ) -> None:
        self.provider_name = provider
        self.auth = auth
        self.browser_type = browser
        self.viewport = viewport or Viewport()
        self._provider: BrowserProvider | None = None
        self._last_url = ""

    # ── lifecycle ─────────────────────────────────────────────────────────

    def open(self, url: str) -> None:
        """Create the provider (applying auth) and navigate to *url*.

        Recording is intentionally disabled during discovery — exploration
        does not need a video, only DOM access.
        """
        _ensure_browser_providers_registered()
        provider = BrowserProviderFactory.create(self.provider_name)
        if self.auth is not None and hasattr(provider, "set_auth_config"):
            provider.set_auth_config(self.auth.model_dump())  # type: ignore[attr-defined]
        provider.launch_without_recording(browser_type=self.browser_type, viewport=self.viewport)
        self._provider = provider
        self.navigate(url)

    @property
    def provider(self) -> BrowserProvider:
        if self._provider is None:
            raise RuntimeError("BrowserController.open() must be called first")
        return self._provider

    # ── WebEnvironment ────────────────────────────────────────────────────

    def extract_elements(self) -> list[dict[str, Any]]:
        try:
            result = self.provider.evaluate_js(_ELEMENT_EXTRACT_JS)
        except Exception:
            logger.debug("element extraction failed", exc_info=True)
            return []
        return result if isinstance(result, list) else []

    def current_url(self) -> str:
        try:
            self._last_url = str(self.provider.evaluate_js("window.location.href"))
        except Exception:
            logger.debug("current_url: evaluate_js failed; using last known URL", exc_info=True)
        return self._last_url

    def title(self) -> str:
        try:
            return str(self.provider.evaluate_js("document.title"))
        except Exception:
            return ""

    def page_content(self, limit: int = 12) -> list[dict[str, Any]]:
        """Ranked, *visible* on-page arguments with geometry (issue #29).

        DOM order is not argument order: a heading buried inside a decorative
        product mockup comes first, and a modern hero built out of ``div``/
        ``span`` never matches ``h1,h2,h3`` at all. So this collects candidates
        by **rendered weight** instead of by tag:

        - any ``h1``-``h3`` / price-ish element, *plus* any text node whose
          computed ``font-size`` is in the top decile of the page — that is
          what actually catches ``div``-based heroes;
        - filtered on real visibility (``display``/``visibility``/``opacity``,
          non-zero box, not ``aria-hidden``, not off-canvas);
        - scored on font size, viewport position (above the fold wins),
          heading tag and "does it look like footer furniture".

        Each item: ``{text, tag, fontSizePx, bbox, viewportY, insideMockup,
        score}``. Best-effort: returns ``[]`` on any failure.
        """
        js = _PAGE_CONTENT_JS.replace("__LIMIT__", str(int(limit)))
        try:
            result = self.provider.evaluate_js(js)
        except Exception:
            logger.debug("page content extraction failed", exc_info=True)
            return []
        if not isinstance(result, list):
            return []
        return [r for r in result if isinstance(r, dict) and r.get("text")]

    def page_hero(self) -> str:
        """The page's actual headline — the heaviest visible text above the fold.

        Callers used to reach for ``headings[0]``, which is DOM order and
        therefore frequently a caption inside a screenshot. This is explicit.
        """
        return pick_hero(self.page_content(limit=24))

    def page_headings(self, limit: int = 12) -> list[str]:
        """Visible headings / price-like labels — content for review narration.

        Backwards-compatible flat list, but ordered by **argument weight**
        rather than DOM order, so ``headings[0]`` is the page's real headline
        and footer navigation sinks to the bottom (issue #29). Use
        :meth:`page_content` when you need the geometry behind the ranking.
        """
        return [str(c["text"]) for c in self.page_content(limit)]

    def navigate(self, url: str) -> None:
        self.provider.navigate(url)
        self._last_url = url

    def click(self, locator: Locator) -> None:
        self.provider.click(locator)

    def type_text(self, locator: Locator, value: str) -> None:
        self.provider.type_text(locator, value)

    def scroll(self, direction: str, pixels: int) -> None:
        self.provider.scroll(direction, pixels, smooth=False)

    def wait_for(self, locator: Locator, timeout: float = 5.0) -> None:
        self.provider.wait_for(locator, timeout)

    def hover(self, locator: Locator) -> None:
        self.provider.hover(locator)

    def screenshot_to_tmp(self) -> Path | None:
        fd = tempfile.NamedTemporaryFile(prefix="discover_", suffix=".png", delete=False)
        fd.close()
        try:
            return self.provider.screenshot(Path(fd.name))
        except Exception:
            return None

    def get_element_bbox(self, locator: Locator) -> dict[str, float] | None:
        return self.provider.get_element_bbox(locator)

    def close(self) -> None:
        if self._provider is not None:
            try:
                self._provider.close()
            finally:
                self._provider = None
