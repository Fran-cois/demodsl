"""Real-browser visual regression tests for every registered browser effect.

These are the first tests in the suite that actually launch a headless
Chrome (via :class:`SeleniumBrowserProvider`) and verify effects produce a
*real, measurable* visual change -- as opposed to the rest of the test suite,
which only asserts on the shape of the generated JS string. That gap is what
let a serious bug ship silently: ``_cleanup_browser_effects`` used to
brute-force ``clearInterval``/``clearTimeout`` every timer id between steps,
which also killed the Selenium provider's own requestAnimationFrame shim
(``_install_raf_shim``). Headless Chrome does not reliably fire native rAF
callbacks, so once that shim's driving interval was killed, every
canvas/particle effect (confetti, sparkle, matrix_rain, ...) rendered exactly
one frame and then froze silently for the rest of the scenario -- with zero
error anywhere. 200+ unit tests stayed green throughout.

Marked ``slow`` (deselected by the fast CI suite, which runs
``-m "not slow"``) since each test launches a real browser. Run explicitly
with e.g. ``pytest -m slow tests/test_browser_effects_visual.py``.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest

from demodsl.effects.browser import _BROWSER_EFFECTS
from demodsl.models.scenario import Viewport
from demodsl.orchestrators.scenario import ScenarioOrchestrator
from demodsl.providers.selenium_browser import SeleniumBrowserProvider

pytestmark = pytest.mark.slow


# A minimal, static (no ambient CSS animation) fixture page. Effects are
# validated against real, more complex marketing pages in manual testing;
# this fixture exists solely so pixel diffs reflect ONLY what the injected
# effect drew, not the page's own decorative motion.
#
def _fixture_url(nonce: str) -> str:
    # A literal '#' ANYWHERE in a data: URL is parsed as the URI fragment
    # delimiter -- everything after the FIRST one never reaches the document
    # at all (confirmed: an earlier version used '#11131a'/'#fff' hex colors
    # here and `document.body` came back completely empty, silently
    # breaking any effect that looks for pre-existing page content like
    # text_scramble). Every color below MUST be rgb()/named, no hex, and
    # hrefs must not be bare '#'.
    return "data:text/html," + (
        "<html><head><style>"
        "html,body{margin:0;padding:0;width:1280px;height:720px;"
        "background:rgb(17,19,26);overflow:hidden;}"
        "</style></head><body>"
        f"<!-- nonce:{nonce} -->"
        "<h1 id='title' style='color:white;font-family:sans-serif;"
        "position:absolute;top:200px;left:400px;'>Fixture</h1>"
        "<p id='subtitle' style='color:silver;font-family:sans-serif;"
        "position:absolute;top:260px;left:400px;'>A sample paragraph.</p>"
        "<a href='javascript:void(0)' id='link' style='color:dodgerblue;"
        "position:absolute;top:300px;left:400px;'>A link</a>"
        "<button id='cta' style='position:absolute;top:400px;left:560px;'>Go</button>"
        "</body></html>"
    )


def _fresh_navigate(browser: SeleniumBrowserProvider, nonce: str) -> None:
    """Navigate to a truly fresh, empty document before injecting an effect.

    Chrome does not reliably discard the previous document's DOM when
    ``driver.get()`` is called again with a *different* ``data:`` URL -- even
    with a unique nonce embedded in the HTML payload, canvases and other
    elements from the PREVIOUS effect kept silently accumulating across
    parametrized tests (confirmed empirically: sampling "the" canvas for
    ``neon_glow`` was actually reading ``matrix_rain``'s leftover one, five
    tests earlier). Routing through a real intermediate ``about:blank``
    navigation forces an actual new document every time.
    """
    browser._driver.get("about:blank")
    browser.navigate(_fixture_url(nonce))


# Effects once thought to need a real anchored target/selector: turned out
# every one of them falls back to a sensible built-in default (target_x/y
# default to 0.5/0.5, or a `document.querySelector('button, a, h1, p, ...')`
# self-lookup) when the orchestrator's locator-anchoring never ran, so all
# 86 registered effects are actually testable against the bare fixture page.
_SKIP: set[str] = set()

# Effects with a `simulate_mouse` opt-in that auto-dispatches a synthetic
# mousemove path (see js_builder.simulate_mouse_path) for headless testing.
_SIMULATE_MOUSE = {
    "cursor_trail",
    "cursor_trail_comet",
    "cursor_trail_fire",
    "cursor_trail_glow",
    "cursor_trail_line",
    "cursor_trail_particles",
    "cursor_trail_rainbow",
}
# Effects driven purely by a real click/scroll event, no headless fallback.
_NEEDS_CLICK = {"click_particles", "click_ripple"}
_NEEDS_SCROLL = {"scroll_parallax"}
_PARAMS: dict[str, dict[str, object]] = {"device_frame": {"device": "iphone"}}

_TESTABLE_EFFECTS = sorted(set(_BROWSER_EFFECTS) - _SKIP)


@pytest.fixture(scope="module")
def browser() -> Iterator[SeleniumBrowserProvider]:
    provider = SeleniumBrowserProvider()
    try:
        provider.launch_without_recording("chrome", Viewport(width=1280, height=720))
    except Exception as exc:  # pragma: no cover - depends on local Chrome
        pytest.skip(f"real Chrome/chromedriver unavailable: {exc}")
    yield provider
    try:
        provider._driver.quit()
    except Exception:
        pass


def _inject_with_interaction(browser: SeleniumBrowserProvider, name: str, handler: object) -> None:
    params = dict(_PARAMS.get(name, {}))
    if name in _SIMULATE_MOUSE:
        params["simulate_mouse"] = True
    handler.inject(browser.evaluate_js, params)  # type: ignore[attr-defined]
    if name in _NEEDS_CLICK:
        browser.evaluate_js(
            "document.body.dispatchEvent(new MouseEvent('click',"
            "{clientX: window.innerWidth/2, clientY: window.innerHeight/2,"
            " bubbles:true, cancelable:true}));"
        )
    if name in _NEEDS_SCROLL:
        browser.evaluate_js("window.scrollTo(0, 400);")


@pytest.mark.parametrize("name", _TESTABLE_EFFECTS)
def test_effect_produces_dom_or_canvas_content(browser: SeleniumBrowserProvider, name: str) -> None:
    """Every effect must have SOME observable effect on the page.

    Deliberately effect-agnostic and generous: a "camera move" style effect
    (``rotation_3d``, ``perspective_tilt``, ``zoom_focus``, ``zoom_through``)
    animates ``document.body``'s own inline style rather than creating a new
    node, ``ripple``'s spawned divs are identified only via a scoped
    ``@keyframes`` name, never a real ``id`` attribute, and ``text_scramble``
    mutates existing elements' ``textContent`` in place (no new node, no
    style change) -- so this checks, in order: (1) a new
    ``__demodsl_``/``__drip_``-prefixed element exists, OR (2)
    ``document.body``'s computed transform/filter changed from the default,
    OR (3) the total element count under ``<body>`` grew, OR (4) the
    concatenated text content under ``<body>`` changed. This does not prove
    the effect is *visible*, only that ``inject()`` ran without raising and
    actually touched the page. Canvas-based effects get the stronger
    pixel-level check in ``test_canvas_effect_actually_animates``.
    """
    _fresh_navigate(browser, name)
    time.sleep(0.2)
    before_count = browser.evaluate_js("return document.body.getElementsByTagName('*').length;")
    before_text = browser.evaluate_js("return document.body.textContent;")
    handler = _BROWSER_EFFECTS[name]()
    _inject_with_interaction(browser, name, handler)
    time.sleep(0.2)
    result = browser.evaluate_js(
        "const prefixed = document.querySelectorAll("
        '\'[id^="__demodsl_"], [id^="__drip_"]\').length;'
        "const cs = getComputedStyle(document.body);"
        "const bodyChanged = cs.transform !== 'none' || cs.filter !== 'none';"
        "const afterCount = document.body.getElementsByTagName('*').length;"
        "const afterText = document.body.textContent;"
        "return {prefixed, bodyChanged, afterCount, afterText};"
    )
    changed = (
        result["prefixed"] > 0
        or result["bodyChanged"]
        or result["afterCount"] > before_count
        or result["afterText"] != before_text
    )
    assert changed, f"{name}: inject() had no observable effect on the page ({result})"


@pytest.mark.parametrize(
    "name",
    [n for n in _TESTABLE_EFFECTS if "cursor_trail" not in n],
)
def test_canvas_effect_actually_animates(browser: SeleniumBrowserProvider, name: str) -> None:
    """Canvas/rAF-driven effects must keep drawing across real time.

    Regression guard for the RAF-shim-killed-by-cleanup bug: a canvas that
    renders exactly one frame and then freezes (e.g. because the driving
    ``requestAnimationFrame`` shim was stopped) is indistinguishable from
    "broken" to a real viewer, even though ``inject()`` succeeded and the
    canvas DOM node exists.
    """
    _fresh_navigate(browser, name)
    time.sleep(0.2)
    handler = _BROWSER_EFFECTS[name]()
    _inject_with_interaction(browser, name, handler)

    has_canvas = browser.evaluate_js(
        "return !!document.querySelector('canvas[id^=\"__demodsl_\"]');"
    )
    if not has_canvas:
        pytest.skip(f"{name}: not canvas-based, covered by the DOM-presence test")

    sample_js = (
        "const c = document.querySelector('canvas[id^=\"__demodsl_\"]');"
        "if (!c) return -1;"
        "const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;"
        "let n = 0;"
        "for (let i = 3; i < d.length; i += 4) { if (d[i] !== 0) n++; }"
        "return n;"
    )
    samples = []
    for delay in (0.05, 0.2, 0.5):
        time.sleep(delay)
        samples.append(browser.evaluate_js(sample_js))

    assert any(s and s > 0 for s in samples), (
        f"{name}: canvas never had any non-transparent pixel across "
        f"samples {samples} -- effect likely never renders"
    )


def test_raf_shim_survives_cleanup_between_steps(
    browser: SeleniumBrowserProvider,
) -> None:
    """End-to-end regression test for the exact bug fixed in this session.

    Uses the REAL ``ScenarioOrchestrator._cleanup_browser_effects`` (not a
    hand-reconstructed approximation) to clean up between two steps, then
    confirms a freshly-injected confetti canvas keeps animating (pixel count
    grows across samples) instead of freezing after a single frame.
    """
    _fresh_navigate(browser, "raf-shim-regression")
    time.sleep(0.3)

    orch = ScenarioOrchestrator.__new__(ScenarioOrchestrator)
    orch._has_injected_effects = True
    orch._cleanup_browser_effects(browser)

    confetti = _BROWSER_EFFECTS["confetti"]()
    confetti.inject(browser.evaluate_js, {"duration": 2.0})

    sample_js = (
        "const c = document.getElementById('__demodsl_confetti');"
        "if (!c) return -1;"
        "const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;"
        "let n = 0;"
        "for (let i = 3; i < d.length; i += 4) { if (d[i] !== 0) n++; }"
        "return n;"
    )
    samples = []
    for delay in (0.1, 0.3, 0.5):
        time.sleep(delay)
        samples.append(browser.evaluate_js(sample_js))

    assert max(samples) > 0, (
        f"confetti canvas never drew any pixel after a real cleanup pass "
        f"(samples={samples}) -- the RAF shim was likely killed by "
        f"_cleanup_browser_effects"
    )


def test_cleanup_resets_body_transform_before_it_self_reverts(
    browser: SeleniumBrowserProvider,
) -> None:
    """Regression test for the second bug found in this session.

    ``rotation_3d``/``perspective_tilt``/``zoom_focus``/``zoom_through``
    mutate ``document.body``'s inline style directly and schedule their OWN
    revert via a JS ``setTimeout``. If a step's wait is shorter than that
    effect's total lifetime, ``_cleanup_browser_effects``'s brute-force timer
    clear cancels the revert before it ever fires -- leaving body's
    transform/clipPath/border stuck for the rest of the recording, so every
    later effect renders against a warped, mostly-black page. Injects
    rotation_3d with a long revert delay, calls the REAL cleanup
    immediately (well before that revert would fire), and asserts body's
    computed style is already back to its untransformed default.
    """
    _fresh_navigate(browser, "body-transform-cleanup-regression")
    time.sleep(0.3)

    orch = ScenarioOrchestrator.__new__(ScenarioOrchestrator)
    orch._has_injected_effects = True

    rotation_3d = _BROWSER_EFFECTS["rotation_3d"]()
    rotation_3d.inject(browser.evaluate_js, {"angle": 35, "duration": 10.0})
    time.sleep(0.2)  # well inside the tilt -- body IS mid-transform here

    orch._cleanup_browser_effects(browser)

    computed = browser.evaluate_js(
        "const cs = getComputedStyle(document.body);"
        "return {transform: cs.transform, clipPath: cs.clipPath};"
    )
    assert computed["transform"] in ("none", ""), (
        f"document.body still transformed after cleanup: {computed} -- "
        f"the effect's own revert setTimeout was cancelled before it fired "
        f"and cleanup didn't reset body itself"
    )
    assert computed["clipPath"] in ("none", ""), (
        f"document.body still clipped after cleanup: {computed}"
    )
