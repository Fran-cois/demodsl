import { describe, expect, it } from "vitest";

import { parseConcurrency } from "../renderOptions";

describe("parseConcurrency", () => {
  it("falls back to Remotion's own choice when unset", () => {
    expect(parseConcurrency(undefined)).toBeNull();
    expect(parseConcurrency("")).toBeNull();
    expect(parseConcurrency("   ")).toBeNull();
  });

  it("accepts a positive integer", () => {
    expect(parseConcurrency("8")).toBe(8);
    expect(parseConcurrency("1")).toBe(1);
  });

  it("ignores values that would break the render", () => {
    // A typo must degrade to the default rather than fail the whole render.
    expect(parseConcurrency("0")).toBeNull();
    expect(parseConcurrency("-4")).toBeNull();
    expect(parseConcurrency("2.5")).toBeNull();
    expect(parseConcurrency("many")).toBeNull();
  });
});
