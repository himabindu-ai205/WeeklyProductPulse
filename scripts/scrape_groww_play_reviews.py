"""Fetch Groww Play Store reviews into data/exports/groww_play_reviews.csv.

Package: com.nextbillion.groww (hl=en_IN listing).
"""

from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

from google_play_scraper import Sort, reviews

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "exports" / "groww_play_reviews.csv"

APP_ID = "com.nextbillion.groww"
LANG = "en"
COUNTRY = "in"
DEFAULT_TARGET_COUNT = 10000
BATCH = 200


def fetch_reviews(*, target_count: int = DEFAULT_TARGET_COUNT, out: Path = OUT) -> Path:
    all_rows: list[dict] = []
    token = None
    seen_ids: set[str] = set()
    target_count = max(1, int(target_count))

    while len(all_rows) < target_count:
        batch, token = reviews(
            APP_ID,
            lang=LANG,
            country=COUNTRY,
            sort=Sort.NEWEST,
            count=min(BATCH, target_count - len(all_rows)),
            continuation_token=token,
        )
        if not batch:
            break

        for item in batch:
            rid = str(item.get("reviewId") or "")
            if rid and rid in seen_ids:
                continue
            if rid:
                seen_ids.add(rid)

            at = item.get("at")
            if isinstance(at, datetime):
                if at.tzinfo is not None:
                    at = at.astimezone(timezone.utc).replace(tzinfo=None)
                date_str = at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                date_str = str(at or "")

            content = (item.get("content") or "").strip()
            if not content:
                continue

            all_rows.append(
                {
                    "Review Submit Date and Time": date_str,
                    "Star Rating": item.get("score") or "",
                    "Review Title": "",  # Play public feed often has no title
                    "Review Text": content,
                    "App Version Name": item.get("reviewCreatedVersion") or "",
                }
            )

        print(f"fetched {len(all_rows)} unique reviews (batch={len(batch)})")
        if token is None:
            break
        time.sleep(0.5)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Review Submit Date and Time",
                "Star Rating",
                "Review Title",
                "Review Text",
                "App Version Name",
            ],
        )
        writer.writeheader()
        writer.writerows(all_rows)

    dates = [r["Review Submit Date and Time"] for r in all_rows if r["Review Submit Date and Time"]]
    print(f"wrote {len(all_rows)} reviews -> {out}")
    if dates:
        print(f"date range: {min(dates)} .. {max(dates)}")
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Scrape Groww Play Store reviews")
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_TARGET_COUNT,
        help=f"Max reviews to fetch (default {DEFAULT_TARGET_COUNT})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUT,
        help="Output CSV path",
    )
    args = parser.parse_args(argv)
    fetch_reviews(target_count=args.count, out=args.out)


if __name__ == "__main__":
    main()
