# Groww Play Store exports

Product: **Groww** (`com.nextbillion.groww`)  
Listing: https://play.google.com/store/apps/details?id=com.nextbillion.groww&hl=en_IN

## Current export

| File | Source | Notes |
| --- | --- | --- |
| `groww_play_reviews.csv` | Scraped public Play reviews for `com.nextbillion.groww` (`en` / `in`) | Written by `scripts/scrape_groww_play_reviews.py` |

Refresh:

```powershell
py -3 scripts\scrape_groww_play_reviews.py
py -3 -m src
```
