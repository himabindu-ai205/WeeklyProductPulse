"""Fetch Groww Play Store reviews into data/exports/groww_play_reviews.csv.

Package: com.nextbillion.groww (hl=en_IN listing).
"""

from __future__ import annotations

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
# Newest reviews; enough to cover ~8–12 weeks for a high-volume app
TARGET_COUNT = 10000
BATCH = 200


def main() -> None:
    all_rows: list[dict] = []
    token = None
    seen_ids: set[str] = set()

    while len(all_rows) < TARGET_COUNT:
        batch, token = reviews(
            APP_ID,
            lang=LANG,
            country=COUNTRY,
            sort=Sort.NEWEST,
            count=BATCH,
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

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
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
    print(f"wrote {len(all_rows)} reviews -> {OUT}")
    if dates:
        print(f"date range: {min(dates)} .. {max(dates)}")


if __name__ == "__main__":
    main()
