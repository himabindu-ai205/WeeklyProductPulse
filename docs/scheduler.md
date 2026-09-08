# Phase 7 — Weekly scheduler

Ops automation on top of Phases 1–6: refresh Groww Play reviews, run the pulse pipeline, publish via MCP.

## Trigger (preferred): GitHub Actions

Workflow: [`.github/workflows/weekly-pulse.yml`](../.github/workflows/weekly-pulse.yml)

| When | Cron |
| --- | --- |
| Every Monday 09:00 IST | `30 3 * * 1` (UTC) |
| Manual | Actions → **Weekly Review Pulse** → Run workflow |

### Repository secrets

| Secret | Required | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | Yes | Cluster + generate |
| `MCP_HTTP_TOKEN` | Yes (unless skip publish) | Railway Google Workspace MCP |
| `GOOGLE_DOC_ID` | Yes (unless skip publish) | Doc to append |
| `MCP_SERVER_URL` | Optional | Defaults to Railway MCP URL |
| `PULSE_MODEL` | Optional | Defaults to `openai/gpt-oss-120b` |

Set secrets under **Settings → Secrets and variables → Actions**.

### Manual workflow inputs

- `skip_fetch` — use an existing CSV (no Play scrape)
- `skip_publish` — stop after validate (no Docs/Gmail)

Artifacts from each run are uploaded as `weekly-pulse-<run_id>` (pulse JSON/MD, run log, export CSV, doc registry).

## Local / OS scheduler

```powershell
# Full weekly job (fetch + pipeline + publish)
py -3 scripts\run_weekly_pulse.py

# Use existing export only
py -3 scripts\run_weekly_pulse.py --skip-fetch

# Classify only
py -3 scripts\run_weekly_pulse.py --skip-fetch --skip-publish
```

| Platform | Install |
| --- | --- |
| **Windows** | Task Scheduler → weekly Monday 09:00 → `py -3 S:\path\to\M3-9\scripts\run_weekly_pulse.py` (start in repo root) |
| **macOS/Linux** | cron: `30 3 * * 1 cd /path/to/repo && python scripts/run_weekly_pulse.py` |

Config knobs live under `schedule:` in [`config.yaml`](../config.yaml) (`fetch_before_run`, `scrape_count`, `once_per_week`, etc.).

## Behaviour

1. Acquires `data/state/weekly.lock` (overlapping runs exit `5`).
2. Optionally refreshes `data/exports/groww_play_reviews.csv` via `scripts/scrape_groww_play_reviews.py`.
3. Runs `python -m src` (ingest → redact → cluster → generate → validate → publish).
4. Appends a line to `data/artifacts/weekly_run.jsonl`.
5. With `once_per_week: true`, skips Docs/Gmail if that `week_ending` is already in `doc_registry.json`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | OK |
| 1 | Fetch / LLM / generic failure |
| 2 | Empty corpus |
| 3 | Validate abort |
| 4 | Publish hard-fail |
| 5 | Lock busy |
