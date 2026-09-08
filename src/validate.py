"""Deterministic validation gates for the weekly pulse (architecture §10.5)."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Sequence

from .redact import (
    _EMAIL_RE,
    _HANDLE_RE,
    _LONG_ALNUM_RE,
    _LONG_DIGIT_RE,
    _PHONE_RE,
    _PROTECT_CURRENCY_RE,
    _PROTECT_RATING_FLOAT_RE,
    _PROTECT_STARS_RE,
    _PROTECT_VERSION_RE,
    _URL_RE,
)
from .render import count_body_words
from .schemas import Pulse, Review, Theme, ValidationResult

# Fixable by re-running generate
FIXABLE_CODES = frozenset(
    {
        "WORD_LIMIT",
        "THEME_COUNT",
        "THEME_CAP",
        "QUOTE_COUNT",
        "QUOTE_NOT_VERBATIM",
        "QUOTE_OUT_OF_WINDOW",
        "ACTION_COUNT",
    }
)

# Abort — do not publish
NON_FIXABLE_CODES = frozenset({"NON_PLAY_DATA", "PII_DETECTED"})

# Dates in the pulse metadata line must not look like phone numbers
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# Day–month ranges like "27–2 Sep" or "24–30 Aug" with en-dash or hyphen
_DAY_RANGE_RE = re.compile(r"\b\d{1,2}[–-]\d{1,2}\b")
# Corpus counts like "1,042" should not trip digit-ID rules
_COMMA_NUMBER_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")


def scan_pii_in_text(text: str) -> list[str]:
    """Re-run §10.2 patterns on rendered note; return human-readable hits.

    Placeholders like ``[email]`` do not match. Amounts/versions/ISO dates are
    protected before digit-heavy scans so ``₹500``, ``v3.4.1``, and ``2026-08-30``
    are not false positives.
    """
    hits: list[str] = []
    if not text:
        return hits

    protected = text
    for pattern in (
        _PROTECT_CURRENCY_RE,
        _PROTECT_VERSION_RE,
        _PROTECT_STARS_RE,
        _PROTECT_RATING_FLOAT_RE,
        _ISO_DATE_RE,
        _DAY_RANGE_RE,
        _COMMA_NUMBER_RE,
    ):
        protected = pattern.sub(" ", protected)

    checks = (
        ("email", _EMAIL_RE),
        ("phone", _PHONE_RE),
        ("link", _URL_RE),
        ("handle", _HANDLE_RE),
        ("id", _LONG_DIGIT_RE),
        ("id", _LONG_ALNUM_RE),
    )
    for label, pattern in checks:
        for match in pattern.finditer(protected):
            snippet = match.group(0)
            # Skip redaction placeholders
            if snippet.startswith("[") and snippet.endswith("]"):
                continue
            hits.append(f"{label}:{snippet[:40]}")
    return hits


def validate_pulse(
    pulse: Pulse,
    *,
    md: str,
    reviews: Sequence[Review],
    themes: Sequence[Theme],
    reporting_from: date,
    reporting_to: date,
    max_words: int = 250,
    highlight: int = 3,
    quote_count: int = 3,
    action_count: int = 3,
    max_themes: int = 5,
) -> ValidationResult:
    """Run **all** checks; collect failure codes before deciding.

    ``fixable`` is False if any non-fixable code is present.
    """
    failures: list[str] = []
    pii_hits: list[str] = []
    reviews_by_id = {r.id: r for r in reviews}
    top_theme_ids = {t.id for t in pulse.top_themes}

    body_word_count = count_body_words(pulse)
    # Keep pulse field in sync for callers
    if pulse.body_word_count != body_word_count:
        pulse = pulse.model_copy(update={"body_word_count": body_word_count})

    if body_word_count > max_words:
        failures.append("WORD_LIMIT")

    if len(pulse.top_themes) != highlight:
        failures.append("THEME_COUNT")

    if len(themes) > max_themes:
        failures.append("THEME_CAP")

    if len(pulse.quotes) != quote_count:
        failures.append("QUOTE_COUNT")

    if len(pulse.actions) != action_count or any(
        a.theme_id not in top_theme_ids for a in pulse.actions
    ):
        failures.append("ACTION_COUNT")

    for q in pulse.quotes:
        review = reviews_by_id.get(q.review_id)
        if review is None:
            failures.append("QUOTE_NOT_VERBATIM")
            continue
        source = f"{review.title}\n{review.text}"
        if q.text not in source:
            failures.append("QUOTE_NOT_VERBATIM")
        if not (reporting_from <= review.date <= reporting_to):
            # Also allow quote.date if review missing date edge — use review.date
            failures.append("QUOTE_OUT_OF_WINDOW")

    if any(r.store != "play_store" for r in reviews):
        failures.append("NON_PLAY_DATA")

    pii_hits = scan_pii_in_text(md)
    if pii_hits:
        failures.append("PII_DETECTED")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_failures: list[str] = []
    for code in failures:
        if code not in seen:
            seen.add(code)
            unique_failures.append(code)

    has_non_fixable = any(c in NON_FIXABLE_CODES for c in unique_failures)
    passed = len(unique_failures) == 0

    return ValidationResult(
        passed=passed,
        body_word_count=body_word_count,
        failures=unique_failures,
        pii_hits=pii_hits,
        # False when any non-fixable code is present (PII / non-play) — abort, no publish
        fixable=not has_non_fixable,
    )


def write_validation_artifact(result: ValidationResult, artifacts_dir: Path) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / "validation.json"
    path.write_text(json.dumps(result.model_dump(mode="json"), indent=2), encoding="utf-8")
