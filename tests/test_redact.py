"""Phase 2 redact tests (implementation-plan acceptance)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.config import load_settings
from src.ingest import ingest_paths
from src.redact import (
    redact_from_artifacts,
    redact_reviews,
    redact_text,
)
from src.schemas import Review

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PLAY = FIXTURES / "play_reviews_sample.csv"


@pytest.fixture
def app_config():
    return load_settings().app


def test_redact_patterns():
    samples = {
        "email": "Reach me at user@example.com please",
        "phone": "Please call +91 98765 43210 regarding KYC",
        "handle": "Follow up via @angryuser on this bug",
        "link": "Details at https://example.com/u/jane now",
        "id": "device ABCDEF123456 failed",
        "name": "App froze during onboarding again. - Firstname L.",
    }
    assert "[email]" in redact_text(samples["email"])
    assert "user@example.com" not in redact_text(samples["email"])
    assert "[phone]" in redact_text(samples["phone"])
    assert "98765" not in redact_text(samples["phone"])
    assert "[handle]" in redact_text(samples["handle"])
    assert "@angryuser" not in redact_text(samples["handle"])
    assert "[link]" in redact_text(samples["link"])
    assert "https://" not in redact_text(samples["link"])
    assert "[id]" in redact_text(samples["id"])
    assert "ABCDEF123456" not in redact_text(samples["id"])
    assert "[name]" in redact_text(samples["name"])
    assert "Firstname L." not in redact_text(samples["name"])


def test_redact_preserves_amounts():
    text = "Debit of ₹500 failed; INR 1200 pending; rated 5 stars and 4.2 overall on v3.4.1"
    out = redact_text(text)
    assert "₹500" in out
    assert "INR 1200" in out
    assert "5 stars" in out
    assert "4.2" in out
    assert "v3.4.1" in out


def test_redact_fixture_pii_gone(tmp_path: Path, app_config):
    ingest_paths([PLAY], app_config, artifacts_dir=tmp_path, write_artifacts=True)
    result = redact_from_artifacts(tmp_path, write_artifacts=True)
    redacted_path = tmp_path / "reviews.redacted.json"
    assert redacted_path.is_file()
    blob = redacted_path.read_text(encoding="utf-8")
    assert "user@example.com" not in blob
    assert "98765 43210" not in blob
    assert "@angryuser" not in blob
    assert "https://example.com" not in blob
    assert "ABCDEF123456" not in blob
    assert "Firstname L." not in blob
    assert result.report.reviews_out == result.report.reviews_in
    assert result.report.replacements["email"] >= 1
    assert result.report.replacements["phone"] >= 1
    assert result.report.replacements["handle"] >= 1
    assert result.report.replacements["link"] >= 1


def test_redact_discards_raw_strings():
    review = Review(
        id="abc123def456",
        date=date(2026, 8, 1),
        rating=2,
        title="Contact user@example.com",
        text="Call +91 98765 43210 now",
        app_version="3.4.1",
    )
    result = redact_reviews([review])
    out = result.reviews[0]
    assert "user@example.com" not in out.title
    assert "98765" not in out.text
    assert out.id == review.id
    assert out.app_version == "3.4.1"
    dumped = json.dumps(out.model_dump(mode="json"))
    assert "user@example.com" not in dumped
