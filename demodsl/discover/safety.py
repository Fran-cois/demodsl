"""Safety guard for autonomous actions on authenticated sessions.

Discovery drives a *real* browser. When that browser is authenticated
(``auth`` was supplied), an autonomous click/type can trigger a destructive,
irreversible action on the signed-in account (delete, pay, send, log out…).
This module gates those actions.

On an authenticated session, and unless the caller explicitly opts in with
``allow_writes=True``, the guard

* blocks every ``type`` (filling a real field is a write),
* blocks ``click`` on a *risky* control — one whose accessible name or attributes
  match a destructive-verb deny-list (EN + FR), and
* blocks ``press_key`` for keys that can submit a focused form (Enter / Space).

Read-only actions (``navigate``, ``scroll``, ``hover``, ``wait_for``, ``done``)
are never blocked, so discovery still explores an authenticated site — it just
refuses to push the dangerous buttons. Without authentication the guard is a
no-op (the public web is the user's to click). The deny-list is intentionally
conservative: a benign "Send feedback" may be blocked; the user can opt back in
with ``allow_writes`` / ``--allow-writes``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from demodsl.discover.actions import AgentAction
from demodsl.discover.observation import PageObservation

#: Destructive / state-changing labels (EN + FR), matched case-insensitively
#: against an element's accessible name and flattened grounding attributes.
#: Short, false-positive-prone English verbs use word boundaries; accented and
#: multi-word forms are matched as substrings (``re.UNICODE`` ``\b`` around
#: accents is brittle).
RISKY_LABEL_PATTERNS: tuple[str, ...] = (
    # delete / remove
    r"\bdelete\b",
    r"\bremove\b",
    r"supprimer",
    r"effacer",
    # purchase / payment
    r"\bpay\b",
    r"\bpayment\b",
    r"\bbuy\b",
    r"\bpurchase\b",
    r"\bcheckout\b",
    r"\bcheck out\b",
    r"payer",
    r"acheter",
    r"commander",
    r"paiement",
    # subscription
    r"\bsubscribe\b",
    r"abonner",
    # send / publish
    r"\bsend\b",
    r"\bsubmit\b",
    r"\bpublish\b",
    r"\bpost\b",
    r"envoyer",
    r"publier",
    r"soumettre",
    # logout
    r"\blog ?out\b",
    r"\bsign ?out\b",
    r"déconnexion",
    r"deconnexion",
    r"déconnecter",
    r"deconnecter",
    # cancel / deactivate / close
    r"\bcancel\b",
    r"annuler",
    r"résilier",
    r"resilier",
    r"\bdeactivate\b",
    r"désactiver",
    r"desactiver",
    r"close account",
    r"delete account",
    r"supprimer le compte",
    # money movement
    r"\btransfer\b",
    r"wire transfer",
    r"virement",
    r"\bwithdraw\b",
    r"retrait",
    # commit / confirm
    r"\bconfirm\b",
    r"confirmer",
)

#: Keys that can submit a focused form / activate a control.
_SUBMIT_KEYS: frozenset[str] = frozenset({"enter", "return", " ", "space", "spacebar"})

_RISKY_RE = re.compile("|".join(RISKY_LABEL_PATTERNS), re.IGNORECASE)


def is_risky_label(text: str) -> bool:
    """Whether *text* (an element name / attrs blob) names a destructive control."""
    return bool(text) and _RISKY_RE.search(text) is not None


@dataclass(frozen=True)
class ActionGuard:
    """Decides whether an action is safe to execute against the environment.

    Parameters
    ----------
    authenticated:
        ``True`` when discovery runs against a signed-in session (``auth`` set).
    allow_writes:
        When ``True`` the caller explicitly accepted write / destructive actions,
        so the guard becomes a no-op. Defaults to ``False`` (safe).
    """

    authenticated: bool = False
    allow_writes: bool = False

    @property
    def active(self) -> bool:
        """Whether the guard will block anything at all."""
        return self.authenticated and not self.allow_writes

    def reason_for(self, kind: str, *, label: str = "", key: str = "") -> str | None:
        """Core check: return a block reason for an action *kind*, or ``None``.

        ``label`` is the target element's name (+ attrs) for ``click``; ``key`` is
        the key for ``press_key``. Exposed so callers without a live
        :class:`PageObservation` (e.g. the explore-first planner) can reuse the
        exact same policy by passing a label they already hold.
        """
        if not self.active:
            return None
        if kind == "type":
            return (
                "typing into a field is a write action; blocked on an authenticated "
                "session (pass allow_writes / --allow-writes to enable)"
            )
        if kind == "press_key":
            if key.strip().lower() in _SUBMIT_KEYS:
                return (
                    f"key {key!r} can submit a form; blocked on an authenticated "
                    "session (pass allow_writes / --allow-writes to enable)"
                )
            return None
        if kind == "click" and is_risky_label(label):
            return (
                f"click on a risky control ({label.strip()!r}) is blocked on an "
                "authenticated session (pass allow_writes / --allow-writes to enable)"
            )
        return None

    def evaluate(
        self, action: AgentAction, observation: PageObservation | None = None
    ) -> str | None:
        """Return a human-readable block reason for *action*, or ``None`` if allowed."""
        if not self.active:
            return None
        return self.reason_for(
            action.kind,
            label=_action_label(action, observation),
            key=action.key or "",
        )


def _action_label(action: AgentAction, observation: PageObservation | None) -> str:
    """Best-effort label for *action*'s target element (name + grounding attrs).

    Returns ``""`` when no element can be resolved — such a click carries no
    locator and cannot execute anyway, so there is nothing to gate.
    """
    if observation is not None and action.mark is not None:
        el = observation.by_mark(action.mark)
        if el is not None:
            return f"{el.name} {el.attrs}".strip()
    return ""
