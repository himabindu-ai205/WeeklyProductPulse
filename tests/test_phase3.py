"""Phase 3 tests: theme math, quote pool, render, word count (implementation-plan acceptance)."""

from __future__ import annotations

from datetime import date

import pytest

from src.quote_pool import build_quote_pool
from src.render import count_body_words, render_pulse_md
from src.schemas import (
    DateWindow,
    Pulse,
    PulseAction,
    PulseQuote,
    PulseTheme,
    Review,
    Theme,
)
from src.theme_math import compute_trend, rank_themes, top_n_themes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_review(rid: str, d: date, rating: int = 3, text: str = "ok") -> Review:
    return Review(id=rid, date=d, rating=rating, text=text)


def _make_theme(
    tid: str,
    label: str = "",
    count_week: int = 0,
    avg_rating_week: float | None = None,
    review_ids: list[str] | None = None,
) -> Theme:
    return Theme(
        id=tid,
        label=label or tid.title(),
        count_week=count_week,
        avg_rating_week=avg_rating_week,
        review_ids=review_ids or [],
    )


def _sample_pulse(**overrides) -> Pulse:
    """Return a minimal valid Pulse for render/word-count tests."""
    defaults = dict(
        product_name="Groww",
        week_ending=date(2026, 8, 30),
        corpus_window=DateWindow(**{"from": date(2026, 6, 7), "to": date(2026, 8, 30)}),
        reporting_window=DateWindow(**{"from": date(2026, 8, 24), "to": date(2026, 8, 30)}),
        review_count_week=87,
        review_count_corpus=1042,
        avg_rating_week=3.4,
        top_themes=[
            PulseTheme(
                id="payments",
                label="Payments & UPI",
                count_week=31,
                avg_rating_week=2.1,
                trend="rising",
                summary="Add-money fails at confirmation after debit.",
            ),
            PulseTheme(
                id="kyc",
                label="KYC & verification",
                count_week=22,
                avg_rating_week=2.4,
                trend="steady",
                summary="Document upload rejects valid IDs without giving a reason.",
            ),
            PulseTheme(
                id="trading",
                label="Trading & orders",
                count_week=14,
                avg_rating_week=3.1,
                trend="falling",
                summary="Order execution lag frustrates active traders.",
            ),
        ],
        quotes=[
            PulseQuote(
                text="Money left my account but the app says payment failed, third time this month.",
                review_id="r1",
                theme_id="payments",
                rating=1,
                date=date(2026, 8, 28),
            ),
            PulseQuote(
                text="Uploaded my ID four times and it keeps saying invalid, no explanation at all.",
                review_id="r2",
                theme_id="kyc",
                rating=2,
                date=date(2026, 8, 25),
            ),
            PulseQuote(
                text="App gets stuck at trade execution even after setting profit and loss limits.",
                review_id="r3",
                theme_id="trading",
                rating=1,
                date=date(2026, 8, 26),
            ),
        ],
        actions=[
            PulseAction(
                title="Add idempotent payment retry",
                detail="Reconcile debited-but-failed transactions automatically.",
                theme_id="payments",
            ),
            PulseAction(
                title="Return specific KYC rejection reasons",
                detail="Replace the generic invalid error with field-level feedback.",
                theme_id="kyc",
            ),
            PulseAction(
                title="Instrument order-path latency",
                detail="Alert when execution stalls beyond SLO.",
                theme_id="trading",
            ),
        ],
    )
    defaults.update(overrides)
    return Pulse(**defaults)


# ===================================================================
# test_ranking_is_deterministic
# ===================================================================


class TestRanking:
    def test_basic_ranking_by_count_week(self):
        themes = [
            _make_theme("a", count_week=10, avg_rating_week=3.0),
            _make_theme("b", count_week=20, avg_rating_week=3.0),
            _make_theme("c", count_week=15, avg_rating_week=3.0),
        ]
        ranked = rank_themes(themes)
        assert [t.id for t in ranked] == ["b", "c", "a"]

    def test_tiebreak_by_avg_rating(self):
        """Same count_week → lower avg_rating ranks higher (more urgent)."""
        themes = [
            _make_theme("x", count_week=10, avg_rating_week=4.0),
            _make_theme("y", count_week=10, avg_rating_week=2.0),
        ]
        ranked = rank_themes(themes)
        assert [t.id for t in ranked] == ["y", "x"]

    def test_tiebreak_by_id_alpha(self):
        """Same count and avg → alphabetical id."""
        themes = [
            _make_theme("beta", count_week=5, avg_rating_week=3.0),
            _make_theme("alpha", count_week=5, avg_rating_week=3.0),
        ]
        ranked = rank_themes(themes)
        assert [t.id for t in ranked] == ["alpha", "beta"]

    def test_deterministic_repeated_runs(self):
        """Identical inputs produce identical order across repeated calls."""
        themes = [
            _make_theme("payments", count_week=31, avg_rating_week=2.1),
            _make_theme("kyc", count_week=22, avg_rating_week=2.4),
            _make_theme("trading", count_week=14, avg_rating_week=3.1),
            _make_theme("onboarding", count_week=14, avg_rating_week=3.1),
            _make_theme("withdrawals", count_week=8, avg_rating_week=3.5),
        ]
        first = [t.id for t in rank_themes(themes)]
        for _ in range(10):
            assert [t.id for t in rank_themes(themes)] == first

    def test_none_avg_sorts_last(self):
        themes = [
            _make_theme("a", count_week=10, avg_rating_week=None),
            _make_theme("b", count_week=10, avg_rating_week=2.0),
        ]
        ranked = rank_themes(themes)
        assert ranked[0].id == "b"

    def test_top_n_excludes_other(self):
        themes = [
            _make_theme("other", count_week=100, avg_rating_week=1.0),
            _make_theme("payments", count_week=50, avg_rating_week=2.0),
            _make_theme("kyc", count_week=30, avg_rating_week=2.5),
            _make_theme("trading", count_week=20, avg_rating_week=3.0),
        ]
        ranked = rank_themes(themes)
        top3 = top_n_themes(ranked, 3)
        assert "other" not in [t.id for t in top3]
        assert len(top3) == 3

    def test_top_n_includes_other_when_too_few_real(self):
        themes = [
            _make_theme("other", count_week=100, avg_rating_week=1.0),
            _make_theme("payments", count_week=50, avg_rating_week=2.0),
        ]
        ranked = rank_themes(themes)
        top3 = top_n_themes(ranked, 3)
        assert len(top3) == 2  # only 2 themes exist


# ===================================================================
# test_trend_calculation
# ===================================================================


class TestTrend:
    def test_rising(self):
        assert compute_trend(count_week=13, baseline_weekly=10.0) == "rising"

    def test_falling(self):
        assert compute_trend(count_week=7, baseline_weekly=10.0) == "falling"

    def test_steady(self):
        assert compute_trend(count_week=10, baseline_weekly=10.0) == "steady"

    def test_exact_rising_boundary(self):
        """w == 1.25 * b → rising."""
        assert compute_trend(count_week=125, baseline_weekly=100.0) == "rising"

    def test_exact_falling_boundary(self):
        """w == 0.75 * b → falling."""
        assert compute_trend(count_week=75, baseline_weekly=100.0) == "falling"

    def test_just_below_rising(self):
        """w just below 1.25 * b → steady."""
        assert compute_trend(count_week=124, baseline_weekly=100.0) == "steady"

    def test_just_above_falling(self):
        """w just above 0.75 * b → steady."""
        assert compute_trend(count_week=76, baseline_weekly=100.0) == "steady"

    def test_zero_baseline_with_reviews(self):
        """New theme with no history → rising."""
        assert compute_trend(count_week=5, baseline_weekly=0.0) == "rising"

    def test_zero_baseline_zero_week(self):
        assert compute_trend(count_week=0, baseline_weekly=0.0) == "steady"


# ===================================================================
# test_word_count_rule
# ===================================================================


class TestWordCount:
    def test_sample_pulse_word_count(self):
        pulse = _sample_pulse()
        wc = count_body_words(pulse)
        assert wc > 0
        assert wc <= 250

    def test_headings_not_counted(self):
        """Only summaries, quotes, and actions count."""
        pulse = _sample_pulse()
        wc = count_body_words(pulse)
        # Headings like "Top themes", "What users said", "Action ideas" should
        # NOT inflate the count. The word count should reflect prose only.
        # Build a pulse with minimal prose to ensure headings aren't leaking.
        tiny = _sample_pulse(
            top_themes=[
                PulseTheme(
                    id="a", label="A", count_week=1, trend="steady", summary="One."
                )
            ],
            quotes=[
                PulseQuote(
                    text="Two.", review_id="r1", theme_id="a", date=date(2026, 8, 28)
                )
            ],
            actions=[
                PulseAction(title="Three", detail="Four.", theme_id="a")
            ],
        )
        wc_tiny = count_body_words(tiny)
        # "One" + "Two" + "Three" + "Four" = 4 words
        assert wc_tiny == 4

    def test_empty_pulse(self):
        pulse = _sample_pulse(top_themes=[], quotes=[], actions=[])
        assert count_body_words(pulse) == 0


# ===================================================================
# test_thin_week_fallback (integration with ingest compute_windows)
# ===================================================================


class TestThinWeekFallback:
    def test_thin_week_sets_window_note(self):
        from src.ingest import compute_windows

        class FakeWindows:
            corpus_weeks = 12
            reporting_days = 7
            min_week_reviews = 15
            fallback_days = 28

        # Only 5 reviews in the last 7 days → thin week
        reviews = [
            _make_review(f"r{i}", date(2026, 8, 30 - i))
            for i in range(5)
        ]
        # Add 20 reviews spread across the 4-week window
        for i in range(20):
            reviews.append(_make_review(f"old{i}", date(2026, 8, 10 + i)))

        (
            corpus_from,
            corpus_to,
            reporting_from,
            reporting_to,
            window_note,
            count_week,
        ) = compute_windows(date(2026, 8, 30), reviews, FakeWindows())

        assert window_note is not None
        assert "4-week" in window_note.lower() or "rollup" in window_note.lower()
        assert count_week >= 15  # after widening to 28 days

    def test_normal_week_no_note(self):
        from src.ingest import compute_windows

        class FakeWindows:
            corpus_weeks = 12
            reporting_days = 7
            min_week_reviews = 15
            fallback_days = 28

        # 20 reviews all within the last 7 days (Aug 24–30)
        reviews = [
            _make_review(f"r{i}", date(2026, 8, 24 + (i % 7)))
            for i in range(20)
        ]
        _, _, _, _, window_note, count_week = compute_windows(
            date(2026, 8, 30), reviews, FakeWindows()
        )
        assert window_note is None
        assert count_week >= 15


# ===================================================================
# test_render
# ===================================================================


class TestRender:
    def test_render_has_required_sections(self):
        pulse = _sample_pulse()
        md = render_pulse_md(pulse)
        assert "# Weekly Review Pulse" in md
        assert "## Top themes" in md
        assert "## What users said" in md
        assert "## Action ideas" in md

    def test_render_contains_product_name(self):
        pulse = _sample_pulse()
        md = render_pulse_md(pulse)
        assert "Groww" in md

    def test_render_contains_quotes(self):
        pulse = _sample_pulse()
        md = render_pulse_md(pulse)
        for q in pulse.quotes:
            assert q.text in md

    def test_render_contains_actions(self):
        pulse = _sample_pulse()
        md = render_pulse_md(pulse)
        for a in pulse.actions:
            assert a.title in md
            assert a.detail in md

    def test_render_trend_arrows(self):
        pulse = _sample_pulse()
        md = render_pulse_md(pulse)
        assert "↑ rising" in md
        assert "→ steady" in md
        assert "↓ falling" in md

    def test_render_window_note(self):
        pulse = _sample_pulse(window_note="4-week rollup (low weekly volume)")
        md = render_pulse_md(pulse)
        assert "4-week rollup" in md

    def test_render_no_window_note(self):
        pulse = _sample_pulse(window_note=None)
        md = render_pulse_md(pulse)
        assert "rollup" not in md


# ===================================================================
# test_quote_pool
# ===================================================================


class TestQuotePool:
    def _reviews_and_theme(self):
        reviews = [
            Review(
                id=f"r{i}",
                date=date(2026, 8, 25 + (i % 6)),
                rating=2 + (i % 3),
                text=f"This is review number {i} with enough text to pass the minimum character limit for quoting.",
            )
            for i in range(20)
        ]
        theme = Theme(
            id="payments",
            label="Payments & UPI",
            review_ids=[r.id for r in reviews],
            avg_rating_week=3.0,
        )
        by_id = {r.id: r for r in reviews}
        return reviews, theme, by_id

    def test_pool_respects_window(self):
        reviews, theme, by_id = self._reviews_and_theme()
        pool = build_quote_pool(
            theme,
            by_id,
            reporting_from=date(2026, 8, 25),
            reporting_to=date(2026, 8, 30),
        )
        for r in pool:
            assert date(2026, 8, 25) <= r.date <= date(2026, 8, 30)

    def test_pool_respects_length(self):
        reviews, theme, by_id = self._reviews_and_theme()
        pool = build_quote_pool(
            theme,
            by_id,
            reporting_from=date(2026, 8, 25),
            reporting_to=date(2026, 8, 30),
            min_chars=40,
            max_chars=200,
        )
        for r in pool:
            assert 40 <= len(r.text) <= 200

    def test_pool_excludes_placeholders(self):
        reviews = [
            Review(
                id="clean",
                date=date(2026, 8, 28),
                rating=3,
                text="This is a clean review text with enough characters to qualify as a quote candidate.",
            ),
            Review(
                id="pii",
                date=date(2026, 8, 28),
                rating=3,
                text="Contact me at [email] for more details about the payment issue I reported.",
            ),
        ]
        theme = Theme(
            id="t",
            label="T",
            review_ids=["clean", "pii"],
            avg_rating_week=3.0,
        )
        by_id = {r.id: r for r in reviews}
        pool = build_quote_pool(
            theme, by_id,
            reporting_from=date(2026, 8, 25),
            reporting_to=date(2026, 8, 30),
        )
        assert all(r.id != "pii" for r in pool)

    def test_pool_max_candidates(self):
        reviews, theme, by_id = self._reviews_and_theme()
        pool = build_quote_pool(
            theme,
            by_id,
            reporting_from=date(2026, 8, 25),
            reporting_to=date(2026, 8, 30),
            max_candidates=3,
        )
        assert len(pool) <= 3

    def test_pool_near_duplicate_filter(self):
        reviews = [
            Review(
                id="r1",
                date=date(2026, 8, 28),
                rating=3,
                text="Money left my account but the app says payment failed, third time this month.",
            ),
            Review(
                id="r2",
                date=date(2026, 8, 28),
                rating=3,
                text="Money left my account but the app says payment failed, third time this month!",
            ),
            Review(
                id="r3",
                date=date(2026, 8, 28),
                rating=3,
                text="KYC rejected my passport photo without saying which field actually failed here.",
            ),
        ]
        theme = Theme(
            id="t",
            label="T",
            review_ids=["r1", "r2", "r3"],
            avg_rating_week=3.0,
        )
        by_id = {r.id: r for r in reviews}
        pool = build_quote_pool(
            theme, by_id,
            reporting_from=date(2026, 8, 25),
            reporting_to=date(2026, 8, 30),
        )
        ids = [r.id for r in pool]
        # r1 and r2 are near-duplicates; only one should be in the pool
        assert not ("r1" in ids and "r2" in ids)
        # r3 is different so it should be present
        assert "r3" in ids
