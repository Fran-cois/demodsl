"""Skeleton loading — animated placeholder blocks simulating content load."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import inject_style, iife
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class SkeletonLoadingEffect(BrowserEffect):
    effect_id = "skeleton_loading"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#e2e8f0"))
        duration = sanitize_number(
            params.get("duration", 3.0), default=3.0, min_val=1.0, max_val=10.0
        )
        intensity = sanitize_number(
            params.get("intensity", 0.6), default=0.6, min_val=0.1, max_val=1.0
        )
        lifetime = int(duration * 1000)
        shimmer_speed = round(1.0 + (1 - intensity) * 1.5, 1)

        css = (
            "@keyframes __demodsl_skel_shimmer {\n"
            f"  0% {{ background-position: -400px 0; }}\n"
            f"  100% {{ background-position: 400px 0; }}\n"
            "}\n"
            ".__demodsl_skel_block {\n"
            f"  background: linear-gradient(90deg, {color} 25%, {color}44 50%, {color} 75%);\n"
            "  background-size: 800px 100%;\n"
            f"  animation: __demodsl_skel_shimmer {shimmer_speed}s ease-in-out infinite;\n"
            "  border-radius: 6px;\n"
            "  position: absolute;\n"
            "}\n"
        )

        # Generate skeleton block layout: header, avatar, text lines, card
        blocks_js = (
            "const blocks = [\n"
            "  {x:'5%',  y:'8%',  w:'60%', h:'28px'},\n"  # title bar
            "  {x:'5%',  y:'14%', w:'35%', h:'16px'},\n"  # subtitle
            "  {x:'5%',  y:'22%', w:'48px',h:'48px', r:'50%'},\n"  # avatar circle
            "  {x:'12%', y:'22%', w:'25%', h:'14px'},\n"  # name
            "  {x:'12%', y:'26%', w:'18%', h:'10px'},\n"  # subtext
            "  {x:'5%',  y:'36%', w:'90%', h:'12px'},\n"  # text line 1
            "  {x:'5%',  y:'40%', w:'85%', h:'12px'},\n"  # text line 2
            "  {x:'5%',  y:'44%', w:'70%', h:'12px'},\n"  # text line 3
            "  {x:'5%',  y:'52%', w:'42%', h:'120px'},\n"  # card left
            "  {x:'52%', y:'52%', w:'42%', h:'120px'},\n"  # card right
            "  {x:'5%',  y:'78%', w:'90%', h:'12px'},\n"  # bottom text 1
            "  {x:'5%',  y:'82%', w:'60%', h:'12px'},\n"  # bottom text 2
            "];\n"
        )

        js = (
            inject_style("__demodsl_skel_style", css)
            + "const container = document.createElement('div');\n"
            "container.id = '__demodsl_skeleton_loading';\n"
            "container.style.cssText = `\n"
            "    position:fixed; top:0; left:0; width:100%; height:100%;\n"
            f"    background:rgba(255,255,255,{round(0.85 * intensity, 2)});\n"
            "    z-index:99999; pointer-events:none;\n"
            "`;\n"
            "document.body.appendChild(container);\n"
            + blocks_js
            + "blocks.forEach(b => {\n"
            "    const el = document.createElement('div');\n"
            "    el.className = '__demodsl_skel_block';\n"
            "    el.style.left = b.x;\n"
            "    el.style.top = b.y;\n"
            "    el.style.width = b.w;\n"
            "    el.style.height = b.h;\n"
            "    if (b.r) el.style.borderRadius = b.r;\n"
            "    el.style.animationDelay = (Math.random() * 0.4).toFixed(2) + 's';\n"
            "    container.appendChild(el);\n"
            "});\n"
            # Fade out then reveal
            f"setTimeout(() => {{\n"
            "    container.style.transition = 'opacity 0.5s ease';\n"
            "    container.style.opacity = '0';\n"
            "    setTimeout(() => {\n"
            "        container.remove();\n"
            "        const s = document.getElementById('__demodsl_skel_style');\n"
            "        if (s) s.remove();\n"
            f"    }}, 600);\n"
            f"}}, {lifetime - 600});\n"
        )
        evaluate_js(iife(js))
