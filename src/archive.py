"""Pulse history archive — last N weeks for the dashboard period picker."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

HISTORY_DIRNAME = "history"
PERIOD_WEEKS = 4


def history_root(artifacts_dir: Path) -> Path:
    return artifacts_dir / HISTORY_DIRNAME


def week_dir(artifacts_dir: Path, week_ending: date | str) -> Path:
    key = week_ending if isinstance(week_ending, str) else week_ending.isoformat()
    return history_root(artifacts_dir) / key


def archive_pulse(
    pulse: dict[str, Any] | Any,
    md: str,
    artifacts_dir: Path,
    *,
    update_latest: bool = True,
) -> Path:
    """Persist pulse into ``history/<week_ending>/`` and optionally refresh latest files."""
    if hasattr(pulse, "model_dump"):
        payload = pulse.model_dump(mode="json")
    else:
        payload = dict(pulse)

    week_raw = payload.get("week_ending")
    if not week_raw:
        raise ValueError("pulse missing week_ending")
    if isinstance(week_raw, date):
        week_key = week_raw.isoformat()
        payload["week_ending"] = week_key
    else:
        week_key = str(week_raw)[:10]

    dest = week_dir(artifacts_dir, week_key)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "pulse.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (dest / "pulse.md").write_text(md, encoding="utf-8")

    if update_latest:
        _maybe_promote_latest(artifacts_dir, week_key, payload, md)
    return dest


def ensure_latest_archived(artifacts_dir: Path) -> None:
    """If top-level pulse.json exists but history lacks it, copy into history."""
    latest = artifacts_dir / "pulse.json"
    if not latest.is_file():
        return
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    week_key = str(payload.get("week_ending") or "")[:10]
    if not week_key:
        return
    dest = week_dir(artifacts_dir, week_key) / "pulse.json"
    if dest.is_file():
        return
    md_path = artifacts_dir / "pulse.md"
    md = md_path.read_text(encoding="utf-8") if md_path.is_file() else ""
    archive_pulse(payload, md, artifacts_dir, update_latest=False)


def _maybe_promote_latest(
    artifacts_dir: Path, week_key: str, payload: dict[str, Any], md: str
) -> None:
    latest_path = artifacts_dir / "pulse.json"
    promote = True
    if latest_path.is_file():
        try:
            existing = json.loads(latest_path.read_text(encoding="utf-8"))
            existing_week = str(existing.get("week_ending") or "")[:10]
            if existing_week and existing_week > week_key:
                promote = False
        except json.JSONDecodeError:
            pass
    if not promote:
        return
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (artifacts_dir / "pulse.md").write_text(md, encoding="utf-8")


def parse_week_ending(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if "W" in value.upper():
        try:
            return date.fromisocalendar(
                int(value[:4]), int(value.upper().split("W", 1)[1]), 6
            )
        except ValueError:
            return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def iso_week_label(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def reporting_range(week_ending: date, reporting_days: int = 7) -> tuple[date, date]:
    return week_ending - timedelta(days=reporting_days - 1), week_ending


def format_range_label(from_d: date, to_d: date) -> str:
    months = (
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    )
    if from_d.year != to_d.year:
        return (
            f"{months[from_d.month - 1]} {from_d.day}, {from_d.year} – "
            f"{months[to_d.month - 1]} {to_d.day}, {to_d.year}"
        )
    if from_d.month != to_d.month:
        return (
            f"{months[from_d.month - 1]} {from_d.day} – "
            f"{months[to_d.month - 1]} {to_d.day}, {to_d.year}"
        )
    return f"{months[from_d.month - 1]} {from_d.day} – {to_d.day}, {to_d.year}"


def _latest_week_key(artifacts_dir: Path) -> str | None:
    path = artifacts_dir / "pulse.json"
    keys: list[str] = []
    if path.is_file():
        try:
            key = str(json.loads(path.read_text(encoding="utf-8")).get("week_ending") or "")[
                :10
            ]
            if key:
                keys.append(key)
        except json.JSONDecodeError:
            pass
    root = history_root(artifacts_dir)
    if root.is_dir():
        for child in root.iterdir():
            if child.is_dir() and (child / "pulse.json").is_file():
                try:
                    date.fromisoformat(child.name[:10])
                    keys.append(child.name[:10])
                except ValueError:
                    continue
    return max(keys) if keys else None


def _anchor_week_ending(artifacts_dir: Path) -> date:
    ensure_latest_archived(artifacts_dir)
    latest_key = _latest_week_key(artifacts_dir)
    if latest_key:
        try:
            return date.fromisoformat(latest_key)
        except ValueError:
            pass
    today = date.today()
    return today - timedelta(days=(today.weekday() + 2) % 7)


def pulse_available(artifacts_dir: Path, week_ending: date) -> bool:
    if (week_dir(artifacts_dir, week_ending) / "pulse.json").is_file():
        return True
    return _latest_week_key(artifacts_dir) == week_ending.isoformat() and (
        artifacts_dir / "pulse.json"
    ).is_file()


def list_period_weeks(
    artifacts_dir: Path,
    *,
    count: int = PERIOD_WEEKS,
    reporting_days: int = 7,
) -> list[dict[str, Any]]:
    """Return the latest ``count`` week endings (newest first) for the period dropdown."""
    ensure_latest_archived(artifacts_dir)
    anchor = _anchor_week_ending(artifacts_dir)
    weeks: list[dict[str, Any]] = []
    for i in range(count):
        ending = anchor - timedelta(days=7 * i)
        start, end = reporting_range(ending, reporting_days)
        weeks.append(
            {
                "week_ending": ending.isoformat(),
                "iso_week": iso_week_label(ending),
                "from": start.isoformat(),
                "to": end.isoformat(),
                "label": format_range_label(start, end),
                "available": pulse_available(artifacts_dir, ending),
                "is_latest": i == 0,
            }
        )
    return weeks


def load_pulse(
    artifacts_dir: Path, week_ending: date | str | None = None
) -> dict[str, Any] | None:
    ensure_latest_archived(artifacts_dir)
    if week_ending is None:
        path = artifacts_dir / "pulse.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    if isinstance(week_ending, str):
        parsed = parse_week_ending(week_ending)
        if parsed is None:
            return None
        week_ending = parsed

    hist = week_dir(artifacts_dir, week_ending) / "pulse.json"
    if hist.is_file():
        return json.loads(hist.read_text(encoding="utf-8"))

    latest_key = _latest_week_key(artifacts_dir)
    if latest_key == week_ending.isoformat():
        path = artifacts_dir / "pulse.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def load_pulse_md(
    artifacts_dir: Path, week_ending: date | str | None = None
) -> str | None:
    ensure_latest_archived(artifacts_dir)
    if week_ending is None:
        path = artifacts_dir / "pulse.md"
        return path.read_text(encoding="utf-8") if path.is_file() else None

    if isinstance(week_ending, str):
        parsed = parse_week_ending(week_ending)
        if parsed is None:
            return None
        week_ending = parsed

    hist = week_dir(artifacts_dir, week_ending) / "pulse.md"
    if hist.is_file():
        return hist.read_text(encoding="utf-8")

    latest_key = _latest_week_key(artifacts_dir)
    if latest_key == week_ending.isoformat():
        path = artifacts_dir / "pulse.md"
        return path.read_text(encoding="utf-8") if path.is_file() else None
    return None


def resolve_week_query(
    artifacts_dir: Path, week: str | None, week_ending: str | None
) -> date | None:
    """Resolve ``?week=`` / ``?week_ending=`` against the period list when possible."""
    raw = (week_ending or week or "").strip()
    if not raw:
        return None

    periods = list_period_weeks(artifacts_dir)
    for slot in periods:
        if slot["iso_week"].upper() == raw.upper() or slot["week_ending"] == raw[:10]:
            return date.fromisoformat(slot["week_ending"])

    return parse_week_ending(raw)
