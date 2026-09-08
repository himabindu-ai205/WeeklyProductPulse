"""LangGraph orchestration (Phase 5 — Option A, recommended).

Edges (architecture §10.5):
  generate → validate
  validate → generate   if fixable and attempts < max
  validate → abort      if PII / non-fixable / attempts exhausted
  validate → publish    on pass (Phase 6 hook; may be a no-op)

Option B (plain Python loop) remains in ``runner.py`` as a fallback API with
the same ``OrchestrationResult`` contract.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Sequence

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from ..config import AppConfig
from ..schemas import Review, Theme
from .nodes import PublishFn, make_graph_nodes, route_from_state
from .result import OrchestrationResult, orchestration_status_block
from .state import PulseGraphState


def build_pulse_graph(
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
):
    """Compile generate → validate → retry/abort/publish LangGraph."""
    limit = max_attempts if max_attempts is not None else app.limits.generate_max_attempts
    nodes = make_graph_nodes(
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
        max_attempts=limit,
    )

    graph = StateGraph(PulseGraphState)
    graph.add_node("generate", nodes["generate"])
    graph.add_node("validate", nodes["validate"])
    graph.add_node("publish", nodes["publish"])
    graph.add_node("abort", nodes["abort"])

    graph.add_edge(START, "generate")
    graph.add_edge("generate", "validate")

    def _route(state: PulseGraphState) -> str:
        return route_from_state(state, limit)

    graph.add_conditional_edges(
        "validate",
        _route,
        {
            "retry_generate": "generate",
            "publish": "publish",
            "abort": "abort",
        },
    )
    graph.add_edge("publish", END)
    graph.add_edge("abort", END)
    return graph.compile()


def run_pulse_graph(
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
    """Run the LangGraph and map final state → OrchestrationResult."""
    compiled = build_pulse_graph(
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
    final: PulseGraphState = compiled.invoke(
        {
            "attempts": 0,
            "failure_codes": [],
            "status": "pending",
            "failure_history": [],
            "published": False,
            "pulse": None,
            "md": None,
            "validation": None,
        }
    )
    return OrchestrationResult(
        pulse=final.get("pulse"),
        md=final.get("md"),
        validation=final.get("validation"),
        attempts=int(final.get("attempts", 0)),
        status=str(final.get("status", "pending")),
        published=bool(final.get("published", False)),
        failure_history=list(final.get("failure_history") or []),
    )


__all__ = [
    "OrchestrationResult",
    "build_pulse_graph",
    "orchestration_status_block",
    "run_pulse_graph",
]
