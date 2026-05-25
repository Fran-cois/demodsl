import React from "react";
import type { Resolved } from "./types";
export const h = React.createElement;

export function ContentLayout(c: Resolved) {
  return h(
    "div",
    { className: "ss-stage" },
    h(
      "div",
      { className: "ss-header" },
      h("div", { className: "ss-eyebrow" }, c.eyebrow),
      h(
        "div",
        { className: "ss-live" },
        h("span", { className: "ss-live-dot" }),
        h("span", null, "LIVE"),
      ),
    ),
    h("h1", { className: "ss-title" }, c.title),
    h("div", { className: "ss-rule" }),
    h("p", { className: "ss-subtitle" }, c.subtitle),
    h(
      "div",
      { className: "ss-cta-row" },
      h(
        "div",
        { className: "ss-cta" },
        c.cta,
        h("span", { className: "ss-cta-arrow" }, " \u2192"),
      ),
      h("div", { className: "ss-cta-2" }, c.cta2),
    ),
    h(
      "div",
      {
        className: "ss-kpis",
        style: { gridTemplateColumns: `repeat(${Math.max(c.meta.length, 1)}, 1fr)` },
      },
      c.meta.map((m, i) =>
        h(
          "div",
          { key: `${m.label}-${i}`, className: "ss-kpi", style: { ["--i" as any]: i } },
          h("div", { className: "ss-meta-label" }, m.label.toUpperCase()),
          h("div", { className: "ss-meta-value" }, m.value),
        ),
      ),
    ),
  );
}

// Shared layout geometry — every style sets COLOR/TYPO via CSS vars and
// then overrides specific selectors for animation/decoration.
export const SHARED_LAYOUT = `
  .ss-root { width:100%; height:100%; position:relative; overflow:hidden; box-sizing:border-box;
             color: var(--ss-ink); background: var(--ss-bg);
             font-family: var(--ss-font, "Inter", -apple-system, system-ui, sans-serif); }
  .ss-stage { position:relative; z-index:2; width:100%; height:100%;
              padding: 56px 64px; box-sizing:border-box;
              display:flex; flex-direction:column; gap:18px; }
  .ss-header { display:flex; justify-content:space-between; align-items:center; }
  .ss-eyebrow { font-size:12px; letter-spacing:0.24em; text-transform:uppercase;
                color: var(--ss-sub); font-weight:600; }
  .ss-live { display:flex; align-items:center; gap:8px; font-size:12px;
             letter-spacing:0.22em; color: var(--ss-sub); font-weight:600; }
  .ss-live-dot { width:8px; height:8px; border-radius:50%; background: var(--ss-accent); }
  .ss-title { margin: 18px 0 0; font-size: 84px; line-height: 1.02;
              letter-spacing: -0.025em; font-weight: 700;
              font-family: var(--ss-title-font, inherit);
              color: var(--ss-ink); max-width: 92%; }
  .ss-rule { width: 96px; height: 4px; background: var(--ss-accent); margin-top: 22px;
             transform-origin: left center; }
  .ss-subtitle { margin: 22px 0 0; font-size: 22px; line-height: 1.5;
                 color: var(--ss-sub); max-width: 70%; }
  .ss-cta-row { display:flex; gap:14px; margin-top: 12px; align-items:center; }
  .ss-cta { display:inline-flex; align-items:center; gap:6px;
            background: var(--ss-ink); color: var(--ss-bg);
            padding: 14px 22px; border-radius: 10px; font-weight: 600; font-size: 15px;
            border: 1px solid var(--ss-ink); }
  .ss-cta-2 { padding: 14px 20px; border-radius: 10px; font-weight: 600; font-size: 15px;
              background: transparent; color: var(--ss-ink);
              border: 1px solid rgba(0,0,0,0.18); }
  .ss-kpis { display:grid; gap: 24px; margin-top: auto;
             padding-top: 26px; border-top: 1px solid rgba(0,0,0,0.18); }
  .ss-meta-label { font-size: 11px; letter-spacing: 0.28em; color: var(--ss-sub);
                   font-family: "JetBrains Mono","SF Mono",ui-monospace,monospace;
                   margin-bottom: 8px; }
  .ss-meta-value { font-size: 46px; line-height: 1; letter-spacing: -0.02em;
                   font-variant-numeric: tabular-nums; font-weight: 700;
                   font-family: var(--ss-num-font, inherit); }
`;
