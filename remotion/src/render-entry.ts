/**
 * Render entry point — called from Python via subprocess.
 *
 * Usage:
 *   npx tsx src/render-entry.ts --props /path/to/props.json --output /path/to/output.mp4
 *
 * Reads DemoProps JSON, calculates total duration, and renders the composition.
 */

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import * as path from "path";
import * as fs from "fs";
import type { DemoProps } from "./types";
import { parseConcurrency } from "./utils/renderOptions";

async function main() {
  const args = process.argv.slice(2);
  const propsIndex = args.indexOf("--props");
  const outputIndex = args.indexOf("--output");
  const publicDirIndex = args.indexOf("--public-dir");

  if (propsIndex === -1 || outputIndex === -1) {
    console.error("Usage: --props <path.json> --output <path.mp4> [--public-dir <dir>]");
    process.exit(1);
  }

  const propsPath = args[propsIndex + 1];
  const outputPath = args[outputIndex + 1];
  const publicDir =
    publicDirIndex !== -1 ? args[publicDirIndex + 1] : undefined;

  if (!propsPath || !outputPath) {
    console.error("Missing required arguments");
    process.exit(1);
  }

  // Read and parse props
  const propsJson = fs.readFileSync(propsPath, "utf-8");
  const props: DemoProps = JSON.parse(propsJson);

  // Calculate total duration in frames
  const fps = props.fps || 30;
  const introDur = props.intro?.durationInSeconds ?? 0;
  const outroDur = props.outro?.durationInSeconds ?? 0;
  const segmentsDur = props.segments.reduce(
    (sum, s) => sum + s.durationInSeconds,
    0
  );
  const totalDurationInFrames = Math.ceil(
    (introDur + segmentsDur + outroDur) * fps
  );

  if (totalDurationInFrames <= 0) {
    console.error("Total duration is 0 — no segments provided");
    process.exit(1);
  }

  console.log(
    `Rendering: ${totalDurationInFrames} frames (${(totalDurationInFrames / fps).toFixed(1)}s) at ${fps}fps`
  );
  console.log(
    `  Intro: ${introDur}s, Segments: ${segmentsDur.toFixed(1)}s, Outro: ${outroDur}s`
  );

  // Bundle the Remotion project
  const entryPoint = path.join(__dirname, "index.ts");
  console.log("Bundling Remotion project...");
  const bundled = await bundle({
    entryPoint,
    webpackOverride: (config) => config,
    ...(publicDir ? { publicDir } : {}),
  });

  // Select the composition
  const composition = await selectComposition({
    serveUrl: bundled,
    id: "DemoComposition",
    inputProps: props,
  });

  // Override duration from calculated value
  composition.durationInFrames = totalDurationInFrames;
  composition.fps = fps;
  composition.width = props.width;
  composition.height = props.height;

  // Ensure output directory exists
  const outputDir = path.dirname(outputPath);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Render
  console.log(`Rendering to ${outputPath}...`);
  const concurrency = parseConcurrency(process.env.REMOTION_CONCURRENCY);
  if (concurrency !== null) {
    console.log(`  Concurrency: ${concurrency}`);
  }
  let lastLoggedPct = -1;
  await renderMedia({
    composition,
    serveUrl: bundled,
    codec: "h264",
    outputLocation: outputPath,
    inputProps: props,
    ...(concurrency !== null ? { concurrency } : {}),
    ...(publicDir ? { publicDir } : {}),
    onProgress: ({ progress }) => {
      const pct = Math.round(progress * 100);
      if (pct % 10 === 0) {
        process.stdout.write(`\r  Progress: ${pct}%`);
      }
      // The `\r`-updated line above never reaches a caller that reads this
      // process's stdout line-by-line (it has no trailing "\n"), so the
      // parent's progress bar sees nothing for the whole render and looks
      // frozen. Emit a real newline-terminated line at each new milestone
      // too, so a line-based reader can surface incremental progress.
      if (pct >= lastLoggedPct + 10) {
        lastLoggedPct = pct - (pct % 10);
        console.log(`\nRemotion progress: ${pct}%`);
      }
    },
  });

  console.log(`\nDone: ${outputPath}`);
}

main().catch((err) => {
  console.error("Render failed:", err);
  process.exit(1);
});
