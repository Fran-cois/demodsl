# demodsl

> DSL-driven automated product demo video generator — npm wrapper

This package installs the [demodsl](https://github.com/Fran-cois/demodsl) CLI tool via npm. It wraps the Python package in an isolated virtual environment so you can use it from any Node.js project.

## Prerequisites

- **Node.js** >= 16
- **Python** >= 3.11 (must be available as `python3` or `python` in your PATH)

## Install

```bash
# Global install (recommended)
npm install -g demodsl

# Or use directly with npx
npx demodsl run demo.yaml
```

During installation, the postinstall script will automatically:

1. Create an isolated Python virtual environment
2. Install `demodsl` from PyPI
3. Install Playwright Chromium

## Usage

```bash
# Initialize a new demo config
demodsl init

# Run a demo
demodsl run demo.yaml

# Validate a config without executing
demodsl validate demo.yaml

# Dry run (validate + log, no execution)
demodsl run demo.yaml --dry-run
```

All CLI arguments are passed through to the Python `demodsl` CLI. Run `demodsl --help` for the full list of options.

## Troubleshooting

**Python not found**: Make sure `python3` (or `python` on Windows) is in your PATH and is version 3.11+.

**Reinstall the venv**: Run `npm rebuild demodsl` to re-trigger the postinstall setup.

**Skip postinstall**: Set `DEMODSL_SKIP_POSTINSTALL=1` to skip automatic setup (useful in CI when you manage the Python env yourself).

## License

MIT
