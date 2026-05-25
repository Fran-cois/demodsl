import { ContentLayout, SHARED_LAYOUT, h } from "../shared";
import type { Resolved } from "../types";

export function GlowFiFrame(c: Resolved) {
  // Deterministic star field (no Math.random — render must be repeatable)
  const STARS: Array<[number, number, number, number]> = [
    // [left%, top%, size_px, delay_s]
    [6, 12, 2, 0.0], [11, 38, 1, 1.2], [18, 8, 2, 2.4], [23, 56, 1, 0.6],
    [28, 22, 3, 3.0], [34, 72, 1, 1.8], [40, 14, 2, 0.3], [46, 44, 1, 2.1],
    [52, 28, 2, 1.5], [58, 66, 1, 0.9], [64, 18, 3, 2.7], [70, 50, 1, 0.4],
    [76, 32, 2, 1.6], [82, 70, 1, 2.9], [88, 22, 2, 0.7], [94, 58, 1, 1.3],
    [9, 82, 1, 2.2], [17, 90, 2, 0.5], [27, 86, 1, 3.1], [37, 92, 2, 1.0],
    [49, 78, 1, 2.5], [59, 88, 2, 0.2], [69, 84, 1, 1.7], [79, 92, 2, 3.3],
    [89, 78, 1, 0.8], [4, 50, 1, 2.0], [13, 26, 1, 3.4], [97, 12, 2, 1.1],
  ];

  return h(
    "div",
    {
      className: "ss-root gs-root",
      style: {
        ["--ss-bg" as any]: "#06070C",
        ["--ss-ink" as any]: "#F4F6FB",
        ["--ss-sub" as any]: "rgba(244,246,251,0.62)",
        ["--ss-accent" as any]: c.accent,
        ["--gs-cyan" as any]: "#22D3EE",
        ["--gs-pink" as any]: "#F472B6",
      },
    },
    h(
      "style",
      null,
      SHARED_LAYOUT +
        `
      /* ── Mesh background ─────────────────────────────────────────────── */
      .gs-root {
        background:
          radial-gradient(55% 80% at 88% -10%, rgba(99,102,241,0.55) 0%, transparent 60%),
          radial-gradient(48% 70% at 8% 110%, rgba(34,211,238,0.42) 0%, transparent 65%),
          radial-gradient(38% 50% at 78% 78%, rgba(244,114,182,0.20) 0%, transparent 70%),
          radial-gradient(120% 120% at 50% 50%, #0A0C16 0%, #04050A 100%);
      }
      /* diagonal light beam (Linear-style) — static fade, no drift */
      .gs-beam { position:absolute; inset:-20%; z-index:1; pointer-events:none;
                 background: linear-gradient(118deg, transparent 38%, rgba(255,255,255,0.06) 50%, transparent 62%);
                 mix-blend-mode: screen;
                 animation: gs-beam-fade 2.4s cubic-bezier(.22,.61,.36,1) .2s both; }
      /* soft dot grid (masked to fade out at edges) */
      .gs-grid { position:absolute; inset:0; z-index:1; pointer-events:none;
                 background-image: radial-gradient(circle, rgba(255,255,255,0.07) 1px, transparent 1px);
                 background-size: 28px 28px;
                 -webkit-mask-image: radial-gradient(75% 65% at 50% 42%, #000 25%, transparent 85%);
                         mask-image: radial-gradient(75% 65% at 50% 42%, #000 25%, transparent 85%); }
      /* concentric orbit rings, bottom-right */
      .gs-orbit { position:absolute; bottom:-420px; right:-420px; width:980px; height:980px;
                  border-radius:50%; border:1px solid rgba(255,255,255,0.06);
                  box-shadow: inset 0 0 100px rgba(99,102,241,0.18);
                  z-index:1; pointer-events:none; }
      .gs-orbit::before, .gs-orbit::after {
        content:""; position:absolute; border-radius:50%;
        border:1px solid rgba(255,255,255,0.05); }
      .gs-orbit::before { inset: 90px; }
      .gs-orbit::after  { inset:200px; border-color: rgba(255,255,255,0.04); }
      /* twinkling star field */
      .gs-stars { position:absolute; inset:0; z-index:1; pointer-events:none; }
      .gs-stars i { position:absolute; display:block; border-radius:50%; background:#fff;
                    opacity:.35; box-shadow: 0 0 3px rgba(255,255,255,0.4); }
      /* fine top hairline */
      .gs-hairline { position:absolute; top:0; left:0; right:0; height:1px; z-index:2;
                     background: linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent);
                     transform-origin: left center;
                     animation: gs-hairline 2.2s cubic-bezier(.22,.61,.36,1) both; }

      /* ── Shared content overrides ─────────────────────────────────────── */
      .gs-root .ss-eyebrow {
        color: var(--ss-ink); align-self:flex-start;
        display:inline-flex; align-items:center; gap:10px;
        padding: 7px 14px 7px 12px; border-radius:999px;
        background: linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.02));
        border:1px solid rgba(255,255,255,0.10);
        box-shadow: 0 6px 20px -8px rgba(99,102,241,0.5), inset 0 1px 0 rgba(255,255,255,0.06);
        backdrop-filter: blur(14px);
        animation: gs-rise 1.4s cubic-bezier(.22,.61,.36,1) .15s both;
      }
      .gs-root .ss-eyebrow::before {
        content:""; width:8px; height:8px; border-radius:50%;
        background: var(--ss-accent);
        box-shadow: 0 0 10px var(--ss-accent);
      }
      .gs-root .ss-live {
        padding: 7px 14px; border-radius:999px;
        background: rgba(255,255,255,0.04);
        border:1px solid rgba(255,255,255,0.10);
        backdrop-filter: blur(14px);
        animation: gs-rise 1.4s cubic-bezier(.22,.61,.36,1) .35s both;
      }
      .gs-root .ss-live-dot { background:#22C55E; box-shadow: 0 0 8px rgba(34,197,94,0.6); }

      .gs-root .ss-title {
        color:#FFFFFF; font-weight:600; letter-spacing:-0.035em; line-height:1.02;
        text-shadow:
          0 0 1px rgba(255,255,255,0.4),
          0 0 60px rgba(99,102,241,0.55),
          0 0 140px rgba(99,102,241,0.30);
        position:relative; isolation:isolate;
        animation: gs-title-in 1.6s cubic-bezier(.22,.61,.36,1) .55s both;
      }
      .gs-root .ss-title::after { display:none; }
      .gs-root .ss-rule {
        background: linear-gradient(90deg, var(--ss-accent), var(--gs-cyan));
        box-shadow: 0 0 26px var(--ss-accent);
        height:3px; width:72px; border-radius:2px;
        transform-origin: left center;
        animation: gs-grow 1.2s cubic-bezier(.22,.61,.36,1) 1.35s both;
      }
      .gs-root .ss-subtitle {
        color: rgba(244,246,251,0.72);
        animation: gs-rise 1.4s cubic-bezier(.22,.61,.36,1) 1.10s both;
      }

      .gs-root .ss-cta-row { animation: gs-rise 1.4s cubic-bezier(.22,.61,.36,1) 1.45s both; }
      .gs-root .ss-cta {
        position:relative; background:#FFFFFF; color:#0B0D16;
        border:none; padding:13px 22px; border-radius:11px; font-weight:600;
        box-shadow: 0 14px 40px -10px rgba(99,102,241,0.55), inset 0 1px 0 rgba(255,255,255,0.6);
        isolation:isolate;
      }
      .gs-root .ss-cta::before {
        content:""; position:absolute; inset:-1px; border-radius:12px; z-index:-1;
        background: linear-gradient(180deg, var(--ss-accent), rgba(99,102,241,0.4));
        filter: blur(14px); opacity:.55;
      }
      .gs-root .ss-cta-2 {
        background: rgba(255,255,255,0.04); color: var(--ss-ink);
        border:1px solid rgba(255,255,255,0.12); border-radius:11px;
        backdrop-filter: blur(14px);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
      }

      .gs-root .ss-kpis { border-top:none; padding-top:0;
        animation: gs-rise 1.4s cubic-bezier(.22,.61,.36,1) 1.65s both; }
      .gs-root .ss-kpi {
        position:relative; padding:22px 24px 20px;
        background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.015));
        border:1px solid rgba(255,255,255,0.12); border-radius:16px;
        backdrop-filter: blur(16px);
        box-shadow:
          0 24px 50px -22px rgba(0,0,0,0.7),
          inset 0 1px 0 rgba(255,255,255,0.07);
        animation: gs-rise 1.2s cubic-bezier(.22,.61,.36,1) calc(1.75s + var(--i) * .22s) both;
      }
      /* subtle static top-edge accent line, no rotation */
      .gs-root .ss-kpi::before {
        content:""; position:absolute; left:18px; right:18px; top:0; height:1px;
        background: linear-gradient(90deg, transparent, rgba(99,102,241,0.6), transparent);
        pointer-events:none;
      }
      .gs-root .ss-meta-label { color: rgba(244,246,251,0.45); }
      .gs-root .ss-meta-value {
        background: linear-gradient(180deg, #FFFFFF 0%, rgba(255,255,255,0.55) 100%);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent;
        background-clip:text; color: transparent;
        text-shadow: 0 0 30px rgba(255,255,255,0.25);
      }

      /* ── Keyframes ────────────────────────────────────────────────────── */
      @keyframes gs-rise      { from{opacity:0; transform:translateY(28px);} to{opacity:1; transform:none;} }
      @keyframes gs-title-in  { from{opacity:0; transform:translateY(36px) scale(.985);}
                                to{opacity:1; transform:none;} }
      @keyframes gs-grow      { from{opacity:0; transform:scaleX(0);} to{opacity:1; transform:scaleX(1);} }
      @keyframes gs-float     { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-14px);} }
      @keyframes gs-spin      { to{transform:rotate(360deg);} }
      @keyframes gs-pulse-dot { 0%{box-shadow:0 0 0 0 rgba(34,197,94,0.55);}
                                70%{box-shadow:0 0 0 14px rgba(34,197,94,0);}
                                100%{box-shadow:0 0 0 0 rgba(34,197,94,0);} }
      @keyframes gs-scan      { 0%{clip-path: inset(0 0 100% 0); opacity:.0;}
                                15%{opacity:1;}
                                50%{clip-path: inset(0 0 0% 0); opacity:1;}
                                85%{opacity:1;}
                                100%{clip-path: inset(100% 0 0% 0); opacity:0;} }
      @keyframes gs-twinkle   { 0%,100%{opacity:0; transform:scale(.6);}
                                50%{opacity:.85; transform:scale(1);} }
      @keyframes gs-beam-fade { from{opacity:0;} to{opacity:1;} }
      @keyframes gs-beam-drift{ 0%,100%{transform:translateX(-2%);} 50%{transform:translateX(2%);} }
      @keyframes gs-hairline  { from{transform:scaleX(0);} to{transform:scaleX(1);} }
    `,
    ),
    h("div", { className: "gs-hairline" }),
    h("div", { className: "gs-orbit" }),
    h("div", { className: "gs-grid" }),
    h("div", { className: "gs-beam" }),
    h(
      "div",
      { className: "gs-stars" },
      ...STARS.map(([x, y, s, d], i) =>
        h("i", {
          key: i,
          style: {
            left: `${x}%`,
            top: `${y}%`,
            width: `${s}px`,
            height: `${s}px`,
            animationDelay: `${d}s`,
          },
        }),
      ),
    ),
    h(ContentLayout, c),
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. NEO-BRUTALISM — bouncy: pop with overshoot, tilt + press, blink.
// ─────────────────────────────────────────────────────────────────────────────

export function GlowFiFocusFrame(c: Resolved) {
  return h(
    "div",
    {
      className: "ss-root gf-focus-root",
      style: {
        ["--ss-bg" as any]: "#05070D",
        ["--ss-ink" as any]: "#F7F8FC",
        ["--ss-sub" as any]: "rgba(247,248,252,0.66)",
        ["--ss-accent" as any]: c.accent,
      },
    },
    h(
      "style",
      null,
      SHARED_LAYOUT +
        `
      @keyframes gf-focus-rise  { from{opacity:0; transform:translateY(26px);} to{opacity:1; transform:none;} }
      @keyframes gf-focus-grow  { from{opacity:0; transform:scaleX(0);} to{opacity:1; transform:scaleX(1);} }
      @keyframes gf-focus-sweep { from{transform:translateX(-16%) rotate(-8deg); opacity:0;} 35%{opacity:.55;} to{transform:translateX(10%) rotate(-8deg); opacity:.18;} }
      @keyframes gf-focus-orbit { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-10px);} }
      .gf-focus-root {
        background:
          radial-gradient(62% 90% at 76% 16%, rgba(99,102,241,0.34) 0%, transparent 62%),
          radial-gradient(70% 80% at 18% 8%, rgba(34,211,238,0.14) 0%, transparent 58%),
          linear-gradient(180deg, #0A0E19 0%, #05070D 68%, #030409 100%);
      }
      .gf-focus-spot { position:absolute; inset:-12%; z-index:1; pointer-events:none;
                       background: radial-gradient(40% 56% at 64% 30%, rgba(255,255,255,0.13) 0%, rgba(255,255,255,0.04) 26%, transparent 62%);
                       filter: blur(18px); }
      .gf-focus-beam { position:absolute; inset:-20%; z-index:1; pointer-events:none;
                       background: linear-gradient(104deg, transparent 34%, rgba(255,255,255,0.10) 48%, transparent 60%);
                       mix-blend-mode: screen; animation: gf-focus-sweep 2.6s cubic-bezier(.22,.61,.36,1) .25s both; }
      .gf-focus-orbit { position:absolute; right:-220px; top:-140px; width:720px; height:720px; z-index:1;
                        border-radius:50%; border:1px solid rgba(255,255,255,0.07);
                        box-shadow: inset 0 0 120px rgba(99,102,241,0.18);
                        animation: gf-focus-orbit 8s ease-in-out 1.2s infinite; }
      .gf-focus-orbit::before, .gf-focus-orbit::after {
        content:""; position:absolute; border-radius:50%; border:1px solid rgba(255,255,255,0.05);
      }
      .gf-focus-orbit::before { inset: 86px; }
      .gf-focus-orbit::after  { inset: 180px; }
      .gf-focus-frame { position:absolute; inset:20px; z-index:2; pointer-events:none;
                        border:1px solid rgba(255,255,255,0.06); border-radius:30px;
                        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02); }
      .gf-focus-root .ss-stage { padding: 64px 68px; }
      .gf-focus-root .ss-eyebrow,
      .gf-focus-root .ss-live {
        background: rgba(255,255,255,0.05);
        border:1px solid rgba(255,255,255,0.10);
        border-radius:999px; padding:8px 14px; backdrop-filter: blur(16px);
        animation: gf-focus-rise 1.0s cubic-bezier(.22,.61,.36,1) both;
      }
      .gf-focus-root .ss-live { animation-delay:.18s; }
      .gf-focus-root .ss-live-dot { background:#22D3EE; box-shadow: 0 0 12px rgba(34,211,238,.55); }
      .gf-focus-root .ss-title {
        max-width:78%; margin-top: 28px; font-size: 92px; font-weight: 620;
        text-shadow: 0 0 34px rgba(99,102,241,.26), 0 0 120px rgba(99,102,241,.18);
        animation: gf-focus-rise 1.25s cubic-bezier(.22,.61,.36,1) .28s both;
      }
      .gf-focus-root .ss-rule {
        width: 148px; height: 3px; border-radius:2px;
        background: linear-gradient(90deg, rgba(255,255,255,.14), var(--ss-accent), transparent);
        box-shadow: 0 0 26px rgba(99,102,241,.45);
        animation: gf-focus-grow 1.0s cubic-bezier(.22,.61,.36,1) .72s both;
      }
      .gf-focus-root .ss-subtitle {
        max-width: 58%; color: rgba(247,248,252,.70);
        animation: gf-focus-rise 1.1s cubic-bezier(.22,.61,.36,1) .54s both;
      }
      .gf-focus-root .ss-cta-row { animation: gf-focus-rise 1.1s cubic-bezier(.22,.61,.36,1) .76s both; }
      .gf-focus-root .ss-cta {
        background:#F7F8FC; color:#09101A; border:none; border-radius:12px;
        box-shadow: 0 18px 42px -12px rgba(99,102,241,.45);
      }
      .gf-focus-root .ss-cta-2 {
        background: rgba(255,255,255,0.04); color: var(--ss-ink);
        border:1px solid rgba(255,255,255,0.12); border-radius:12px;
      }
      .gf-focus-root .ss-kpis {
        gap: 18px; border-top:none; padding:22px;
        background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
        border:1px solid rgba(255,255,255,0.08); border-radius:22px;
        backdrop-filter: blur(18px);
        animation: gf-focus-rise 1.2s cubic-bezier(.22,.61,.36,1) .96s both;
      }
      .gf-focus-root .ss-kpi {
        padding: 0; background: transparent; border:none; box-shadow:none;
        animation: gf-focus-rise .9s cubic-bezier(.22,.61,.36,1) calc(1.02s + var(--i) * .12s) both;
      }
      .gf-focus-root .ss-meta-label { color: rgba(247,248,252,.44); }
      .gf-focus-root .ss-meta-value { color:#fff; text-shadow: 0 0 24px rgba(255,255,255,.12); }
    `,
    ),
    h("div", { className: "gf-focus-spot" }),
    h("div", { className: "gf-focus-beam" }),
    h("div", { className: "gf-focus-orbit" }),
    h("div", { className: "gf-focus-frame" }),
    h(ContentLayout, c),
  );
}

export function GlowFiPrismFrame(c: Resolved) {
  return h(
    "div",
    {
      className: "ss-root gf-prism-root",
      style: {
        ["--ss-bg" as any]: "#04060B",
        ["--ss-ink" as any]: "#F8FAFF",
        ["--ss-sub" as any]: "rgba(248,250,255,0.66)",
        ["--ss-accent" as any]: c.accent,
      },
    },
    h(
      "style",
      null,
      SHARED_LAYOUT +
        `
      @keyframes gf-prism-rise   { from{opacity:0; transform:translateY(24px) scale(.985);} to{opacity:1; transform:none;} }
      @keyframes gf-prism-glide  { from{opacity:0; transform:translateX(-18px) skewX(-10deg);} to{opacity:1; transform:none;} }
      @keyframes gf-prism-sheen  { 0%{transform:translateX(-18%) skewX(-18deg); opacity:0;} 30%{opacity:.45;} 100%{transform:translateX(24%) skewX(-18deg); opacity:0;} }
      @keyframes gf-prism-float  { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-8px);} }
      .gf-prism-root {
        background:
          radial-gradient(52% 80% at 12% 12%, rgba(34,211,238,0.18) 0%, transparent 62%),
          radial-gradient(48% 72% at 92% 18%, rgba(99,102,241,0.24) 0%, transparent 60%),
          linear-gradient(180deg, #09101A 0%, #04060B 72%, #020307 100%);
      }
      .gf-prism-grid { position:absolute; inset:0; z-index:1; pointer-events:none;
                       background-image: linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
                       background-size: 56px 56px; mask-image: radial-gradient(70% 72% at 50% 40%, #000 32%, transparent 90%); }
      .gf-prism-sheet { position:absolute; inset: 80px 80px 110px 80px; z-index:1; pointer-events:none;
                        border-radius:36px; overflow:hidden;
                        border:1px solid rgba(255,255,255,.08);
                        background: linear-gradient(140deg, rgba(255,255,255,.07), rgba(255,255,255,.01) 28%, rgba(255,255,255,.05) 64%, rgba(255,255,255,.015));
                        box-shadow: inset 0 1px 0 rgba(255,255,255,.05), 0 40px 100px rgba(0,0,0,.45); }
      .gf-prism-sheet::before { content:""; position:absolute; inset:-20% -10%;
                                background: linear-gradient(105deg, transparent 34%, rgba(255,255,255,.22) 47%, transparent 58%);
                                animation: gf-prism-sheen 2.4s cubic-bezier(.22,.61,.36,1) .45s both; }
      .gf-prism-stripe-a,
      .gf-prism-stripe-b,
      .gf-prism-stripe-c { position:absolute; inset:auto; z-index:1; pointer-events:none; border-radius:999px; filter: blur(0.5px); }
      .gf-prism-stripe-a { top: 110px; right: 160px; width: 520px; height: 2px; background: linear-gradient(90deg, transparent, rgba(34,211,238,.8), transparent); }
      .gf-prism-stripe-b { top: 158px; right: 120px; width: 460px; height: 2px; background: linear-gradient(90deg, transparent, rgba(255,255,255,.55), transparent); }
      .gf-prism-stripe-c { bottom: 186px; left: 120px; width: 420px; height: 2px; background: linear-gradient(90deg, transparent, rgba(99,102,241,.75), transparent); }
      .gf-prism-root .ss-stage { padding: 72px 76px; }
      .gf-prism-root .ss-eyebrow,
      .gf-prism-root .ss-live {
        background: rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.10);
        border-radius:999px; padding:8px 14px; backdrop-filter: blur(14px);
        animation: gf-prism-glide .9s cubic-bezier(.22,.61,.36,1) both;
      }
      .gf-prism-root .ss-live { animation-delay:.16s; }
      .gf-prism-root .ss-live-dot { background:#A78BFA; box-shadow: 0 0 14px rgba(167,139,250,.55); }
      .gf-prism-root .ss-title {
        max-width: 84%; margin-top: 34px; font-size: 90px; font-weight: 620;
        letter-spacing: -.04em;
        text-shadow: 0 0 44px rgba(99,102,241,.22);
        animation: gf-prism-rise 1.2s cubic-bezier(.22,.61,.36,1) .24s both;
      }
      .gf-prism-root .ss-rule {
        width: 112px; height: 3px; border-radius: 999px;
        background: linear-gradient(90deg, var(--ss-accent), #A78BFA, #22D3EE);
        box-shadow: 0 0 32px rgba(99,102,241,.45);
        animation: gf-prism-glide .9s cubic-bezier(.22,.61,.36,1) .66s both;
      }
      .gf-prism-root .ss-subtitle {
        max-width: 62%; color: rgba(248,250,255,.72);
        animation: gf-prism-rise 1.0s cubic-bezier(.22,.61,.36,1) .48s both;
      }
      .gf-prism-root .ss-cta-row { animation: gf-prism-rise 1.0s cubic-bezier(.22,.61,.36,1) .72s both; }
      .gf-prism-root .ss-cta {
        background: linear-gradient(180deg, #FCFDFF, #E7EBFF); color:#09101A; border:none; border-radius:12px;
        box-shadow: 0 18px 44px -16px rgba(99,102,241,.50);
      }
      .gf-prism-root .ss-cta-2 {
        background: rgba(255,255,255,.035); color: var(--ss-ink); border-radius:12px;
        border:1px solid rgba(255,255,255,.12);
      }
      .gf-prism-root .ss-kpis { gap: 18px; border-top:none; padding-top:0; animation: gf-prism-rise 1.1s cubic-bezier(.22,.61,.36,1) .92s both; }
      .gf-prism-root .ss-kpi {
        position:relative; padding:22px 22px 20px;
        background: linear-gradient(180deg, rgba(255,255,255,.08), rgba(255,255,255,.02));
        border:1px solid rgba(255,255,255,.10); border-radius:18px;
        backdrop-filter: blur(18px);
        box-shadow: 0 28px 60px -28px rgba(0,0,0,.75);
        animation: gf-prism-rise .95s cubic-bezier(.22,.61,.36,1) calc(1.0s + var(--i) * .14s) both,
                   gf-prism-float 6s ease-in-out calc(1.8s + var(--i) * .22s) infinite;
      }
      .gf-prism-root .ss-kpi::before {
        content:""; position:absolute; inset:0 0 auto 0; height:1px; border-radius:18px 18px 0 0;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,.35), transparent);
      }
      .gf-prism-root .ss-meta-label { color: rgba(248,250,255,.45); }
      .gf-prism-root .ss-meta-value {
        background: linear-gradient(180deg, #FFFFFF, rgba(255,255,255,.58));
        -webkit-background-clip:text; -webkit-text-fill-color:transparent;
        background-clip:text; color: transparent;
      }
    `,
    ),
    h("div", { className: "gf-prism-grid" }),
    h("div", { className: "gf-prism-sheet" }),
    h("div", { className: "gf-prism-stripe-a" }),
    h("div", { className: "gf-prism-stripe-b" }),
    h("div", { className: "gf-prism-stripe-c" }),
    h(ContentLayout, c),
  );
}

export function GlowFiSignalFrame(c: Resolved) {
  return h(
    "div",
    {
      className: "ss-root gf-signal-root",
      style: {
        ["--ss-bg" as any]: "#04070D",
        ["--ss-ink" as any]: "#F4F8FF",
        ["--ss-sub" as any]: "rgba(244,248,255,0.64)",
        ["--ss-accent" as any]: c.accent,
      },
    },
    h(
      "style",
      null,
      SHARED_LAYOUT +
        `
      @keyframes gf-signal-rise  { from{opacity:0; transform:translateY(22px);} to{opacity:1; transform:none;} }
      @keyframes gf-signal-grow  { from{opacity:0; transform:scaleX(0);} to{opacity:1; transform:scaleX(1);} }
      @keyframes gf-signal-scan  { 0%{transform:translateX(-22%); opacity:0;} 25%{opacity:.34;} 100%{transform:translateX(18%); opacity:0;} }
      @keyframes gf-signal-pulse { 0%,100%{opacity:.42;} 50%{opacity:.95;} }
      .gf-signal-root {
        background:
          radial-gradient(54% 76% at 86% 16%, rgba(99,102,241,0.28) 0%, transparent 58%),
          radial-gradient(44% 60% at 18% 100%, rgba(34,211,238,0.18) 0%, transparent 60%),
          linear-gradient(180deg, #07101B 0%, #04070D 72%, #020409 100%);
      }
      .gf-signal-rails { position:absolute; inset:18px; z-index:1; pointer-events:none; border-radius:28px;
                         border:1px solid rgba(255,255,255,.06); }
      .gf-signal-rails::before,
      .gf-signal-rails::after {
        content:""; position:absolute; left:26px; right:26px; height:1px;
        background: linear-gradient(90deg, transparent, rgba(99,102,241,.55), transparent);
      }
      .gf-signal-rails::before { top: 20px; }
      .gf-signal-rails::after  { bottom: 20px; }
      .gf-signal-bars { position:absolute; right:64px; top:96px; width:220px; height:140px; z-index:1; pointer-events:none; }
      .gf-signal-bars i { display:block; height:10px; margin-bottom:14px; border-radius:999px;
                          background: linear-gradient(90deg, rgba(255,255,255,.08), rgba(34,211,238,.55), rgba(255,255,255,.08)); }
      .gf-signal-bars i:nth-child(1) { width: 72%; }
      .gf-signal-bars i:nth-child(2) { width: 100%; }
      .gf-signal-bars i:nth-child(3) { width: 58%; }
      .gf-signal-bars i:nth-child(4) { width: 88%; }
      .gf-signal-sweep { position:absolute; inset:120px 80px 150px 80px; z-index:1; pointer-events:none; overflow:hidden; border-radius:28px; }
      .gf-signal-sweep::before { content:""; position:absolute; inset:-15% -10%;
                                 background: linear-gradient(106deg, transparent 36%, rgba(255,255,255,.16) 50%, transparent 62%);
                                 mix-blend-mode: screen; animation: gf-signal-scan 2.2s cubic-bezier(.22,.61,.36,1) .35s both; }
      .gf-signal-root .ss-stage { padding: 60px 68px; }
      .gf-signal-root .ss-eyebrow,
      .gf-signal-root .ss-live {
        background: rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.10);
        border-radius:999px; padding:8px 14px; backdrop-filter: blur(16px);
        animation: gf-signal-rise .9s cubic-bezier(.22,.61,.36,1) both;
      }
      .gf-signal-root .ss-live { animation-delay:.14s; }
      .gf-signal-root .ss-live-dot {
        background:#34D399; box-shadow: 0 0 12px rgba(52,211,153,.6);
        animation: gf-signal-pulse 1.7s ease-in-out 1.1s infinite;
      }
      .gf-signal-root .ss-title {
        max-width: 82%; margin-top: 30px; font-size: 90px; font-weight: 620;
        text-shadow: 0 0 22px rgba(255,255,255,.08), 0 0 84px rgba(99,102,241,.22);
        animation: gf-signal-rise 1.1s cubic-bezier(.22,.61,.36,1) .24s both;
      }
      .gf-signal-root .ss-rule {
        width: 148px; height: 4px; border-radius:999px;
        background: linear-gradient(90deg, rgba(255,255,255,.15) 0 18%, var(--ss-accent) 18% 48%, #22D3EE 48% 72%, rgba(255,255,255,.15) 72% 100%);
        box-shadow: 0 0 28px rgba(99,102,241,.42);
        animation: gf-signal-grow .9s cubic-bezier(.22,.61,.36,1) .64s both;
      }
      .gf-signal-root .ss-subtitle { max-width: 60%; animation: gf-signal-rise 1.0s cubic-bezier(.22,.61,.36,1) .46s both; }
      .gf-signal-root .ss-cta-row { animation: gf-signal-rise 1.0s cubic-bezier(.22,.61,.36,1) .7s both; }
      .gf-signal-root .ss-cta {
        border:none; border-radius:12px; background: linear-gradient(180deg, #FFFFFF, #E8EEFF); color:#09101A;
        box-shadow: 0 16px 44px -14px rgba(99,102,241,.55);
      }
      .gf-signal-root .ss-cta-2 {
        background: rgba(255,255,255,.04); border-radius:12px; color: var(--ss-ink);
        border:1px solid rgba(255,255,255,.12);
      }
      .gf-signal-root .ss-kpis { gap: 16px; border-top:none; padding-top:0; animation: gf-signal-rise 1.1s cubic-bezier(.22,.61,.36,1) .92s both; }
      .gf-signal-root .ss-kpi {
        position:relative; padding:20px 20px 18px;
        background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.015));
        border:1px solid rgba(255,255,255,.10); border-radius:16px;
        overflow:hidden; backdrop-filter: blur(18px);
        animation: gf-signal-rise .9s cubic-bezier(.22,.61,.36,1) calc(1.0s + var(--i) * .12s) both;
      }
      .gf-signal-root .ss-kpi::before {
        content:""; position:absolute; left:-10%; right:-10%; top:0; height:2px;
        background: linear-gradient(90deg, transparent, rgba(34,211,238,.7), rgba(99,102,241,.7), transparent);
      }
      .gf-signal-root .ss-kpi::after {
        content:""; position:absolute; left:20px; right:20px; bottom:16px; height:4px; border-radius:999px;
        background: linear-gradient(90deg, rgba(255,255,255,.10), rgba(52,211,153,.58)); opacity:.8;
      }
      .gf-signal-root .ss-meta-label { color: rgba(244,248,255,.44); }
      .gf-signal-root .ss-meta-value { color:#fff; }
    `,
    ),
    h("div", { className: "gf-signal-rails" }),
    h(
      "div",
      { className: "gf-signal-bars" },
      h("i"),
      h("i"),
      h("i"),
      h("i"),
    ),
    h("div", { className: "gf-signal-sweep" }),
    h(ContentLayout, c),
  );
}
