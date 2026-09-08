"""Phase 4 tests: stubbed-model cluster + generate (implementation-plan acceptance).

Tests use a fake LLM that returns canned JSON so no API key is needed.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from src.cluster import cluster_reviews, write_cluster_artifacts
from src.config import load_settings
from src.generate import generate_pulse, write_generate_artifacts
from src.schemas import Review, Theme


# ---------------------------------------------------------------------------
# Fake LLM
# ---------------------------------------------------------------------------


class FakeLLM(BaseChatModel):
    """A fake chat model that returns pre-configured responses in order."""

    responses: list[str]
    call_index: int = 0  # public field so pydantic v1 allows mutation

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> ChatResult:
        idx = self.call_index
        self.call_index += 1
        text = self.responses[idx % len(self.responses)]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_reviews(n: int = 30, start_date: date = date(2026, 8, 1)) -> list[Review]:
    """Create synthetic reviews spread across a date range."""
    reviews = []
    themes_cycle = ["payments", "kyc", "trading", "onboarding", "withdrawals"]
    for i in range(n):
        d = date(start_date.year, start_date.month, start_date.day + (i % 28))
        reviews.append(
            Review(
                id=f"r{i:03d}",
                date=d,
                rating=1 + (i % 5),
                text=f"Review {i} about {themes_cycle[i % 5]} with enough detail for testing purposes in the pipeline.",
            )
        )
    return reviews


@pytest.fixture
def app_config():
    return load_settings().app


# ===================================================================
# Cluster tests
# ===================================================================


class TestCluster:
    def test_cluster_produces_max_5_themes(self, app_config):
        """Canned assignments → correct themes.json shape and cap of 5."""
        reviews = _make_reviews(50)

        # Build canned response: assign each review to one of the 5 seed themes
        seed_ids = [s.id for s in app_config.themes.seeds]
        canned_assignments = [
            {
                "review_id": r.id,
                "theme_id": seed_ids[i % len(seed_ids)],
                "confidence": 0.9,
            }
            for i, r in enumerate(reviews)
        ]

        # Split into batches of 25 to match cluster_batch_size
        batch1 = json.dumps(canned_assignments[:25])
        batch2 = json.dumps(canned_assignments[25:])

        llm = FakeLLM(responses=[batch1, batch2])

        themes = cluster_reviews(
            llm,
            reviews,
            app_config,
            corpus_from=date(2026, 6, 1),
            corpus_to=date(2026, 8, 30),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
        )

        assert len(themes) <= 5
        all_rids = []
        for t in themes:
            all_rids.extend(t.review_ids)
        assert len(all_rids) == len(reviews)

    def test_cluster_writes_artifacts(self, tmp_path: Path, app_config):
        """themes.json is written correctly."""
        themes = [
            Theme(id="payments", label="Payments & UPI", review_ids=["r1", "r2"]),
            Theme(id="kyc", label="KYC & verification", review_ids=["r3"]),
        ]
        write_cluster_artifacts(themes, tmp_path)
        path = tmp_path / "themes.json"
        assert path.is_file()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[0]["id"] == "payments"

    def test_cluster_unassigned_falls_to_other(self, app_config):
        """Reviews the model skips are assigned to 'other'."""
        reviews = _make_reviews(10)

        # Only assign 5 of 10 reviews
        seed_ids = [s.id for s in app_config.themes.seeds]
        partial = [
            {
                "review_id": reviews[i].id,
                "theme_id": seed_ids[i % len(seed_ids)],
                "confidence": 0.8,
            }
            for i in range(5)
        ]
        canned = json.dumps(partial)

        llm = FakeLLM(responses=[canned])

        themes = cluster_reviews(
            llm,
            reviews,
            app_config,
            corpus_from=date(2026, 6, 1),
            corpus_to=date(2026, 8, 30),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
        )

        # The missing 5 should be in "other"
        other = next((t for t in themes if t.id == "other"), None)
        assert other is not None
        assert len(other.review_ids) >= 5

    def test_cluster_over_5_merges(self, app_config):
        """If model returns > 5 themes, smallest are merged into other."""
        reviews = _make_reviews(30)

        # 6 different theme IDs (one more than max)
        assignments = [
            {
                "review_id": r.id,
                "theme_id": ["payments", "kyc", "trading", "onboarding", "withdrawals", "extra"][i % 6],
                "confidence": 0.9,
            }
            for i, r in enumerate(reviews)
        ]
        canned = json.dumps(assignments)
        llm = FakeLLM(responses=[canned])

        themes = cluster_reviews(
            llm,
            reviews,
            app_config,
            corpus_from=date(2026, 6, 1),
            corpus_to=date(2026, 8, 30),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
        )

        assert len(themes) <= 5


# ===================================================================
# Generate tests
# ===================================================================


class TestGenerate:
    def test_generate_produces_pulse(self, app_config):
        """Stubbed model → valid Pulse with 3 themes, 3 quotes, 3 actions."""
        reviews = _make_reviews(50, start_date=date(2026, 8, 1))
        reviews_by_id = {r.id: r for r in reviews}

        # Build top 3 themes with review_ids from the reporting window
        reporting_reviews = [r for r in reviews if date(2026, 8, 24) <= r.date <= date(2026, 8, 30)]

        themes = [
            Theme(
                id="payments",
                label="Payments & UPI",
                review_ids=[r.id for r in reporting_reviews if "payments" in r.text],
                count_week=10,
                avg_rating_week=2.1,
                trend="rising",
            ),
            Theme(
                id="kyc",
                label="KYC & verification",
                review_ids=[r.id for r in reporting_reviews if "kyc" in r.text],
                count_week=8,
                avg_rating_week=2.5,
                trend="steady",
            ),
            Theme(
                id="trading",
                label="Trading & orders",
                review_ids=[r.id for r in reporting_reviews if "trading" in r.text],
                count_week=5,
                avg_rating_week=3.0,
                trend="falling",
            ),
        ]

        # Pick actual review IDs from each theme for the canned response
        quote_ids = {}
        for t in themes:
            for rid in t.review_ids:
                r = reviews_by_id[rid]
                if 40 <= len(r.text) <= 200:
                    quote_ids[t.id] = rid
                    break
            if t.id not in quote_ids and t.review_ids:
                quote_ids[t.id] = t.review_ids[0]

        canned_response = json.dumps({
            "summaries": [
                {"theme_id": "payments", "summary": "Payment failures after debit frustrate users."},
                {"theme_id": "kyc", "summary": "KYC document uploads rejected without clear reasons."},
                {"theme_id": "trading", "summary": "Trade execution lags cause missed opportunities."},
            ],
            "selected_quotes": [
                {"theme_id": tid, "review_id": rid}
                for tid, rid in quote_ids.items()
            ],
            "actions": [
                {"theme_id": "payments", "title": "Add payment retry", "detail": "Auto-reconcile failed debits."},
                {"theme_id": "kyc", "title": "Show KYC rejection reasons", "detail": "Provide field-level feedback."},
                {"theme_id": "trading", "title": "Reduce execution latency", "detail": "Alert on SLO breaches."},
            ],
        })

        llm = FakeLLM(responses=[canned_response])

        pulse, md = generate_pulse(
            llm,
            themes,
            reviews,
            app_config,
            corpus_from=date(2026, 6, 1),
            corpus_to=date(2026, 8, 30),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
            week_ending=date(2026, 8, 30),
            review_count_corpus=len(reviews),
        )

        assert len(pulse.top_themes) == 3
        assert len(pulse.actions) == 3
        assert pulse.body_word_count > 0
        assert pulse.body_word_count <= 250
        assert "## Top themes" in md
        assert "## What users said" in md
        assert "## Action ideas" in md

    def test_generate_quotes_are_verbatim(self, app_config):
        """Rendered quotes must be exact substrings of redacted reviews."""
        reviews = [
            Review(
                id="r001",
                date=date(2026, 8, 28),
                rating=2,
                text="Money left my account but the app says payment failed, third time this month.",
            ),
            Review(
                id="r002",
                date=date(2026, 8, 27),
                rating=2,
                text="KYC rejected my passport photo without saying which field actually failed here.",
            ),
            Review(
                id="r003",
                date=date(2026, 8, 26),
                rating=3,
                text="App gets stuck at trade execution even after setting profit and loss limits.",
            ),
        ]
        reviews_by_id = {r.id: r for r in reviews}

        themes = [
            Theme(id="payments", label="Payments", review_ids=["r001"], count_week=5, avg_rating_week=2.0, trend="rising"),
            Theme(id="kyc", label="KYC", review_ids=["r002"], count_week=4, avg_rating_week=2.5, trend="steady"),
            Theme(id="trading", label="Trading", review_ids=["r003"], count_week=3, avg_rating_week=3.0, trend="falling"),
        ]

        canned = json.dumps({
            "summaries": [
                {"theme_id": "payments", "summary": "Payments fail after debit."},
                {"theme_id": "kyc", "summary": "KYC rejects valid documents."},
                {"theme_id": "trading", "summary": "Execution lags on trades."},
            ],
            "selected_quotes": [
                {"theme_id": "payments", "review_id": "r001"},
                {"theme_id": "kyc", "review_id": "r002"},
                {"theme_id": "trading", "review_id": "r003"},
            ],
            "actions": [
                {"theme_id": "payments", "title": "Fix payment retry", "detail": "Auto-reconcile."},
                {"theme_id": "kyc", "title": "Show rejection reasons", "detail": "Field-level feedback."},
                {"theme_id": "trading", "title": "Reduce latency", "detail": "Alert on stalls."},
            ],
        })

        llm = FakeLLM(responses=[canned])
        pulse, md = generate_pulse(
            llm,
            themes,
            reviews,
            app_config,
            corpus_from=date(2026, 6, 1),
            corpus_to=date(2026, 8, 30),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
            week_ending=date(2026, 8, 30),
            review_count_corpus=3,
        )

        # Each quote text must be exact review text
        for q in pulse.quotes:
            source = reviews_by_id[q.review_id]
            assert q.text == source.text, (
                f"Quote for {q.review_id} is not verbatim: "
                f"{q.text!r} != {source.text!r}"
            )

    def test_generate_writes_artifacts(self, tmp_path: Path, app_config):
        """pulse.json and pulse.md are written."""
        from src.schemas import DateWindow, Pulse, PulseTheme, PulseQuote, PulseAction

        pulse = Pulse(
            product_name="Groww",
            week_ending=date(2026, 8, 30),
            corpus_window=DateWindow(**{"from": date(2026, 6, 7), "to": date(2026, 8, 30)}),
            reporting_window=DateWindow(**{"from": date(2026, 8, 24), "to": date(2026, 8, 30)}),
            review_count_week=87,
            review_count_corpus=1042,
            avg_rating_week=3.4,
            top_themes=[
                PulseTheme(id="p", label="P", count_week=10, trend="rising", summary="Test."),
            ],
            quotes=[
                PulseQuote(text="Test quote.", review_id="r1", theme_id="p", date=date(2026, 8, 28)),
            ],
            actions=[
                PulseAction(title="Fix it", detail="Do the thing.", theme_id="p"),
            ],
            body_word_count=5,
        )
        md = "# Test\nTest content.\n"
        write_generate_artifacts(pulse, md, tmp_path)

        assert (tmp_path / "pulse.json").is_file()
        assert (tmp_path / "pulse.md").is_file()

        data = json.loads((tmp_path / "pulse.json").read_text(encoding="utf-8"))
        assert data["product_name"] == "Groww"
        assert data["body_word_count"] == 5

    def test_prompts_never_receive_normalized(self):
        """Verify prompts reference only redacted data — no normalized imports."""
        import inspect
        import src.generate as gen_mod

        source = inspect.getsource(gen_mod)
        assert "reviews.normalized.json" not in source
        assert "normalized" not in source.lower().replace("reviews.normalized", "")
