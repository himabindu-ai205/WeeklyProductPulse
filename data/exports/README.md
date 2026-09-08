# Groww Play Store exports

Product: **Groww** (`com.nextbillion.groww`)  
Listing: https://play.google.com/store/apps/details?id=com.nextbillion.groww&hl=en_IN

## Current export

| File | Source | Notes |
| --- | --- | --- |
| `groww_play_reviews.csv` | Scraped public Play reviews for `com.nextbillion.groww` (`en` / `in`) | Written by `scripts/scrape_groww_play_reviews.py` |

Refresh manually:

```powershell
py -3 scripts\scrape_groww_play_reviews.py --count 2000
py -3 -m src
```

Or the Phase 7 weekly job (fetch + classify + publish):

```powershell
py -3 scripts\run_weekly_pulse.py
```

On GitHub, the same job runs every Monday 09:00 IST via [`.github/workflows/weekly-pulse.yml`](../../.github/workflows/weekly-pulse.yml). See [`docs/scheduler.md`](../../docs/scheduler.md).
