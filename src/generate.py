"""LangChain pulse generation chain (architecture §10.4).

The model writes theme summaries and action ideas, and selects quotes by
review_id only. render.py fills in the verbatim quote text afterwards.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from .config import AppConfig
from .llm import invoke_structured
from .quote_pool import build_quote_pool
from .render import count_body_words, render_pulse_md
from .schemas import (
    DateWindow,
    Pulse,
    PulseAction,
    PulseQuote,
    PulseTheme,
    Review,
    Theme,
)


# ---------------------------------------------------------------------------
# Structured LLM output (model never types quote text)
# ---------------------------------------------------------------------------


class ThemeSummaryOut(BaseModel):
    theme_id: str
    summary: str


class SelectedQuoteOut(BaseModel):
    theme_id: str
    review_id: str


class ActionOut(BaseModel):
    theme_id: str
    title: str
    detail: str


class PulseLLMOutput(BaseModel):
    summaries: list[ThemeSummaryOut] = Field(default_factory=list)
    selected_quotes: list[SelectedQuoteOut] = Field(default_factory=list)
    actions: list[ActionOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "pulse.md"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------


def generate_pulse(
    llm: BaseChatModel,
    top_themes: list[Theme],
    reviews: list[Review],
    app: AppConfig,
    *,
    corpus_from: date,
    corpus_to: date,
    reporting_from: date,
    reporting_to: date,
    week_ending: date,
    window_note: str | None = None,
    review_count_corpus: int = 0,
    failure_codes: list[str] | None = None,
) -> tuple[Pulse, str]:
    """Generate the weekly pulse. Returns (Pulse object, rendered markdown)."""
    reviews_by_id = {r.id: r for r in reviews}

    quote_pools: dict[str, list[Review]] = {}
    for theme in top_themes:
        pool = build_quote_pool(
            theme,
            reviews_by_id,
            reporting_from,
            reporting_to,
            min_chars=app.note.quote_min_chars,
            max_chars=app.note.quote_max_chars,
            max_candidates=8,
        )
        quote_pools[theme.id] = pool

    themes_json = json.dumps(
        [
            {
                "theme_id": t.id,
                "label": t.label,
                "count_week": t.count_week,
                "avg_rating_week": t.avg_rating_week,
                "trend": t.trend,
            }
            for t in top_themes
        ],
        indent=2,
    )

    quotes_json = json.dumps(
        {
            tid: [
                {"review_id": r.id, "text": r.text, "rating": r.rating}
                for r in pool
            ]
            for tid, pool in quote_pools.items()
        },
        indent=2,
    )

    prompt_text = (
        _load_prompt()
        .replace("{themes_json}", themes_json)
        .replace("{quotes_json}", quotes_json)
    )

    if failure_codes:
        prompt_text += (
            "\n\n## Previous attempt failed with these codes — fix them:\n"
            + ", ".join(failure_codes)
        )

    messages = [
        SystemMessage(
            content=(
                "You are a product-insight writer. Return only structured JSON "
                "with summaries, selected_quotes (review_id only), and actions."
            )
        ),
        HumanMessage(content=prompt_text),
    ]

    parsed = invoke_structured(
        llm,
        PulseLLMOutput,
        messages,
        min_interval_seconds=app.limits.llm_request_interval_seconds,
    )

    pulse = _assemble_pulse(
        parsed,
        top_themes,
        reviews_by_id,
        app=app,
        corpus_from=corpus_from,
        corpus_to=corpus_to,
        reporting_from=reporting_from,
        reporting_to=reporting_to,
        week_ending=week_ending,
        window_note=window_note,
        review_count_corpus=review_count_corpus,
    )

    md = render_pulse_md(pulse)
    pulse = pulse.model_copy(update={"body_word_count": count_body_words(pulse)})

    return pulse, md


def _assemble_pulse(
    parsed: PulseLLMOutput,
    top_themes: list[Theme],
    reviews_by_id: dict[str, Review],
    *,
    app: AppConfig,
    corpus_from: date,
    corpus_to: date,
    reporting_from: date,
    reporting_to: date,
    week_ending: date,
    window_note: str | None,
    review_count_corpus: int,
) -> Pulse:
    """Build a Pulse from structured LLM output + deterministic data."""
    summary_map = {s.theme_id: s.summary for s in parsed.summaries}

    pulse_themes: list[PulseTheme] = []
    for t in top_themes:
        pulse_themes.append(
            PulseTheme(
                id=t.id,
                label=t.label,
                count_week=t.count_week,
                avg_rating_week=t.avg_rating_week,
                trend=t.trend,
                summary=summary_map.get(t.id, ""),
            )
        )

    quotes: list[PulseQuote] = []
    for sq in parsed.selected_quotes:
        review = reviews_by_id.get(sq.review_id)
        if review:
            quotes.append(
                PulseQuote(
                    text=review.text,
                    review_id=sq.review_id,
                    theme_id=sq.theme_id,
                    rating=review.rating,
                    date=review.date,
                )
            )

    actions = [
        PulseAction(title=a.title, detail=a.detail, theme_id=a.theme_id)
        for a in parsed.actions
    ]

    week_reviews = [
        r for r in reviews_by_id.values()
        if reporting_from <= r.date <= reporting_to
    ]
    rated = [r.rating for r in week_reviews if r.rating is not None]
    avg_rating_week = round(sum(rated) / len(rated), 2) if rated else None

    return Pulse(
        product_name=app.product_name,
        week_ending=week_ending,
        corpus_window=DateWindow(**{"from": corpus_from, "to": corpus_to}),
        reporting_window=DateWindow(**{"from": reporting_from, "to": reporting_to}),
        window_note=window_note,
        review_count_week=len(week_reviews),
        review_count_corpus=review_count_corpus,
        avg_rating_week=avg_rating_week,
        top_themes=pulse_themes,
        quotes=quotes,
        actions=actions,
    )


def write_generate_artifacts(
    pulse: Pulse, md: str, artifacts_dir: Path
) -> None:
    """Write pulse.json and pulse.md to the artifacts directory."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "pulse.json").write_text(
        json.dumps(pulse.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    (artifacts_dir / "pulse.md").write_text(md, encoding="utf-8")
