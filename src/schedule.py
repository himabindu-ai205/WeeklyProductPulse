"""Phase 7 — weekly lock, run log, and orchestration helpers.

Used by ``scripts/run_weekly_pulse.py`` and unit tests. No live scrape or MCP here.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


class WeeklyLockError(RuntimeError):
    """Another weekly run holds ``data/state/weekly.lock``."""


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we cannot signal it
        return True
    except OSError:
        return False
    return True


@contextmanager
def weekly_lock(lock_path: Path) -> Iterator[None]:
    """Acquire an exclusive lock file; raise ``WeeklyLockError`` if busy."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.is_file():
        try:
            raw = lock_path.read_text(encoding="utf-8").strip()
            old_pid = int(raw.splitlines()[0])
        except (ValueError, OSError):
            old_pid = -1
        if _pid_alive(old_pid):
            raise WeeklyLockError(
                f"Weekly run already in progress (pid={old_pid}, lock={lock_path})"
            )
        try:
            lock_path.unlink()
        except OSError:
            pass

    lock_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    try:
        yield
    finally:
        try:
            if lock_path.is_file():
                contents = lock_path.read_text(encoding="utf-8").strip()
                if contents.splitlines()[0] == str(os.getpid()):
                    lock_path.unlink()
        except OSError:
            pass


def append_run_log(log_path: Path, record: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_doc_registry(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def week_already_published(registry_path: Path, week_ending: str) -> bool:
    registry = load_doc_registry(registry_path)
    return bool(week_ending and week_ending in registry)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_weekly_job(
    *,
    root: Path,
    fetch: bool,
    fetch_fn: Callable[[], None] | None,
    pipeline_fn: Callable[[], int],
    once_per_week: bool = False,
    registry_path: Path | None = None,
    lock_path: Path | None = None,
    log_path: Path | None = None,
) -> int:
    """Ordered weekly job: lock → optional fetch → pipeline → log.

    ``pipeline_fn`` should return the same exit codes as ``python -m src``.
    When ``once_per_week`` is set, ``pipeline_fn`` is responsible for skipping
    publish (caller wires ``--once-per-week`` / ``skip_publish``).
    """
    lock = lock_path or (root / "data" / "state" / "weekly.lock")
    log = log_path or (root / "data" / "artifacts" / "weekly_run.jsonl")
    started = utc_now_iso()
    record: dict[str, Any] = {
        "started_at": started,
        "finished_at": None,
        "week_ending": None,
        "status": "started",
        "draft_id": None,
        "doc_url": None,
        "error": None,
        "fetch": fetch,
        "once_per_week": once_per_week,
    }

    try:
        with weekly_lock(lock):
            if fetch:
                if fetch_fn is None:
                    raise RuntimeError("fetch requested but fetch_fn is None")
                print("[weekly] refreshing reviews…", file=sys.stderr)
                fetch_fn()
            else:
                print("[weekly] skip fetch", file=sys.stderr)

            # Optional hint for logging: peek registry / pulse after run
            _ = registry_path

            print("[weekly] running pipeline…", file=sys.stderr)
            code = int(pipeline_fn())

            pulse_path = root / "data" / "artifacts" / "pulse.json"
            if pulse_path.is_file():
                try:
                    pulse = json.loads(pulse_path.read_text(encoding="utf-8"))
                    record["week_ending"] = pulse.get("week_ending")
                    record["draft_id"] = pulse.get("draft_id")
                    record["doc_url"] = pulse.get("doc_url")
                except json.JSONDecodeError:
                    pass

            if code == 0:
                record["status"] = "ok"
            elif code == 2:
                record["status"] = "empty_corpus"
                record["error"] = f"exit_code={code}"
            elif code == 3:
                record["status"] = "validate_abort"
                record["error"] = f"exit_code={code}"
            elif code == 4:
                record["status"] = "publish_failed"
                record["error"] = f"exit_code={code}"
            else:
                record["status"] = "failed"
                record["error"] = f"exit_code={code}"

            record["finished_at"] = utc_now_iso()
            append_run_log(log, record)
            return code
    except WeeklyLockError as e:
        record["status"] = "lock_busy"
        record["error"] = str(e)
        record["finished_at"] = utc_now_iso()
        append_run_log(log, record)
        print(f"[weekly] {e}", file=sys.stderr)
        return 5
    except Exception as e:  # noqa: BLE001
        record["status"] = "failed"
        record["error"] = str(e)
        record["finished_at"] = utc_now_iso()
        append_run_log(log, record)
        print(f"[weekly] error: {e}", file=sys.stderr)
        return 1
