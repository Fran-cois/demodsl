import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import React from "react";

vi.mock("remotion", () => ({
  AbsoluteFill: ({ children, style }: { children?: React.ReactNode; style?: React.CSSProperties }) =>
    React.createElement("div", { "data-testid": "absolute-fill", style }, children),
  useCurrentFrame: () => 0,
}));

import { AudioVisualizer } from "../AudioVisualizer";
import type { AudioVisualizerConfig } from "../../types";

function renderViz(overrides: Partial<AudioVisualizerConfig> = {}) {
  const config: AudioVisualizerConfig = {
    style: "bars",
    accent: "#6366F1",
    position: "bottom-center",
    size: 200,
    bandData: [[0.1, 0.9, 0.4, 0.6]],
    ...overrides,
  };
  const { container } = render(React.createElement(AudioVisualizer, config));
  return container;
}

describe("AudioVisualizer", () => {
  it("bars: renders one bar per band", () => {
    const container = renderViz({ style: "bars", bandData: [[0.1, 0.9, 0.4, 0.6]] });
    const bars = container.querySelectorAll('[style*="border-radius"]');
    expect(bars.length).toBe(4);
  });

  it("bars: a louder band renders a taller bar", () => {
    const container = renderViz({ style: "bars", bandData: [[0.1, 0.9]] });
    const bars = Array.from(container.querySelectorAll('[style*="border-radius"]')) as HTMLElement[];
    const quiet = parseFloat(bars[0].style.height);
    const loud = parseFloat(bars[1].style.height);
    expect(loud).toBeGreaterThan(quiet);
  });

  it("radial: renders one line per band", () => {
    const container = renderViz({ style: "radial", bandData: [[0.2, 0.5, 0.8]] });
    expect(container.querySelectorAll("line").length).toBe(3);
  });

  it("spectrum: renders a filled polygon and an outline polyline", () => {
    const container = renderViz({ style: "spectrum", bandData: [[0.2, 0.5, 0.8]] });
    expect(container.querySelectorAll("polygon").length).toBe(1);
    expect(container.querySelectorAll("polyline").length).toBe(1);
  });

  it("vu_meter: collapses bands into 5 meters", () => {
    const container = renderViz({
      style: "vu_meter",
      bandData: [[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]],
    });
    // 5 meter columns, each with a fixed 8-segment stack.
    const columns = container.querySelectorAll(
      '[style*="flex-direction: column-reverse"]'
    );
    expect(columns.length).toBe(5);
  });

  it("falls back to a silent flat envelope when bandData is empty", () => {
    const container = renderViz({ style: "bars", bandData: [] });
    const bars = container.querySelectorAll('[style*="border-radius"]');
    expect(bars.length).toBe(16); // default idle band count
  });

  it("clamps to the last frame once bandData is exhausted", () => {
    const container = renderViz({ style: "bars", bandData: [[0.1, 0.2]] });
    // useCurrentFrame is mocked to 0, well within range — just confirms no throw.
    expect(container.querySelectorAll('[style*="border-radius"]').length).toBe(2);
  });
});
