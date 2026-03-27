"""Browser effects — JS/CSS injection for real-time visual effects."""

from __future__ import annotations

from typing import Any

from demodsl.effects.registry import BrowserEffect


class SpotlightEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = params.get("intensity", 0.8)
        evaluate_js(f"""
        (() => {{
            const overlay = document.createElement('div');
            overlay.id = '__demodsl_spotlight';
            overlay.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: radial-gradient(circle at center, transparent 30%, rgba(0,0,0,{intensity}) 70%);
                z-index: 99999; pointer-events: none;
            `;
            document.body.appendChild(overlay);
        }})()
        """)


class HighlightEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = params.get("color", "#FFD700")
        intensity = params.get("intensity", 0.9)
        evaluate_js(f"""
        (() => {{
            const style = document.createElement('style');
            style.id = '__demodsl_highlight';
            style.textContent = `
                * {{ transition: box-shadow 0.3s ease; }}
                :hover {{ box-shadow: 0 0 20px {color}; }}
            `;
            document.head.appendChild(style);
        }})()
        """)


class ConfettiEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_confetti';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const colors = ['#f44336','#e91e63','#9c27b0','#2196f3','#4caf50','#ff9800'];
            const pieces = Array.from({length: 80}, () => ({
                x: Math.random()*canvas.width, y: -20,
                w: Math.random()*8+4, h: Math.random()*6+2,
                color: colors[Math.floor(Math.random()*colors.length)],
                vy: Math.random()*3+2, vx: Math.random()*4-2, rot: Math.random()*360
            }));
            let frame = 0;
            function draw() {
                ctx.clearRect(0,0,canvas.width,canvas.height);
                pieces.forEach(p => {
                    ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);
                    ctx.fillStyle=p.color; ctx.fillRect(-p.w/2,-p.h/2,p.w,p.h);
                    ctx.restore();
                    p.y+=p.vy; p.x+=p.vx; p.rot+=3;
                });
                if (++frame < 120) requestAnimationFrame(draw);
                else canvas.remove();
            }
            draw();
        })()
        """)


class TypewriterEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const style = document.createElement('style');
            style.id = '__demodsl_typewriter';
            style.textContent = `
                input, textarea {
                    caret-color: #333;
                    animation: demodsl-blink 0.7s step-end infinite;
                }
                @keyframes demodsl-blink { 50% { caret-color: transparent; } }
            `;
            document.head.appendChild(style);
        })()
        """)


class GlowEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = params.get("color", "#00FF00")
        evaluate_js(f"""
        (() => {{
            const overlay = document.createElement('div');
            overlay.id = '__demodsl_glow';
            overlay.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                box-shadow: inset 0 0 80px {color}40;
                z-index: 99999; pointer-events: none;
            `;
            document.body.appendChild(overlay);
        }})()
        """)


class ShockwaveEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const el = document.createElement('div');
            el.id = '__demodsl_shockwave';
            el.style.cssText = `
                position:fixed; top:50%; left:50%; width:10px; height:10px;
                border-radius:50%; border:3px solid rgba(255,255,255,0.8);
                transform:translate(-50%,-50%); z-index:99999; pointer-events:none;
                animation: demodsl-shock 0.6s ease-out forwards;
            `;
            const style = document.createElement('style');
            style.textContent = `
                @keyframes demodsl-shock {
                    to { width:600px; height:600px; opacity:0; border-width:1px; }
                }
            `;
            document.head.appendChild(style);
            document.body.appendChild(el);
            setTimeout(() => { el.remove(); style.remove(); }, 700);
        })()
        """)


class SparkleEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_sparkle';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const sparkles = Array.from({length: 40}, () => ({
                x: Math.random()*canvas.width, y: Math.random()*canvas.height,
                size: Math.random()*4+1, alpha: Math.random()
            }));
            let f = 0;
            function draw() {
                ctx.clearRect(0,0,canvas.width,canvas.height);
                sparkles.forEach(s => {
                    s.alpha = 0.5 + 0.5*Math.sin(f*0.1 + s.x);
                    ctx.globalAlpha = s.alpha;
                    ctx.fillStyle = '#FFD700';
                    ctx.beginPath(); ctx.arc(s.x,s.y,s.size,0,Math.PI*2); ctx.fill();
                });
                if (++f < 120) requestAnimationFrame(draw);
                else canvas.remove();
            }
            draw();
        })()
        """)


class CursorTrailEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const trail = [];
            document.addEventListener('mousemove', (e) => {
                const dot = document.createElement('div');
                dot.style.cssText = `
                    position:fixed; left:${e.clientX}px; top:${e.clientY}px;
                    width:8px; height:8px; border-radius:50%;
                    background:rgba(100,150,255,0.7); pointer-events:none;
                    z-index:99999; transition: all 0.5s ease;
                `;
                document.body.appendChild(dot);
                trail.push(dot);
                setTimeout(() => { dot.style.opacity='0'; dot.style.transform='scale(0)'; }, 200);
                setTimeout(() => dot.remove(), 700);
                if (trail.length > 50) trail.shift()?.remove();
            });
        })()
        """)


class RippleEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            document.addEventListener('click', (e) => {
                const ripple = document.createElement('div');
                ripple.style.cssText = `
                    position:fixed; left:${e.clientX-25}px; top:${e.clientY-25}px;
                    width:50px; height:50px; border-radius:50%;
                    border:2px solid rgba(100,150,255,0.8);
                    z-index:99999; pointer-events:none;
                    animation: demodsl-ripple 0.6s ease-out forwards;
                `;
                const style = document.createElement('style');
                style.textContent = '@keyframes demodsl-ripple { to { width:200px;height:200px;left:'+(e.clientX-100)+'px;top:'+(e.clientY-100)+'px;opacity:0; } }';
                document.head.appendChild(style);
                document.body.appendChild(ripple);
                setTimeout(() => { ripple.remove(); style.remove(); }, 700);
            });
        })()
        """)


class NeonGlowEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = params.get("color", "#FF00FF")
        evaluate_js(f"""
        (() => {{
            const overlay = document.createElement('div');
            overlay.id = '__demodsl_neon';
            overlay.style.cssText = `
                position:fixed; top:0; left:0; width:100%; height:100%;
                box-shadow: inset 0 0 60px {color}50, inset 0 0 120px {color}20;
                z-index:99999; pointer-events:none;
            `;
            document.body.appendChild(overlay);
        }})()
        """)


class SuccessCheckmarkEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const el = document.createElement('div');
            el.id = '__demodsl_checkmark';
            el.innerHTML = '✓';
            el.style.cssText = `
                position:fixed; top:50%; left:50%; transform:translate(-50%,-50%) scale(0);
                font-size:120px; color:#4CAF50; z-index:99999; pointer-events:none;
                animation: demodsl-check 0.8s ease-out forwards;
            `;
            const style = document.createElement('style');
            style.textContent = '@keyframes demodsl-check { 50% { transform:translate(-50%,-50%) scale(1.2); } 100% { transform:translate(-50%,-50%) scale(1); opacity:0; } }';
            document.head.appendChild(style);
            document.body.appendChild(el);
            setTimeout(() => { el.remove(); style.remove(); }, 1500);
        })()
        """)


def register_all_browser_effects(registry: Any) -> None:
    """Register all built-in browser effects."""
    registry.register_browser("spotlight", SpotlightEffect())
    registry.register_browser("highlight", HighlightEffect())
    registry.register_browser("confetti", ConfettiEffect())
    registry.register_browser("typewriter", TypewriterEffect())
    registry.register_browser("glow", GlowEffect())
    registry.register_browser("shockwave", ShockwaveEffect())
    registry.register_browser("sparkle", SparkleEffect())
    registry.register_browser("cursor_trail", CursorTrailEffect())
    registry.register_browser("ripple", RippleEffect())
    registry.register_browser("neon_glow", NeonGlowEffect())
    registry.register_browser("success_checkmark", SuccessCheckmarkEffect())
