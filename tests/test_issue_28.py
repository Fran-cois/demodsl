"""Regression tests for GitHub issue #28.

A web scenario used to accept a mobile-only locator strategy
(``accessibility_id``, ``class_name``, ``android_uiautomator``,
``ios_predicate``, ``ios_class_chain``), pass ``demodsl validate``, and then
die **mid-render** with ``ValueError: Unsupported locator type`` — after the
browser recording and the TTS work, and outside the reach of the per-step
``on_error`` policy.

The three expectations from the report are covered here:

1. validate per provider, at load time, naming the allowed set;
2. make the runtime failure degradable, so ``on_error`` applies;
3. expose the support matrix machine-readably, so a generator never proposes
   an unusable strategy in the first place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml
from pydantic import ValidationError

from demodsl.models import (
    LOCATOR_SUPPORT,
    MOBILE_ONLY_LOCATOR_TYPES,
    WEB_LOCATOR_TYPES,
    DemoConfig,
    Locator,
    Metadata,
    Scenario,
    Step,
    supported_locator_types,
)

# The exact config from the report.
REPRO = {
    "metadata": {"title": "repro"},
    "scenarios": [
        {
            "name": "web",
            "url": "https://example.com",
            "provider": "playwright",
            "steps": [
                {"action": "navigate", "url": "https://example.com"},
                {
                    "action": "hover",
                    "locator": {"type": "accessibility_id", "value": "link:Home"},
                },
            ],
        }
    ],
}


# ── 1. Validate per provider ─────────────────────────────────────────────────


class TestLoadTimeValidation:
    def test_repro_is_rejected_at_load_time(self) -> None:
        """`demodsl validate` used to say OK, then `demodsl run` crashed."""
        with pytest.raises(ValidationError) as excinfo:
            DemoConfig(**REPRO)

        message = str(excinfo.value)
        assert "accessibility_id" in message
        assert "not supported by web scenarios" in message

    def test_message_names_the_allowed_set(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            DemoConfig(**REPRO)

        message = str(excinfo.value)
        for allowed in sorted(WEB_LOCATOR_TYPES):
            assert allowed in message
        # …and points at the way out.
        assert "mobile-only strategy" in message

    def test_the_failing_step_is_identified(self) -> None:
        with pytest.raises(ValidationError, match="Step 2"):
            DemoConfig(**REPRO)

    @pytest.mark.parametrize("locator_type", sorted(MOBILE_ONLY_LOCATOR_TYPES))
    def test_every_mobile_only_strategy_is_rejected_on_web(self, locator_type: str) -> None:
        with pytest.raises(ValidationError):
            Scenario(
                name="web",
                url="https://example.com",
                steps=[Step(action="hover", locator=Locator(type=locator_type, value="x"))],
            )

    @pytest.mark.parametrize("locator_type", sorted(WEB_LOCATOR_TYPES))
    def test_web_strategies_still_pass(self, locator_type: str) -> None:
        scenario = Scenario(
            name="web",
            url="https://example.com",
            steps=[Step(action="hover", locator=Locator(type=locator_type, value="x"))],
        )
        assert scenario.subsystem == "web"

    def test_mobile_scenarios_accept_their_own_strategies(self) -> None:
        scenario = Scenario(
            name="app",
            mobile={
                "platform": "ios",
                "bundle_id": "com.acme.app",
                "device_name": "iPhone 15",
            },
            steps=[Step(action="tap", locator=Locator(type="accessibility_id", value="link:Home"))],
        )
        assert scenario.subsystem == "mobile"

    def test_pre_steps_are_checked_too(self) -> None:
        with pytest.raises(ValidationError, match="Pre-step 1"):
            Scenario(
                name="web",
                url="https://example.com",
                pre_steps=[Step(action="hover", locator=Locator(type="ios_predicate", value="x"))],
                steps=[Step(action="navigate", url="https://example.com")],
            )

    def test_target_locator_is_checked_too(self) -> None:
        """`drag` carries a second locator that the render also has to resolve."""
        with pytest.raises(ValidationError, match="Step 1"):
            Scenario(
                name="web",
                url="https://example.com",
                steps=[
                    Step(
                        action="drag",
                        locator=Locator(type="css", value="#a"),
                        target_locator=Locator(type="class_name", value="B"),
                    )
                ],
            )

    def test_validate_cli_now_fails_the_repro(self, tmp_path: Path) -> None:
        """The reported symptom was `demodsl validate` → OK."""
        from typer.testing import CliRunner

        from demodsl.cli import app

        config = tmp_path / "demo.yaml"
        config.write_text(yaml.safe_dump(REPRO), encoding="utf-8")

        result = CliRunner().invoke(app, ["validate", str(config)])

        assert result.exit_code != 0


# ── 2. The runtime failure must be degradable ────────────────────────────────


class _WebBrowser:
    """A web provider handed a mobile-only locator, as the real one behaves."""

    viewport_size = (1920, 1080)

    def __init__(self) -> None:
        self.evaluated: list[str] = []

    @staticmethod
    def _resolve(locator: Locator) -> str:
        from demodsl.providers.browser import PlaywrightBrowserProvider

        return PlaywrightBrowserProvider._resolve_selector(locator)

    def hover(self, locator: Locator) -> None:
        self._resolve(locator)

    def click(self, locator: Locator) -> None:
        self._resolve(locator)

    def navigate(self, url: str) -> None:
        pass

    def scroll_into_view(self, locator: Locator) -> bool:
        return False

    def evaluate_js(self, script: str) -> Any:
        self.evaluated.append(script)
        return 0

    def get_element_bbox(self, locator: Locator) -> dict[str, float] | None:
        return None

    def get_element_center(self, locator: Locator) -> tuple[float, float] | None:
        return None


def _orchestrator(step: Step):
    from demodsl.effects.registry import EffectRegistry
    from demodsl.orchestrators.scenario import ScenarioOrchestrator

    # model_construct all the way down: this exercises the runtime backstop
    # for configs built in code, which the load-time guard never sees.
    config = DemoConfig.model_construct(
        metadata=Metadata(title="t"),
        scenarios=[Scenario.model_construct(name="s", url="https://example.com", steps=[step])],
    )
    return ScenarioOrchestrator(config, EffectRegistry(), turbo=True)


class TestRuntimeIsDegradable:
    def _step(self, **kwargs: Any) -> Step:
        # model_construct bypasses the new load-time guard on purpose: this
        # is the "config built in code" path the runtime backstop exists for.
        return Step.model_construct(
            action="hover",
            locator=Locator(type="accessibility_id", value="link:Home"),
            **kwargs,
        )

    def test_unsupported_locator_obeys_the_on_error_policy(self, tmp_path: Path) -> None:
        """It used to escape the policy: the error was raised while resolving."""
        step = self._step()
        orch = _orchestrator(step)
        ws = MagicMock()
        ws.frames = tmp_path

        orch._execute_step(_WebBrowser(), step, ws)  # must not raise

        assert orch.skipped_steps
        assert orch.skipped_steps[0]["code"] == "step.locator_unsupported"

    def test_on_error_fail_still_aborts(self, tmp_path: Path) -> None:
        from demodsl.providers.base import UnsupportedLocatorError

        step = self._step(on_error="fail")
        orch = _orchestrator(step)
        ws = MagicMock()
        ws.frames = tmp_path

        with pytest.raises(UnsupportedLocatorError):
            orch._execute_step(_WebBrowser(), step, ws)

    def test_error_is_recognised_as_a_locator_problem(self) -> None:
        from demodsl.orchestrators.scenario import ScenarioOrchestrator
        from demodsl.providers.base import UnsupportedLocatorError

        exc = UnsupportedLocatorError("accessibility_id", "web")
        assert ScenarioOrchestrator._is_missing_element_error(exc)
        assert ScenarioOrchestrator._diagnostic_code(exc) == "step.locator_unsupported"

    def test_error_message_names_the_supported_set(self) -> None:
        from demodsl.providers.base import UnsupportedLocatorError

        message = str(UnsupportedLocatorError("accessibility_id", "web"))
        assert "css" in message and "xpath" in message

    def test_error_is_still_a_value_error(self) -> None:
        """Existing `except ValueError` handlers must keep working."""
        from demodsl.providers.base import UnsupportedLocatorError

        assert issubclass(UnsupportedLocatorError, ValueError)

    def test_element_helpers_degrade_instead_of_raising(self) -> None:
        """These resolved the selector *outside* their try, so they exploded."""
        from demodsl.providers.browser import PlaywrightBrowserProvider

        provider = PlaywrightBrowserProvider()
        provider._page = MagicMock()
        locator = Locator(type="accessibility_id", value="link:Home")

        assert provider.get_element_bbox(locator) is None
        assert provider.get_element_center(locator) is None
        assert provider.scroll_into_view(locator) is False

    def test_mobile_provider_reports_the_mobile_set(self) -> None:
        from demodsl.providers.base import UnsupportedLocatorError
        from demodsl.providers.mobile import _build_locator_args

        with pytest.raises(UnsupportedLocatorError) as excinfo:
            _build_locator_args(Locator.model_construct(type="nonexistent", value="x"))
        assert excinfo.value.subsystem == "mobile"


# ── 3. Machine-readable support matrix ───────────────────────────────────────


class TestCapabilityMatrix:
    def test_matrix_is_exposed_in_the_manifest(self) -> None:
        from demodsl.capabilities import build_manifest

        manifest = build_manifest()
        assert manifest["locator_support"]["web"] == sorted(WEB_LOCATOR_TYPES)
        assert "accessibility_id" in manifest["locator_support"]["mobile"]
        assert manifest["locator_types"]["accessibility_id"] == ["mobile"]

    def test_manifest_matrix_is_derived_not_duplicated(self) -> None:
        """The hand-written copy had already drifted (it claimed css was web-only)."""
        from demodsl.capabilities import build_manifest

        manifest = build_manifest()
        for subsystem, types_ in LOCATOR_SUPPORT.items():
            assert manifest["locator_support"][subsystem] == sorted(types_)

    def test_matrix_matches_what_the_web_provider_implements(self) -> None:
        """The whole bug: the schema advertised more than the provider had."""
        from demodsl.providers.base import UnsupportedLocatorError
        from demodsl.providers.browser import PlaywrightBrowserProvider

        for locator_type in supported_locator_types("web"):
            PlaywrightBrowserProvider._resolve_selector(Locator(type=locator_type, value="x"))
        for locator_type in MOBILE_ONLY_LOCATOR_TYPES:
            with pytest.raises(UnsupportedLocatorError):
                PlaywrightBrowserProvider._resolve_selector(Locator(type=locator_type, value="x"))

    def test_matrix_matches_what_the_mobile_provider_implements(self) -> None:
        from demodsl.providers.mobile import _LOCATOR_MAP

        assert set(_LOCATOR_MAP) == set(supported_locator_types("mobile"))

    def test_diagnostics_emit_a_stable_code(self) -> None:
        from demodsl.diagnostics import DIAGNOSTIC_CODES, diagnose_raw

        diagnostics, config = diagnose_raw(REPRO)

        assert config is None
        codes = {d.code for d in diagnostics}
        assert "step.locator_unsupported" in codes
        assert "step.locator_unsupported" in DIAGNOSTIC_CODES

    def test_diagnostic_points_at_the_scenario_and_hints_the_fix(self) -> None:
        from demodsl.diagnostics import diagnose_raw

        diagnostics, _ = diagnose_raw(REPRO)
        finding = next(d for d in diagnostics if d.code == "step.locator_unsupported")

        assert finding.path.startswith("scenarios[0]")
        assert finding.hint and "css" in finding.hint

    def test_every_published_code_is_declared(self) -> None:
        from demodsl.capabilities import build_manifest

        assert "step.locator_unsupported" in build_manifest()["diagnostic_codes"]
