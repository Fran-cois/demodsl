"""Shared, dependency-free token estimator for the discovery harness.

A single source of truth so the observation builder and the LLM providers agree
on the same heuristic (they previously each defined their own identical copy).
"""

from __future__ import annotations

#: Roughly four characters per token (OpenAI/Anthropic BPE heuristic).
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Cheap, dependency-free token estimate (~4 chars/token)."""
    return max(1, len(text) // _CHARS_PER_TOKEN)
