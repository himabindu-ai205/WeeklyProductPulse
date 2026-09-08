"""Deterministic theme ranking, trend calculation, and stats (architecture §9.2, §10.4).

No LLM calls. All functions are pure Python operating on Theme / Review objects.
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

from .schemas import Review, Theme, Trend


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------


def compute_theme_stats(
    theme: Theme,
    reviews: Sequence[Review],
    corpus_from: date,
    corpus_to: date,
    reporting_from: date,
    reporting_to: date,
    corpus_weeks: int,
) -> Theme:
    """Populate count_corpus, count_week, avg_rating_week, baseline_weekly, trend.

    Returns a *new* Theme with stats filled in (does not mutate the original).
    """
    theme_reviews = [r for r in reviews if r.id in set(theme.review_ids)]

    corpus_reviews = [
        r for r in theme_reviews if corpus_from <= r.date <= corpus_to
    ]
    week_reviews = [
        r for r in theme_reviews if reporting_from <= r.date <= reporting_to
    ]

    count_corpus = len(corpus_reviews)
    count_week = len(week_reviews)

    rated_week = [r.rating for r in week_reviews if r.rating is not None]
    avg_rating_week = (
        round(sum(rated_week) / len(rated_week), 2) if rated_week else None
    )

    baseline_weekly = (
        round(count_corpus / corpus_weeks, 2) if corpus_weeks > 0 else 0.0
    )

    trend = compute_trend(count_week, baseline_weekly)

    return theme.model_copy(
        update={
            "count_corpus": count_corpus,
            "count_week": count_week,
            "avg_rating_week": avg_rating_week,
            "baseline_weekly": baseline_weekly,
            "trend": trend,
        }
    )


# ---------------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------------


def compute_trend(count_week: int, baseline_weekly: float) -> Trend:
    """Return 'rising', 'falling', or 'steady' per architecture §9.2.

    * ``w >= 1.25 * b`` → rising
    * ``w <= 0.75 * b`` → falling
    * else → steady
    """
    if baseline_weekly <= 0:
        return "rising" if count_week > 0 else "steady"
    ratio = count_week / baseline_weekly
    if ratio >= 1.25:
        return "rising"
    if ratio <= 0.75:
        return "falling"
    return "steady"


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def rank_themes(themes: Sequence[Theme]) -> list[Theme]:
    """Sort themes for the weekly pulse (architecture §9.2).

    Order: ``count_week`` descending, then ``avg_rating_week`` ascending
    (lower rating = more urgent = higher rank), then ``id`` alphabetical
    as a deterministic tie-breaker.
    """

    def sort_key(t: Theme) -> tuple[int, float, str]:
        # Negate count_week for descending sort; use 999 for None avg so it
        # sorts last among same-count themes.
        return (
            -t.count_week,
            t.avg_rating_week if t.avg_rating_week is not None else 999.0,
            t.id,
        )

    return sorted(themes, key=sort_key)


def top_n_themes(
    ranked: Sequence[Theme],
    n: int = 3,
    *,
    exclude_other: bool = True,
) -> list[Theme]:
    """Return the top *n* themes, excluding ``other`` unless fewer than *n* real themes."""
    if exclude_other:
        real = [t for t in ranked if t.id != "other"]
        if len(real) >= n:
            return real[:n]
    return list(ranked[:n])
