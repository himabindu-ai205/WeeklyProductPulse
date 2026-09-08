"""LangGraph node functions and routing (Phase 5 — Option A)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

from langchain_core.language_models import BaseChatModel

from ..config import AppConfig
from ..generate import generate_pulse, write_generate_artifacts
from ..schemas import Pulse, Review, Theme, ValidationResult
from ..validate import validate_pulse, write_validation_artifact
from .state import PulseGraphState

Route = Literal["publish", "retry_generate", "abort"]
PublishFn = Callable[[Pulse, str], None]


def route_after_validate(
    validation: ValidationResult,
    attempts: int,
    max_attempts: int,
) -> Route:
    """Map validation outcome to next edge (architecture §10.5)."""
    if validation.passed:
        return "publish"
    if not validation.fixable:
        return "abort"
    if attempts >= max_attempts:
        return "abort"
    return "retry_generate"


def validate_node(
    pulse: Pulse,
    md: str,
    reviews: Sequence[Review],
    themes: Sequence[Theme],
    app: AppConfig,
    *,
    reporting_from: date,
    reporting_to: date,
) -> ValidationResult:
    """Standalone validate helper (tests + graph)."""
    return validate_pulse(
        pulse,
        md=md,
        reviews=reviews,
        themes=themes,
        reporting_from=reporting_from,
        reporting_to=reporting_to,
        max_words=app.note.max_words,
        highlight=app.themes.highlight,
        quote_count=app.note.quote_count,
        action_count=app.note.action_count,
        max_themes=app.themes.max_total,
    )


def make_graph_nodes(
    llm: BaseChatModel,
    top_themes: list[Theme],
    all_themes: list[Theme],
    reviews: Sequence[Review],
    app: AppConfig,
    *,
    corpus_from: date,
    corpus_to: date,
    reporting_from: date,
    reporting_to: date,
    week_ending: date,
    window_note: str | None,
    review_count_corpus: int,
    artifacts_dir: Path | None,
    publish_fn: PublishFn | None,
    max_attempts: int,
) -> dict[str, Callable[[PulseGraphState], dict[str, Any]]]:
    """Build node callables that close over pipeline dependencies."""

    def generate_node(state: PulseGraphState) -> dict[str, Any]:
        attempts = int(state.get("attempts", 0)) + 1
        codes = state.get("failure_codes") or []
        failure_codes = codes if codes else None
        pulse, md = generate_pulse(
            llm,
            top_themes,
            list(reviews),
            app,
            corpus_from=corpus_from,
            corpus_to=corpus_to,
            reporting_from=reporting_from,
            reporting_to=reporting_to,
            week_ending=week_ending,
            window_note=window_note,
            review_count_corpus=review_count_corpus,
            failure_codes=failure_codes,
        )
        if artifacts_dir is not None:
            write_generate_artifacts(pulse, md, artifacts_dir)
        return {
            "attempts": attempts,
            "pulse": pulse,
            "md": md,
            "status": "pending",
        }

    def validate_graph_node(state: PulseGraphState) -> dict[str, Any]:
        pulse = state["pulse"]
        md = state["md"] or ""
        validation = validate_node(
            pulse,
            md,
            reviews,
            all_themes,
            app,
            reporting_from=reporting_from,
            reporting_to=reporting_to,
        )
        history = list(state.get("failure_history") or [])
        history.append(list(validation.failures))
        if artifacts_dir is not None:
            write_validation_artifact(validation, artifacts_dir)
        return {
            "validation": validation,
            "failure_history": history,
            "failure_codes": list(validation.failures),
        }

    def publish_node(state: PulseGraphState) -> dict[str, Any]:
        pulse = state["pulse"]
        md = state.get("md") or ""
        published = False
        if publish_fn is not None and pulse is not None:
            publish_fn(pulse, md)
            published = True
        return {"status": "passed", "published": published}

    def abort_node(state: PulseGraphState) -> dict[str, Any]:
        validation = state.get("validation")
        attempts = int(state.get("attempts", 0))
        if validation is not None and not validation.fixable:
            status = "aborted_non_fixable"
        elif attempts >= max_attempts:
            status = "aborted_attempts_exhausted"
        else:
            status = "aborted_non_fixable"
        return {"status": status, "published": False}

    return {
        "generate": generate_node,
        "validate": validate_graph_node,
        "publish": publish_node,
        "abort": abort_node,
    }


def route_from_state(state: PulseGraphState, max_attempts: int) -> Route:
    validation = state.get("validation")
    attempts = int(state.get("attempts", 0))
    if validation is None:
        return "abort"
    return route_after_validate(validation, attempts, max_attempts)
