"""JS builder — safe, composable helpers for generating browser-injected JavaScript."""

from __future__ import annotations

_OVERLAY_Z = 99999
_DEMODSL_PREFIX = "__demodsl_"


def effect_dom_id(name: str) -> str:
    """Return the canonical DOM id for an effect: ``__demodsl_{name}``."""
    return f"{_DEMODSL_PREFIX}{name}"


# ── IIFE wrapper ──────────────────────────────────────────────────────────────


def iife(body: str) -> str:
    """Wrap *body* in an immediately-invoked function expression."""
    return f"(() => {{\n{body}\n}})()"


# ── DOM element creation helpers ──────────────────────────────────────────────


def create_overlay(
    dom_id: str, extra_css: str = "", *, z_index: int | None = None
) -> str:
    """Return JS that creates a fixed full-screen ``<div>`` overlay.

    The element gets ``id=dom_id``, ``z-index``, ``pointer-events: none``,
    and is appended to ``document.body``.

    *z_index* defaults to ``_OVERLAY_Z`` (99999).  Pass a lower value to
    render the overlay **behind** sticky/fixed navbars.
    """
    z = z_index if z_index is not None else _OVERLAY_Z
    return (
        f"const overlay = document.createElement('div');\n"
        f"overlay.id = '{dom_id}';\n"
        f"overlay.style.cssText = `\n"
        f"    position: fixed; top: 0; left: 0; width: 100%; height: 100%;\n"
        f"    z-index: {z}; pointer-events: none;\n"
        f"    {extra_css}\n"
        f"`;\n"
        f"document.body.appendChild(overlay);\n"
    )


def create_canvas(dom_id: str, setup_and_draw: str, max_frames: str | int) -> str:
    """Return JS that creates a full-screen ``<canvas>`` with an animation loop.

    *setup_and_draw* must define a ``draw()`` function.  The generated code
    provides ``canvas``, ``ctx`` (2d context), and ``maxF`` (frame budget).
    After *max_frames* the canvas auto-removes itself.
    """
    return (
        f"const canvas = document.createElement('canvas');\n"
        f"canvas.id = '{dom_id}';\n"
        f"canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;"
        f"z-index:{_OVERLAY_Z};pointer-events:none;';\n"
        f"document.body.appendChild(canvas);\n"
        f"canvas.width = window.innerWidth;\n"
        f"canvas.height = window.innerHeight;\n"
        f"const ctx = canvas.getContext('2d');\n"
        f"const maxF = {max_frames};\n"
        f"let frame = 0;\n"
        f"{setup_and_draw}\n"
        f"draw();\n"
    )


def inject_style(dom_id: str, css_text: str) -> str:
    """Return JS that injects a ``<style>`` element into ``<head>``."""
    return (
        f"const style = document.createElement('style');\n"
        f"style.id = '{dom_id}';\n"
        f"style.textContent = `\n{css_text}\n`;\n"
        f"document.head.appendChild(style);\n"
    )


def create_element(tag: str, dom_id: str, css_text: str, inner_html: str = "") -> str:
    """Return JS that creates an arbitrary element with given style and optional HTML."""
    lines = [
        f"const el = document.createElement('{tag}');\n",
        f"el.id = '{dom_id}';\n",
        f"el.style.cssText = `{css_text}`;\n",
    ]
    if inner_html:
        lines.append(f"el.innerHTML = '{inner_html}';\n")
    lines.append("document.body.appendChild(el);\n")
    return "".join(lines)


def auto_remove(var: str, delay_ms: int) -> str:
    """Return JS ``setTimeout`` to remove a DOM element after *delay_ms*."""
    return f"setTimeout(() => {{ {var}.remove(); }}, {delay_ms});\n"


def auto_remove_multi(pairs: list[tuple[str, int]]) -> str:
    """Return JS to remove multiple variables after their respective delays."""
    return "".join(
        f"setTimeout(() => {{ {var}.remove(); }}, {ms});\n" for var, ms in pairs
    )


# ── Cleanup ───────────────────────────────────────────────────────────────────


def cleanup_js(effect_name: str) -> str:
    """Return JS that removes all DOM artefacts for a given effect.

    Removes elements by id ``__demodsl_{effect_name}`` and by className
    ``__demodsl_{effect_name}``.
    """
    dom_id = effect_dom_id(effect_name)
    return iife(
        f"const el = document.getElementById('{dom_id}');\n"
        f"if (el) el.remove();\n"
        f"document.querySelectorAll('.{dom_id}').forEach(e => e.remove());\n"
    )


def cleanup_all_js() -> str:
    """Return JS that removes **all** DemoDSL effect artefacts from the page."""
    return iife(
        f"document.querySelectorAll('[id^=\"{_DEMODSL_PREFIX}\"]').forEach(e => e.remove());\n"
        f"document.querySelectorAll('[class*=\"{_DEMODSL_PREFIX}\"]').forEach(e => e.remove());\n"
    )


# ── Canvas animation loop pattern ────────────────────────────────────────────


def canvas_animation_loop(body: str) -> str:
    """Return a ``draw()`` function body with frame counting and auto-cleanup.

    Use inside *setup_and_draw* passed to :func:`create_canvas`.
    *body* is the per-frame drawing logic (has access to ``ctx``, ``canvas``,
    ``frame``, ``maxF``).
    """
    return (
        f"function draw() {{\n"
        f"    {body}\n"
        f"    if (++frame < maxF) requestAnimationFrame(draw);\n"
        f"    else canvas.remove();\n"
        f"}}\n"
    )


# ── Mouse listener pattern ───────────────────────────────────────────────────


def on_mousemove(body: str) -> str:
    """Return JS registering a ``mousemove`` listener with *body* as handler."""
    return f"document.addEventListener('mousemove', (e) => {{\n{body}\n}});\n"


def on_click(body: str) -> str:
    """Return JS registering a ``click`` listener with *body* as handler."""
    return f"document.addEventListener('click', (e) => {{\n{body}\n}});\n"


def simulate_mouse_path(duration_s: float = 3.0, steps: int = 120) -> str:
    """Return JS that auto-dispatches ``mousemove`` events along a sinusoidal path.

    Useful for demonstrating cursor-trail and interactive effects without
    real user interaction.  The path sweeps left-to-right across the viewport
    with a vertical sine wave.

    Uses ``requestAnimationFrame`` instead of ``setInterval`` to avoid
    timer-throttling in headless Chrome / CDP recording.
    """
    duration_ms = int(duration_s * 1000)
    return (
        f"(function() {{\n"
        f"    const W = window.innerWidth, H = window.innerHeight;\n"
        f"    const total = {steps}, dur = {duration_ms};\n"
        f"    const start = performance.now();\n"
        f"    function tick() {{\n"
        f"        const elapsed = performance.now() - start;\n"
        f"        if (elapsed > dur) return;\n"
        f"        const t = elapsed / dur;\n"
        f"        const x = 100 + t * (W - 200);\n"
        f"        const y = H / 2 + 180 * Math.sin(t * Math.PI * 3);\n"
        f"        document.dispatchEvent(new MouseEvent('mousemove', {{\n"
        f"            clientX: x, clientY: y, bubbles: true\n"
        f"        }}));\n"
        f"        requestAnimationFrame(tick);\n"
        f"    }}\n"
        f"    requestAnimationFrame(tick);\n"
        f"}})()\n"
    )
