"""Phase 5 orchestration entrypoints.

**Default (Option A):** LangGraph via ``graph.run_pulse_graph``.
**Fallback (Option B):** plain Python loop in ``run_generate_validate_python``.

``run_generate_validate`` is the stable API used by ``__main__`` and tests.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Sequence

from langchain_core.language_models import BaseChatModel

from ..config import AppConfig
from ..generate import generate_pulse, write_generate_artifacts
from ..schemas import Review, Theme
from ..validate import validate_pulse, write_validation_artifact
from .nodes import PublishFn
from .result import OrchestrationResult, orchestration_status_block


def run_generate_validate_python(
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
    window_note: str | None = None,
    review_count_corpus: int = 0,
    artifacts_dir: Path | None = None,
    publish_fn: PublishFn | None = None,
    max_attempts: int | None = None,
) -> OrchestrationResult:
    """Option B — Python while-loop (same behaviour as LangGraph)."""
    limit = max_attempts if max_attempts is not None else app.limits.generate_max_attempts
    attempts = 0
    failure_codes: list[str] | None = None
    history: list[list[str]] = []
    last_pulse = None
    last_md = None
    last_validation = None

    while attempts < limit:
        attempts += 1
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
        last_pulse, last_md = pulse, md

        if artifacts_dir is not None:
            write_generate_artifacts(pulse, md, artifacts_dir)

        validation = validate_pulse(
            pulse,
            md=md,
            reviews=reviews,
            themes=all_themes,
            reporting_from=reporting_from,
            reporting_to=reporting_to,
            max_words=app.note.max_words,
            highlight=app.themes.highlight,
            quote_count=app.note.quote_count,
            action_count=app.note.action_count,
            max_themes=app.themes.max_total,
        )
        last_validation = validation
        history.append(list(validation.failures))

        if artifacts_dir is not None:
            write_validation_artifact(validation, artifacts_dir)

        if validation.passed:
            published = False
            if publish_fn is not None:
                publish_fn(pulse, md)
                published = True
            return OrchestrationResult(
                pulse=pulse,
                md=md,
                validation=validation,
                attempts=attempts,
                status="passed",
                published=published,
                failure_history=history,
            )

        if not validation.fixable:
            return OrchestrationResult(
                pulse=pulse,
                md=md,
                validation=validation,
                attempts=attempts,
                status="aborted_non_fixable",
                published=False,
                failure_history=history,
            )

        failure_codes = list(validation.failures)

    return OrchestrationResult(
        pulse=last_pulse,
        md=last_md,
        validation=last_validation,
        attempts=attempts,
        status="aborted_attempts_exhausted",
        published=False,
        failure_history=history,
    )


def run_generate_validate(
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
    window_note: str | None = None,
    review_count_corpus: int = 0,
    artifacts_dir: Path | None = None,
    publish_fn: PublishFn | None = None,
    max_attempts: int | None = None,
    use_langgraph: bool = True,
) -> OrchestrationResult:
    """Run orchestration. Default: LangGraph (Option A)."""
    if use_langgraph:
        from .graph import run_pulse_graph

        return run_pulse_graph(
            llm,
            top_themes,
            all_themes,
            reviews,
            app,
            corpus_from=corpus_from,
            corpus_to=corpus_to,
            reporting_from=reporting_from,
            reporting_to=reporting_to,
            week_ending=week_ending,
            window_note=window_note,
            review_count_corpus=review_count_corpus,
            artifacts_dir=artifacts_dir,
            publish_fn=publish_fn,
            max_attempts=max_attempts,
        )
    return run_generate_validate_python(
        llm,
        top_themes,
        all_themes,
        reviews,
        app,
        corpus_from=corpus_from,
        corpus_to=corpus_to,
        reporting_from=reporting_from,
        reporting_to=reporting_to,
        week_ending=week_ending,
        window_note=window_note,
        review_count_corpus=review_count_corpus,
        artifacts_dir=artifacts_dir,
        publish_fn=publish_fn,
        max_attempts=max_attempts,
    )


__all__ = [
    "OrchestrationResult",
    "orchestration_status_block",
    "run_generate_validate",
    "run_generate_validate_python",
]
