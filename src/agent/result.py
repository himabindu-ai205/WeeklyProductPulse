"""Shared orchestration result type (Phase 5)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import Pulse, ValidationResult


@dataclass
class OrchestrationResult:
    pulse: Pulse | None
    md: str | None
    validation: ValidationResult | None
    attempts: int = 0
    status: str = "pending"  # passed | aborted_non_fixable | aborted_attempts_exhausted
    published: bool = False
    failure_history: list[list[str]] = field(default_factory=list)


def orchestration_status_block(result: OrchestrationResult) -> dict:
    """Compact status for the run summary."""
    pulse = result.pulse
    val = result.validation
    return {
        "status": result.status,
        "attempts": result.attempts,
        "published": result.published,
        "validation": None
        if val is None
        else {
            "passed": val.passed,
            "fixable": val.fixable,
            "failures": val.failures,
            "pii_hits": val.pii_hits,
            "body_word_count": val.body_word_count,
        },
        "pulse": None
        if pulse is None
        else {
            "week_ending": pulse.week_ending.isoformat(),
            "review_count_week": pulse.review_count_week,
            "review_count_corpus": pulse.review_count_corpus,
            "top_themes": [t.id for t in pulse.top_themes],
            "quote_count": len(pulse.quotes),
            "action_count": len(pulse.actions),
            "body_word_count": pulse.body_word_count,
        },
        "failure_history": result.failure_history,
    }
