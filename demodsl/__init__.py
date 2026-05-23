"""DemoDSL — DSL-driven automated product demo video generator."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("demodsl")
except PackageNotFoundError:
    __version__ = "3.1.1"  # fallback for editable installs without metadata

from demodsl.models import DemoStoppedError, StopCondition

__all__ = ["__version__", "DemoStoppedError", "StopCondition"]
