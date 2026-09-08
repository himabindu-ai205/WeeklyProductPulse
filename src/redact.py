"""PII redaction for review title/text (architecture §10.2).

Runs before any model sees reviews. Raw title/text are never written to artifacts —
only redacted copies land in ``reviews.redacted.json``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .schemas import Review

# --- patterns (applied after protecting amounts / versions) ---

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)
_URL_RE = re.compile(
    r"(https?://[^\s<>\"']+|www\.[^\s<>\"']+)",
    re.IGNORECASE,
)
_HANDLE_RE = re.compile(r"(?<![A-Za-z0-9_])@[A-Za-z0-9_]{3,30}\b")
# Trailing signed name: "- Firstname L." or "- Firstname Last"
_SIGNED_NAME_RE = re.compile(
    r"(?m)\s*-\s+[A-Z][a-zA-Z]+(?:\s+[A-Z]\.?|\s+[A-Z][a-zA-Z]+)?\s*$"
)
# Phone: optional +, then digits with spaces/dashes/parens; at least 7 digits total
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d[\d\s\-().]{5,}\d)(?!\w)"
)
# Long numeric ID: 8+ consecutive digits
_LONG_DIGIT_RE = re.compile(r"\d{8,}")
# Long alphanumeric token with digits, length ≥ 12
_LONG_ALNUM_RE = re.compile(r"\b(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{12,}\b")

# Protect before digit-heavy redaction
_PROTECT_VERSION_RE = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b", re.IGNORECASE)
_PROTECT_CURRENCY_RE = re.compile(
    r"(?:₹|INR|Rs\.?)\s*\d+(?:,\d{3})*(?:\.\d+)?",
    re.IGNORECASE,
)
_PROTECT_STARS_RE = re.compile(r"\b[1-5]\s*stars?\b", re.IGNORECASE)
_PROTECT_RATING_FLOAT_RE = re.compile(r"\b[1-5]\.\d\b")


@dataclass
class RedactReport:
    reviews_in: int = 0
    reviews_out: int = 0
    fields_touched: int = 0
    replacements: dict[str, int] = field(
        default_factory=lambda: {
            "email": 0,
            "phone": 0,
            "id": 0,
            "link": 0,
            "handle": 0,
            "name": 0,
        }
    )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RedactResult:
    reviews: list[Review]
    report: RedactReport


def _protect(text: str) -> tuple[str, list[str]]:
    """Replace protectable spans with placeholders; return (masked, originals)."""
    vault: list[str] = []

    def stash(match: re.Match[str]) -> str:
        vault.append(match.group(0))
        return f"__KEEP_{len(vault) - 1}__"

    out = text
    for pattern in (
        _PROTECT_CURRENCY_RE,
        _PROTECT_VERSION_RE,
        _PROTECT_STARS_RE,
        _PROTECT_RATING_FLOAT_RE,
    ):
        out = pattern.sub(stash, out)
    return out, vault


def _restore(text: str, vault: list[str]) -> str:
    def unstash(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        return vault[idx]

    return re.sub(r"__KEEP_(\d+)__", unstash, text)


def _count_sub(pattern: re.Pattern[str], text: str, repl: str) -> tuple[str, int]:
    new_text, n = pattern.subn(repl, text)
    return new_text, n


def redact_text(text: str, counters: dict[str, int] | None = None) -> str:
    """Redact a single string. Counters updated in place when provided."""
    if not text:
        return text

    protected, vault = _protect(text)
    counts = counters if counters is not None else {
        "email": 0,
        "phone": 0,
        "id": 0,
        "link": 0,
        "handle": 0,
        "name": 0,
    }

    # Order: URLs and emails before @handles; phones/ids after protect
    protected, n = _count_sub(_URL_RE, protected, "[link]")
    counts["link"] += n
    protected, n = _count_sub(_EMAIL_RE, protected, "[email]")
    counts["email"] += n
    protected, n = _count_sub(_HANDLE_RE, protected, "[handle]")
    counts["handle"] += n
    protected, n = _count_sub(_PHONE_RE, protected, "[phone]")
    counts["phone"] += n
    protected, n = _count_sub(_LONG_DIGIT_RE, protected, "[id]")
    counts["id"] += n
    protected, n = _count_sub(_LONG_ALNUM_RE, protected, "[id]")
    counts["id"] += n
    protected, n = _count_sub(_SIGNED_NAME_RE, protected, " [name]")
    counts["name"] += n

    return _restore(protected, vault).strip()


def redact_review(review: Review, counters: dict[str, int] | None = None) -> Review:
    """Return a new Review with redacted title/text. Raw strings are discarded."""
    title = redact_text(review.title, counters)
    text = redact_text(review.text, counters)
    return Review(
        id=review.id,
        store=review.store,
        date=review.date,
        rating=review.rating,
        title=title,
        text=text,
        app_version=review.app_version,
    )


def redact_reviews(reviews: Iterable[Review]) -> RedactResult:
    report = RedactReport()
    out: list[Review] = []
    for review in reviews:
        report.reviews_in += 1
        before_title, before_text = review.title, review.text
        redacted = redact_review(review, report.replacements)
        if redacted.title != before_title or redacted.text != before_text:
            report.fields_touched += 1
        out.append(redacted)
    report.reviews_out = len(out)
    return RedactResult(reviews=out, report=report)


def write_redact_artifacts(result: RedactResult, artifacts_dir: Path) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / "reviews.redacted.json"
    payload = [r.model_dump(mode="json") for r in result.reviews]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path = artifacts_dir / "redact_report.json"
    report_path.write_text(json.dumps(result.report.to_dict(), indent=2), encoding="utf-8")


def load_normalized_reviews(path: Path) -> list[Review]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a list in {path}")
    return [Review.model_validate(row) for row in data]


def redact_from_artifacts(
    artifacts_dir: Path,
    *,
    write_artifacts: bool = True,
) -> RedactResult:
    normalized = artifacts_dir / "reviews.normalized.json"
    if not normalized.is_file():
        raise FileNotFoundError(
            f"Missing {normalized}; run ingest before redact"
        )
    reviews = load_normalized_reviews(normalized)
    result = redact_reviews(reviews)
    if write_artifacts:
        write_redact_artifacts(result, artifacts_dir)
    return result
