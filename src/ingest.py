"""Ingest public Groww Play Store review exports into normalized reviews (architecture §10.1).

Product: Groww (com.nextbillion.groww). No HTTP. No store APIs. No scraping of the
Play Store listing. App Store files are skipped, never mixed in.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .config import AppConfig, Settings, load_settings
from .schemas import Review

# Column aliases (matched case-insensitively after normalizing whitespace)
TEXT_ALIASES = frozenset({"review text", "body", "content", "comment", "text", "review"})
TITLE_ALIASES = frozenset({"review title", "title", "summary"})
RATING_ALIASES = frozenset({"star rating", "rating", "score", "stars"})
DATE_ALIASES = frozenset(
    {
        "review submit date and time",
        "review last update date and time",
        "date",
        "at",
        "timestamp",
    }
)
APP_VERSION_ALIASES = frozenset({"app version code", "app version name", "version"})
# Explicitly ignored (never mapped into Review)
IGNORE_ALIASES = frozenset({"reviewer language"})

IDENTITY_HINTS = frozenset(
    {
        "reviewer name",
        "reviewer nickname",
        "author name",
        "user name",
        "username",
        "email",
        "user id",
        "userid",
        "device",
        "device id",
        "deviceid",
        "ip",
        "profile",
        "profile url",
    }
)

APPSTORE_HEADER_MARKERS = frozenset({"review id", "reviewer nickname"})


class IngestError(Exception):
    """Fatal ingest failure (missing files, unusable schema, empty corpus)."""


class EmptyCorpusError(IngestError):
    """No reviews remain after filtering — do not invent a pulse."""


@dataclass
class IngestReport:
    files_read: list[str] = field(default_factory=list)
    files_skipped_appstore: list[str] = field(default_factory=list)
    rows_read: int = 0
    rows_kept: int = 0
    rows_dropped_empty_text: int = 0
    rows_dropped_short_text: int = 0
    rows_dropped_non_english: int = 0
    rows_dropped_bad_date: int = 0
    rows_dropped_outside_window: int = 0
    rows_dropped_duplicate: int = 0
    week_ending: str | None = None
    corpus_from: str | None = None
    corpus_to: str | None = None
    reporting_from: str | None = None
    reporting_to: str | None = None
    window_note: str | None = None
    review_count_week: int = 0
    date_min: str | None = None
    date_max: str | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


MIN_REVIEW_WORDS = 8

# Indic / CJK / Arabic / etc. — if enough of these appear, treat as non-English
_NON_LATIN_SCRIPT_RE = re.compile(
    "["
    "\u0900-\u097F"  # Devanagari (Hindi, Marathi, …)
    "\u0980-\u09FF"  # Bengali
    "\u0A00-\u0A7F"  # Gurmukhi
    "\u0A80-\u0AFF"  # Gujarati
    "\u0B00-\u0B7F"  # Oriya
    "\u0B80-\u0BFF"  # Tamil
    "\u0C00-\u0C7F"  # Telugu
    "\u0C80-\u0CFF"  # Kannada
    "\u0D00-\u0D7F"  # Malayalam
    "\u0600-\u06FF"  # Arabic / Urdu
    "\u0750-\u077F"
    "\u4E00-\u9FFF"  # CJK
    "\u3040-\u30FF"  # Hiragana / Katakana
    "\uAC00-\uD7AF"  # Hangul
    "]"
)


def count_review_words(text: str) -> int:
    """Count whitespace-separated tokens that contain a letter (any script) or digit."""
    return sum(
        1
        for tok in text.split()
        if re.search(r"\d", tok) or re.search(r"[^\W\d_]", tok, flags=re.UNICODE)
    )


def is_english_review_text(text: str) -> bool:
    """Return True only when review body looks like English.

    Checks (in order):
    1. Substantial non-Latin script → not English (even if mixed with English words).
    2. ``langdetect`` primary language must be ``en`` with probability ≥ 0.5.
    3. Fallback if langdetect fails: body must be mostly Latin letters.
    """
    cleaned = text.strip()
    if not cleaned:
        return False

    non_latin = _NON_LATIN_SCRIPT_RE.findall(cleaned)
    if len(non_latin) >= 3:
        return False
    # Even 1–2 chars of Indic script in a short review is a strong signal
    if non_latin and len(non_latin) / max(len(cleaned), 1) >= 0.05:
        return False

    latin_letters = len(re.findall(r"[A-Za-z]", cleaned))
    if latin_letters < 5:
        return False

    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0  # deterministic
        langs = detect_langs(cleaned)
        if not langs:
            return False
        top = langs[0]
        return top.lang == "en" and top.prob >= 0.50
    except Exception:
        # Library missing or detection failed: Latin-majority heuristic
        other_letters = len(re.findall(r"[^\W\d_]", cleaned, flags=re.UNICODE)) - latin_letters
        return other_letters == 0 and latin_letters >= 8



@dataclass
class IngestResult:
    reviews: list[Review]
    report: IngestReport
    week_ending: date
    corpus_from: date
    corpus_to: date
    reporting_from: date
    reporting_to: date
    window_note: str | None


def _norm_header(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _map_headers(headers: Iterable[str]) -> dict[str, str]:
    """Return target_field -> original_header for known aliases."""
    mapping: dict[str, str] = {}
    for original in headers:
        key = _norm_header(original)
        if key in IGNORE_ALIASES or key in IDENTITY_HINTS:
            continue
        if key in TEXT_ALIASES and "text" not in mapping:
            mapping["text"] = original
        elif key in TITLE_ALIASES and "title" not in mapping:
            mapping["title"] = original
        elif key in RATING_ALIASES and "rating" not in mapping:
            mapping["rating"] = original
        elif key in DATE_ALIASES and "date" not in mapping:
            mapping["date"] = original
        elif key in APP_VERSION_ALIASES and "app_version" not in mapping:
            mapping["app_version"] = original
    return mapping


def is_appstore_filename(path: Path) -> bool:
    token = path.stem.lower().replace("-", "_").replace(" ", "_")
    parts = set(token.split("_"))
    return "appstore" in token or "app_store" in token or "ios" in parts


def is_appstore_headers(headers: Iterable[str]) -> bool:
    normalized = {_norm_header(h) for h in headers}
    return APPSTORE_HEADER_MARKERS.issubset(normalized)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    # Common Play Console: "2026-08-30 10:00:00" or ISO
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            if "T" in candidate or "+" in candidate or candidate.count("-") >= 2:
                # date-only
                if len(candidate) == 10 and candidate[4] == "-" and candidate[7] == "-":
                    return date.fromisoformat(candidate)
                # datetime with space
                if " " in candidate and "T" not in candidate:
                    return datetime.strptime(candidate[:19], "%Y-%m-%d %H:%M:%S").date()
                return datetime.fromisoformat(candidate).date()
        except ValueError:
            continue
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%b %d, %Y"):
        try:
            return datetime.strptime(text[:32], fmt).date()
        except ValueError:
            continue
    return None


def _parse_rating(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        n = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    if 1 <= n <= 5:
        return n
    return None


def make_review_id(d: date, rating: int | None, title: str, text: str) -> str:
    payload = f"{d.isoformat()}|{'' if rating is None else rating}|{title}|{text}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _load_tabular_rows(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise IngestError(f"CSV has no headers: {path}")
            headers = list(reader.fieldnames)
            rows = [dict(r) for r in reader]
            return headers, rows
    if suffix in {".json", ".jsonl"}:
        with path.open(encoding="utf-8") as f:
            if suffix == ".jsonl":
                rows = [json.loads(line) for line in f if line.strip()]
                if not rows:
                    return [], []
                headers = sorted({k for row in rows for k in row.keys()})
                return headers, rows
            data = json.load(f)
        if isinstance(data, list):
            rows = data
            headers = sorted({k for row in rows for k in row.keys()}) if rows else []
            return headers, rows
        if isinstance(data, dict) and "reviews" in data and isinstance(data["reviews"], list):
            rows = data["reviews"]
            headers = sorted({k for row in rows for k in row.keys()}) if rows else []
            return headers, rows
        raise IngestError(f"Unsupported JSON shape in {path}; expected a list or {{reviews: [...]}}")
    raise IngestError(f"Unsupported export type (use CSV or JSON): {path}")


def _row_to_partial(
    row: dict[str, Any], mapping: dict[str, str]
) -> tuple[Review | None, str | None]:
    """Return (review, drop_reason).

    drop_reason: empty_text|short_text|non_english|bad_date|None
    """
    text_raw = row.get(mapping["text"], "")
    text = "" if text_raw is None else str(text_raw).strip()
    if not text:
        return None, "empty_text"

    if count_review_words(text) < MIN_REVIEW_WORDS:
        return None, "short_text"

    if not is_english_review_text(text):
        return None, "non_english"

    date_raw = row.get(mapping["date"])
    d = _parse_date(date_raw)
    if d is None:
        return None, "bad_date"

    title = ""
    if "title" in mapping:
        t = row.get(mapping["title"], "")
        title = "" if t is None else str(t).strip()

    rating = _parse_rating(row.get(mapping["rating"])) if "rating" in mapping else None

    app_version = None
    if "app_version" in mapping:
        v = row.get(mapping["app_version"])
        if v is not None and str(v).strip():
            app_version = str(v).strip()

    review = Review(
        id=make_review_id(d, rating, title, text),
        store="play_store",
        date=d,
        rating=rating,
        title=title,
        text=text,
        app_version=app_version,
    )
    return review, None


def compute_windows(
    week_ending: date,
    corpus_reviews: list[Review],
    windows_cfg: Any,
) -> tuple[date, date, date, date, str | None, int]:
    """Return corpus_from, corpus_to, reporting_from, reporting_to, window_note, count_week."""
    corpus_to = week_ending
    corpus_from = week_ending - timedelta(weeks=windows_cfg.corpus_weeks)

    reporting_to = week_ending
    reporting_from = week_ending - timedelta(days=windows_cfg.reporting_days - 1)
    window_note: str | None = None

    def count_in(start: date, end: date) -> int:
        return sum(1 for r in corpus_reviews if start <= r.date <= end)

    count_week = count_in(reporting_from, reporting_to)
    if count_week < windows_cfg.min_week_reviews:
        reporting_from = week_ending - timedelta(days=windows_cfg.fallback_days - 1)
        window_note = "4-week rollup (low weekly volume)"
        count_week = count_in(reporting_from, reporting_to)

    return corpus_from, corpus_to, reporting_from, reporting_to, window_note, count_week


def ingest_paths(
    paths: list[Path],
    app: AppConfig,
    *,
    week_ending_override: date | None = None,
    artifacts_dir: Path | None = None,
    write_artifacts: bool = True,
) -> IngestResult:
    """Ingest one or more export files. Skips App Store; aborts if corpus empty."""
    report = IngestReport()
    candidates: list[Review] = []

    if not paths:
        raise IngestError("No export files provided")

    for path in paths:
        path = path.resolve()
        if not path.is_file():
            raise IngestError(f"Export file not found: {path}")

        report.files_read.append(str(path))

        if is_appstore_filename(path):
            report.files_skipped_appstore.append(str(path))
            continue

        try:
            headers, rows = _load_tabular_rows(path)
        except IngestError:
            raise
        except Exception as e:  # noqa: BLE001 — surface parse failures clearly
            raise IngestError(f"Failed to read {path}: {e}") from e

        if is_appstore_headers(headers):
            report.files_skipped_appstore.append(str(path))
            continue

        mapping = _map_headers(headers)
        if "text" not in mapping or "date" not in mapping:
            raise IngestError(
                "Unrecognized columns: need mappable text and date fields. "
                f"Detected headers: {headers}. "
                f"Text aliases: {sorted(TEXT_ALIASES)}; date aliases: {sorted(DATE_ALIASES)}"
            )

        report.rows_read += len(rows)
        for row in rows:
            review, reason = _row_to_partial(row, mapping)
            if reason == "empty_text":
                report.rows_dropped_empty_text += 1
                continue
            if reason == "short_text":
                report.rows_dropped_short_text += 1
                continue
            if reason == "non_english":
                report.rows_dropped_non_english += 1
                continue
            if reason == "bad_date":
                report.rows_dropped_bad_date += 1
                continue
            assert review is not None
            candidates.append(review)

    if not candidates and report.files_skipped_appstore and report.rows_read == 0:
        # Only App Store files (skipped before row read) or empty
        raise EmptyCorpusError(
            "No Play Store reviews to ingest "
            f"(skipped App Store files: {report.files_skipped_appstore})"
        )

    if not candidates:
        raise EmptyCorpusError("No usable review rows after parsing")

    # week_ending = max date in parsed candidates (before corpus filter), unless overridden
    week_ending = week_ending_override or max(r.date for r in candidates)
    corpus_to = week_ending
    corpus_from = week_ending - timedelta(weeks=app.windows.corpus_weeks)

    in_window: list[Review] = []
    for r in candidates:
        if corpus_from <= r.date <= corpus_to:
            in_window.append(r)
        else:
            report.rows_dropped_outside_window += 1

    if not in_window:
        raise EmptyCorpusError(
            f"Zero reviews in corpus window {corpus_from.isoformat()} → {corpus_to.isoformat()}"
        )

    # Deduplicate on id, keep earliest (sorted ascending by date)
    by_id: dict[str, Review] = {}
    for r in sorted(in_window, key=lambda x: (x.date, x.id)):
        if r.id in by_id:
            report.rows_dropped_duplicate += 1
            continue
        by_id[r.id] = r

    reviews = sorted(by_id.values(), key=lambda r: (r.date, r.id))
    report.rows_kept = len(reviews)
    report.date_min = reviews[0].date.isoformat()
    report.date_max = reviews[-1].date.isoformat()
    report.week_ending = week_ending.isoformat()

    (
        corpus_from,
        corpus_to,
        reporting_from,
        reporting_to,
        window_note,
        count_week,
    ) = compute_windows(week_ending, reviews, app.windows)

    report.corpus_from = corpus_from.isoformat()
    report.corpus_to = corpus_to.isoformat()
    report.reporting_from = reporting_from.isoformat()
    report.reporting_to = reporting_to.isoformat()
    report.window_note = window_note
    report.review_count_week = count_week

    result = IngestResult(
        reviews=reviews,
        report=report,
        week_ending=week_ending,
        corpus_from=corpus_from,
        corpus_to=corpus_to,
        reporting_from=reporting_from,
        reporting_to=reporting_to,
        window_note=window_note,
    )

    if write_artifacts:
        if artifacts_dir is None:
            raise IngestError("artifacts_dir is required when write_artifacts=True")
        write_ingest_artifacts(result, artifacts_dir)

    return result


def write_ingest_artifacts(result: IngestResult, artifacts_dir: Path) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    reviews_path = artifacts_dir / "reviews.normalized.json"
    report_path = artifacts_dir / "ingest_report.json"

    payload = [r.model_dump(mode="json") for r in result.reviews]
    reviews_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(result.report.to_dict(), indent=2), encoding="utf-8")


def ingest_exports_dir(
    settings: Settings | None = None,
    *,
    exports_dir: Path | None = None,
    artifacts_dir: Path | None = None,
    week_ending_override: date | None = None,
    write_artifacts: bool = True,
) -> IngestResult:
    settings = settings or load_settings()
    exports = exports_dir or (settings.root / "data" / "exports")
    artifacts = artifacts_dir or (settings.root / "data" / "artifacts")

    if not exports.is_dir():
        raise IngestError(f"Exports directory not found: {exports}")

    paths = sorted(
        p
        for p in exports.iterdir()
        if p.is_file() and p.suffix.lower() in {".csv", ".json", ".jsonl"} and p.name != ".gitkeep"
    )
    if not paths:
        raise IngestError(f"No export file found under {exports}")

    return ingest_paths(
        paths,
        settings.app,
        week_ending_override=week_ending_override,
        artifacts_dir=artifacts if write_artifacts else None,
        write_artifacts=write_artifacts,
    )
