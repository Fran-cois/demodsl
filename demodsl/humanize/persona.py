"""Operator personas — *who* is driving the demo.

A demo reads as machine-made because every gesture is optimal: the cursor
lands on the pixel, the typing is metronomic, the scroll stops exactly where
it should. A human is none of that, and the imperfections are *correlated*:
someone who is tired is imprecise **and** slow, someone confident hesitates
less **and** overshoots more.

A persona is that correlation, expressed once, so every subsystem (cursor,
keyboard, scroll, camera) can derive its own behaviour from a single
coherent source instead of sprinkling independent random noise.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["OperatorProfile", "PERSONAS", "DEFAULT_PERSONA", "get_profile"]


@dataclass(frozen=True)
class OperatorProfile:
    """How a given human handles a mouse, a keyboard and a page.

    Every field is 0–1 where 1 is the "best" end of the axis, so
    ``intensity`` can dial the whole persona back towards the robot
    baseline without any per-field special-casing.
    """

    name: str
    #: Motor accuracy — drives cursor overshoot, resting drift, typo rate.
    precision: float
    #: Speed of execution — 1.0 is a brisk operator, 0.5 a slow one.
    tempo: float
    #: Decisiveness — high confidence means a short pause before acting.
    confidence: float
    #: Tendency to scroll past things and look around.
    curiosity: float
    #: Precision lost per minute of demo (0 = never tires).
    fatigue_rate: float

    def with_fatigue(self, minutes: float) -> OperatorProfile:
        """The same operator, *minutes* into the recording session."""
        if self.fatigue_rate <= 0 or minutes <= 0:
            return self
        drop = min(0.35, self.fatigue_rate * minutes)
        return OperatorProfile(
            name=self.name,
            precision=max(0.15, self.precision - drop),
            tempo=max(0.4, self.tempo - drop * 0.6),
            confidence=max(0.1, self.confidence - drop * 0.5),
            curiosity=self.curiosity,
            fatigue_rate=self.fatigue_rate,
        )


PERSONAS: dict[str, OperatorProfile] = {
    # The product person recording their own tool: fast, sure, but casual —
    # overshoots because they already know where they are going.
    "expert_confident": OperatorProfile(
        name="expert_confident",
        precision=0.75,
        tempo=1.0,
        confidence=0.95,
        curiosity=0.2,
        fatigue_rate=0.01,
    ),
    # Someone discovering the UI on camera: reads before clicking, scrolls
    # past things, mistypes.
    "first_time_user": OperatorProfile(
        name="first_time_user",
        precision=0.5,
        tempo=0.65,
        confidence=0.35,
        curiosity=0.9,
        fatigue_rate=0.02,
    ),
    # End of a long recording day — the default drift of any real screencast.
    "tired_operator": OperatorProfile(
        name="tired_operator",
        precision=0.45,
        tempo=0.7,
        confidence=0.5,
        curiosity=0.3,
        fatigue_rate=0.06,
    ),
    # The house default: someone presenting to an audience. Deliberate,
    # accurate, but unmistakably alive.
    "presenter": OperatorProfile(
        name="presenter",
        precision=0.8,
        tempo=0.85,
        confidence=0.75,
        curiosity=0.4,
        fatigue_rate=0.015,
    ),
}

DEFAULT_PERSONA = "presenter"


def get_profile(name: str | None) -> OperatorProfile:
    """Look up a persona by name, falling back to the house default."""
    return PERSONAS.get(name or DEFAULT_PERSONA, PERSONAS[DEFAULT_PERSONA])
