"""Browser effects — JS/CSS injection for real-time visual effects."""

from __future__ import annotations

from typing import Any

from demodsl.effects.registry import BrowserEffect
from demodsl.effects.sanitize import (
    sanitize_css_color,
    sanitize_css_colors_list,
    sanitize_css_position,
    sanitize_js_string,
    sanitize_number,
)


class SpotlightEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = sanitize_number(
            params.get("intensity", 0.8), default=0.8, min_val=0.0, max_val=1.0
        )
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
        color = sanitize_css_color(params.get("color", "#FFD700"))
        sanitize_number(
            params.get("intensity", 0.9), default=0.9, min_val=0.0, max_val=1.0
        )
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
        duration = sanitize_number(
            params.get("duration", 3), default=3, min_val=0.5, max_val=30
        )
        max_frames = int(duration * 60)
        evaluate_js(f"""
        (() => {{
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_confetti';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const colors = ['#f44336','#e91e63','#9c27b0','#2196f3','#4caf50','#ff9800','#FFEB3B','#00BCD4'];
            const maxF = {max_frames};
            function makePiece() {{
                return {{
                    x: Math.random()*canvas.width, y: -20 - Math.random()*40,
                    w: Math.random()*12+8, h: Math.random()*8+5,
                    color: colors[Math.floor(Math.random()*colors.length)],
                    vy: Math.random()*3+1.5, vx: Math.random()*4-2, rot: Math.random()*360
                }};
            }}
            const pieces = Array.from({{length: 150}}, makePiece);
            let frame = 0;
            function draw() {{
                ctx.clearRect(0,0,canvas.width,canvas.height);
                pieces.forEach(p => {{
                    ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);
                    ctx.fillStyle=p.color; ctx.fillRect(-p.w/2,-p.h/2,p.w,p.h);
                    ctx.restore();
                    p.y+=p.vy; p.x+=p.vx; p.rot+=3;
                    if (p.y > canvas.height + 30) Object.assign(p, makePiece());
                }});
                if (++frame < maxF) requestAnimationFrame(draw);
                else canvas.remove();
            }}
            draw();
        }})()
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
        color = sanitize_css_color(params.get("color", "#00FF00"))
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
        duration = sanitize_number(
            params.get("duration", 3), default=3, min_val=0.5, max_val=30
        )
        max_frames = int(duration * 60)
        evaluate_js(f"""
        (() => {{
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_sparkle';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const maxF = {max_frames};
            const sparkles = Array.from({{length: 80}}, () => ({{
                x: Math.random()*canvas.width, y: Math.random()*canvas.height,
                size: Math.random()*6+2, alpha: Math.random()
            }}));
            let f = 0;
            function draw() {{
                ctx.clearRect(0,0,canvas.width,canvas.height);
                sparkles.forEach(s => {{
                    s.alpha = 0.5 + 0.5*Math.sin(f*0.1 + s.x);
                    ctx.globalAlpha = s.alpha;
                    ctx.fillStyle = '#FFD700';
                    ctx.beginPath(); ctx.arc(s.x,s.y,s.size,0,Math.PI*2); ctx.fill();
                }});
                if (++f < maxF) requestAnimationFrame(draw);
                else canvas.remove();
            }}
            draw();
        }})()
        """)


class CursorTrailEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const trail = [];
            document.addEventListener('mousemove', (e) => {
                const dot = document.createElement('div');
                dot.style.cssText = `
                    position:fixed; left:${e.clientX - 7}px; top:${e.clientY - 7}px;
                    width:14px; height:14px; border-radius:50%;
                    background:rgba(80,130,255,0.85); pointer-events:none;
                    box-shadow: 0 0 8px rgba(80,130,255,0.6);
                    z-index:99999; transition: all 1.2s ease;
                `;
                document.body.appendChild(dot);
                trail.push(dot);
                setTimeout(() => { dot.style.opacity='0'; dot.style.transform='scale(0.3)'; }, 600);
                setTimeout(() => dot.remove(), 1800);
                if (trail.length > 80) trail.shift()?.remove();
            });
        })()
        """)


class CursorTrailRainbowEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            let hue = 0;
            document.addEventListener('mousemove', (e) => {
                hue = (hue + 12) % 360;
                const dot = document.createElement('div');
                dot.className = '__demodsl_trail_rainbow';
                dot.style.cssText = `
                    position:fixed; left:${e.clientX - 9}px; top:${e.clientY - 9}px;
                    width:18px; height:18px; border-radius:50%;
                    background:hsl(${hue},100%,60%); pointer-events:none;
                    box-shadow: 0 0 12px hsl(${hue},100%,50%);
                    z-index:99999; transition: all 1.4s ease;
                `;
                document.body.appendChild(dot);
                setTimeout(() => { dot.style.opacity='0'; dot.style.transform='scale(0.2)'; }, 800);
                setTimeout(() => dot.remove(), 2200);
            });
        })()
        """)


class CursorTrailCometEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            document.addEventListener('mousemove', (e) => {
                for (let i = 0; i < 4; i++) {
                    const dot = document.createElement('div');
                    dot.className = '__demodsl_trail_comet';
                    const size = 20 - i * 5;
                    const alpha = 1.0 - i * 0.2;
                    dot.style.cssText = `
                        position:fixed; left:${e.clientX - size/2}px; top:${e.clientY - size/2 + i*3}px;
                        width:${size}px; height:${size}px; border-radius:50%;
                        background:rgba(255,200,50,${alpha}); pointer-events:none;
                        box-shadow: 0 0 ${8-i*2}px rgba(255,180,0,${alpha*0.6});
                        z-index:99999; transition: all ${0.8 + i*0.3}s ease-out;
                    `;
                    document.body.appendChild(dot);
                    setTimeout(() => { dot.style.opacity='0'; dot.style.transform='scale(0.1) translateY(20px)'; }, 400 + i*100);
                    setTimeout(() => dot.remove(), 1500 + i*300);
                }
            });
        })()
        """)


class CursorTrailGlowEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#00BFFF"))
        evaluate_js(f"""
        (() => {{
            document.addEventListener('mousemove', (e) => {{
                const dot = document.createElement('div');
                dot.className = '__demodsl_trail_glow';
                dot.style.cssText = `
                    position:fixed; left:${{e.clientX}}px; top:${{e.clientY}}px;
                    width:36px; height:36px; border-radius:50%;
                    background:radial-gradient(circle, {color}cc, {color}44, transparent);
                    box-shadow: 0 0 24px {color}aa, 0 0 48px {color}55;
                    pointer-events:none; z-index:99999; transition: all 1.5s ease;
                    transform:translate(-50%,-50%);
                `;
                document.body.appendChild(dot);
                setTimeout(() => {{ dot.style.opacity='0'; dot.style.transform='translate(-50%,-50%) scale(2.5)'; }}, 600);
                setTimeout(() => dot.remove(), 2000);
            }});
        }})()
        """)


class CursorTrailLineEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
            svg.id = '__demodsl_trail_line';
            svg.setAttribute('style','position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;');
            document.body.appendChild(svg);
            const points = [];
            document.addEventListener('mousemove', (e) => {
                points.push({x:e.clientX,y:e.clientY});
                if (points.length > 60) points.shift();
                while (svg.firstChild) svg.removeChild(svg.firstChild);
                if (points.length < 2) return;
                for (let i = 1; i < points.length; i++) {
                    const line = document.createElementNS('http://www.w3.org/2000/svg','line');
                    const alpha = i / points.length;
                    line.setAttribute('x1', points[i-1].x);
                    line.setAttribute('y1', points[i-1].y);
                    line.setAttribute('x2', points[i].x);
                    line.setAttribute('y2', points[i].y);
                    line.setAttribute('stroke', `rgba(80,180,255,${alpha})`);
                    line.setAttribute('stroke-width', `${2 + alpha * 5}`);
                    line.setAttribute('stroke-linecap', 'round');
                    svg.appendChild(line);
                }
            });
        })()
        """)


class CursorTrailParticlesEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            document.addEventListener('mousemove', (e) => {
                for (let i = 0; i < 6; i++) {
                    const p = document.createElement('div');
                    p.className = '__demodsl_trail_particles';
                    const angle = Math.random() * Math.PI * 2;
                    const dist = Math.random() * 35 + 10;
                    const dx = Math.cos(angle) * dist;
                    const dy = Math.sin(angle) * dist;
                    const size = Math.random() * 6 + 4;
                    p.style.cssText = `
                        position:fixed; left:${e.clientX - size/2}px; top:${e.clientY - size/2}px;
                        width:${size}px; height:${size}px; border-radius:50%;
                        background:hsl(${Math.random()*60+180},90%,65%);
                        box-shadow: 0 0 6px hsl(${Math.random()*60+180},80%,50%);
                        pointer-events:none; z-index:99999;
                        transition: all 1.0s ease-out;
                    `;
                    document.body.appendChild(p);
                    requestAnimationFrame(() => {
                        p.style.transform = `translate(${dx}px, ${dy}px)`;
                        p.style.opacity = '0';
                    });
                    setTimeout(() => p.remove(), 1200);
                }
            });
        })()
        """)


class CursorTrailFireEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            document.addEventListener('mousemove', (e) => {
                for (let i = 0; i < 3; i++) {
                    const spark = document.createElement('div');
                    spark.className = '__demodsl_trail_fire';
                    const size = Math.random() * 10 + 6;
                    const hue = Math.random() * 40 + 10;
                    spark.style.cssText = `
                        position:fixed; left:${e.clientX + (Math.random()-0.5)*12}px;
                        top:${e.clientY + (Math.random()-0.5)*12}px;
                        width:${size}px; height:${size}px; border-radius:50%;
                        background:hsl(${hue},100%,55%);
                        box-shadow: 0 0 8px hsl(${hue},100%,50%), 0 0 16px rgba(255,100,0,0.4);
                        pointer-events:none; z-index:99999;
                        transition: all 1.0s ease-out;
                    `;
                    document.body.appendChild(spark);
                    setTimeout(() => {
                        spark.style.transform = `translateY(-${25 + Math.random()*30}px) scale(0)`;
                        spark.style.opacity = '0';
                    }, 100);
                    setTimeout(() => spark.remove(), 1300);
                }
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
        color = sanitize_css_color(params.get("color", "#FF00FF"))
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


class EmojiRainEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 3), default=3, min_val=0.5, max_val=30
        )
        max_frames = int(duration * 60)
        evaluate_js(f"""
        (() => {{
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_emoji_rain';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const emojis = ['🎉','🔥','❤️','⭐','🚀','💯','👏','✨','🎊','💥'];
            const maxF = {max_frames};
            function makeItem() {{
                return {{
                    x: Math.random()*canvas.width, y: -40 - Math.random()*200,
                    emoji: emojis[Math.floor(Math.random()*emojis.length)],
                    vy: Math.random()*2.5+1.5, vx: Math.random()*2-1,
                    size: Math.random()*20+22, rot: Math.random()*360, vr: Math.random()*4-2
                }};
            }}
            const items = Array.from({{length: 60}}, makeItem);
            let frame = 0;
            function draw() {{
                ctx.clearRect(0,0,canvas.width,canvas.height);
                items.forEach(p => {{
                    ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);
                    ctx.font = p.size+'px serif'; ctx.textAlign='center'; ctx.textBaseline='middle';
                    ctx.fillText(p.emoji,0,0); ctx.restore();
                    p.y+=p.vy; p.x+=p.vx; p.rot+=p.vr;
                    if (p.y > canvas.height + 50) Object.assign(p, makeItem());
                }});
                if (++frame < maxF) requestAnimationFrame(draw);
                else canvas.remove();
            }}
            draw();
        }})()
        """)


class FireworksEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 3), default=3, min_val=0.5, max_val=30
        )
        max_frames = int(duration * 60)
        evaluate_js(f"""
        (() => {{
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_fireworks';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const rockets = [];
            const maxF = {max_frames};
            function launch() {{
                const x = Math.random()*canvas.width*0.6+canvas.width*0.2;
                const targetY = Math.random()*canvas.height*0.4+50;
                rockets.push({{x, y:canvas.height, targetY, vy:-6-Math.random()*3, exploded:false, particles:[]}});
            }}
            for (let i=0;i<8;i++) setTimeout(launch, i*300);
            setInterval(launch, 1200);
            let frame=0;
            function draw() {{
                ctx.fillStyle='rgba(0,0,0,0.15)'; ctx.fillRect(0,0,canvas.width,canvas.height);
                rockets.forEach(r => {{
                    if (!r.exploded) {{
                        ctx.fillStyle='#fff'; ctx.beginPath(); ctx.arc(r.x,r.y,3,0,Math.PI*2); ctx.fill();
                        r.y+=r.vy;
                        if (r.y<=r.targetY) {{
                            r.exploded=true;
                            const hue=Math.random()*360;
                            for(let i=0;i<50;i++){{
                                const a=Math.PI*2*i/50;
                                const sp=Math.random()*4+1.5;
                                r.particles.push({{x:r.x,y:r.y,vx:Math.cos(a)*sp,vy:Math.sin(a)*sp,
                                    life:1,color:'hsl('+Math.round(hue+Math.random()*40)+',100%,60%)'}});
                            }}
                        }}
                    }}
                    r.particles.forEach(p=>{{
                        ctx.globalAlpha=p.life; ctx.fillStyle=p.color;
                        ctx.beginPath(); ctx.arc(p.x,p.y,3,0,Math.PI*2); ctx.fill();
                        p.x+=p.vx; p.y+=p.vy; p.vy+=0.05; p.life-=0.012;
                    }});
                    ctx.globalAlpha=1;
                }});
                if(++frame<maxF) requestAnimationFrame(draw); else canvas.remove();
            }}
            draw();
        }})()
        """)


class BubblesEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 3), default=3, min_val=0.5, max_val=30
        )
        max_frames = int(duration * 60)
        evaluate_js(f"""
        (() => {{
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_bubbles';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const maxF = {max_frames};
            function makeBubble() {{
                return {{
                    x:Math.random()*canvas.width, y:canvas.height+Math.random()*100,
                    r:Math.random()*25+10, vy:-(Math.random()*1.5+0.5),
                    vx:Math.random()*0.6-0.3, wobble:Math.random()*Math.PI*2,
                    hue:Math.random()*60+180
                }};
            }}
            const bubbles = Array.from({{length:45}}, makeBubble);
            let frame=0;
            function draw(){{
                ctx.clearRect(0,0,canvas.width,canvas.height);
                bubbles.forEach(b=>{{
                    b.wobble+=0.03;
                    const wx=Math.sin(b.wobble)*15;
                    ctx.beginPath(); ctx.arc(b.x+wx,b.y,b.r,0,Math.PI*2);
                    ctx.fillStyle='hsla('+b.hue+',70%,70%,0.25)';
                    ctx.fill();
                    ctx.strokeStyle='hsla('+b.hue+',80%,80%,0.5)';
                    ctx.lineWidth=1.5; ctx.stroke();
                    ctx.beginPath(); ctx.arc(b.x+wx-b.r*0.3,b.y-b.r*0.3,b.r*0.2,0,Math.PI*2);
                    ctx.fillStyle='rgba(255,255,255,0.6)'; ctx.fill();
                    b.y+=b.vy; b.x+=b.vx;
                    if (b.y < -b.r*2) Object.assign(b, makeBubble());
                }});
                if(++frame<maxF) requestAnimationFrame(draw); else canvas.remove();
            }}
            draw();
        }})()
        """)


class SnowEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 5), default=5, min_val=0.5, max_val=30
        )
        max_frames = int(duration * 60)
        evaluate_js(f"""
        (() => {{
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_snow';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const maxF = {max_frames};
            const flakes = Array.from({{length:100}},()=>({{
                x:Math.random()*canvas.width, y:-10-Math.random()*canvas.height,
                r:Math.random()*4+1.5, vy:Math.random()*1.5+0.5,
                vx:Math.random()*0.8-0.4, wobble:Math.random()*Math.PI*2
            }}));
            let frame=0;
            function draw(){{
                ctx.clearRect(0,0,canvas.width,canvas.height);
                flakes.forEach(f=>{{
                    f.wobble+=0.02;
                    ctx.beginPath(); ctx.arc(f.x+Math.sin(f.wobble)*20,f.y,f.r,0,Math.PI*2);
                    ctx.fillStyle='rgba(255,255,255,'+(0.6+f.r*0.1)+')';
                    ctx.fill();
                    f.y+=f.vy; f.x+=f.vx;
                    if(f.y>canvas.height+10){{f.y=-10;f.x=Math.random()*canvas.width;}}
                }});
                if(++frame<maxF) requestAnimationFrame(draw); else canvas.remove();
            }}
            draw();
        }})()
        """)


class StarBurstEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 3), default=3, min_val=0.5, max_val=30
        )
        max_frames = int(duration * 60)
        evaluate_js(f"""
        (() => {{
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_star_burst';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const cx=canvas.width/2, cy=canvas.height/2;
            const maxF = {max_frames};
            const stars=Array.from({{length:80}},()=>{{
                const a=Math.random()*Math.PI*2;
                const sp=Math.random()*5+2;
                return {{x:cx,y:cy,vx:Math.cos(a)*sp,vy:Math.sin(a)*sp,
                    size:Math.random()*4+2,hue:Math.random()*60+40,life:1}};
            }});
            let frame=0;
            function drawStar(x,y,r){{
                ctx.beginPath();
                for(let i=0;i<5;i++){{
                    const a=Math.PI*2*i/5-Math.PI/2;
                    const ai=a+Math.PI/5;
                    ctx.lineTo(x+Math.cos(a)*r,y+Math.sin(a)*r);
                    ctx.lineTo(x+Math.cos(ai)*r*0.4,y+Math.sin(ai)*r*0.4);
                }}
                ctx.closePath(); ctx.fill();
            }}
            function draw(){{
                ctx.clearRect(0,0,canvas.width,canvas.height);
                stars.forEach(s=>{{
                    ctx.globalAlpha=Math.max(0,s.life);
                    ctx.fillStyle='hsl('+Math.round(s.hue)+',100%,65%)';
                    drawStar(s.x,s.y,s.size*4);
                    s.x+=s.vx; s.y+=s.vy; s.vy+=0.04; s.life-=0.006;
                }});
                ctx.globalAlpha=1;
                if(++frame<maxF) requestAnimationFrame(draw); else canvas.remove();
            }}
            draw();
        }})()
        """)


class PartyPopperEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 3), default=3, min_val=0.5, max_val=30
        )
        max_frames = int(duration * 60)
        evaluate_js(f"""
        (() => {{
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_party_popper';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const maxF = {max_frames};
            const colors=['#FF6B6B','#4ECDC4','#45B7D1','#FFA07A','#98D8C8','#F7DC6F','#BB8FCE','#FF69B4'];
            const shapes=['rect','circle','triangle'];
            const origins=[[0,canvas.height],[canvas.width,canvas.height]];
            const items=[];
            function makeItem(ox, oy) {{
                const a=-Math.PI/4-Math.random()*Math.PI/2;
                const sp=Math.random()*7+4;
                return {{x:ox,y:oy,vx:Math.cos(a)*sp*(ox===0?1:-1),vy:Math.sin(a)*sp,
                    color:colors[Math.floor(Math.random()*colors.length)],
                    shape:shapes[Math.floor(Math.random()*shapes.length)],
                    size:Math.random()*8+5, rot:Math.random()*360, vr:Math.random()*8-4, life:1}};
            }}
            origins.forEach(([ox,oy])=>{{
                for(let i=0;i<55;i++) items.push(makeItem(ox,oy));
            }});
            let frame=0;
            function draw(){{
                ctx.clearRect(0,0,canvas.width,canvas.height);
                items.forEach(p=>{{
                    ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);
                    ctx.globalAlpha=Math.max(0,p.life); ctx.fillStyle=p.color;
                    if(p.shape==='rect'){{ctx.fillRect(-p.size/2,-p.size/2,p.size,p.size*0.6);}}
                    else if(p.shape==='circle'){{ctx.beginPath();ctx.arc(0,0,p.size/2,0,Math.PI*2);ctx.fill();}}
                    else{{ctx.beginPath();ctx.moveTo(0,-p.size/2);ctx.lineTo(p.size/2,p.size/2);ctx.lineTo(-p.size/2,p.size/2);ctx.closePath();ctx.fill();}}
                    ctx.restore();
                    p.x+=p.vx; p.y+=p.vy; p.vy+=0.12; p.rot+=p.vr; p.life-=0.005;
                }});
                if(++frame<maxF) requestAnimationFrame(draw); else canvas.remove();
            }}
            draw();
        }})()
        """)


# ── New browser effects — text / interaction / visual ─────────────────────────


class TextHighlightEffect(BrowserEffect):
    """Animated progressive text highlight (left-to-right colored background)."""

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#FFD700"))
        evaluate_js(f"""
        (() => {{
            const style = document.createElement('style');
            style.id = '__demodsl_text_highlight';
            style.textContent = `
                ::selection {{
                    background: {color}80;
                }}
                .__demodsl_hl {{
                    background: linear-gradient(90deg, {color}60 0%, transparent 100%);
                    background-size: 200% 100%;
                    background-position: 100% 0;
                    animation: demodsl_hl_sweep 1.2s ease forwards;
                }}
                @keyframes demodsl_hl_sweep {{
                    to {{ background-position: 0 0; }}
                }}
            `;
            document.head.appendChild(style);
            document.querySelectorAll('p, h1, h2, h3, li, span, a').forEach(el => {{
                el.classList.add('__demodsl_hl');
            }});
        }})()
        """)


class TextScrambleEffect(BrowserEffect):
    """Hacker-terminal style text scramble that converges to real text."""

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        speed = sanitize_number(
            params.get("speed", 50), default=50, min_val=10, max_val=500
        )
        evaluate_js(f"""
        (() => {{
            const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%&*';
            document.querySelectorAll('h1,h2,h3,p,a,span,button,label').forEach(el => {{
                if (el.children.length > 0 || el.textContent.trim().length === 0) return;
                const original = el.textContent;
                let iteration = 0;
                const interval = setInterval(() => {{
                    el.textContent = original.split('').map((c, i) => {{
                        if (i < iteration) return original[i];
                        return chars[Math.floor(Math.random() * chars.length)];
                    }}).join('');
                    if (iteration >= original.length) clearInterval(interval);
                    iteration += 1 / 3;
                }}, {speed});
            }});
        }})()
        """)


class MagneticHoverEffect(BrowserEffect):
    """Elements subtly follow the cursor when it approaches (parallax hover)."""

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = sanitize_number(
            params.get("intensity", 0.3), default=0.3, min_val=0.0, max_val=2.0
        )
        evaluate_js(f"""
        (() => {{
            const style = document.createElement('style');
            style.id = '__demodsl_magnetic_hover';
            style.textContent = `
                button, a, [role="button"], .btn {{
                    transition: transform 0.3s ease-out;
                }}
            `;
            document.head.appendChild(style);
            const strength = {intensity} * 30;
            document.querySelectorAll('button, a, [role="button"], .btn').forEach(el => {{
                el.addEventListener('mousemove', (e) => {{
                    const rect = el.getBoundingClientRect();
                    const cx = rect.left + rect.width / 2;
                    const cy = rect.top + rect.height / 2;
                    const dx = (e.clientX - cx) / rect.width;
                    const dy = (e.clientY - cy) / rect.height;
                    el.style.transform = `translate(${{dx * strength}}px, ${{dy * strength}}px)`;
                }});
                el.addEventListener('mouseleave', () => {{
                    el.style.transform = 'translate(0, 0)';
                }});
            }});
        }})()
        """)


class TooltipAnnotationEffect(BrowserEffect):
    """Lightweight annotation tooltip on hovered elements."""

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        text = sanitize_js_string(params.get("text", "Click here"))
        color = sanitize_css_color(params.get("color", "#333"))
        evaluate_js(f"""
        (() => {{
            const style = document.createElement('style');
            style.id = '__demodsl_tooltip';
            style.textContent = `
                .__demodsl_tip {{
                    position: absolute; padding: 6px 12px;
                    background: {color}; color: #fff; border-radius: 6px;
                    font-size: 13px; pointer-events: none; z-index: 99999;
                    opacity: 0; transition: opacity 0.25s ease;
                    white-space: nowrap; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                }}
                .__demodsl_tip::after {{
                    content: ''; position: absolute; bottom: -6px; left: 50%;
                    transform: translateX(-50%);
                    border-left: 6px solid transparent;
                    border-right: 6px solid transparent;
                    border-top: 6px solid {color};
                }}
            `;
            document.head.appendChild(style);
            const tip = document.createElement('div');
            tip.className = '__demodsl_tip';
            tip.textContent = '{text}';
            document.body.appendChild(tip);
            document.addEventListener('mouseover', (e) => {{
                const el = e.target.closest('button, a, input, [role="button"]');
                if (!el) {{ tip.style.opacity = '0'; return; }}
                const rect = el.getBoundingClientRect();
                const vw = document.documentElement.clientWidth;
                let lx = rect.left + rect.width / 2 - tip.offsetWidth / 2 + window.scrollX;
                lx = Math.max(0, Math.min(lx, vw - tip.offsetWidth + window.scrollX));
                tip.style.left = lx + 'px';
                tip.style.top = (rect.top - tip.offsetHeight - 10 + window.scrollY) + 'px';
                tip.style.opacity = '1';
            }});
        }})()
        """)


class MorphingBackgroundEffect(BrowserEffect):
    """Slowly morphing animated gradient background."""

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        colors = params.get("colors", ["#667eea", "#764ba2", "#f093fb", "#667eea"])
        safe_colors = (
            sanitize_css_colors_list(colors)
            if isinstance(colors, list)
            else [sanitize_css_color(colors)]
        )
        colors_css = ", ".join(safe_colors)
        evaluate_js(f"""
        (() => {{
            const style = document.createElement('style');
            style.id = '__demodsl_morphing_bg';
            style.textContent = `
                body::before {{
                    content: ''; position: fixed; top: 0; left: 0;
                    width: 100%; height: 100%; z-index: -1;
                    background: linear-gradient(135deg, {colors_css});
                    background-size: 400% 400%;
                    animation: demodsl_morph 8s ease infinite;
                }}
                @keyframes demodsl_morph {{
                    0%   {{ background-position: 0% 50%; }}
                    50%  {{ background-position: 100% 50%; }}
                    100% {{ background-position: 0% 50%; }}
                }}
            `;
            document.head.appendChild(style);
        }})()
        """)


class MatrixRainEffect(BrowserEffect):
    """Falling characters Matrix-style rain overlay."""

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#00FF41"))
        density = sanitize_number(
            params.get("density", 0.6), default=0.6, min_val=0.1, max_val=2.0
        )
        speed = sanitize_number(
            params.get("speed", 1.0), default=1.0, min_val=0.1, max_val=5.0
        )
        max_frames = int(
            sanitize_number(
                params.get("duration", 5), default=5, min_val=0.5, max_val=30
            )
            * 60
        )
        evaluate_js(f"""
        (() => {{
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_matrix_rain';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const fontSize = 14;
            const cols = Math.floor(canvas.width / fontSize * {density});
            const drops = Array.from({{length: cols}}, () => Math.random() * -100);
            const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZアイウエオカキクケコ0123456789@#$%^&*';
            const maxF = {max_frames};
            let frame = 0;
            function draw() {{
                ctx.fillStyle = 'rgba(0,0,0,0.05)';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.fillStyle = '{color}';
                ctx.font = fontSize + 'px monospace';
                for (let i = 0; i < cols; i++) {{
                    const ch = chars[Math.floor(Math.random() * chars.length)];
                    const x = (i / {density}) * fontSize;
                    ctx.fillText(ch, x, drops[i] * fontSize);
                    if (drops[i] * fontSize > canvas.height && Math.random() > 0.975)
                        drops[i] = 0;
                    drops[i] += {speed};
                }}
                if (++frame < maxF) requestAnimationFrame(draw);
                else canvas.remove();
            }}
            draw();
        }})()
        """)


class FrostedGlassEffect(BrowserEffect):
    """Frosted glass / backdrop-filter blur on targeted elements."""

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        intensity = sanitize_number(
            params.get("intensity", 8), default=8, min_val=0, max_val=50
        )
        evaluate_js(f"""
        (() => {{
            const style = document.createElement('style');
            style.id = '__demodsl_frosted_glass';
            style.textContent = `
                .demodsl-frost, nav, header, .card, .modal, [class*="header"], [class*="nav"] {{
                    backdrop-filter: blur({intensity}px) saturate(180%) !important;
                    -webkit-backdrop-filter: blur({intensity}px) saturate(180%) !important;
                    background: rgba(255,255,255,0.25) !important;
                    border: 1px solid rgba(255,255,255,0.18) !important;
                }}
            `;
            document.head.appendChild(style);
        }})()
        """)


# ── New browser effects — utility overlays ────────────────────────────────────


class ProgressBarEffect(BrowserEffect):
    """Animated progress bar synchronized to demo step timing."""

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        color = sanitize_css_color(params.get("color", "#6366f1"))
        position = sanitize_css_position(
            params.get("position", "top"), allowed=frozenset({"top", "bottom"})
        )
        height = sanitize_number(
            params.get("intensity", 4), default=4, min_val=1, max_val=20
        )
        pos_css = "top:0" if position == "top" else "bottom:0"
        evaluate_js(f"""
        (() => {{
            const bar = document.createElement('div');
            bar.id = '__demodsl_progress_bar';
            bar.style.cssText = `
                position:fixed; left:0; {pos_css};
                width:0%; height:{height}px;
                background: linear-gradient(90deg, {color}, {color}cc);
                z-index:99999; pointer-events:none;
                transition: width 0.4s ease;
                box-shadow: 0 0 8px {color}66;
            `;
            document.body.appendChild(bar);
            window.__demodsl_progress_set = (pct) => {{
                bar.style.width = Math.min(100, Math.max(0, pct)) + '%';
            }};
        }})()
        """)


class CountdownTimerEffect(BrowserEffect):
    """Animated countdown timer overlay."""

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        duration = sanitize_number(
            params.get("duration", 10), default=10, min_val=1, max_val=3600
        )
        color = sanitize_css_color(params.get("color", "#FFFFFF"))
        position = sanitize_css_position(
            params.get("position", "top-right"),
            allowed=frozenset({"top-right", "top-left", "bottom-right", "bottom-left"}),
        )
        pos_map = {
            "top-right": "top:20px;right:20px",
            "top-left": "top:20px;left:20px",
            "bottom-right": "bottom:20px;right:20px",
            "bottom-left": "bottom:20px;left:20px",
        }
        pos_css = pos_map.get(position, pos_map["top-right"])
        evaluate_js(f"""
        (() => {{
            const timer = document.createElement('div');
            timer.id = '__demodsl_countdown';
            timer.style.cssText = `
                position:fixed; {pos_css};
                font-size:28px; font-weight:bold; font-family:monospace;
                color:{color}; z-index:99999; pointer-events:none;
                background:rgba(0,0,0,0.5); padding:8px 16px;
                border-radius:8px; min-width:60px; text-align:center;
            `;
            document.body.appendChild(timer);
            let remaining = {duration};
            function tick() {{
                const m = Math.floor(remaining / 60);
                const s = Math.floor(remaining % 60);
                timer.textContent = (m > 0 ? m + ':' : '') + String(s).padStart(2, '0');
                if (remaining <= 0) {{ timer.remove(); return; }}
                remaining -= 1;
                setTimeout(tick, 1000);
            }}
            tick();
        }})()
        """)


class CalloutArrowEffect(BrowserEffect):
    """Animated arrow pointing at a target area with a label."""

    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        text = sanitize_js_string(params.get("text", "Look here!"))
        color = sanitize_css_color(params.get("color", "#ef4444"))
        target_x = sanitize_number(
            params.get("target_x", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        target_y = sanitize_number(
            params.get("target_y", 0.5), default=0.5, min_val=0.0, max_val=1.0
        )
        evaluate_js(f"""
        (() => {{
            const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
            svg.id = '__demodsl_callout_arrow';
            svg.setAttribute('style','position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;');
            svg.innerHTML = `
                <defs>
                    <marker id="dsl-arrowhead" markerWidth="10" markerHeight="7"
                        refX="10" refY="3.5" orient="auto">
                        <polygon points="0 0, 10 3.5, 0 7" fill="{color}"/>
                    </marker>
                </defs>
            `;
            document.body.appendChild(svg);
            const tx = window.innerWidth * {target_x};
            const ty = window.innerHeight * {target_y};
            const sx = tx + (tx > window.innerWidth / 2 ? 120 : -120);
            const sy = ty - 80;
            const line = document.createElementNS('http://www.w3.org/2000/svg','line');
            line.setAttribute('x1', sx); line.setAttribute('y1', sy);
            line.setAttribute('x2', tx); line.setAttribute('y2', ty);
            line.setAttribute('stroke', '{color}');
            line.setAttribute('stroke-width', '3');
            line.setAttribute('marker-end', 'url(#dsl-arrowhead)');
            line.setAttribute('stroke-dasharray', '200');
            line.setAttribute('stroke-dashoffset', '200');
            line.style.transition = 'stroke-dashoffset 0.6s ease';
            svg.appendChild(line);
            const label = document.createElement('div');
            label.id = '__demodsl_callout_label';
            label.textContent = `{text}`;
            label.style.cssText = `
                position:fixed; left:${{sx - 60}}px; top:${{sy - 36}}px;
                background:{color}; color:#fff; padding:6px 14px;
                border-radius:6px; font-size:14px; font-weight:600;
                z-index:99999; pointer-events:none; opacity:0;
                transition: opacity 0.4s ease 0.3s;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            `;
            document.body.appendChild(label);
            requestAnimationFrame(() => {{
                line.setAttribute('stroke-dashoffset', '0');
                label.style.opacity = '1';
            }});
            setTimeout(() => {{ svg.remove(); label.remove(); }}, 4000);
        }})()
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
    registry.register_browser("cursor_trail_rainbow", CursorTrailRainbowEffect())
    registry.register_browser("cursor_trail_comet", CursorTrailCometEffect())
    registry.register_browser("cursor_trail_glow", CursorTrailGlowEffect())
    registry.register_browser("cursor_trail_line", CursorTrailLineEffect())
    registry.register_browser("cursor_trail_particles", CursorTrailParticlesEffect())
    registry.register_browser("cursor_trail_fire", CursorTrailFireEffect())
    registry.register_browser("ripple", RippleEffect())
    registry.register_browser("neon_glow", NeonGlowEffect())
    registry.register_browser("success_checkmark", SuccessCheckmarkEffect())
    registry.register_browser("emoji_rain", EmojiRainEffect())
    registry.register_browser("fireworks", FireworksEffect())
    registry.register_browser("bubbles", BubblesEffect())
    registry.register_browser("snow", SnowEffect())
    registry.register_browser("star_burst", StarBurstEffect())
    registry.register_browser("party_popper", PartyPopperEffect())
    # New text / interaction / visual effects
    registry.register_browser("text_highlight", TextHighlightEffect())
    registry.register_browser("text_scramble", TextScrambleEffect())
    registry.register_browser("magnetic_hover", MagneticHoverEffect())
    registry.register_browser("tooltip_annotation", TooltipAnnotationEffect())
    registry.register_browser("morphing_background", MorphingBackgroundEffect())
    registry.register_browser("matrix_rain", MatrixRainEffect())
    registry.register_browser("frosted_glass", FrostedGlassEffect())
    # New utility overlays
    registry.register_browser("progress_bar", ProgressBarEffect())
    registry.register_browser("countdown_timer", CountdownTimerEffect())
    registry.register_browser("callout_arrow", CalloutArrowEffect())
