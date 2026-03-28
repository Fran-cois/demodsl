# Contributing to DemoDSL

Thanks for your interest in contributing to DemoDSL! This guide covers how to set up your development environment, run tests, and submit changes.

> 🇫🇷 Une version française est disponible : [CONTRIBUTING.fr.md](CONTRIBUTING.fr.md)

## Prerequisites

- Python 3.11 or 3.12
- [ffmpeg](https://ffmpeg.org/) installed and available in your `PATH`
- Git

## Local Setup

```bash
# Clone the repository
git clone https://github.com/Fran-cois/demodsl.git
cd demodsl

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install in dev mode with test dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium
```

## Project Structure

```
demodsl/
├── demodsl/           # Main source code
│   ├── models.py      # Pydantic v2 models (DSL)
│   ├── engine.py      # Execution engine
│   ├── commands.py    # Browser commands (Navigate, Click, Type…)
│   ├── cli.py         # CLI interface (Typer)
│   ├── config_loader.py
│   ├── effects/       # Visual effects registries (browser JS + post-processing)
│   ├── orchestrators/ # Pipeline orchestrators
│   └── providers/     # Factories (voice, browser, render, avatar)
├── tests/             # pytest tests
│   └── perf/          # Performance benchmarks
├── examples/          # Demo YAML files
├── docs/              # Documentation site (Next.js)
└── scripts/           # Generation and CI scripts
```

## Running Tests

```bash
# All tests (excluding perf)
pytest tests/

# With coverage (minimum threshold: 80%)
pytest tests/ --cov=demodsl --cov-report=term-missing

# Performance tests only
pytest tests/perf -m perf

# A specific test file
pytest tests/test_models.py -v
```

## Linting

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
# Check
ruff check demodsl/ tests/

# Auto-fix
ruff check --fix demodsl/ tests/

# Format
ruff format demodsl/ tests/
```

Make sure `ruff check` and `ruff format --check` pass before submitting a PR.

## Code Conventions

- **Pydantic v2** — All models inherit from `_StrictBase` (`extra="forbid"`).
- **Validators** — Use `field_validator` / `model_validator` for business constraints (paths, URLs, CSS colors).
- **Type hints** — Strict typing on all public signatures.
- **No `print()`** — Use `logging.getLogger(__name__)` for logging.
- **Tests** — Every new model or command must have test coverage.
- **Test file names** — `test_<module>.py` mirroring the source module.

## Contribution Workflow

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Implement** your changes with corresponding tests.

3. **Verify** everything passes:
   ```bash
   ruff check demodsl/ tests/
   ruff format --check demodsl/ tests/
   pytest tests/ --cov=demodsl
   ```

4. **Commit** with a clear message:
   ```bash
   git commit -m "feat: add frosted glass duration parameter"
   ```

5. **Push** and open a Pull Request against `main`.

## Commit Types

| Prefix     | Usage                                   |
|------------|-----------------------------------------|
| `feat:`    | New feature                             |
| `fix:`     | Bug fix                                 |
| `docs:`    | Documentation only                      |
| `test:`    | Adding / fixing tests                   |
| `refactor:`| Refactoring with no behavior change     |
| `perf:`    | Performance improvement                 |
| `chore:`   | Maintenance (CI, dependencies…)         |

## Adding a Visual Effect

1. Add the type to `EffectType` (Literal) in `models.py`.
2. Register valid parameters in `EFFECT_VALID_PARAMS` in the effects registry.
3. Implement the effect (browser JS in `effects/` or post-processing).
4. Add a test in `tests/test_effects_registry.py` (the exhaustivity test will automatically check consistency).
5. Create an example file `examples/demo_<effect>.yaml`.

## Adding a Voice Provider

1. Create a class inheriting from the abstract provider in `providers/`.
2. Register the new `engine` in the `VoiceConfig.engine` Literal in `models.py`.
3. Add required environment variables to the README.
4. Add a test in `tests/test_voice_providers.py`.

## Reporting a Bug

Open an [issue](https://github.com/Fran-cois/demodsl/issues) with:
- DemoDSL version (`pip show demodsl`)
- Python version
- Minimal YAML file reproducing the problem
- Full error message

## License

By contributing, you agree that your contributions will be released under the [MIT License](LICENSE).
