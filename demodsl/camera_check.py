"""Camera-flow coherence checks — does the choreography make sense?

A virtual-camera plan can be *valid* (schema-wise) yet *nonsensical* on
screen: a demo that ends zoomed-in, a scroll performed while zoomed (the
page sweeps disorientingly), a camera move attached to a navigate (the
transform is destroyed by the page load), a hold longer than the step…

``check_camera_flow`` replays the scenario's camera state machine and
returns issues. It runs automatically at model-validation time (warnings)
and callers like authoring pipelines can treat ``error`` issues as hard
rejections.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from demodsl.models import Scenario

ERROR = "error"
WARN = "warn"

# Readability bounds for walkthrough zooms (beyond → pixelated / pointless).
_MAX_ZOOM = 2.6
_MIN_ZOOM = 0.75
_ZOOM_EPS = 0.01


@dataclass(frozen=True)
class CameraIssue:
    severity: str  # ERROR | WARN
    step: int  # 0-based step index
    message: str
    #: Stable machine-readable code (issue #18) — agents branch on this.
    code: str = "camera.incoherent"

    def __str__(self) -> str:
        tag = "ERROR" if self.severity == ERROR else "warn "
        return f"[{tag}] camera @ step {self.step}: {self.message}"


def check_camera_flow(scenario: Scenario) -> list[CameraIssue]:
    """Replay camera state across *scenario.steps* and collect incoherences."""
    issues: list[CameraIssue] = []
    zoom = 1.0
    last_move_step: int | None = None  # last non-reset camera move while zoomed

    for i, step in enumerate(scenario.steps or []):
        cam = step.camera
        action = step.action

        # 1. A camera block on a navigate is wiped out by the page load.
        if cam is not None and action == "navigate":
            issues.append(
                CameraIssue(
                    ERROR,
                    i,
                    "camera move on a 'navigate' step is lost when the page loads — "
                    "move it to the following step",
                    "camera.move_on_navigate",
                )
            )

        # 2. Scrolling while zoomed sweeps the page disorientingly.
        if action == "scroll" and zoom > 1 + _ZOOM_EPS:
            issues.append(
                CameraIssue(
                    ERROR,
                    i,
                    f"scroll happens while the camera is still zoomed ({zoom:.2f}x) — "
                    "insert a camera_reset before scrolling",
                    "camera.scroll_while_zoomed",
                )
            )

        # A bare ``action: camera_reset`` step resets the transform just as
        # ``camera: {reset: true}`` does — that is what CameraCommand executes
        # at render time. Honouring only the latter made the checker report
        # ``camera.ends_zoomed`` on nine of the project's own examples.
        if cam is not None or action == "camera_reset":
            if action == "camera_reset" or cam.reset:
                zoom = 1.0
                last_move_step = None
            else:
                if cam.zoom is not None:
                    # 3. Readability bounds.
                    if cam.zoom > _MAX_ZOOM:
                        issues.append(
                            CameraIssue(
                                WARN,
                                i,
                                f"zoom {cam.zoom:.2f}x exceeds {_MAX_ZOOM}x — the page "
                                "will look cropped/pixelated",
                                "camera.zoom_too_high",
                            )
                        )
                    elif cam.zoom < _MIN_ZOOM:
                        issues.append(
                            CameraIssue(
                                WARN,
                                i,
                                f"zoom {cam.zoom:.2f}x zooms out below {_MIN_ZOOM}x — "
                                "the page will float in a void",
                                "camera.zoom_too_low",
                            )
                        )
                    # 4. Back-to-back moves without reset: the pan between two
                    # distant targets sweeps across the zoomed page.
                    if (
                        zoom > 1 + _ZOOM_EPS
                        and cam.zoom > 1 + _ZOOM_EPS
                        and last_move_step is not None
                    ):
                        issues.append(
                            CameraIssue(
                                WARN,
                                i,
                                f"camera re-targets while still zoomed (since step "
                                f"{last_move_step}) — a camera_reset in between reads "
                                "more naturally",
                                "camera.retarget_while_zoomed",
                            )
                        )
                    zoom = cam.zoom
                if zoom > 1 + _ZOOM_EPS:
                    last_move_step = i

                # 5. A hold that outlasts the step's wait does nothing visible.
                wait = step.wait or 0.0
                if cam.hold and wait and cam.hold > wait:
                    issues.append(
                        CameraIssue(
                            WARN,
                            i,
                            f"camera.hold ({cam.hold:.1f}s) exceeds the step wait "
                            f"({wait:.1f}s) — the hold is cut short",
                            "camera.hold_exceeds_wait",
                        )
                    )

                # 6. Framing an element other than the one being interacted with.
                if (
                    cam.target is not None
                    and step.locator is not None
                    and (cam.target.type, cam.target.value)
                    != (step.locator.type, step.locator.value)
                ):
                    issues.append(
                        CameraIssue(
                            WARN,
                            i,
                            f"camera frames '{cam.target.value}' but the step interacts "
                            f"with '{step.locator.value}' — is that intentional?",
                            "camera.target_mismatch",
                        )
                    )

    # 7. The demo must not end zoomed-in.
    if zoom > 1 + _ZOOM_EPS:
        issues.append(
            CameraIssue(
                ERROR,
                max(0, len(scenario.steps or []) - 1),
                f"scenario ends with the camera still zoomed ({zoom:.2f}x) — "
                "add a final camera_reset",
                "camera.ends_zoomed",
            )
        )

    return issues
