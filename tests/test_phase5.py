"""Phase 5 tests: validate gates + generate/validate orchestration."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from src.agent.nodes import route_after_validate
from src.agent.runner import run_generate_validate
from src.config import load_settings
from src.render import render_pulse_md
from src.schemas import (
    DateWindow,
    Pulse,
    PulseAction,
    PulseQuote,
    PulseTheme,
    Review,
    Theme,
    ValidationResult,
)
from src.validate import scan_pii_in_text, validate_pulse, write_validation_artifact


class FakeLLM(BaseChatModel):
    responses: list[str]
    call_index: int = 0

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


@pytest.fixture
def app_config():
    return load_settings().app


def _reviews() -> list[Review]:
    return [
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


def _themes(reviews: list[Review]) -> list[Theme]:
    return [
        Theme(
            id="payments",
            label="Payments & UPI",
            review_ids=["r001"],
            count_week=5,
            avg_rating_week=2.0,
            trend="rising",
        ),
        Theme(
            id="kyc",
            label="KYC & verification",
            review_ids=["r002"],
            count_week=4,
            avg_rating_week=2.5,
            trend="steady",
        ),
        Theme(
            id="trading",
            label="Trading & orders",
            review_ids=["r003"],
            count_week=3,
            avg_rating_week=3.0,
            trend="falling",
        ),
    ]


def _good_pulse(reviews: list[Review]) -> Pulse:
    return Pulse(
        product_name="Groww",
        week_ending=date(2026, 8, 30),
        corpus_window=DateWindow(**{"from": date(2026, 6, 7), "to": date(2026, 8, 30)}),
        reporting_window=DateWindow(**{"from": date(2026, 8, 24), "to": date(2026, 8, 30)}),
        review_count_week=3,
        review_count_corpus=3,
        avg_rating_week=2.3,
        top_themes=[
            PulseTheme(
                id="payments",
                label="Payments & UPI",
                count_week=5,
                avg_rating_week=2.0,
                trend="rising",
                summary="Payment failures after debit frustrate users.",
            ),
            PulseTheme(
                id="kyc",
                label="KYC & verification",
                count_week=4,
                avg_rating_week=2.5,
                trend="steady",
                summary="KYC document uploads are rejected without reasons.",
            ),
            PulseTheme(
                id="trading",
                label="Trading & orders",
                count_week=3,
                avg_rating_week=3.0,
                trend="falling",
                summary="Trade execution lag hurts active traders.",
            ),
        ],
        quotes=[
            PulseQuote(
                text=reviews[0].text,
                review_id="r001",
                theme_id="payments",
                rating=2,
                date=date(2026, 8, 28),
            ),
            PulseQuote(
                text=reviews[1].text,
                review_id="r002",
                theme_id="kyc",
                rating=2,
                date=date(2026, 8, 27),
            ),
            PulseQuote(
                text=reviews[2].text,
                review_id="r003",
                theme_id="trading",
                rating=3,
                date=date(2026, 8, 26),
            ),
        ],
        actions=[
            PulseAction(title="Add payment retry", detail="Auto-reconcile failed debits.", theme_id="payments"),
            PulseAction(title="Show KYC reasons", detail="Field-level rejection feedback.", theme_id="kyc"),
            PulseAction(title="Cut order latency", detail="Alert when execution stalls.", theme_id="trading"),
        ],
    )


def _canned_ok(reviews: list[Review]) -> str:
    return json.dumps(
        {
            "summaries": [
                {"theme_id": "payments", "summary": "Payment failures after debit frustrate users."},
                {"theme_id": "kyc", "summary": "KYC document uploads are rejected without reasons."},
                {"theme_id": "trading", "summary": "Trade execution lag hurts active traders."},
            ],
            "selected_quotes": [
                {"theme_id": "payments", "review_id": "r001"},
                {"theme_id": "kyc", "review_id": "r002"},
                {"theme_id": "trading", "review_id": "r003"},
            ],
            "actions": [
                {"theme_id": "payments", "title": "Add payment retry", "detail": "Auto-reconcile failed debits."},
                {"theme_id": "kyc", "title": "Show KYC reasons", "detail": "Field-level rejection feedback."},
                {"theme_id": "trading", "title": "Cut order latency", "detail": "Alert when execution stalls."},
            ],
        }
    )


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


class TestValidate:
    def test_passing_pulse(self, app_config):
        reviews = _reviews()
        pulse = _good_pulse(reviews)
        md = render_pulse_md(pulse)
        result = validate_pulse(
            pulse,
            md=md,
            reviews=reviews,
            themes=_themes(reviews),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
            max_words=app_config.note.max_words,
        )
        assert result.passed
        assert result.failures == []
        assert result.fixable is True

    def test_quote_provenance(self, app_config):
        """Tampered quote fails QUOTE_NOT_VERBATIM."""
        reviews = _reviews()
        pulse = _good_pulse(reviews)
        pulse.quotes[0] = pulse.quotes[0].model_copy(
            update={"text": "This quote was invented by the model."}
        )
        md = render_pulse_md(pulse)
        result = validate_pulse(
            pulse,
            md=md,
            reviews=reviews,
            themes=_themes(reviews),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
        )
        assert not result.passed
        assert "QUOTE_NOT_VERBATIM" in result.failures
        assert result.fixable is True

    def test_quote_out_of_window(self, app_config):
        reviews = _reviews()
        reviews[0] = reviews[0].model_copy(update={"date": date(2026, 7, 1)})
        pulse = _good_pulse(reviews)
        md = render_pulse_md(pulse)
        result = validate_pulse(
            pulse,
            md=md,
            reviews=reviews,
            themes=_themes(reviews),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
        )
        assert "QUOTE_OUT_OF_WINDOW" in result.failures
        assert result.fixable is True

    def test_word_limit(self, app_config):
        reviews = _reviews()
        pulse = _good_pulse(reviews)
        # Blow up summaries so body exceeds 250 words
        long = "word " * 100
        pulse.top_themes = [
            t.model_copy(update={"summary": long}) for t in pulse.top_themes
        ]
        md = render_pulse_md(pulse)
        result = validate_pulse(
            pulse,
            md=md,
            reviews=reviews,
            themes=_themes(reviews),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
            max_words=250,
        )
        assert "WORD_LIMIT" in result.failures
        assert result.fixable is True

    def test_theme_count(self, app_config):
        reviews = _reviews()
        pulse = _good_pulse(reviews)
        pulse.top_themes = pulse.top_themes[:2]
        md = render_pulse_md(pulse)
        result = validate_pulse(
            pulse,
            md=md,
            reviews=reviews,
            themes=_themes(reviews),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
        )
        assert "THEME_COUNT" in result.failures

    def test_pii_detected_not_fixable(self, app_config):
        reviews = _reviews()
        pulse = _good_pulse(reviews)
        md = render_pulse_md(pulse) + "\nContact me at user@example.com please.\n"
        result = validate_pulse(
            pulse,
            md=md,
            reviews=reviews,
            themes=_themes(reviews),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
        )
        assert "PII_DETECTED" in result.failures
        assert result.fixable is False
        assert any("email" in h for h in result.pii_hits)

    def test_non_play_data_not_fixable(self, app_config):
        reviews = _reviews()
        reviews[0] = reviews[0].model_copy(update={"store": "play_store"})
        # Force a non-play store via model_construct to bypass Literal if needed
        bad = Review.model_construct(
            id="bad",
            store="app_store",  # type: ignore[arg-type]
            date=date(2026, 8, 28),
            rating=1,
            text="x",
        )
        reviews = reviews + [bad]
        pulse = _good_pulse(_reviews())
        md = render_pulse_md(pulse)
        result = validate_pulse(
            pulse,
            md=md,
            reviews=reviews,
            themes=_themes(_reviews()),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
        )
        assert "NON_PLAY_DATA" in result.failures
        assert result.fixable is False

    def test_scan_pii_ignores_placeholders(self):
        assert scan_pii_in_text("Reach me at [email] about the issue.") == []
        assert scan_pii_in_text("Reach me at user@example.com") != []

    def test_write_validation_artifact(self, tmp_path: Path):
        result = ValidationResult(passed=True, body_word_count=10)
        write_validation_artifact(result, tmp_path)
        data = json.loads((tmp_path / "validation.json").read_text(encoding="utf-8"))
        assert data["passed"] is True


# ---------------------------------------------------------------------------
# routing
# ---------------------------------------------------------------------------


class TestRouting:
    def test_route_publish(self):
        assert (
            route_after_validate(
                ValidationResult(passed=True, fixable=True), attempts=1, max_attempts=3
            )
            == "publish"
        )

    def test_route_retry(self):
        assert (
            route_after_validate(
                ValidationResult(passed=False, failures=["WORD_LIMIT"], fixable=True),
                attempts=1,
                max_attempts=3,
            )
            == "retry_generate"
        )

    def test_route_abort_pii(self):
        assert (
            route_after_validate(
                ValidationResult(passed=False, failures=["PII_DETECTED"], fixable=False),
                attempts=1,
                max_attempts=3,
            )
            == "abort"
        )

    def test_route_abort_attempts(self):
        assert (
            route_after_validate(
                ValidationResult(passed=False, failures=["WORD_LIMIT"], fixable=True),
                attempts=3,
                max_attempts=3,
            )
            == "abort"
        )


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------


class TestOrchestration:
    def test_pii_gate_aborts_no_publish(self, app_config, tmp_path: Path):
        """A note containing an email never reaches the publish stage."""
        reviews = _reviews()
        themes = _themes(reviews)

        # Craft a "good" structured response whose rendered note we'll... wait,
        # PII must appear in pulse.md. Inject via a summary containing an email.
        canned = json.dumps(
            {
                "summaries": [
                    {
                        "theme_id": "payments",
                        "summary": "Email user@example.com about payment failures.",
                    },
                    {"theme_id": "kyc", "summary": "KYC uploads rejected without reasons."},
                    {"theme_id": "trading", "summary": "Execution lag hurts traders."},
                ],
                "selected_quotes": [
                    {"theme_id": "payments", "review_id": "r001"},
                    {"theme_id": "kyc", "review_id": "r002"},
                    {"theme_id": "trading", "review_id": "r003"},
                ],
                "actions": [
                    {"theme_id": "payments", "title": "Add payment retry", "detail": "Auto-reconcile."},
                    {"theme_id": "kyc", "title": "Show KYC reasons", "detail": "Field feedback."},
                    {"theme_id": "trading", "title": "Cut latency", "detail": "Alert stalls."},
                ],
            }
        )
        llm = FakeLLM(responses=[canned])
        published: list[str] = []

        def publish_fn(pulse, md):
            published.append("called")

        result = run_generate_validate(
            llm,
            themes,
            themes,
            reviews,
            app_config,
            corpus_from=date(2026, 6, 1),
            corpus_to=date(2026, 8, 30),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
            week_ending=date(2026, 8, 30),
            review_count_corpus=3,
            artifacts_dir=tmp_path,
            publish_fn=publish_fn,
            max_attempts=3,
        )
        assert result.status == "aborted_non_fixable"
        assert result.published is False
        assert published == []
        assert result.validation is not None
        assert "PII_DETECTED" in result.validation.failures
        assert (tmp_path / "validation.json").is_file()

    def test_quote_tamper_retries_then_pass(self, app_config, tmp_path: Path):
        """First response picks bad path via wrong review content simulation —
        use WORD_LIMIT first then OK to prove retry."""
        reviews = _reviews()
        themes = _themes(reviews)

        long_summary = "verbose " * 90
        bad = json.dumps(
            {
                "summaries": [
                    {"theme_id": "payments", "summary": long_summary},
                    {"theme_id": "kyc", "summary": long_summary},
                    {"theme_id": "trading", "summary": long_summary},
                ],
                "selected_quotes": [
                    {"theme_id": "payments", "review_id": "r001"},
                    {"theme_id": "kyc", "review_id": "r002"},
                    {"theme_id": "trading", "review_id": "r003"},
                ],
                "actions": [
                    {"theme_id": "payments", "title": "Add payment retry", "detail": "Auto-reconcile."},
                    {"theme_id": "kyc", "title": "Show KYC reasons", "detail": "Field feedback."},
                    {"theme_id": "trading", "title": "Cut latency", "detail": "Alert stalls."},
                ],
            }
        )
        good = _canned_ok(reviews)
        llm = FakeLLM(responses=[bad, good])
        published: list[str] = []

        result = run_generate_validate(
            llm,
            themes,
            themes,
            reviews,
            app_config,
            corpus_from=date(2026, 6, 1),
            corpus_to=date(2026, 8, 30),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
            week_ending=date(2026, 8, 30),
            review_count_corpus=3,
            artifacts_dir=tmp_path,
            publish_fn=lambda p, m: published.append("ok"),
            max_attempts=3,
        )
        assert result.status == "passed"
        assert result.attempts == 2
        assert result.published is True
        assert published == ["ok"]
        assert "WORD_LIMIT" in result.failure_history[0]

    def test_attempts_exhausted(self, app_config, tmp_path: Path):
        reviews = _reviews()
        themes = _themes(reviews)
        long_summary = "verbose " * 90
        bad = json.dumps(
            {
                "summaries": [
                    {"theme_id": "payments", "summary": long_summary},
                    {"theme_id": "kyc", "summary": long_summary},
                    {"theme_id": "trading", "summary": long_summary},
                ],
                "selected_quotes": [
                    {"theme_id": "payments", "review_id": "r001"},
                    {"theme_id": "kyc", "review_id": "r002"},
                    {"theme_id": "trading", "review_id": "r003"},
                ],
                "actions": [
                    {"theme_id": "payments", "title": "Add payment retry", "detail": "Auto-reconcile."},
                    {"theme_id": "kyc", "title": "Show KYC reasons", "detail": "Field feedback."},
                    {"theme_id": "trading", "title": "Cut latency", "detail": "Alert stalls."},
                ],
            }
        )
        llm = FakeLLM(responses=[bad])
        published: list[str] = []
        result = run_generate_validate(
            llm,
            themes,
            themes,
            reviews,
            app_config,
            corpus_from=date(2026, 6, 1),
            corpus_to=date(2026, 8, 30),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
            week_ending=date(2026, 8, 30),
            review_count_corpus=3,
            artifacts_dir=tmp_path,
            publish_fn=lambda p, m: published.append("ok"),
            max_attempts=2,
        )
        assert result.status == "aborted_attempts_exhausted"
        assert result.attempts == 2
        assert published == []
        assert (tmp_path / "pulse.md").is_file()  # artifacts kept

    def test_langgraph_path_passes(self, app_config, tmp_path: Path):
        """Option A — LangGraph compile/invoke reaches publish on a good pulse."""
        reviews = _reviews()
        themes = _themes(reviews)
        llm = FakeLLM(responses=[_canned_ok(reviews)])
        published: list[str] = []
        result = run_generate_validate(
            llm,
            themes,
            themes,
            reviews,
            app_config,
            corpus_from=date(2026, 6, 1),
            corpus_to=date(2026, 8, 30),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
            week_ending=date(2026, 8, 30),
            review_count_corpus=3,
            artifacts_dir=tmp_path,
            publish_fn=lambda p, m: published.append("ok"),
            max_attempts=3,
            use_langgraph=True,
        )
        assert result.status == "passed"
        assert result.published is True
        assert published == ["ok"]
        assert (tmp_path / "validation.json").is_file()

    def test_python_runner_fallback(self, app_config, tmp_path: Path):
        """Option B — plain Python loop still works."""
        reviews = _reviews()
        themes = _themes(reviews)
        llm = FakeLLM(responses=[_canned_ok(reviews)])
        result = run_generate_validate(
            llm,
            themes,
            themes,
            reviews,
            app_config,
            corpus_from=date(2026, 6, 1),
            corpus_to=date(2026, 8, 30),
            reporting_from=date(2026, 8, 24),
            reporting_to=date(2026, 8, 30),
            week_ending=date(2026, 8, 30),
            review_count_corpus=3,
            artifacts_dir=tmp_path,
            publish_fn=None,
            use_langgraph=False,
        )
        assert result.status == "passed"
        assert result.published is False
