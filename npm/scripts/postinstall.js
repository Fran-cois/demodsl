"use strict";

const { execFileSync, execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const ROOT = path.resolve(__dirname, "..");
const IS_WIN = process.platform === "win32";
const VENV = path.join(ROOT, ".venv");
const PIP = IS_WIN
  ? path.join(VENV, "Scripts", "pip.exe")
  : path.join(VENV, "bin", "pip");
const PLAYWRIGHT = IS_WIN
  ? path.join(VENV, "Scripts", "playwright.exe")
  : path.join(VENV, "bin", "playwright");

const REQUIRED_PYTHON = [3, 11];
const DEMODSL_VERSION = require(path.join(ROOT, "package.json")).version;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function log(msg) {
  console.log(`[demodsl] ${msg}`);
}

function fail(msg) {
  console.error(`\n[demodsl] ERROR: ${msg}\n`);
  process.exit(1);
}

/** Try to find a working python binary. Returns the command name or null. */
function findPython() {
  const candidates = IS_WIN
    ? ["python", "python3", "py -3"]
    : ["python3", "python"];

  for (const cmd of candidates) {
    try {
      const out = execSync(`${cmd} --version 2>&1`, { encoding: "utf-8" });
      if (out.startsWith("Python ")) return cmd;
    } catch {
      // not found — try next
    }
  }
  return null;
}

/** Parse "Python 3.12.1" → [3, 12] */
function parsePythonVersion(cmd) {
  const out = execSync(`${cmd} --version 2>&1`, { encoding: "utf-8" }).trim();
  const match = out.match(/Python (\d+)\.(\d+)/);
  if (!match) return null;
  return [parseInt(match[1], 10), parseInt(match[2], 10)];
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  // Skip in CI-like environments where the user knows what they're doing
  if (process.env.DEMODSL_SKIP_POSTINSTALL === "1") {
    log("Skipping postinstall (DEMODSL_SKIP_POSTINSTALL=1)");
    return;
  }

  // 1. Find Python
  const pythonCmd = findPython();
  if (!pythonCmd) {
    fail(
      "Python not found.\n" +
        "  demodsl requires Python >= 3.11.\n" +
        "  Install it from https://www.python.org/downloads/ and make sure\n" +
        "  `python3` or `python` is available in your PATH."
    );
  }

  // 2. Check version
  const version = parsePythonVersion(pythonCmd);
  if (
    !version ||
    version[0] < REQUIRED_PYTHON[0] ||
    (version[0] === REQUIRED_PYTHON[0] && version[1] < REQUIRED_PYTHON[1])
  ) {
    fail(
      `Python >= ${REQUIRED_PYTHON.join(".")} is required, but found ${
        version ? version.join(".") : "unknown"
      }.\n` + "  Please upgrade: https://www.python.org/downloads/"
    );
  }

  log(`Found ${pythonCmd} ${version.join(".")}`);

  // 3. Create venv (skip if already present)
  if (!fs.existsSync(VENV)) {
    log("Creating isolated virtual environment...");
    execFileSync(pythonCmd, ["-m", "venv", VENV], { stdio: "inherit" });
  } else {
    log("Virtual environment already exists, reusing.");
  }

  // 4. Install demodsl from PyPI
  log(`Installing demodsl==${DEMODSL_VERSION} from PyPI...`);
  execFileSync(PIP, ["install", `demodsl==${DEMODSL_VERSION}`], {
    stdio: "inherit",
  });

  // 5. Install Playwright Chromium
  log("Installing Playwright Chromium browser...");
  execFileSync(PLAYWRIGHT, ["install", "chromium"], { stdio: "inherit" });

  log("Setup complete! Run `demodsl --help` to get started.");
}

try {
  main();
} catch (err) {
  fail(`Unexpected error during setup: ${err.message}`);
}
