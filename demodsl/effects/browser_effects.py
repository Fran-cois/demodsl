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
        color = params.get("color", "#00BFFF")
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


class EmojiRainEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_emoji_rain';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const emojis = ['🎉','🔥','❤️','⭐','🚀','💯','👏','✨','🎊','💥'];
            const items = Array.from({length: 50}, () => ({
                x: Math.random()*canvas.width, y: -40 - Math.random()*200,
                emoji: emojis[Math.floor(Math.random()*emojis.length)],
                vy: Math.random()*2.5+1.5, vx: Math.random()*2-1,
                size: Math.random()*16+18, rot: Math.random()*360, vr: Math.random()*4-2
            }));
            let frame = 0;
            function draw() {
                ctx.clearRect(0,0,canvas.width,canvas.height);
                items.forEach(p => {
                    ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);
                    ctx.font = p.size+'px serif'; ctx.textAlign='center'; ctx.textBaseline='middle';
                    ctx.fillText(p.emoji,0,0); ctx.restore();
                    p.y+=p.vy; p.x+=p.vx; p.rot+=p.vr;
                });
                if (++frame < 180) requestAnimationFrame(draw);
                else canvas.remove();
            }
            draw();
        })()
        """)


class FireworksEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_fireworks';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const rockets = [];
            function launch() {
                const x = Math.random()*canvas.width*0.6+canvas.width*0.2;
                const targetY = Math.random()*canvas.height*0.4+50;
                rockets.push({x, y:canvas.height, targetY, vy:-6-Math.random()*3, exploded:false, particles:[]});
            }
            for (let i=0;i<5;i++) setTimeout(launch, i*400);
            let frame=0;
            function draw() {
                ctx.fillStyle='rgba(0,0,0,0.15)'; ctx.fillRect(0,0,canvas.width,canvas.height);
                rockets.forEach(r => {
                    if (!r.exploded) {
                        ctx.fillStyle='#fff'; ctx.beginPath(); ctx.arc(r.x,r.y,2,0,Math.PI*2); ctx.fill();
                        r.y+=r.vy;
                        if (r.y<=r.targetY) {
                            r.exploded=true;
                            const hue=Math.random()*360;
                            for(let i=0;i<40;i++){
                                const a=Math.PI*2*i/40;
                                const sp=Math.random()*3+1;
                                r.particles.push({x:r.x,y:r.y,vx:Math.cos(a)*sp,vy:Math.sin(a)*sp,
                                    life:1,color:'hsl('+Math.round(hue+Math.random()*40)+',100%,60%)'});
                            }
                        }
                    }
                    r.particles.forEach(p=>{
                        ctx.globalAlpha=p.life; ctx.fillStyle=p.color;
                        ctx.beginPath(); ctx.arc(p.x,p.y,2,0,Math.PI*2); ctx.fill();
                        p.x+=p.vx; p.y+=p.vy; p.vy+=0.05; p.life-=0.015;
                    });
                    ctx.globalAlpha=1;
                });
                if(++frame<200) requestAnimationFrame(draw); else canvas.remove();
            }
            draw();
        })()
        """)


class BubblesEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_bubbles';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const bubbles = Array.from({length:35},()=>({
                x:Math.random()*canvas.width, y:canvas.height+Math.random()*100,
                r:Math.random()*20+8, vy:-(Math.random()*1.5+0.5),
                vx:Math.random()*0.6-0.3, wobble:Math.random()*Math.PI*2,
                hue:Math.random()*60+180
            }));
            let frame=0;
            function draw(){
                ctx.clearRect(0,0,canvas.width,canvas.height);
                bubbles.forEach(b=>{
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
                });
                if(++frame<200) requestAnimationFrame(draw); else canvas.remove();
            }
            draw();
        })()
        """)


class SnowEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_snow';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const flakes = Array.from({length:80},()=>({
                x:Math.random()*canvas.width, y:-10-Math.random()*canvas.height,
                r:Math.random()*3+1, vy:Math.random()*1.5+0.5,
                vx:Math.random()*0.8-0.4, wobble:Math.random()*Math.PI*2
            }));
            let frame=0;
            function draw(){
                ctx.clearRect(0,0,canvas.width,canvas.height);
                flakes.forEach(f=>{
                    f.wobble+=0.02;
                    ctx.beginPath(); ctx.arc(f.x+Math.sin(f.wobble)*20,f.y,f.r,0,Math.PI*2);
                    ctx.fillStyle='rgba(255,255,255,'+(0.6+f.r*0.1)+')';
                    ctx.fill();
                    f.y+=f.vy; f.x+=f.vx;
                    if(f.y>canvas.height+10){f.y=-10;f.x=Math.random()*canvas.width;}
                });
                if(++frame<300) requestAnimationFrame(draw); else canvas.remove();
            }
            draw();
        })()
        """)


class StarBurstEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_star_burst';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const cx=canvas.width/2, cy=canvas.height/2;
            const stars=Array.from({length:60},()=>{
                const a=Math.random()*Math.PI*2;
                const sp=Math.random()*5+2;
                return {x:cx,y:cy,vx:Math.cos(a)*sp,vy:Math.sin(a)*sp,
                    size:Math.random()*3+1,hue:Math.random()*60+40,life:1};
            });
            let frame=0;
            function drawStar(x,y,r){
                ctx.beginPath();
                for(let i=0;i<5;i++){
                    const a=Math.PI*2*i/5-Math.PI/2;
                    const ai=a+Math.PI/5;
                    ctx.lineTo(x+Math.cos(a)*r,y+Math.sin(a)*r);
                    ctx.lineTo(x+Math.cos(ai)*r*0.4,y+Math.sin(ai)*r*0.4);
                }
                ctx.closePath(); ctx.fill();
            }
            function draw(){
                ctx.clearRect(0,0,canvas.width,canvas.height);
                stars.forEach(s=>{
                    ctx.globalAlpha=s.life;
                    ctx.fillStyle='hsl('+Math.round(s.hue)+',100%,65%)';
                    drawStar(s.x,s.y,s.size*3);
                    s.x+=s.vx; s.y+=s.vy; s.vy+=0.04; s.life-=0.008;
                });
                ctx.globalAlpha=1;
                if(++frame<140) requestAnimationFrame(draw); else canvas.remove();
            }
            draw();
        })()
        """)


class PartyPopperEffect(BrowserEffect):
    def inject(self, evaluate_js: Any, params: dict[str, Any]) -> None:
        evaluate_js("""
        (() => {
            const canvas = document.createElement('canvas');
            canvas.id = '__demodsl_party_popper';
            canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
            document.body.appendChild(canvas);
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            const colors=['#FF6B6B','#4ECDC4','#45B7D1','#FFA07A','#98D8C8','#F7DC6F','#BB8FCE','#FF69B4'];
            const shapes=['rect','circle','triangle'];
            const origins=[[0,canvas.height],[canvas.width,canvas.height]];
            const items=[];
            origins.forEach(([ox,oy])=>{
                for(let i=0;i<45;i++){
                    const a=-Math.PI/4-Math.random()*Math.PI/2;
                    const sp=Math.random()*7+4;
                    items.push({x:ox,y:oy,vx:Math.cos(a)*sp*(ox===0?1:-1),vy:Math.sin(a)*sp,
                        color:colors[Math.floor(Math.random()*colors.length)],
                        shape:shapes[Math.floor(Math.random()*shapes.length)],
                        size:Math.random()*6+3, rot:Math.random()*360, vr:Math.random()*8-4, life:1});
                }
            });
            let frame=0;
            function draw(){
                ctx.clearRect(0,0,canvas.width,canvas.height);
                items.forEach(p=>{
                    ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180);
                    ctx.globalAlpha=p.life; ctx.fillStyle=p.color;
                    if(p.shape==='rect'){ctx.fillRect(-p.size/2,-p.size/2,p.size,p.size*0.6);}
                    else if(p.shape==='circle'){ctx.beginPath();ctx.arc(0,0,p.size/2,0,Math.PI*2);ctx.fill();}
                    else{ctx.beginPath();ctx.moveTo(0,-p.size/2);ctx.lineTo(p.size/2,p.size/2);ctx.lineTo(-p.size/2,p.size/2);ctx.closePath();ctx.fill();}
                    ctx.restore();
                    p.x+=p.vx; p.y+=p.vy; p.vy+=0.12; p.rot+=p.vr; p.life-=0.006;
                });
                if(++frame<180) requestAnimationFrame(draw); else canvas.remove();
            }
            draw();
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
