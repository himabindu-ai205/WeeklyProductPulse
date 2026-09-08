"""Phase 7 — weekly pulse: refresh reviews → classify → report.

Usage:
  py -3 scripts/run_weekly_pulse.py
  py -3 scripts/run_weekly_pulse.py --skip-fetch
  py -3 scripts/run_weekly_pulse.py --once-per-week

Exit codes (same as ``python -m src``, plus lock busy):
  0 ok
  1 generic / fetch / LLM failure
  2 empty corpus
  3 validate abort
  4 publish hard-fail
  5 weekly.lock held by another run
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_settings  # noqa: E402
from src.schedule import run_weekly_job  # noqa: E402


def _fetch(export_path: Path, scrape_count: int) -> None:
    scrape = ROOT / "scripts" / "scrape_groww_play_reviews.py"
    cmd = [
        sys.executable,
        str(scrape),
        "--count",
        str(scrape_count),
        "--out",
        str(export_path),
    ]
    print(f"[weekly] {' '.join(cmd)}", file=sys.stderr)
    proc = subprocess.run(cmd, cwd=str(ROOT), check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"review refresh failed (exit {proc.returncode})")
    if not export_path.is_file():
        raise RuntimeError(f"expected export missing after fetch: {export_path}")


def _pipeline(
    *,
    skip_publish: bool,
    once_per_week: bool,
    export_path: Path | None,
) -> int:
    cmd = [sys.executable, "-m", "src"]
    if skip_publish:
        cmd.append("--skip-publish")
    if once_per_week:
        cmd.append("--once-per-week")
    if export_path is not None and export_path.is_file():
        cmd.append(str(export_path))
    print(f"[weekly] {' '.join(cmd)}", file=sys.stderr)
    proc = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return int(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    settings = load_settings()
    sched = settings.app.schedule

    parser = argparse.ArgumentParser(description="Weekly Review Pulse scheduler")
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Do not refresh reviews (use existing CSV in data/exports/)",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Force review refresh even if schedule.fetch_before_run is false",
    )
    parser.add_argument(
        "--once-per-week",
        action="store_true",
        help="Skip Docs/Gmail publish if week_ending is already in doc_registry",
    )
    parser.add_argument(
        "--skip-publish",
        action="store_true",
        help="Never publish (Docs/Gmail) for this run",
    )
    args = parser.parse_args(argv)

    export_path = (ROOT / sched.export_path).resolve()
    do_fetch = sched.fetch_before_run
    if args.skip_fetch:
        do_fetch = False
    if args.fetch:
        do_fetch = True

    once = bool(args.once_per_week or sched.once_per_week)
    skip_publish = bool(args.skip_publish)

    def fetch_fn() -> None:
        _fetch(export_path, sched.scrape_count)

    def pipeline_fn() -> int:
        return _pipeline(
            skip_publish=skip_publish,
            once_per_week=once,
            export_path=export_path if export_path.is_file() else None,
        )

    return run_weekly_job(
        root=ROOT,
        fetch=do_fetch,
        fetch_fn=fetch_fn if do_fetch else None,
        pipeline_fn=pipeline_fn,
        once_per_week=once,
        registry_path=ROOT / "data" / "state" / "doc_registry.json",
        lock_path=ROOT / "data" / "state" / "weekly.lock",
        log_path=ROOT / "data" / "artifacts" / "weekly_run.jsonl",
    )


if __name__ == "__main__":
    raise SystemExit(main())
