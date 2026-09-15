"""Default pulse must be the newest archived week, not a stale pulse.json."""

from __future__ import annotations

import json
from pathlib import Path

from src.archive import load_pulse, load_pulse_md


def _write_week(art: Path, week: str, *, md: str | None = None) -> None:
    dest = art / "history" / week
    dest.mkdir(parents=True, exist_ok=True)
    payload = {"week_ending": week, "product_name": "Groww"}
    (dest / "pulse.json").write_text(json.dumps(payload), encoding="utf-8")
    (dest / "pulse.md").write_text(md or f"# {week}\n", encoding="utf-8")


def test_load_pulse_prefers_newest_history_over_stale_top_level(tmp_path: Path):
    art = tmp_path / "artifacts"
    art.mkdir()
    (art / "pulse.json").write_text(
        json.dumps({"week_ending": "2026-08-30", "product_name": "Groww"}),
        encoding="utf-8",
    )
    (art / "pulse.md").write_text("# 2026-08-30\n", encoding="utf-8")
    _write_week(art, "2026-08-30")
    _write_week(art, "2026-09-06", md="# 2026-09-06\n")

    data = load_pulse(art)
    assert data is not None
    assert data["week_ending"] == "2026-09-06"
    assert load_pulse_md(art) == "# 2026-09-06\n"


def test_list_period_weeks_uses_archived_folders(tmp_path: Path):
    from src.archive import list_period_weeks

    art = tmp_path / "artifacts"
    art.mkdir()
    for week in ("2026-08-16", "2026-08-23", "2026-08-30", "2026-09-06", "2026-09-14"):
        _write_week(art, week)

    weeks = list_period_weeks(art, count=4)
    assert [w["week_ending"] for w in weeks] == [
        "2026-09-14",
        "2026-09-06",
        "2026-08-30",
        "2026-08-23",
    ]
    assert weeks[0]["is_latest"] is True
    assert all(w["available"] for w in weeks)
