"""Human-operator simulation — makes a scripted demo feel hand-recorded.

Public entry point: :func:`build_state`, which turns the scenario's
``humanize:`` block into a :class:`HumanState` consumed by the cursor
overlay, the typing routine and the scroll routine.
"""

from demodsl.humanize.keyboard import neighbour_key
from demodsl.humanize.persona import (
    DEFAULT_PERSONA,
    PERSONAS,
    OperatorProfile,
    get_profile,
)
from demodsl.humanize.state import CHANNELS, HumanState, build_state, state_for_scenario

__all__ = [
    "CHANNELS",
    "DEFAULT_PERSONA",
    "PERSONAS",
    "HumanState",
    "OperatorProfile",
    "build_state",
    "get_profile",
    "neighbour_key",
    "state_for_scenario",
]
