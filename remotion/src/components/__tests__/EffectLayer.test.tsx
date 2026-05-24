import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import React from "react";

// Mock Remotion hooks before importing the component
vi.mock("remotion", () => ({
  AbsoluteFill: ({ children, style }: { children?: React.ReactNode; style?: React.CSSProperties }) =>
    React.createElement("div", { "data-testid": "absolute-fill", style }, children),
  useCurrentFrame: () => 30,
  useVideoConfig: () => ({ durationInFrames: 120, fps: 30, width: 1920, height: 1080 }),
  interpolate: (input: number, inputRange: number[], outputRange: number[]) => {
    // Simple linear interpolation with clamping for tests
    if (input <= inputRange[0]) return outputRange[0];
    if (input >= inputRange[inputRange.length - 1]) return outputRange[outputRange.length - 1];
    for (let i = 0; i < inputRange.length - 1; i++) {
      if (input >= inputRange[i] && input <= inputRange[i + 1]) {
        const t = (input - inputRange[i]) / (inputRange[i + 1] - inputRange[i]);
        return outputRange[i] + (outputRange[i + 1] - outputRange[i]) * t;
      }
    }
    return outputRange[0];
  },
}));

import { EffectLayer } from "../EffectLayer";
import type { EffectConfig } from "../../types";

function renderEffect(effects: EffectConfig[]) {
  const { container } = render(React.createElement(EffectLayer, { effects }));
  return container;
}

function getTransform(container: HTMLElement): string {
  const fill = container.querySelector('[data-testid="absolute-fill"]') as HTMLElement | null;
  return fill?.style.transform ?? "";
}

describe("EffectLayer", () => {
  it("returns null for empty effects", () => {
    const container = renderEffect([]);
    expect(container.firstChild).toBeNull();
  });

  it("ken_burns applies scale + translate", () => {
    const c = renderEffect([{ type: "ken_burns", scale: 1.2, direction: "right" } as EffectConfig]);
    const t = getTransform(c);
    expect(t).toMatch(/scale\(/);
    expect(t).toMatch(/translate\(/);
  });

  it("zoom_pulse applies a scale", () => {
    const c = renderEffect([{ type: "zoom_pulse", scale: 1.5 } as EffectConfig]);
    expect(getTransform(c)).toMatch(/scale\(/);
  });

  it("parallax applies a scale", () => {
    const c = renderEffect([{ type: "parallax", intensity: 0.1 } as EffectConfig]);
    expect(getTransform(c)).toMatch(/scale\(1\.1\)/);
  });

  it("drone_zoom applies scale + translate", () => {
    const c = renderEffect([
      { type: "drone_zoom", scale: 2.0, targetX: 0.3, targetY: 0.7 } as EffectConfig,
    ]);
    const t = getTransform(c);
    expect(t).toMatch(/scale\(/);
    expect(t).toMatch(/translate\(/);
  });

  it("camera_shake applies translate", () => {
    const c = renderEffect([{ type: "camera_shake", intensity: 0.5, speed: 5 } as EffectConfig]);
    expect(getTransform(c)).toMatch(/translate\(/);
  });

  it("elastic_zoom applies scale", () => {
    const c = renderEffect([{ type: "elastic_zoom", scale: 1.4 } as EffectConfig]);
    expect(getTransform(c)).toMatch(/scale\(/);
  });

  it("zoom_to applies scale + translate honouring target", () => {
    const c = renderEffect([
      { type: "zoom_to", scale: 1.8, targetX: 0.25, targetY: 0.5 } as EffectConfig,
    ]);
    const t = getTransform(c);
    expect(t).toMatch(/scale\(/);
    expect(t).toMatch(/translate\(/);
  });

  it("vignette injects a radial-gradient overlay", () => {
    const c = renderEffect([{ type: "vignette", intensity: 0.6 } as EffectConfig]);
    const html = c.innerHTML;
    expect(html).toMatch(/radial-gradient/);
  });

  it("letterbox injects two black bars", () => {
    const c = renderEffect([{ type: "letterbox", ratio: 2.35 } as EffectConfig]);
    const bars = c.querySelectorAll('div[style*="background-color: rgb(0, 0, 0)"]');
    expect(bars.length).toBeGreaterThanOrEqual(2);
  });

  it("glitch may apply translateX depending on frame parity", () => {
    // frame=30 → 30 % 4 === 2 (no glitch), so transform should be empty/no translateX
    const c = renderEffect([{ type: "glitch", intensity: 0.5 } as EffectConfig]);
    // Just verify it renders without error
    expect(c.querySelector('[data-testid="absolute-fill"]')).not.toBeNull();
  });

  it("film_grain injects an overlay", () => {
    const c = renderEffect([{ type: "film_grain", intensity: 0.2 } as EffectConfig]);
    // jsdom strips data: url backgroundImage from innerHTML, so check overlay div exists.
    const overlays = c.querySelectorAll('div[style*="mix-blend-mode: overlay"]');
    expect(overlays.length).toBeGreaterThanOrEqual(1);
  });

  it("fade_in injects a black overlay", () => {
    const c = renderEffect([{ type: "fade_in", duration: 1.0 } as EffectConfig]);
    expect(c.innerHTML).toMatch(/background-color: rgb\(0, 0, 0\)/);
  });

  it("fade_out injects a black overlay", () => {
    const c = renderEffect([{ type: "fade_out", duration: 1.0 } as EffectConfig]);
    expect(c.innerHTML).toMatch(/background-color: rgb\(0, 0, 0\)/);
  });

  it("slide_in applies translate", () => {
    const c = renderEffect([
      { type: "slide_in", direction: "left", duration: 0.5 } as EffectConfig,
    ]);
    expect(getTransform(c)).toMatch(/translate\(/);
  });

  it("dolly_zoom applies scale", () => {
    const c = renderEffect([{ type: "dolly_zoom", intensity: 0.3 } as EffectConfig]);
    expect(getTransform(c)).toMatch(/scale\(/);
  });

  it("rotate applies scale + rotate", () => {
    const c = renderEffect([{ type: "rotate", angle: 5, speed: 1 } as EffectConfig]);
    const t = getTransform(c);
    expect(t).toMatch(/scale\(/);
    expect(t).toMatch(/rotate\(/);
  });

  it("combines multiple effects into a single transform string", () => {
    const c = renderEffect([
      { type: "ken_burns", scale: 1.2, direction: "right" } as EffectConfig,
      { type: "camera_shake", intensity: 0.2 } as EffectConfig,
    ]);
    const t = getTransform(c);
    expect(t.match(/scale\(/g)?.length).toBeGreaterThanOrEqual(1);
    expect(t.match(/translate\(/g)?.length).toBeGreaterThanOrEqual(2);
  });
});
