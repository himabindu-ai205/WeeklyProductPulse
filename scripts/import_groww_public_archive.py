"""Convert public Groww review archive DB into an ingest-ready Play CSV."""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "raw" / "groww_pulse.db"
OUT = ROOT / "data" / "exports" / "groww_play_reviews.csv"
SAMPLE = ROOT / "data" / "exports" / "play_reviews_sample.csv"


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print("tables:", tables)

    # Prefer a reviews-like table
    review_table = None
    for name in tables:
        cols = [r[1].lower() for r in cur.execute(f"PRAGMA table_info({name})")]
        print(name, cols)
        if any(c in cols for c in ("content", "text", "review", "body", "review_text")):
            review_table = name
            break
    if review_table is None:
        raise SystemExit(f"No review table found in {tables}")

    rows = list(cur.execute(f"SELECT * FROM {review_table}"))
    print(f"using table={review_table} rows={len(rows)}")
    if rows:
        print("sample keys:", rows[0].keys())

    # Detect store filter if present
    colset = {k.lower() for k in rows[0].keys()} if rows else set()

    def get(row: sqlite3.Row, *names: str) -> str:
        mapping = {k.lower(): k for k in row.keys()}
        for n in names:
            if n.lower() in mapping:
                val = row[mapping[n.lower()]]
                return "" if val is None else str(val)
        return ""

    play_rows = []
    for row in rows:
        store = get(row, "store", "source", "platform").lower()
        # Keep Play/Android only (this archive labels Play as "android")
        if store and store not in {
            "",
            "play",
            "play_store",
            "google_play",
            "android",
            "gp",
        }:
            continue
        if store == "ios":
            continue

        text = get(row, "content", "text", "review", "body", "review_text", "reviewText")
        if not text.strip():
            continue
        title = get(row, "title", "review_title", "reviewTitle", "summary")
        rating = get(row, "score", "rating", "star_rating", "stars")
        date_raw = get(
            row,
            "at",
            "date",
            "created_at",
            "review_date",
            "timestamp",
            "submitted_at",
        )
        version = get(row, "reviewCreatedVersion", "app_version", "version", "appVersion")

        # Normalize date to Play-like string
        date_out = date_raw
        if date_raw:
            for fmt in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d",
                "%d-%m-%Y",
            ):
                try:
                    dt = datetime.strptime(date_raw[:19].replace("Z", ""), fmt.replace("Z", ""))
                    date_out = dt.strftime("%Y-%m-%d %H:%M:%S")
                    break
                except ValueError:
                    continue
            else:
                # epoch?
                try:
                    ts = float(date_raw)
                    if ts > 1e12:
                        ts /= 1000.0
                    date_out = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

        play_rows.append(
            {
                "Review Submit Date and Time": date_out,
                "Star Rating": rating,
                "Review Title": title,
                "Review Text": text,
                "App Version Name": version,
            }
        )

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
        writer.writerows(play_rows)

    # Keep sample out of the default exports folder so ingest uses real Groww data
    if SAMPLE.is_file():
        archived = ROOT / "tests" / "fixtures" / "play_reviews_sample.csv"
        # sample already lives in fixtures; remove export copy
        SAMPLE.unlink()
        print(f"removed sample export {SAMPLE} (fixture remains at {archived})")

    print(f"wrote {len(play_rows)} reviews -> {OUT}")
    if play_rows:
        print("date sample:", play_rows[0]["Review Submit Date and Time"], play_rows[-1]["Review Submit Date and Time"])


if __name__ == "__main__":
    main()
