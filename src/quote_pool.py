"""Quote-pool builder (architecture §10.4 — deterministic, before the model runs).

For each of the top themes, selects candidate quotes from reporting-window
reviews that pass length, placeholder, and near-duplicate filters, then ranks
by representativeness.
"""

from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher
from typing import Sequence

from .schemas import Review, Theme


# Residual redaction placeholders that disqualify a quote
_PLACEHOLDER_RE = re.compile(
    r"\[(email|phone|id|link|handle|name|redacted)\]", re.IGNORECASE
)


def _similarity(a: str, b: str) -> float:
    """Normalized similarity ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def build_quote_pool(
    theme: Theme,
    reviews_by_id: dict[str, Review],
    reporting_from: date,
    reporting_to: date,
    *,
    min_chars: int = 40,
    max_chars: int = 200,
    similarity_threshold: float = 0.8,
    max_candidates: int = 8,
) -> list[Review]:
    """Return up to *max_candidates* quote-eligible reviews for *theme*.

    Filtering (architecture §10.4):
    1. Must be in the reporting window.
    2. Text length between *min_chars* and *max_chars*.
    3. No residual redaction placeholders.
    4. No near-duplicate (similarity ≥ threshold) to an already-selected candidate.

    Ranking: ``abs(rating − theme_avg)`` ascending so quotes are representative
    rather than the loudest outlier.
    """
    avg = theme.avg_rating_week if theme.avg_rating_week is not None else 3.0

    # Collect eligible reviews
    eligible: list[Review] = []
    for rid in theme.review_ids:
        review = reviews_by_id.get(rid)
        if review is None:
            continue
        if not (reporting_from <= review.date <= reporting_to):
            continue
        text = review.text.strip()
        if len(text) < min_chars or len(text) > max_chars:
            continue
        if _PLACEHOLDER_RE.search(text):
            continue
        eligible.append(review)

    # Sort by representativeness: closest rating to theme avg, then by id for stability
    eligible.sort(
        key=lambda r: (
            abs((r.rating if r.rating is not None else 3) - avg),
            r.id,
        )
    )

    # Near-duplicate filter
    selected: list[Review] = []
    for review in eligible:
        if any(
            _similarity(review.text, s.text) >= similarity_threshold
            for s in selected
        ):
            continue
        selected.append(review)
        if len(selected) >= max_candidates:
            break

    return selected
