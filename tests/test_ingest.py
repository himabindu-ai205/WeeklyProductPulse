"""Phase 1 ingest tests (implementation-plan acceptance)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from src.config import load_settings
from src.ingest import (
    EmptyCorpusError,
    count_review_words,
    ingest_paths,
    is_appstore_filename,
    is_appstore_headers,
    is_english_review_text,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PLAY = FIXTURES / "play_reviews_sample.csv"
APPSTORE = FIXTURES / "appstore_reviews_sample.csv"


@pytest.fixture
def app_config():
    return load_settings().app


def test_ingest_window(tmp_path: Path, app_config):
    result = ingest_paths(
        [PLAY],
        app_config,
        artifacts_dir=tmp_path,
        write_artifacts=True,
    )
    assert result.week_ending.isoformat() == "2026-08-30"
    assert all(r.date >= result.corpus_from for r in result.reviews)
    assert result.report.rows_dropped_outside_window >= 1
    assert result.report.date_max == "2026-08-30"
    assert result.week_ending.isoformat() == result.report.week_ending


def test_ingest_rejects_appstore(tmp_path: Path, app_config):
    assert is_appstore_filename(APPSTORE)
    assert is_appstore_headers(
        ["Review ID", "Reviewer Nickname", "Rating", "Title", "Review", "Date"]
    )

    result = ingest_paths(
        [PLAY, APPSTORE],
        app_config,
        artifacts_dir=tmp_path,
        write_artifacts=True,
    )
    assert any("appstore" in p.lower() for p in result.report.files_skipped_appstore)
    assert all(r.store == "play_store" for r in result.reviews)
    assert result.report.rows_kept == len(result.reviews)


def test_ingest_rejects_appstore_only(tmp_path: Path, app_config):
    with pytest.raises(EmptyCorpusError):
        ingest_paths(
            [APPSTORE],
            app_config,
            artifacts_dir=tmp_path,
            write_artifacts=False,
        )


def test_ingest_drops_identity_columns(tmp_path: Path, app_config):
    result = ingest_paths(
        [PLAY],
        app_config,
        artifacts_dir=tmp_path,
        write_artifacts=True,
    )
    raw = json.loads((tmp_path / "reviews.normalized.json").read_text(encoding="utf-8"))
    assert raw, "expected normalized reviews"
    for row in raw:
        keys = set(row.keys())
        assert "Reviewer Name" not in keys
        assert "reviewer_name" not in keys
        assert "Device" not in keys
        assert "device" not in keys
        assert keys <= {"id", "store", "date", "rating", "title", "text", "app_version"}
        assert row["store"] == "play_store"


def test_ingest_empty_corpus_abort(tmp_path: Path, app_config):
    empty = tmp_path / "empty.csv"
    empty.write_text(
        "Review Submit Date and Time,Star Rating,Review Title,Review Text\n",
        encoding="utf-8",
    )
    with pytest.raises(EmptyCorpusError):
        ingest_paths([empty], app_config, write_artifacts=False)


def test_ingest_writes_artifacts(tmp_path: Path, app_config):
    result = ingest_paths([PLAY], app_config, artifacts_dir=tmp_path, write_artifacts=True)
    assert (tmp_path / "reviews.normalized.json").is_file()
    assert (tmp_path / "ingest_report.json").is_file()
    report = json.loads((tmp_path / "ingest_report.json").read_text(encoding="utf-8"))
    assert report["rows_kept"] == result.report.rows_kept
    assert report["week_ending"] == "2026-08-30"


def test_ingest_no_http_imports():
    import src.ingest as ingest_mod

    source = inspect.getsource(ingest_mod)
    assert "urllib" not in source
    assert "requests" not in source
    assert "httpx" not in source
    assert "http.client" not in source


def test_count_review_words():
    assert count_review_words("one two three") == 3
    assert count_review_words("Great app for stocks trading daily use!") == 7
    assert count_review_words("a b c d e f g h") == 8
    assert count_review_words("!!! ???") == 0


def test_is_english_review_text():
    assert is_english_review_text(
        "The app gets stuck during trade execution and orders do not go through."
    )
    assert not is_english_review_text("बहुत अच्छा ऐप है निवेश के लिए धन्यवाद")
    assert not is_english_review_text("Excelente aplicación para invertir en la bolsa todos los días")
    # Mixed: clear Devanagari → drop
    assert not is_english_review_text(
        "Good app but KYC बहुत समस्या है document upload fail"
    )


def test_ingest_drops_short_and_non_english(tmp_path: Path, app_config):
    path = tmp_path / "mixed.csv"
    path.write_text(
        "\n".join(
            [
                "Review Submit Date and Time,Star Rating,Review Title,Review Text",
                "2026-08-20 10:00:00,5,,Too short",
                "2026-08-20 10:00:00,1,,एक दो तीन चार पांच छह सात आठ नौ दस",
                "2026-08-20 10:00:00,2,,"
                "Payment failed after debit and the app still shows pending status forever.",
            ]
        ),
        encoding="utf-8",
    )
    result = ingest_paths([path], app_config, write_artifacts=False)
    assert result.report.rows_dropped_short_text >= 1
    assert result.report.rows_dropped_non_english >= 1
    assert result.report.rows_kept == 1
    assert "Payment failed" in result.reviews[0].text
    assert all(count_review_words(r.text) >= 8 for r in result.reviews)
    assert all(is_english_review_text(r.text) for r in result.reviews)
