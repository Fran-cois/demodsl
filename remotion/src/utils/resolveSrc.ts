import { staticFile } from "remotion";

/**
 * Resolve a media src for use in Remotion components.
 *
 * - HTTP/HTTPS URLs are returned as-is.
 * - Anything else is treated as a relative path inside the publicDir
 *   and resolved via staticFile().
 */
export const resolveSrc = (src: string): string => {
  if (!src) return src;
  if (src.startsWith("http://") || src.startsWith("https://")) {
    return src;
  }
  // Strip a leading slash so staticFile gets a relative path
  return staticFile(src.replace(/^\/+/, ""));
};
