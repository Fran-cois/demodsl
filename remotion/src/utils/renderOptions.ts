/**
 * Rendering knobs read from the environment.
 *
 * Rasterisation is the dominant cost of a composition and scales with the
 * number of Chrome tabs Remotion runs in parallel, so the render worker has to
 * be able to match it to the machine it lands on without a rebuild.
 */

/**
 * Parse `REMOTION_CONCURRENCY`.
 *
 * Returns `null` — Remotion's "decide for me" — when unset or unusable, so a
 * typo degrades to the default instead of failing the render.
 */
export const parseConcurrency = (
  raw: string | undefined
): number | null => {
  if (raw === undefined || raw.trim() === "") {
    return null;
  }
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 1) {
    return null;
  }
  return value;
};
