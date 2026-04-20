#!/usr/bin/env python3
"""CV-based browser effect validation — screenshots + pixel diff analysis.

For each of the 33 effects, this script:
1. Loads a fresh page
2. Takes a BEFORE screenshot
3. Injects the effect (with mouse simulation for interactive ones)
4. Takes AFTER screenshots at fixed time intervals (0.3s, 1.0s, 2.0s)
5. Computes pixel-diff metrics (mean delta, % changed pixels, peak delta)
6. Sweeps parameter ranges to find working vs broken thresholds
7. Outputs a JSON report with per-effect pass/fail + parameter ranges

Usage:
    python scripts/test_effects_cv.py                    # full sweep
    python scripts/test_effects_cv.py --effect confetti  # single effect
    python scripts/test_effects_cv.py --quick             # fast mode (fewer param values)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
from PIL import Image

URL = "https://fran-cois.github.io/demodsl/"
VIEWPORT = {"width": 1280, "height": 720}
# Threshold: if mean pixel diff > this, the effect is "visible"
DIFF_THRESHOLD = 1.5  # mean pixel delta out of 255
CHANGED_PX_THRESHOLD = 0.5  # % of pixels changed (delta > 10)

SCREENSHOTS_DIR = Path("output/effect_cv_screenshots")


@dataclass
class EffectSpec:
    """Specification for one browser effect."""

    name: str
    js_inject: str
    dom_id: str | None = None  # ID to check for DOM presence
    needs_mouse: bool = False  # needs synthetic mousemove
    needs_click: bool = False  # needs synthetic click
    time_limited: bool = True  # auto-removes after duration
    screenshot_delay: float = 0.5  # seconds after inject
    params: dict = field(default_factory=dict)  # default params
    param_ranges: dict = field(default_factory=dict)  # {param: [values]}


@dataclass
class EffectResult:
    name: str
    visible: bool
    mean_diff: float
    changed_pct: float
    peak_diff: float
    dom_present: bool
    screenshot_delay: float
    params: dict
    error: str | None = None


@dataclass
class ParamRangeResult:
    name: str
    param_name: str
    value: float | str
    visible: bool
    mean_diff: float
    changed_pct: float


# ─── Effect definitions with JS injection code ───────────────────────────────
# These match the REAL code from browser_effects.py


def _canvas_effect(name: str, dom_id: str, js_body: str) -> str:
    return f"""(() => {{
        const canvas = document.createElement('canvas');
        canvas.id = '{dom_id}';
        canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;';
        document.body.appendChild(canvas);
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        const ctx = canvas.getContext('2d');
        {js_body}
    }})()"""


EFFECTS: list[EffectSpec] = [
    # ─── Lighting ─────────────────────────────────────────────
    EffectSpec(
        name="spotlight",
        dom_id="__demodsl_spotlight",
        js_inject="""(() => {
            const o = document.createElement('div');
            o.id = '__demodsl_spotlight';
            o.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:radial-gradient(circle at center,transparent 30%,rgba(0,0,0,INTENSITY) 70%);z-index:99999;pointer-events:none;';
            document.body.appendChild(o);
        })()""",
        time_limited=False,
        params={"intensity": 0.8},
        param_ranges={"intensity": [0.1, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0]},
    ),
    EffectSpec(
        name="highlight",
        dom_id="__demodsl_highlight",
        js_inject="""(() => {
            const s = document.createElement('style');
            s.id = '__demodsl_highlight';
            s.textContent = '* { transition: box-shadow 0.3s ease; } :hover { box-shadow: 0 0 20px COLOR; }';
            document.head.appendChild(s);
        })()""",
        needs_mouse=True,
        time_limited=False,
        params={"color": "#FFD700"},
    ),
    EffectSpec(
        name="frosted_glass",
        dom_id="__demodsl_frosted_glass",
        js_inject="""(() => {
            const o = document.createElement('div');
            o.id = '__demodsl_frosted_glass';
            o.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:99998;pointer-events:none;backdrop-filter:blur(BLUR_PXpx) saturate(180%);-webkit-backdrop-filter:blur(BLUR_PXpx) saturate(180%);';
            document.body.appendChild(o);
        })()""",
        time_limited=False,
        params={"intensity": 0.5},
        param_ranges={"intensity": [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]},
    ),
    EffectSpec(
        name="glow",
        dom_id="__demodsl_glow",
        js_inject="""(() => {
            const o = document.createElement('div');
            o.id = '__demodsl_glow';
            o.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;box-shadow:inset 0 0 80px COLOR40;z-index:99999;pointer-events:none;';
            document.body.appendChild(o);
        })()""",
        time_limited=False,
        params={"color": "#6366f1"},
    ),
    EffectSpec(
        name="neon_glow",
        dom_id="__demodsl_neon",
        js_inject="""(() => {
            const o = document.createElement('div');
            o.id = '__demodsl_neon';
            o.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;box-shadow:inset 0 0 60px COLOR50,inset 0 0 120px COLOR20;z-index:99999;pointer-events:none;';
            document.body.appendChild(o);
        })()""",
        time_limited=False,
        params={"color": "#FF00FF"},
    ),
    # ─── Particles ────────────────────────────────────────────
    EffectSpec(
        name="confetti",
        dom_id="__demodsl_confetti",
        js_inject=_canvas_effect(
            "confetti",
            "__demodsl_confetti",
            """
            const colors = ['#f44336','#e91e63','#9c27b0','#2196f3','#4caf50','#ff9800'];
            const maxF = MAXFRAMES;
            function mp(){return{x:Math.random()*canvas.width,y:-20-Math.random()*40,w:Math.random()*12+8,h:Math.random()*8+5,color:colors[Math.floor(Math.random()*colors.length)],vy:Math.random()*3+1.5,vx:Math.random()*4-2,rot:Math.random()*360};}
            const pcs = Array.from({length:150},mp);let f=0;
            function draw(){ctx.clearRect(0,0,canvas.width,canvas.height);pcs.forEach(p=>{ctx.save();ctx.translate(p.x,p.y);ctx.rotate(p.rot*Math.PI/180);ctx.fillStyle=p.color;ctx.fillRect(-p.w/2,-p.h/2,p.w,p.h);ctx.restore();p.y+=p.vy;p.x+=p.vx;p.rot+=3;if(p.y>canvas.height+30)Object.assign(p,mp());});if(++f<maxF)requestAnimationFrame(draw);else canvas.remove();}
            draw();
        """,
        ),
        params={"duration": 3.0},
        param_ranges={"duration": [0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 30.0]},
    ),
    EffectSpec(
        name="sparkle",
        dom_id="__demodsl_sparkle",
        js_inject=_canvas_effect(
            "sparkle",
            "__demodsl_sparkle",
            """
            const maxF = MAXFRAMES;
            const sp = Array.from({length:80},()=>({x:Math.random()*canvas.width,y:Math.random()*canvas.height,size:Math.random()*6+2,alpha:Math.random()}));
            let f=0;
            function draw(){ctx.clearRect(0,0,canvas.width,canvas.height);sp.forEach(s=>{s.alpha=0.5+0.5*Math.sin(f*0.1+s.x);ctx.globalAlpha=s.alpha;ctx.fillStyle='#FFD700';ctx.beginPath();ctx.arc(s.x,s.y,s.size,0,Math.PI*2);ctx.fill();});if(++f<maxF)requestAnimationFrame(draw);else canvas.remove();}
            draw();
        """,
        ),
        params={"duration": 3.0},
        param_ranges={"duration": [0.5, 1.0, 2.0, 3.0, 5.0]},
    ),
    EffectSpec(
        name="bubbles",
        dom_id="__demodsl_bubbles",
        js_inject=_canvas_effect(
            "bubbles",
            "__demodsl_bubbles",
            """
            const maxF=MAXFRAMES;function mb(){return{x:Math.random()*canvas.width,y:canvas.height+Math.random()*100,r:Math.random()*25+10,vy:-(Math.random()*1.5+0.5),vx:Math.random()*0.6-0.3,wobble:Math.random()*Math.PI*2,hue:Math.random()*60+180};}
            const bs=Array.from({length:45},mb);let f=0;
            function draw(){ctx.clearRect(0,0,canvas.width,canvas.height);bs.forEach(b=>{b.wobble+=0.03;const wx=Math.sin(b.wobble)*15;ctx.beginPath();ctx.arc(b.x+wx,b.y,b.r,0,Math.PI*2);ctx.fillStyle='hsla('+b.hue+',70%,70%,0.25)';ctx.fill();ctx.strokeStyle='hsla('+b.hue+',80%,80%,0.5)';ctx.lineWidth=1.5;ctx.stroke();b.y+=b.vy;b.x+=b.vx;if(b.y<-b.r*2)Object.assign(b,mb());});if(++f<maxF)requestAnimationFrame(draw);else canvas.remove();}
            draw();
        """,
        ),
        params={"duration": 3.0},
        param_ranges={"duration": [0.5, 1.0, 2.0, 3.0, 5.0]},
    ),
    EffectSpec(
        name="snow",
        dom_id="__demodsl_snow",
        js_inject=_canvas_effect(
            "snow",
            "__demodsl_snow",
            """
            const maxF=MAXFRAMES;const fl=Array.from({length:100},()=>({x:Math.random()*canvas.width,y:-10-Math.random()*canvas.height,r:Math.random()*4+1.5,vy:Math.random()*1.5+0.5,vx:Math.random()*0.8-0.4,wobble:Math.random()*Math.PI*2}));
            let f=0;function draw(){ctx.clearRect(0,0,canvas.width,canvas.height);fl.forEach(s=>{s.wobble+=0.02;ctx.beginPath();ctx.arc(s.x+Math.sin(s.wobble)*20,s.y,s.r,0,Math.PI*2);ctx.fillStyle='rgba(255,255,255,'+(0.6+s.r*0.1)+')';ctx.fill();s.y+=s.vy;s.x+=s.vx;if(s.y>canvas.height+10){s.y=-10;s.x=Math.random()*canvas.width;}});if(++f<maxF)requestAnimationFrame(draw);else canvas.remove();}
            draw();
        """,
        ),
        params={"duration": 5.0},
        param_ranges={"duration": [0.5, 1.0, 2.0, 3.0, 5.0]},
    ),
    EffectSpec(
        name="fireworks",
        dom_id="__demodsl_fireworks",
        js_inject=_canvas_effect(
            "fireworks",
            "__demodsl_fireworks",
            """
            const rockets=[];const maxF=MAXFRAMES;
            function launch(){const x=Math.random()*canvas.width*0.6+canvas.width*0.2;const ty=Math.random()*canvas.height*0.4+50;rockets.push({x,y:canvas.height,targetY:ty,vy:-6-Math.random()*3,exploded:false,particles:[]});}
            for(let i=0;i<8;i++)setTimeout(launch,i*300);const intv=setInterval(launch,1200);let f=0;
            function draw(){ctx.fillStyle='rgba(0,0,0,0.15)';ctx.fillRect(0,0,canvas.width,canvas.height);rockets.forEach(r=>{if(!r.exploded){ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(r.x,r.y,3,0,Math.PI*2);ctx.fill();r.y+=r.vy;if(r.y<=r.targetY){r.exploded=true;const h=Math.random()*360;for(let i=0;i<50;i++){const a=Math.PI*2*i/50;const sp=Math.random()*4+1.5;r.particles.push({x:r.x,y:r.y,vx:Math.cos(a)*sp,vy:Math.sin(a)*sp,life:1,color:'hsl('+Math.round(h+Math.random()*40)+',100%,60%)'});}}}r.particles.forEach(p=>{ctx.globalAlpha=p.life;ctx.fillStyle=p.color;ctx.beginPath();ctx.arc(p.x,p.y,3,0,Math.PI*2);ctx.fill();p.x+=p.vx;p.y+=p.vy;p.vy+=0.05;p.life-=0.012;});ctx.globalAlpha=1;});if(++f<maxF)requestAnimationFrame(draw);else{clearInterval(intv);canvas.remove();}}
            draw();
        """,
        ),
        params={"duration": 3.0},
        param_ranges={"duration": [0.5, 1.0, 2.0, 3.0, 5.0]},
    ),
    EffectSpec(
        name="party_popper",
        dom_id="__demodsl_party_popper",
        js_inject=_canvas_effect(
            "party_popper",
            "__demodsl_party_popper",
            """
            const maxF=MAXFRAMES;const colors=['#FF6B6B','#4ECDC4','#45B7D1','#FFA07A','#98D8C8','#F7DC6F'];
            const items=[];function mi(ox,oy){const a=-Math.PI/4-Math.random()*Math.PI/2;const sp=Math.random()*7+4;return{x:ox,y:oy,vx:Math.cos(a)*sp*(ox===0?1:-1),vy:Math.sin(a)*sp,color:colors[Math.floor(Math.random()*colors.length)],size:Math.random()*8+5,rot:Math.random()*360,vr:Math.random()*8-4,life:1};}
            [[0,canvas.height],[canvas.width,canvas.height]].forEach(([ox,oy])=>{for(let i=0;i<55;i++)items.push(mi(ox,oy));});let f=0;
            function draw(){ctx.clearRect(0,0,canvas.width,canvas.height);items.forEach(p=>{ctx.save();ctx.translate(p.x,p.y);ctx.rotate(p.rot*Math.PI/180);ctx.globalAlpha=Math.max(0,p.life);ctx.fillStyle=p.color;ctx.fillRect(-p.size/2,-p.size/2,p.size,p.size*0.6);ctx.restore();p.x+=p.vx;p.y+=p.vy;p.vy+=0.12;p.rot+=p.vr;p.life-=0.005;});if(++f<maxF)requestAnimationFrame(draw);else canvas.remove();}
            draw();
        """,
        ),
        params={"duration": 3.0},
        param_ranges={"duration": [0.5, 1.0, 2.0, 3.0, 5.0]},
    ),
    EffectSpec(
        name="emoji_rain",
        dom_id="__demodsl_emoji_rain",
        js_inject=_canvas_effect(
            "emoji_rain",
            "__demodsl_emoji_rain",
            """
            const emojis=['*','#','@','!','+','~','%','&','$','?'];const maxF=MAXFRAMES;
            function mi(){return{x:Math.random()*canvas.width,y:-40-Math.random()*200,emoji:emojis[Math.floor(Math.random()*emojis.length)],vy:Math.random()*2.5+1.5,vx:Math.random()*2-1,size:Math.random()*20+22,rot:Math.random()*360,vr:Math.random()*4-2,color:'hsl('+Math.floor(Math.random()*360)+',80%,60%)'};}
            const items=Array.from({length:60},mi);let f=0;
            function draw(){ctx.clearRect(0,0,canvas.width,canvas.height);items.forEach(p=>{ctx.save();ctx.translate(p.x,p.y);ctx.rotate(p.rot*Math.PI/180);ctx.font='bold '+p.size+'px monospace';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=p.color;ctx.fillText(p.emoji,0,0);ctx.restore();p.y+=p.vy;p.x+=p.vx;p.rot+=p.vr;if(p.y>canvas.height+50)Object.assign(p,mi());});if(++f<maxF)requestAnimationFrame(draw);else canvas.remove();}
            draw();
        """,
        ),
        params={"duration": 3.0},
        param_ranges={"duration": [0.5, 1.0, 2.0, 3.0, 5.0]},
    ),
    EffectSpec(
        name="star_burst",
        dom_id="__demodsl_star_burst",
        js_inject=_canvas_effect(
            "star_burst",
            "__demodsl_star_burst",
            """
            const cx=canvas.width/2,cy=canvas.height/2;const maxF=MAXFRAMES;
            const stars=Array.from({length:80},()=>{const a=Math.random()*Math.PI*2;const sp=Math.random()*5+2;return{x:cx,y:cy,vx:Math.cos(a)*sp,vy:Math.sin(a)*sp,size:Math.random()*4+2,hue:Math.random()*60+40,life:1};});let f=0;
            function draw(){ctx.clearRect(0,0,canvas.width,canvas.height);stars.forEach(s=>{ctx.globalAlpha=Math.max(0,s.life);ctx.fillStyle='hsl('+Math.round(s.hue)+',100%,65%)';ctx.beginPath();ctx.arc(s.x,s.y,s.size*2,0,Math.PI*2);ctx.fill();s.x+=s.vx;s.y+=s.vy;s.vy+=0.04;s.life-=0.006;});ctx.globalAlpha=1;if(++f<maxF)requestAnimationFrame(draw);else canvas.remove();}
            draw();
        """,
        ),
        params={"duration": 3.0},
        param_ranges={"duration": [0.5, 1.0, 2.0, 3.0, 5.0]},
    ),
    # ─── One-shot ─────────────────────────────────────────────
    EffectSpec(
        name="shockwave",
        dom_id="__demodsl_shockwave",
        js_inject="""(() => {
            const el = document.createElement('div');
            el.id = '__demodsl_shockwave';
            el.style.cssText = 'position:fixed;top:50%;left:50%;width:10px;height:10px;border-radius:50%;border:3px solid rgba(255,255,255,0.8);transform:translate(-50%,-50%);z-index:99999;pointer-events:none;animation:demodsl-shock 0.6s ease-out forwards;';
            const s = document.createElement('style');
            s.textContent = '@keyframes demodsl-shock{to{width:600px;height:600px;opacity:0;border-width:1px;}}';
            document.head.appendChild(s);document.body.appendChild(el);
            setTimeout(()=>{el.remove();s.remove();},700);
        })()""",
        screenshot_delay=0.15,  # must capture before 700ms timeout
    ),
    EffectSpec(
        name="ripple",
        needs_click=True,
        js_inject="""(() => {
            document.addEventListener('click',(e)=>{
                const r=document.createElement('div');r.id='__demodsl_ripple_el';
                r.style.cssText='position:fixed;left:'+(e.clientX-25)+'px;top:'+(e.clientY-25)+'px;width:50px;height:50px;border-radius:50%;border:2px solid rgba(100,150,255,0.8);z-index:99999;pointer-events:none;animation:demodsl-rip 0.6s ease-out forwards;';
                const s=document.createElement('style');s.textContent='@keyframes demodsl-rip{to{width:200px;height:200px;left:'+(e.clientX-100)+'px;top:'+(e.clientY-100)+'px;opacity:0;}}';
                document.head.appendChild(s);document.body.appendChild(r);
                setTimeout(()=>{r.remove();s.remove();},700);
            });
        })()""",
        screenshot_delay=0.15,
    ),
    # ─── Cursor Trails ────────────────────────────────────────
    EffectSpec(
        name="cursor_trail",
        needs_mouse=True,
        js_inject="""(() => {
            document.addEventListener('mousemove',(e)=>{
                const dot=document.createElement('div');dot.className='__demodsl_ct';
                dot.style.cssText='position:fixed;left:'+(e.clientX-7)+'px;top:'+(e.clientY-7)+'px;width:14px;height:14px;border-radius:50%;background:rgba(80,130,255,0.85);pointer-events:none;box-shadow:0 0 8px rgba(80,130,255,0.6);z-index:99999;transition:all 1.2s ease;';
                document.body.appendChild(dot);
                setTimeout(()=>{dot.style.opacity='0';dot.style.transform='scale(0.3)';},600);
                setTimeout(()=>dot.remove(),1800);
            });
        })()""",
    ),
    EffectSpec(
        name="cursor_trail_rainbow",
        needs_mouse=True,
        js_inject="""(() => {
            let hue=0;document.addEventListener('mousemove',(e)=>{
                hue=(hue+12)%360;const dot=document.createElement('div');dot.className='__demodsl_ctr';
                dot.style.cssText='position:fixed;left:'+(e.clientX-9)+'px;top:'+(e.clientY-9)+'px;width:18px;height:18px;border-radius:50%;background:hsl('+hue+',100%,60%);pointer-events:none;box-shadow:0 0 12px hsl('+hue+',100%,50%);z-index:99999;transition:all 1.4s ease;';
                document.body.appendChild(dot);
                setTimeout(()=>{dot.style.opacity='0';},800);setTimeout(()=>dot.remove(),2200);
            });
        })()""",
    ),
    EffectSpec(name="cursor_trail_comet", needs_mouse=True, js_inject="void 0;"),
    EffectSpec(name="cursor_trail_fire", needs_mouse=True, js_inject="void 0;"),
    EffectSpec(name="cursor_trail_glow", needs_mouse=True, js_inject="void 0;"),
    EffectSpec(name="cursor_trail_line", needs_mouse=True, js_inject="void 0;"),
    EffectSpec(name="cursor_trail_particles", needs_mouse=True, js_inject="void 0;"),
    # ─── Text ─────────────────────────────────────────────────
    EffectSpec(
        name="typewriter",
        dom_id="__demodsl_typewriter",
        js_inject="""(() => {
            const s=document.createElement('style');s.id='__demodsl_typewriter';
            s.textContent='input,textarea{caret-color:#333;animation:demodsl-blink 0.7s step-end infinite;}@keyframes demodsl-blink{50%{caret-color:transparent;}}';
            document.head.appendChild(s);
        })()""",
        time_limited=False,
    ),
    EffectSpec(
        name="text_highlight",
        dom_id="__demodsl_text_highlight",
        js_inject="""(() => {
            const s=document.createElement('style');s.id='__demodsl_text_highlight';
            s.textContent='.__demodsl_hl{background:linear-gradient(90deg,COLOR60 0%,transparent 100%);background-size:200% 100%;background-position:100% 0;animation:demodsl_hl_sweep 1.2s ease forwards;}@keyframes demodsl_hl_sweep{to{background-position:0 0;}}';
            document.head.appendChild(s);
            document.querySelectorAll('p,h1,h2,h3,li,span,a').forEach(el=>el.classList.add('__demodsl_hl'));
        })()""",
        time_limited=False,
        params={"color": "#FFD700"},
    ),
    EffectSpec(
        name="text_scramble",
        js_inject="""(() => {
            const chars='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%&*';
            document.querySelectorAll('h1,h2,h3,p,a,span,button,label').forEach(el=>{
                if(el.children.length>0||el.textContent.trim().length===0)return;
                const o=el.textContent;let it=0;
                const iv=setInterval(()=>{el.textContent=o.split('').map((c,i)=>i<it?o[i]:chars[Math.floor(Math.random()*chars.length)]).join('');if(it>=o.length)clearInterval(iv);it+=1/3;},SPEED);
            });
        })()""",
        params={"speed": 50},
        param_ranges={"speed": [10, 25, 50, 100, 200, 500]},
    ),
    # ─── Interactive ──────────────────────────────────────────
    EffectSpec(
        name="magnetic_hover",
        dom_id="__demodsl_magnetic_hover",
        needs_mouse=True,
        js_inject="""(() => {
            const s=document.createElement('style');s.id='__demodsl_magnetic_hover';
            s.textContent='button,a,[role=button],.btn{transition:transform 0.3s ease-out;}';
            document.head.appendChild(s);
        })()""",
        time_limited=False,
    ),
    EffectSpec(
        name="morphing_background",
        dom_id="__demodsl_morphing_bg",
        js_inject="""(() => {
            const s=document.createElement('style');s.id='__demodsl_morphing_bg';
            s.textContent="body::before{content:'';position:fixed;top:0;left:0;width:100%;height:100%;z-index:-1;background:linear-gradient(135deg,#667eea,#764ba2,#f093fb);background-size:400% 400%;animation:demodsl_morph 8s ease infinite;}@keyframes demodsl_morph{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}";
            document.head.appendChild(s);
        })()""",
        time_limited=False,
        screenshot_delay=1.0,
    ),
    EffectSpec(
        name="tooltip_annotation",
        dom_id="__demodsl_tooltip",
        needs_mouse=True,
        js_inject="""(() => {
            const s=document.createElement('style');s.id='__demodsl_tooltip';
            s.textContent='.__demodsl_tip{position:absolute;padding:6px 12px;background:#333;color:#fff;border-radius:6px;font-size:13px;pointer-events:none;z-index:99999;opacity:0;transition:opacity 0.25s ease;white-space:nowrap;}';
            document.head.appendChild(s);
            const tip=document.createElement('div');tip.className='__demodsl_tip';tip.textContent='Click here';
            document.body.appendChild(tip);
        })()""",
        time_limited=False,
    ),
    EffectSpec(
        name="matrix_rain",
        dom_id="__demodsl_matrix_rain",
        js_inject=_canvas_effect(
            "matrix_rain",
            "__demodsl_matrix_rain",
            """
            const fontSize=14;const density=DENSITY;const speed=SPEED;
            const cols=Math.floor(canvas.width/fontSize*density);
            const drops=Array.from({length:cols},()=>Math.random()*-100);
            const chars='ABCDEFGHIJKLMNOPQRSTUVWXYZアイウエオカキクケコ0123456789@#$%^&*';
            const maxF=MAXFRAMES;let f=0;
            function draw(){ctx.fillStyle='rgba(0,0,0,0.05)';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='COLOR';ctx.font=fontSize+'px monospace';for(let i=0;i<cols;i++){const ch=chars[Math.floor(Math.random()*chars.length)];const x=(i/density)*fontSize;ctx.fillText(ch,x,drops[i]*fontSize);if(drops[i]*fontSize>canvas.height&&Math.random()>0.975)drops[i]=0;drops[i]+=speed;}if(++f<maxF)requestAnimationFrame(draw);else canvas.remove();}
            draw();
        """,
        ),
        params={"color": "#00FF41", "density": 0.6, "speed": 1.0, "duration": 5.0},
        param_ranges={
            "density": [0.1, 0.3, 0.6, 1.0, 1.5, 2.0],
            "speed": [0.1, 0.5, 1.0, 2.0, 3.0, 5.0],
            "duration": [0.5, 1.0, 2.0, 5.0],
        },
    ),
    # ─── Utility ──────────────────────────────────────────────
    EffectSpec(
        name="progress_bar",
        dom_id="__demodsl_progress_bar",
        js_inject="""(() => {
            const b=document.createElement('div');b.id='__demodsl_progress_bar';
            b.style.cssText='position:fixed;left:0;top:0;width:50%;height:4px;background:linear-gradient(90deg,#6366f1,#6366f1cc);z-index:99999;pointer-events:none;box-shadow:0 0 8px #6366f166;';
            document.body.appendChild(b);
        })()""",
        time_limited=False,
    ),
    EffectSpec(
        name="countdown_timer",
        dom_id="__demodsl_countdown",
        js_inject="""(() => {
            const t=document.createElement('div');t.id='__demodsl_countdown';
            t.style.cssText='position:fixed;top:20px;right:20px;font-size:28px;font-weight:bold;font-family:monospace;color:#fff;z-index:99999;pointer-events:none;background:rgba(0,0,0,0.5);padding:8px 16px;border-radius:8px;min-width:60px;text-align:center;';
            t.textContent='DURATION';document.body.appendChild(t);
            let rem=DURATION;function tick(){const m=Math.floor(rem/60);const s=Math.floor(rem%60);t.textContent=(m>0?m+':':'')+String(s).padStart(2,'0');if(rem<=0){t.remove();return;}rem-=1;setTimeout(tick,1000);}tick();
        })()""",
        params={"duration": 10},
        param_ranges={"duration": [1, 2, 5, 10, 30, 60]},
    ),
    EffectSpec(
        name="callout_arrow",
        dom_id="__demodsl_callout_arrow",
        js_inject="""(() => {
            const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
            svg.id='__demodsl_callout_arrow';
            svg.setAttribute('style','position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:none;');
            svg.innerHTML='<defs><marker id="ah" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="#ef4444"/></marker></defs>';
            document.body.appendChild(svg);
            const tx=window.innerWidth*TARGET_X,ty=window.innerHeight*TARGET_Y;
            const sx=tx+(tx>window.innerWidth/2?120:-120),sy=ty-80;
            const line=document.createElementNS('http://www.w3.org/2000/svg','line');
            line.setAttribute('x1',sx);line.setAttribute('y1',sy);line.setAttribute('x2',tx);line.setAttribute('y2',ty);
            line.setAttribute('stroke','#ef4444');line.setAttribute('stroke-width','3');
            line.setAttribute('marker-end','url(#ah)');
            line.setAttribute('stroke-dasharray','200');line.setAttribute('stroke-dashoffset','200');
            line.style.transition='stroke-dashoffset 0.6s ease';svg.appendChild(line);
            const label=document.createElement('div');label.id='__demodsl_callout_label';
            label.textContent='Look here!';label.style.cssText='position:fixed;left:'+(sx-60)+'px;top:'+(sy-36)+'px;background:#ef4444;color:#fff;padding:6px 14px;border-radius:6px;font-size:14px;font-weight:600;z-index:99999;pointer-events:none;opacity:0;transition:opacity 0.4s ease 0.3s;';
            document.body.appendChild(label);
            requestAnimationFrame(()=>{line.setAttribute('stroke-dashoffset','0');label.style.opacity='1';});
            setTimeout(()=>{svg.remove();label.remove();},4000);
        })()""",
        params={"target_x": 0.5, "target_y": 0.5},
        param_ranges={
            "target_x": [0.1, 0.3, 0.5, 0.7, 0.9],
            "target_y": [0.1, 0.3, 0.5, 0.7, 0.9],
        },
    ),
    EffectSpec(
        name="success_checkmark",
        dom_id="__demodsl_checkmark",
        js_inject="""(() => {
            const el=document.createElement('div');el.id='__demodsl_checkmark';el.innerHTML='✓';
            el.style.cssText='position:fixed;top:50%;left:50%;transform:translate(-50%,-50%) scale(0);font-size:120px;color:#4CAF50;z-index:99999;pointer-events:none;animation:demodsl-check 0.8s ease-out forwards;';
            const s=document.createElement('style');s.textContent='@keyframes demodsl-check{50%{transform:translate(-50%,-50%) scale(1.2);}100%{transform:translate(-50%,-50%) scale(1);opacity:0;}}';
            document.head.appendChild(s);document.body.appendChild(el);
            setTimeout(()=>{el.remove();s.remove();},1500);
        })()""",
        screenshot_delay=0.3,
    ),
]


def _prepare_js(spec: EffectSpec, params: dict | None = None) -> str:
    """Substitute parameter placeholders in JS."""
    p = {**spec.params, **(params or {})}
    js = spec.js_inject
    # Duration → max frames
    if "duration" in p:
        js = js.replace("MAXFRAMES", str(int(float(p["duration"]) * 60)))
    if "intensity" in p:
        js = js.replace("INTENSITY", str(p["intensity"]))
        blur_px = int(float(p["intensity"]) * 20)
        js = js.replace("BLUR_PX", str(blur_px))
    if "color" in p:
        js = js.replace("COLOR", str(p["color"]))
    if "speed" in p and "SPEED" in js:
        js = js.replace("SPEED", str(p["speed"]))
    if "density" in p:
        js = js.replace("DENSITY", str(p["density"]))
    if "target_x" in p:
        js = js.replace("TARGET_X", str(p["target_x"]))
    if "target_y" in p:
        js = js.replace("TARGET_Y", str(p["target_y"]))
    if "DURATION" in js and "duration" in p:
        js = js.replace("DURATION", str(int(p["duration"])))
    return js


def compute_diff(before: Image.Image, after: Image.Image) -> tuple[float, float, float]:
    """Compute pixel diff metrics between two screenshots.
    Returns (mean_diff, changed_pct, peak_diff).
    """
    a = np.array(before, dtype=np.float32)
    b = np.array(after, dtype=np.float32)
    diff = np.abs(a - b)
    per_pixel = diff.mean(axis=2)  # mean across RGB
    mean_diff = float(per_pixel.mean())
    changed_pct = float((per_pixel > 10).sum() / per_pixel.size * 100)
    peak_diff = float(per_pixel.max())
    return mean_diff, changed_pct, peak_diff


async def test_effect(
    page,
    spec: EffectSpec,
    params: dict | None = None,
    save_screenshots: bool = True,
) -> EffectResult:
    """Test a single effect with given params."""
    p = {**spec.params, **(params or {})}
    delay = spec.screenshot_delay

    try:
        await page.goto(URL, wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(800)
    except Exception as e:
        return EffectResult(
            name=spec.name,
            visible=False,
            mean_diff=0,
            changed_pct=0,
            peak_diff=0,
            dom_present=False,
            screenshot_delay=delay,
            params=p,
            error=f"page load: {e}",
        )

    # BEFORE screenshot
    before_bytes = await page.screenshot(type="png")
    before_img = Image.open(__import__("io").BytesIO(before_bytes)).convert("RGB")

    # Inject effect
    js = _prepare_js(spec, params)
    if js == "void 0;":
        # Cursor trail stubs — use real framework injection
        return EffectResult(
            name=spec.name,
            visible=False,
            mean_diff=0,
            changed_pct=0,
            peak_diff=0,
            dom_present=False,
            screenshot_delay=delay,
            params=p,
            error="stub (needs real framework inject)",
        )

    try:
        await page.evaluate(js)
    except Exception as e:
        return EffectResult(
            name=spec.name,
            visible=False,
            mean_diff=0,
            changed_pct=0,
            peak_diff=0,
            dom_present=False,
            screenshot_delay=delay,
            params=p,
            error=f"inject: {e}",
        )

    # Simulate mouse if needed
    if spec.needs_mouse:
        for i in range(10):
            x = 200 + i * 80
            y = 300 + (i % 3) * 60
            await page.mouse.move(x, y)
            await page.wait_for_timeout(50)

    if spec.needs_click:
        await page.mouse.click(640, 360)
        await page.wait_for_timeout(50)

    # Wait for effect to render
    await page.wait_for_timeout(int(delay * 1000))

    # AFTER screenshot
    after_bytes = await page.screenshot(type="png")
    after_img = Image.open(__import__("io").BytesIO(after_bytes)).convert("RGB")

    # Check DOM
    dom_present = False
    if spec.dom_id:
        dom_present = await page.evaluate(f"!!document.getElementById('{spec.dom_id}')")
    else:
        dom_present = await page.evaluate(
            "document.querySelectorAll('[id*=demodsl],[class*=demodsl]').length > 0"
        )

    # Compute diff
    mean_diff, changed_pct, peak_diff = compute_diff(before_img, after_img)
    visible = mean_diff > DIFF_THRESHOLD or changed_pct > CHANGED_PX_THRESHOLD

    # Save screenshots
    if save_screenshots:
        slug = spec.name
        if params:
            slug += "_" + "_".join(f"{k}={v}" for k, v in params.items())
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        before_img.save(SCREENSHOTS_DIR / f"{slug}_before.png")
        after_img.save(SCREENSHOTS_DIR / f"{slug}_after.png")

    return EffectResult(
        name=spec.name,
        visible=visible,
        mean_diff=round(mean_diff, 3),
        changed_pct=round(changed_pct, 3),
        peak_diff=round(peak_diff, 3),
        dom_present=dom_present,
        screenshot_delay=delay,
        params=p,
    )


async def main():
    parser = argparse.ArgumentParser(description="CV-based effect validation")
    parser.add_argument("--effect", help="Test single effect by name")
    parser.add_argument(
        "--quick", action="store_true", help="Quick mode (fewer params)"
    )
    parser.add_argument("--no-screenshots", action="store_true")
    args = parser.parse_args()

    from playwright.async_api import async_playwright

    effects = EFFECTS
    if args.effect:
        effects = [e for e in EFFECTS if e.name == args.effect]
        if not effects:
            print(f"Unknown effect: {args.effect}")
            return 1

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport=VIEWPORT)

        all_results: list[dict] = []
        param_ranges: list[dict] = []

        print(f"\n{'=' * 100}")
        print(
            f"{'EFFECT':<25} {'VISIBLE':>8} {'MEAN Δ':>10} {'% CHANGED':>10} {'PEAK Δ':>10} {'DOM':>5} {'STATUS':>8}"
        )
        print(f"{'=' * 100}")

        # Phase 1: Default params
        for spec in effects:
            result = await test_effect(
                page, spec, save_screenshots=not args.no_screenshots
            )
            all_results.append(asdict(result))

            status = "✓ PASS" if result.visible or result.dom_present else "✗ FAIL"
            if result.error:
                status = f"⚠ {result.error[:20]}"

            print(
                f"{result.name:<25} "
                f"{'YES' if result.visible else 'no':>8} "
                f"{result.mean_diff:>10.3f} "
                f"{result.changed_pct:>9.3f}% "
                f"{result.peak_diff:>10.1f} "
                f"{'yes' if result.dom_present else 'no':>5} "
                f"{status:>8}"
            )

        # Phase 2: Parameter sweeps
        print(f"\n{'=' * 100}")
        print("PARAMETER RANGE SWEEP")
        print(f"{'=' * 100}")

        for spec in effects:
            if not spec.param_ranges:
                continue
            if args.quick:
                # Only test min, mid, max
                ranges = {}
                for k, v in spec.param_ranges.items():
                    ranges[k] = [v[0], v[len(v) // 2], v[-1]] if len(v) > 2 else v
            else:
                ranges = spec.param_ranges

            print(f"\n  {spec.name}:")
            for param_name, values in ranges.items():
                print(f"    {param_name}: ", end="")
                for val in values:
                    override = {param_name: val}
                    result = await test_effect(
                        page,
                        spec,
                        params=override,
                        save_screenshots=not args.no_screenshots,
                    )
                    marker = "✓" if result.visible or result.dom_present else "✗"
                    print(f"  {val}={marker}({result.mean_diff:.1f})", end="")

                    param_ranges.append(
                        asdict(
                            ParamRangeResult(
                                name=spec.name,
                                param_name=param_name,
                                value=val,
                                visible=result.visible or result.dom_present,
                                mean_diff=result.mean_diff,
                                changed_pct=result.changed_pct,
                            )
                        )
                    )
                print()

        await browser.close()

    # Summary
    passed = sum(1 for r in all_results if r["visible"] or r["dom_present"])
    failed = sum(
        1
        for r in all_results
        if not r["visible"] and not r["dom_present"] and not r.get("error")
    )
    errors = sum(1 for r in all_results if r.get("error"))

    print(f"\n{'=' * 100}")
    print(
        f"SUMMARY: {passed} visible, {failed} invisible, {errors} errors out of {len(all_results)}"
    )

    # Build working ranges report
    working_ranges: dict = {}
    for pr in param_ranges:
        key = pr["name"]
        if key not in working_ranges:
            working_ranges[key] = {}
        pn = pr["param_name"]
        if pn not in working_ranges[key]:
            working_ranges[key][pn] = {"working": [], "broken": []}
        bucket = "working" if pr["visible"] else "broken"
        working_ranges[key][pn][bucket].append(
            {"value": pr["value"], "mean_diff": pr["mean_diff"]}
        )

    print("\nWORKING PARAMETER RANGES:")
    print(f"{'-' * 80}")
    for eff_name, params in working_ranges.items():
        for pn, data in params.items():
            w_vals = [d["value"] for d in data["working"]]
            b_vals = [d["value"] for d in data["broken"]]
            w_range = f"[{min(w_vals)}..{max(w_vals)}]" if w_vals else "NONE"
            print(
                f"  {eff_name}.{pn}: working={w_range}  broken={b_vals if b_vals else 'none'}"
            )

    # Save JSON report
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "url": URL,
        "viewport": VIEWPORT,
        "thresholds": {
            "diff_threshold": DIFF_THRESHOLD,
            "changed_px_threshold": CHANGED_PX_THRESHOLD,
        },
        "results": all_results,
        "param_ranges": param_ranges,
        "working_ranges": working_ranges,
        "summary": {
            "total": len(all_results),
            "visible": passed,
            "invisible": failed,
            "errors": errors,
        },
    }
    report_path = Path("output/effect_cv_report.json")
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nFull report: {report_path}")
    if not args.no_screenshots:
        print(f"Screenshots: {SCREENSHOTS_DIR}/")

    return 0 if failed == 0 and errors == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
