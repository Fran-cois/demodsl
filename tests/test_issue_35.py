"""Regression tests for issue #35.

``voice.engine: gtts`` was an accepted ``Literal`` value, registered in the
factory, and declared in no dependency or extra: the config passed
``demodsl validate`` and then died with a bare ``ModuleNotFoundError`` deep in
``providers/voice.py``, after the run had started.

Three guarantees are covered here:

1. the ``gtts`` extra exists, so there is something to point users at;
2. ``VoiceProviderFactory.create`` fails fast with the install command;
3. ``validate`` surfaces the gap *before* anything is rendered.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from demodsl.providers.base import (
    VOICE_ENGINE_REQUIREMENTS,
    MissingVoiceDependencyError,
    VoiceProviderFactory,
    missing_voice_dependency,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestExtraIsDeclared:
    def test_pyproject_declares_a_gtts_extra(self) -> None:
        import tomllib

        data = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        extras = data["project"]["optional-dependencies"]
        assert "gtts" in extras, "voice.engine 'gtts' must be installable via an extra"
        assert any(spec.startswith("gtts") for spec in extras["gtts"])

    def test_install_hint_matches_the_declared_extra(self) -> None:
        _module, install = VOICE_ENGINE_REQUIREMENTS["gtts"]
        assert "demodsl[gtts]" in install


class TestRequirementsMap:
    def test_every_requirement_is_a_registered_engine(self) -> None:
        import demodsl.providers.voice  # noqa: F401  (populates the registry)

        registered = set(VoiceProviderFactory._registry)
        assert set(VOICE_ENGINE_REQUIREMENTS) <= registered

    def test_every_requirement_is_a_valid_config_value(self) -> None:
        from demodsl.models import VoiceConfig

        for engine in VOICE_ENGINE_REQUIREMENTS:
            VoiceConfig(engine=engine)  # type: ignore[arg-type]

    def test_engines_without_a_python_package_are_not_listed(self) -> None:
        # These reach their backend over HTTP or through an external binary;
        # listing them would produce a bogus "pip install" hint.
        for engine in ("elevenlabs", "openai", "azure", "espeak", "piper", "dummy"):
            assert engine not in VOICE_ENGINE_REQUIREMENTS

    def test_unknown_engine_has_no_requirement(self) -> None:
        assert missing_voice_dependency("does-not-exist") is None


class TestFactoryFailsFast:
    def test_create_raises_actionable_error_when_package_missing(self, monkeypatch) -> None:
        import demodsl.providers.voice  # noqa: F401

        monkeypatch.setattr(
            "demodsl.providers.base.importlib.util.find_spec",
            lambda name: None,
        )
        with pytest.raises(MissingVoiceDependencyError) as excinfo:
            VoiceProviderFactory.create("gtts")

        message = str(excinfo.value)
        assert "gtts" in message
        assert "pip install 'demodsl[gtts]'" in message
        assert excinfo.value.engine == "gtts"

    def test_error_is_not_swallowed_by_the_dummy_fallback(self) -> None:
        # ``orchestrators/narration`` falls back to the silent dummy provider on
        # OSError/ValueError. A missing package must not produce a mute video.
        assert not issubclass(MissingVoiceDependencyError, OSError | ValueError)
        assert issubclass(MissingVoiceDependencyError, RuntimeError)

    def test_create_succeeds_when_package_present(self, monkeypatch, tmp_path: Path) -> None:
        import demodsl.providers.voice  # noqa: F401

        monkeypatch.setattr(
            "demodsl.providers.base.importlib.util.find_spec",
            lambda name: object(),
        )
        provider = VoiceProviderFactory.create("gtts", output_dir=tmp_path)
        assert provider is not None

    def test_namespace_package_lookup_error_is_treated_as_missing(self, monkeypatch) -> None:
        # ``find_spec("google.cloud.texttospeech")`` raises when ``google`` is
        # absent instead of returning None.
        def boom(name: str):
            raise ModuleNotFoundError(name)

        monkeypatch.setattr("demodsl.providers.base.importlib.util.find_spec", boom)
        assert missing_voice_dependency("google") == VOICE_ENGINE_REQUIREMENTS["google"]


class TestValidateWarns:
    def _config(self, engine: str = "gtts"):
        from demodsl.models import DemoConfig

        return DemoConfig(
            metadata={"title": "T"},
            voice={"engine": engine, "voice_id": "en"},
            scenarios=[
                {
                    "name": "S",
                    "url": "https://example.com",
                    "steps": [{"action": "navigate", "url": "https://example.com"}],
                }
            ],
        )

    def test_diagnose_reports_the_missing_dependency(self, monkeypatch) -> None:
        from demodsl.diagnostics import DIAGNOSTIC_CODES, voice_dependency_diagnostics

        monkeypatch.setattr(
            "demodsl.providers.base.importlib.util.find_spec",
            lambda name: None,
        )
        diags = voice_dependency_diagnostics(self._config())
        assert [d.code for d in diags] == ["voice.missing_dependency"]
        assert "voice.missing_dependency" in DIAGNOSTIC_CODES
        assert diags[0].path == "voice.engine"
        assert diags[0].hint == "pip install 'demodsl[gtts]'"

    def test_it_is_a_warning_not_an_error(self, monkeypatch) -> None:
        # The config is correct; it is this machine that cannot render it.
        # Authoring on a laptop and rendering on a worker is a normal split, so
        # ``validate --json`` must still report ``ok: true``.
        from demodsl.diagnostics import ERROR, voice_dependency_diagnostics

        monkeypatch.setattr(
            "demodsl.providers.base.importlib.util.find_spec",
            lambda name: None,
        )
        assert all(d.severity != ERROR for d in voice_dependency_diagnostics(self._config()))

    def test_silent_when_the_package_is_installed(self, monkeypatch) -> None:
        from demodsl.diagnostics import voice_dependency_diagnostics

        monkeypatch.setattr(
            "demodsl.providers.base.importlib.util.find_spec",
            lambda name: object(),
        )
        assert voice_dependency_diagnostics(self._config()) == []

    def test_per_language_voices_are_checked_too(self, monkeypatch) -> None:
        from demodsl.diagnostics import voice_dependency_diagnostics
        from demodsl.models import DemoConfig

        monkeypatch.setattr(
            "demodsl.providers.base.importlib.util.find_spec",
            lambda name: None,
        )
        config = DemoConfig(
            metadata={"title": "T"},
            voice={"engine": "elevenlabs"},
            languages={"default": "en", "voices": {"fr": {"engine": "gtts", "voice_id": "fr"}}},
            scenarios=[
                {
                    "name": "S",
                    "url": "https://example.com",
                    "steps": [{"action": "navigate", "url": "https://example.com"}],
                }
            ],
        )
        diags = voice_dependency_diagnostics(config)
        assert [d.path for d in diags] == ["languages.voices.fr.engine"]

    def test_cli_validate_prints_the_install_command(self, monkeypatch, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from demodsl.cli import app

        config = tmp_path / "demo.yaml"
        config.write_text(
            "metadata:\n"
            "  title: T\n"
            "voice:\n"
            "  engine: gtts\n"
            "  voice_id: en\n"
            "scenarios:\n"
            "  - name: S\n"
            "    url: https://example.com\n"
            "    steps:\n"
            "      - action: navigate\n"
            "        url: https://example.com\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "demodsl.providers.base.importlib.util.find_spec",
            lambda name: None,
        )
        result = CliRunner().invoke(app, ["validate", str(config)])
        assert result.exit_code == 0, result.output
        assert "demodsl[gtts]" in result.output
