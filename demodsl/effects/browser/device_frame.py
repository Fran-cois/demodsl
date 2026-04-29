"""Device frame — overlay a MacBook / iPad / monitor frame around the viewport."""

from __future__ import annotations

from typing import Any

from demodsl.effects.js_builder import iife, inject_style
from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import sanitize_css_color, sanitize_number


class DeviceFrameEffect(BrowserEffect):
    effect_id = "device_frame"

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        device = params.get("text", "macbook")
        if device not in ("macbook", "ipad", "monitor"):
            device = "macbook"
        color = sanitize_css_color(params.get("color", "#1e1e1e"))
        duration = sanitize_number(
            params.get("duration", 4.0), default=4.0, min_val=1.0, max_val=15.0
        )
        lifetime = int(duration * 1000)

        # Device-specific dimensions — generous padding for a realistic look
        configs = {
            "macbook": {
                "bezel_top": 44,
                "bezel_side": 32,
                "bezel_bottom": 60,
                "radius": 16,
                "chin_h": 26,
                "has_notch": True,
            },
            "ipad": {
                "bezel_top": 48,
                "bezel_side": 44,
                "bezel_bottom": 48,
                "radius": 24,
                "chin_h": 0,
                "has_notch": False,
            },
            "monitor": {
                "bezel_top": 36,
                "bezel_side": 28,
                "bezel_bottom": 76,
                "radius": 12,
                "chin_h": 42,
                "has_notch": False,
            },
        }
        cfg = configs[device]

        screen_top = cfg["bezel_top"]
        screen_left = cfg["bezel_side"]
        screen_w = f"calc(100% - {cfg['bezel_side'] * 2}px)"
        screen_h = f"calc(100% - {cfg['bezel_top'] + cfg['bezel_bottom']}px)"

        css = (
            "@keyframes __demodsl_df_fadein {\n"
            "  0%   { opacity: 0; transform: scale(0.95); }\n"
            "  100% { opacity: 1; transform: scale(1); }\n"
            "}\n"
        )

        js = (
            inject_style("__demodsl_df_style", css)
            + "const frame = document.createElement('div');\n"
            "frame.id = '__demodsl_device_frame';\n"
            "frame.style.cssText = `\n"
            "    position:fixed; top:0; left:0; width:100%; height:100%;\n"
            "    z-index:99999; pointer-events:none;\n"
            "    animation: __demodsl_df_fadein 0.5s ease forwards;\n"
            "`;\n"
            # Top bezel
            "const top = document.createElement('div');\n"
            f"top.style.cssText = 'position:absolute; top:0; left:0; width:100%;"
            f" height:{cfg['bezel_top']}px; background:{color};"
            f" border-radius:{cfg['radius']}px {cfg['radius']}px 0 0;';\n"
        )

        if cfg["has_notch"]:
            js += (
                "const notch = document.createElement('div');\n"
                "notch.style.cssText = 'position:absolute; bottom:0; left:50%;"
                " transform:translateX(-50%); width:140px; height:22px;"
                f" background:{color}; border-radius:0 0 10px 10px;';\n"
                "const cam = document.createElement('div');\n"
                "cam.style.cssText = 'position:absolute; top:5px; left:50%;"
                " transform:translateX(-50%); width:7px; height:7px;"
                " border-radius:50%; background:#333; border:1px solid #555;';\n"
                "notch.appendChild(cam);\n"
                "top.appendChild(notch);\n"
            )
        else:
            js += (
                "const cam = document.createElement('div');\n"
                "cam.style.cssText = 'position:absolute; top:50%;"
                " left:50%; transform:translate(-50%,-50%);"
                " width:8px; height:8px; border-radius:50%;"
                " background:#333; border:1px solid #555;';\n"
                "top.appendChild(cam);\n"
            )

        js += (
            "frame.appendChild(top);\n"
            # Side bezels
            "const leftB = document.createElement('div');\n"
            f"leftB.style.cssText = 'position:absolute; top:{screen_top}px; left:0;"
            f" width:{cfg['bezel_side']}px;"
            f" height:{screen_h};"
            f" background:{color};';\n"
            "frame.appendChild(leftB);\n"
            "const rightB = document.createElement('div');\n"
            f"rightB.style.cssText = 'position:absolute; top:{screen_top}px; right:0;"
            f" width:{cfg['bezel_side']}px;"
            f" height:{screen_h};"
            f" background:{color};';\n"
            "frame.appendChild(rightB);\n"
            # Bottom bezel
            "const bot = document.createElement('div');\n"
            f"bot.style.cssText = 'position:absolute; bottom:0; left:0; width:100%;"
            f" height:{cfg['bezel_bottom']}px; background:{color};"
            f" border-radius:0 0 {cfg['radius']}px {cfg['radius']}px;';\n"
        )

        if cfg["chin_h"] > 0:
            js += (
                "const chin = document.createElement('div');\n"
                f"chin.style.cssText = 'position:absolute; top:0; left:50%;"
                f" transform:translateX(-50%); width:40%; height:{cfg['chin_h']}px;"
                f" background:linear-gradient(180deg, {color}, #555);"
                f" border-radius:0 0 6px 6px;';\n"
                "bot.appendChild(chin);\n"
            )

        js += (
            "frame.appendChild(bot);\n"
            # Inner screen border — inset shadow for depth
            "const screenBorder = document.createElement('div');\n"
            f"screenBorder.style.cssText = `\n"
            f"    position:absolute; top:{screen_top}px; left:{screen_left}px;\n"
            f"    width:{screen_w}; height:{screen_h};\n"
            "    border:1px solid rgba(255,255,255,0.06);\n"
            "    box-shadow: inset 0 0 20px rgba(0,0,0,0.3),\n"
            "                inset 0 0 3px rgba(0,0,0,0.4);\n"
            "    border-radius:2px;\n"
            "    pointer-events:none;\n"
            "`;\n"
            "frame.appendChild(screenBorder);\n"
            # Subtle screen glare
            "const glare = document.createElement('div');\n"
            f"glare.style.cssText = `\n"
            f"    position:absolute; top:{screen_top}px; left:{screen_left}px;\n"
            f"    width:{screen_w}; height:{screen_h};\n"
            "    background: linear-gradient(135deg, rgba(255,255,255,0.05) 0%,"
            " transparent 40%);\n"
            "    pointer-events:none;\n"
            "`;\n"
            "frame.appendChild(glare);\n"
            "document.body.appendChild(frame);\n"
            # Cleanup
            f"setTimeout(() => {{\n"
            "    frame.style.transition = 'opacity 0.4s ease';\n"
            "    frame.style.opacity = '0';\n"
            "    setTimeout(() => {\n"
            "        frame.remove();\n"
            "        document.getElementById('__demodsl_df_style')?.remove();\n"
            f"    }}, 500);\n"
            f"}}, {lifetime - 500});\n"
        )
        evaluate_js(iife(js))
