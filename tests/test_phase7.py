"""Phase 7 — weekly scheduler wrapper (lock, order, run log)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.schedule import (
    WeeklyLockError,
    append_run_log,
    run_weekly_job,
    week_already_published,
    weekly_lock,
)


def test_weekly_lock_blocks_second_entry(tmp_path: Path):
    lock = tmp_path / "weekly.lock"
    order: list[str] = []

    with weekly_lock(lock):
        order.append("inside")
        assert lock.is_file()
        with pytest.raises(WeeklyLockError):
            with weekly_lock(lock):
                order.append("should-not-run")

    assert order == ["inside"]
    assert not lock.is_file()


def test_run_weekly_job_order_fetch_then_pipeline(tmp_path: Path):
    order: list[str] = []

    def fetch() -> None:
        order.append("fetch")

    def pipeline() -> int:
        order.append("pipeline")
        # Simulate pulse artifact for log enrichment
        art = tmp_path / "data" / "artifacts"
        art.mkdir(parents=True)
        (art / "pulse.json").write_text(
            json.dumps(
                {
                    "week_ending": "2026-09-02",
                    "draft_id": "d1",
                    "doc_url": "https://docs.example/x",
                }
            ),
            encoding="utf-8",
        )
        return 0

    code = run_weekly_job(
        root=tmp_path,
        fetch=True,
        fetch_fn=fetch,
        pipeline_fn=pipeline,
        lock_path=tmp_path / "data" / "state" / "weekly.lock",
        log_path=tmp_path / "data" / "artifacts" / "weekly_run.jsonl",
    )
    assert code == 0
    assert order == ["fetch", "pipeline"]

    log = (tmp_path / "data" / "artifacts" / "weekly_run.jsonl").read_text(encoding="utf-8")
    row = json.loads(log.strip())
    assert row["status"] == "ok"
    assert row["week_ending"] == "2026-09-02"
    assert row["draft_id"] == "d1"
    assert row["fetch"] is True


def test_run_weekly_job_skip_fetch(tmp_path: Path):
    order: list[str] = []

    def pipeline() -> int:
        order.append("pipeline")
        return 0

    code = run_weekly_job(
        root=tmp_path,
        fetch=False,
        fetch_fn=lambda: order.append("fetch"),
        pipeline_fn=pipeline,
        lock_path=tmp_path / "lock",
        log_path=tmp_path / "weekly_run.jsonl",
    )
    assert code == 0
    assert order == ["pipeline"]


def test_run_weekly_job_lock_busy_exit_5(tmp_path: Path):
    lock = tmp_path / "weekly.lock"
    # Fake a live lock with this process pid
    import os

    lock.write_text(str(os.getpid()), encoding="utf-8")

    code = run_weekly_job(
        root=tmp_path,
        fetch=False,
        fetch_fn=None,
        pipeline_fn=lambda: 0,
        lock_path=lock,
        log_path=tmp_path / "weekly_run.jsonl",
    )
    assert code == 5
    row = json.loads((tmp_path / "weekly_run.jsonl").read_text(encoding="utf-8").strip())
    assert row["status"] == "lock_busy"


def test_week_already_published(tmp_path: Path):
    reg = tmp_path / "doc_registry.json"
    reg.write_text(json.dumps({"2026-09-02": "doc123", "_default": "doc123"}), encoding="utf-8")
    assert week_already_published(reg, "2026-09-02") is True
    assert week_already_published(reg, "2026-09-09") is False
    assert week_already_published(tmp_path / "missing.json", "2026-09-02") is False


def test_append_run_log(tmp_path: Path):
    log = tmp_path / "weekly_run.jsonl"
    append_run_log(log, {"status": "ok", "n": 1})
    append_run_log(log, {"status": "failed", "n": 2})
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["n"] == 2


def test_schedule_config_loads():
    from src.config import load_settings

    settings = load_settings()
    assert settings.app.schedule.fetch_before_run is True
    assert settings.app.schedule.export_path.endswith("groww_play_reviews.csv")
    assert settings.app.schedule.scrape_count >= 100
