"""Orchestration state for LangGraph (Phase 5 — Option A)."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class PulseGraphState(TypedDict):
    """State for generate → validate → retry / abort / publish."""

    attempts: int
    failure_codes: list[str]
    status: str  # pending | passed | aborted_non_fixable | aborted_attempts_exhausted
    failure_history: list[list[str]]
    published: bool
    # Runtime payloads (not serialized across machines in this project)
    pulse: NotRequired[Any]  # Pulse | None
    md: NotRequired[str | None]
    validation: NotRequired[Any]  # ValidationResult | None
