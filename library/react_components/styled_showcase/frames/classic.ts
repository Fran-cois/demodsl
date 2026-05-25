import { ContentLayout, SHARED_LAYOUT, h } from "../shared";
import type { Resolved } from "../types";

export function TechMinimalismFrame(c: Resolved) {
  return h(
    "div",
    {
      className: "ss-root",
      style: {
        ["--ss-bg" as any]: "#F7F6F2",
        ["--ss-ink" as any]: "#0B0D10",
        ["--ss-sub" as any]: "#5B6470",
        ["--ss-accent" as any]: c.accent,
        ["--ss-title-font" as any]: '"Newsreader","Iowan Old Style",Georgia,serif',
        ["--ss-num-font" as any]: '"Newsreader",Georgia,serif',
      },
    },
    h(
      "style",
      null,
      SHARED_LAYOUT +
        `
      @keyframes tm-reveal  { from{opacity:0; transform:translateY(8px);} to{opacity:1; transform:none;} }
      @keyframes tm-grow    { from{transform:scaleX(0);} to{transform:scaleX(1);} }
      @keyframes tm-blink   { 0%,49%{opacity:1;} 50%,100%{opacity:0;} }
      @keyframes tm-marquee { from{transform:translateX(0);} to{transform:translateX(-50%);} }
      .ss-root .ss-eyebrow  { animation: tm-reveal .7s ease-out .15s both; }
      .ss-root .ss-live     { animation: tm-reveal .7s ease-out .25s both; }
      .ss-root .ss-live::after { content:""; display:inline-block; width:8px; height:16px;
                                 background: var(--ss-ink); margin-left:4px;
                                 animation: tm-blink 1s steps(1,end) infinite; }
      .ss-root .ss-title    { font-weight:500; animation: tm-reveal .9s cubic-bezier(.7,0,.2,1) .35s both; }
      .ss-root .ss-rule     { animation: tm-grow .7s cubic-bezier(.7,0,.2,1) .9s both; }
      .ss-root .ss-subtitle { animation: tm-reveal .9s ease-out .55s both; }
      .ss-root .ss-cta-row  { animation: tm-reveal .9s ease-out .75s both; }
      .ss-root .ss-kpi      { animation: tm-reveal .6s ease-out calc(.85s + var(--i) * .12s) both; }
      .ss-rule-top          { position:absolute; top:0; left:0; right:0; height:1px; z-index:3;
                              background: var(--ss-ink); transform-origin:left;
                              animation: tm-grow 1.2s cubic-bezier(.7,0,.2,1) both; }
      .ss-marquee { position:absolute; bottom:18px; left:0; right:0; overflow:hidden;
                    height:18px; opacity:.5; z-index:3; }
      .ss-marquee-track { display:flex; gap:28px; white-space:nowrap;
                          animation: tm-marquee 22s linear infinite;
                          font-family:"JetBrains Mono","SF Mono",ui-monospace,monospace;
                          font-size:11px; letter-spacing:.32em; color: var(--ss-sub); }
    `,
    ),
    h("div", { className: "ss-rule-top" }),
    h(ContentLayout, c),
    h(
      "div",
      { className: "ss-marquee" },
      h(
        "div",
        { className: "ss-marquee-track" },
        Array.from({ length: 2 }).flatMap((_, k) =>
          [
            "DEMOS-AS-CODE",
            "//",
            "YAML \u2192 MP4",
            "//",
            "REACT LAYERS",
            "//",
            "PRECISION PIPELINE",
            "//",
            "OPEN SOURCE",
            "//",
          ].map((s, i) => h("span", { key: `${k}-${i}` }, s)),
        ),
      ),
    ),
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. VORTICISM — angular: hard offset slides, rotated stamps, sharp easings.
// ─────────────────────────────────────────────────────────────────────────────

export function VorticismFrame(c: Resolved) {
  return h(
    "div",
    {
      className: "ss-root",
      style: {
        ["--ss-bg" as any]: "#F4EFE6",
        ["--ss-ink" as any]: "#0B0B0B",
        ["--ss-sub" as any]: "#3A3633",
        ["--ss-accent" as any]: "#D62828",
        ["--ss-title-font" as any]: '"Archivo Black","Helvetica Neue",Inter,sans-serif',
      },
    },
    h(
      "style",
      null,
      SHARED_LAYOUT +
        `
      @keyframes vs-slash { from{transform:translate(-40px,-20px) skewX(-12deg); opacity:0;} to{transform:none; opacity:1;} }
      @keyframes vs-stamp { 0%{transform:scale(.6) rotate(-14deg); opacity:0;} 60%{transform:scale(1.06) rotate(-3deg); opacity:1;} 100%{transform:scale(1) rotate(-3deg); opacity:1;} }
      @keyframes vs-shard { 0%,100%{transform:translate(0,0) rotate(0);} 50%{transform:translate(-6px,4px) rotate(-1deg);} }
      @keyframes vs-spin  { from{transform:rotate(0);} to{transform:rotate(360deg);} }
      @keyframes vs-step  { 0%,100%{transform:translateY(-50%) rotate(90deg) translateX(0);} 50%{transform:translateY(-50%) rotate(90deg) translateX(-4px);} }
      .ss-root .ss-header   { align-items:flex-start; }
      .ss-root .ss-eyebrow  { background: var(--ss-ink); color: var(--ss-bg); padding:6px 12px;
                              display:inline-block; align-self:flex-start;
                              animation: vs-stamp .7s cubic-bezier(.2,1.4,.3,1) .1s both; }
      .ss-root .ss-live     { background: var(--ss-accent); color:#fff; padding:6px 12px;
                              letter-spacing:.3em;
                              animation: vs-stamp .7s cubic-bezier(.2,1.4,.3,1) .25s both; }
      .ss-root .ss-live-dot { background:#fff; }
      .ss-root .ss-title    { text-transform:uppercase; font-weight:900;
                              letter-spacing:-.02em; font-size:88px;
                              text-shadow: 6px 6px 0 var(--ss-accent);
                              animation: vs-slash .55s cubic-bezier(.2,.9,.2,1) .4s both; }
      .ss-root .ss-rule     { height:6px; background: var(--ss-ink); width:140px;
                              animation: vs-slash .5s cubic-bezier(.2,.9,.2,1) .85s both; }
      .ss-root .ss-subtitle { text-transform:uppercase; letter-spacing:.18em; font-size:14px;
                              font-weight:700; line-height:1.6; color: var(--ss-ink);
                              animation: vs-slash .6s cubic-bezier(.2,.9,.2,1) 1.0s both; }
      .ss-root .ss-cta      { border-radius:0; box-shadow: 6px 6px 0 var(--ss-accent);
                              text-transform:uppercase; letter-spacing:.12em; font-weight:800;
                              animation: vs-stamp .6s cubic-bezier(.2,1.4,.3,1) 1.2s both; }
      .ss-root .ss-cta-2    { border-radius:0; border-width:3px; border-color: var(--ss-ink);
                              text-transform:uppercase; letter-spacing:.12em; font-weight:800;
                              animation: vs-stamp .6s cubic-bezier(.2,1.4,.3,1) 1.35s both; }
      .ss-root .ss-kpi      { animation: vs-slash .55s cubic-bezier(.2,.9,.2,1) calc(1.5s + var(--i) * .12s) both; }
      .ss-root .ss-meta-value { font-weight:900; }
      .ss-gear { position:absolute; bottom:-220px; right:-220px; width:580px; height:580px;
                 opacity:.18; animation: vs-spin 28s linear infinite; z-index:1; }
      .ss-shards { position:absolute; top:30%; right:5%; width:220px; height:220px;
                   opacity:.42; animation: vs-shard 4s ease-in-out infinite; z-index:1; }
      .ss-year { position:absolute; top:50%; right:24px;
                 transform:translateY(-50%) rotate(90deg);
                 transform-origin:right center; font-weight:900; font-size:64px;
                 letter-spacing:.06em; color: var(--ss-accent); opacity:.55;
                 animation: vs-step 3s ease-in-out infinite; z-index:1; }
    `,
    ),
    h(
      "svg",
      { className: "ss-gear", viewBox: "-100 -100 200 200" },
      ...Array.from({ length: 16 }).map((_, i) =>
        h("rect", {
          key: i,
          x: -6,
          y: -94,
          width: 12,
          height: 22,
          fill: "#1F2A36",
          transform: `rotate(${(i * 360) / 16})`,
        }),
      ),
      h("circle", { cx: 0, cy: 0, r: 72, fill: "none", stroke: "#1F2A36", strokeWidth: 6 }),
    ),
    h(
      "svg",
      { className: "ss-shards", viewBox: "0 0 240 240" },
      h("polygon", { points: "120,120 20,30 20,210", fill: "#F1B400" }),
      h("polygon", { points: "120,120 220,30 210,120", fill: "#D62828" }),
      h("polygon", { points: "120,120 80,230 160,230", fill: "#0B0B0B" }),
    ),
    h("div", { className: "ss-year" }, "1914"),
    h(ContentLayout, c),
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. GLOWFI — premium dark: mesh-gradient bg, orbit ring, beam, twinkling
// stars, conic-bordered glass KPI cards, crisp halo title with a scan-line.
// Inspired by Linear / Vercel / Raycast / Framer hero patterns.
// ─────────────────────────────────────────────────────────────────────────────

export function NeoBrutalismFrame(c: Resolved) {
  return h(
    "div",
    {
      className: "ss-root",
      style: {
        ["--ss-bg" as any]: "#FFE066",
        ["--ss-ink" as any]: "#0A0A0A",
        ["--ss-sub" as any]: "#1a1a1a",
        ["--ss-accent" as any]: c.accent,
        ["--ss-title-font" as any]: '"Archivo Black","Inter",system-ui,sans-serif',
      },
    },
    h(
      "style",
      null,
      SHARED_LAYOUT +
        `
      @keyframes nb-pop      { 0%{transform:translate(-10px,-10px) rotate(-2deg); opacity:0;} 60%{transform:translate(4px,4px) rotate(.5deg); opacity:1;} 100%{transform:translate(0,0) rotate(0); opacity:1;} }
      @keyframes nb-pop-tilt { 0%{transform:translate(-10px,-10px) rotate(-10deg); opacity:0;} 60%{transform:translate(2px,2px) rotate(-3deg); opacity:1;} 100%{transform:translate(0,0) rotate(-3deg); opacity:1;} }
      @keyframes nb-blink    { 0%,49%{opacity:1;} 50%,100%{opacity:0;} }
      @keyframes nb-press    { 0%,100%{transform:translate(0,0); box-shadow: 8px 8px 0 0 var(--ss-ink);} 50%{transform:translate(4px,4px); box-shadow: 4px 4px 0 0 var(--ss-ink);} }
      @keyframes nb-stripes  { from{background-position:0 0;} to{background-position:48px 0;} }
      .ss-root { background-image: repeating-linear-gradient(45deg, transparent 0 22px, rgba(10,10,10,.05) 22px 24px);
                 background-color: var(--ss-bg); background-size:48px 48px;
                 animation: nb-stripes 6s linear infinite; }
      .ss-root .ss-eyebrow  { background:#fff; padding:8px 14px; border:3px solid var(--ss-ink);
                              box-shadow: 6px 6px 0 var(--ss-ink); align-self:flex-start;
                              animation: nb-pop .6s cubic-bezier(.2,1.4,.3,1) .05s both; }
      .ss-root .ss-live     { background:#B5FF3D; padding:8px 14px; border:3px solid var(--ss-ink);
                              box-shadow: 6px 6px 0 var(--ss-ink);
                              animation: nb-pop .6s cubic-bezier(.2,1.4,.3,1) .18s both; }
      .ss-root .ss-live-dot { background: var(--ss-ink);
                              animation: nb-blink 1s steps(1,end) infinite; }
      .ss-root .ss-title    { font-weight:900; text-transform:uppercase; letter-spacing:-.03em;
                              text-shadow: 4px 4px 0 var(--ss-accent);
                              animation: nb-pop .7s cubic-bezier(.2,1.4,.3,1) .3s both; }
      .ss-root .ss-rule     { background: var(--ss-ink); height:6px;
                              animation: nb-pop .5s cubic-bezier(.2,1.4,.3,1) .55s both; }
      .ss-root .ss-subtitle { font-weight:600; color: var(--ss-ink);
                              animation: nb-pop .6s cubic-bezier(.2,1.4,.3,1) .7s both; }
      .ss-root .ss-cta      { border:4px solid var(--ss-ink); border-radius:0;
                              background: var(--ss-ink); color: var(--ss-bg);
                              box-shadow: 8px 8px 0 var(--ss-ink); text-transform:uppercase;
                              letter-spacing:.12em; font-weight:900;
                              animation: nb-pop .6s cubic-bezier(.2,1.4,.3,1) .9s both,
                                         nb-press 1.6s ease-in-out 1.6s infinite; }
      .ss-root .ss-cta-2    { border:4px solid var(--ss-ink); border-radius:0;
                              background:#fff; color: var(--ss-ink);
                              box-shadow: 8px 8px 0 var(--ss-ink); text-transform:uppercase;
                              letter-spacing:.12em; font-weight:900;
                              animation: nb-pop .6s cubic-bezier(.2,1.4,.3,1) 1.05s both; }
      .ss-root .ss-kpis     { border-top: 4px solid var(--ss-ink); padding-top:22px; }
      .ss-root .ss-kpi      { background:#fff; border:4px solid var(--ss-ink); padding:18px 18px 16px;
                              box-shadow: 6px 6px 0 var(--ss-ink);
                              animation: nb-pop-tilt .6s cubic-bezier(.2,1.4,.3,1) calc(1.2s + var(--i) * .12s) both; }
      .ss-root .ss-kpi:nth-child(2n) { background:#3DD5FF; }
      .ss-root .ss-kpi:nth-child(3n) { background: var(--ss-accent); color:#fff; }
      .ss-root .ss-kpi:nth-child(3n) .ss-meta-label { color: rgba(255,255,255,.85); }
      .ss-root .ss-meta-value { font-weight:900; }
    `,
    ),
    h(ContentLayout, c),
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. LAYERED PRODUCT — floating parallax: rise + drift, soft glass, gradient bg.
// ─────────────────────────────────────────────────────────────────────────────

export function LayeredProductFrame(c: Resolved) {
  return h(
    "div",
    {
      className: "ss-root",
      style: {
        ["--ss-bg" as any]: "#EAEEF7",
        ["--ss-ink" as any]: "#0B1220",
        ["--ss-sub" as any]: "#4B5568",
        ["--ss-accent" as any]: c.accent,
      },
    },
    h(
      "style",
      null,
      SHARED_LAYOUT +
        `
      @keyframes lp-rise   { from{opacity:0; transform:translateY(24px);} to{opacity:1; transform:none;} }
      @keyframes lp-float  { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-8px);} }
      @keyframes lp-drift  { 0%,100%{transform:translateY(0) rotate(-1deg);} 50%{transform:translateY(-6px) rotate(-1deg);} }
      @keyframes lp-aurora { 0%,100%{transform:translate(0,0) scale(1);} 50%{transform:translate(2%,-2%) scale(1.05);} }
      @keyframes lp-pulse  { 0%,100%{box-shadow: 0 0 0 0 rgba(99,102,241,.35);} 50%{box-shadow: 0 0 0 12px rgba(99,102,241,0);} }
      @keyframes lp-shimmer{ from{background-position:-240px 0;} to{background-position:240px 0;} }
      .ss-root { background: linear-gradient(180deg, #F4F6FB 0%, #EAEEF7 60%, #E2E8F4 100%); }
      .ss-root .ss-eyebrow  { display:inline-flex; align-items:center; gap:10px; align-self:flex-start;
                              padding:8px 14px; border-radius:999px;
                              background: rgba(255,255,255,.75); backdrop-filter: blur(10px);
                              border:1px solid rgba(11,18,32,.08);
                              box-shadow: 0 2px 10px rgba(11,18,32,.06);
                              animation: lp-rise .8s cubic-bezier(.2,.8,.2,1) .1s both,
                                         lp-float 5s ease-in-out 1s infinite; }
      .ss-root .ss-eyebrow::before { content:""; width:8px; height:8px; border-radius:50%;
                                     background: var(--ss-accent);
                                     animation: lp-pulse 1.8s ease-out infinite; }
      .ss-root .ss-live     { padding:8px 14px; border-radius:999px;
                              background: rgba(255,255,255,.75); backdrop-filter: blur(10px);
                              border:1px solid rgba(11,18,32,.08);
                              animation: lp-rise .8s cubic-bezier(.2,.8,.2,1) .2s both,
                                         lp-drift 6s ease-in-out 1s infinite; }
      .ss-root .ss-title    { animation: lp-rise .9s cubic-bezier(.2,.8,.2,1) .3s both; }
      .ss-root .ss-rule     { background: linear-gradient(90deg, var(--ss-accent), #22D3EE, var(--ss-accent));
                              background-size: 240px 100%;
                              box-shadow: 0 6px 14px rgba(99,102,241,.35);
                              animation: lp-rise .6s cubic-bezier(.2,.8,.2,1) .55s both,
                                         lp-shimmer 2.4s linear 1.2s infinite; }
      .ss-root .ss-subtitle { animation: lp-rise .9s cubic-bezier(.2,.8,.2,1) .55s both; }
      .ss-root .ss-cta-row  { animation: lp-rise .9s cubic-bezier(.2,.8,.2,1) .75s both; }
      .ss-root .ss-cta      { background: var(--ss-ink); color:#fff; border-radius:12px;
                              border-color: transparent;
                              box-shadow: 0 10px 24px rgba(99,102,241,.45),
                                          inset 0 1px 0 rgba(255,255,255,.18); }
      .ss-root .ss-cta-2    { border-radius:12px; background: rgba(255,255,255,.75);
                              border-color: rgba(11,18,32,.1); backdrop-filter: blur(10px); }
      .ss-root .ss-kpis     { border-top: none;
                              background: rgba(255,255,255,.6); backdrop-filter: blur(18px);
                              border: 1px solid rgba(255,255,255,.9);
                              border-radius: 20px; padding: 22px 24px;
                              box-shadow: 0 30px 60px rgba(11,18,32,.16);
                              animation: lp-rise .9s cubic-bezier(.2,.8,.2,1) .9s both,
                                         lp-float 7s ease-in-out 1.6s infinite; }
      .ss-root .ss-kpi      { animation: lp-rise .6s cubic-bezier(.2,.8,.2,1) calc(1.05s + var(--i) * .12s) both; }
      .ss-root .ss-meta-value { background: linear-gradient(180deg, var(--ss-ink), var(--ss-accent));
                                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                                background-clip: text; color: transparent; }
      .ss-blob-a { position:absolute; top:-160px; right:-120px; width:640px; height:640px;
                   background: radial-gradient(closest-side, var(--ss-accent), transparent 70%);
                   opacity:.35; filter: blur(20px);
                   animation: lp-aurora 10s ease-in-out infinite; z-index:0; }
      .ss-blob-b { position:absolute; bottom:-200px; left:-140px; width:560px; height:560px;
                   background: radial-gradient(closest-side, #22D3EE, transparent 70%);
                   opacity:.3; filter: blur(20px);
                   animation: lp-aurora 12s ease-in-out infinite reverse; z-index:0; }
      .ss-dotgrid { position:absolute; inset:0;
                    background-image: radial-gradient(circle, rgba(11,18,32,.08) 1px, transparent 1px);
                    background-size: 28px 28px; opacity:.55; z-index:1; pointer-events:none; }
    `,
    ),
    h("div", { className: "ss-blob-a" }),
    h("div", { className: "ss-blob-b" }),
    h("div", { className: "ss-dotgrid" }),
    h(ContentLayout, c),
  );
}
