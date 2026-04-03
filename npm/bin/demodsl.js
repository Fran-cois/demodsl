#!/usr/bin/env node
"use strict";

const { spawnSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const root = path.resolve(__dirname, "..");
const isWin = process.platform === "win32";

const venvBin = isWin
  ? path.join(root, ".venv", "Scripts", "demodsl.exe")
  : path.join(root, ".venv", "bin", "demodsl");

if (!fs.existsSync(venvBin)) {
  console.error(
    "demodsl: Python virtual environment not found.\n" +
      "Run `npm rebuild demodsl` or reinstall the package to trigger setup.\n" +
      "Expected binary at: " +
      venvBin
  );
  process.exit(1);
}

const result = spawnSync(venvBin, process.argv.slice(2), {
  stdio: "inherit",
  cwd: process.cwd(),
});

if (result.error) {
  console.error("demodsl: failed to start —", result.error.message);
  process.exit(1);
}

process.exit(result.status ?? 1);
