# Weekly Review Pulse — Groww

LangChain-powered weekly intelligence from **Groww** Play Store reviews (`com.nextbillion.groww`).

The pipeline ingests a public review export, redacts PII, clusters themes, writes a short pulse note (themes · quotes · actions), validates it, then can append a Google Doc and create a Gmail **draft** (never auto-send) via MCP.

| Surface | URL |
| --- | --- |
| Dashboard (Vercel) | https://weeklyproductpulse-kappa.vercel.app |
| Backend API (Railway) | https://weeklyproductpulse-production-c41d.up.railway.app |
| Repo | https://github.com/himabindu-ai205/WeeklyProductPulse |

---

## What it does

1. **Ingest** Play Store CSV/JSON exports (App Store files are skipped).
2. Keep a rolling **12-week corpus**; report on the last **7 days** (or a 4-week rollup if volume is low).
3. **Redact** emails, phones, handles, etc.
4. **Cluster** into up to 5 themes (Groww-oriented seeds in `config.yaml`).
5. **Generate** a pulse with 3 highlighted themes, 3 verbatim quotes, 3 actions.
6. **Validate** (word limit, quote provenance, PII, theme counts) with retries.
7. **Publish** (optional): append Google Doc + Gmail draft through [Google Workspace MCP](https://github.com/himabindu-ai205/MCP-Server).
8. **Dashboard**: last 4 reporting weeks; add to Google Doc / share link / download `.md` / open Gmail compose.

Weekly ops: GitHub Actions every Monday 09:00 IST — see [`docs/scheduler.md`](docs/scheduler.md).

---

## Stack

- **Python 3.12** — pipeline (`src/`), stdlib HTTP API (`src/web.py`)
- **LangChain + Groq** — cluster / generate
- **LangGraph** (optional path) — generate → validate orchestration
- **MCP** — Docs append + Gmail draft only
- **Frontend** — static HTML/CSS/JS in `frontend/` (Vercel)
- **Backend** — Docker on Railway (`Dockerfile`, `requirements-app.txt`)

---

## Quick start (local)

### 1. Clone and install

```bash
git clone https://github.com/himabindu-ai205/WeeklyProductPulse.git
cd WeeklyProductPulse
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Fill in at least:

| Variable | Purpose |
| --- | --- |
| `GROQ_API_KEY` | Required for cluster/generate |
| `MCP_HTTP_TOKEN` | Required to publish Docs/Gmail |
| `GOOGLE_DOC_ID` | Existing Doc id (MCP appends; it cannot create Docs) |
| `PULSE_MODEL` | Optional (default `openai/gpt-oss-120b`) |

Behavioural knobs (windows, themes, schedule, empty `delivery.recipient` for a blank share field) live in [`config.yaml`](config.yaml).

### 3. Get reviews

```bash
# Scrape public Groww Play reviews into data/exports/
python scripts/scrape_groww_play_reviews.py --count 2000
```

Or drop a Play Console / compatible CSV under `data/exports/`.

### 4. Run the pipeline

```bash
python -m src                     # full run (publish if MCP configured)
python -m src --skip-publish      # stop after validate
python -m src --skip-llm          # ingest + redact only
python -m src --week-ending 2026-08-30 --skip-publish   # regenerate a past week into history/
python -m src --config-only       # print loaded config
```

Artifacts: `data/artifacts/pulse.json`, `pulse.md`, and `data/artifacts/history/<week_ending>/`.

### 5. Local dashboard

```bash
python -m src --serve
# → http://127.0.0.1:8080/
```

API-only (matches Railway):

```bash
python -m src --serve --backend-only
# or: python -m src.web --backend-only
```

| Endpoint | Description |
| --- | --- |
| `GET /api/health` | Liveness |
| `GET /api/weeks` | Last 4 reporting weeks + availability |
| `GET /api/pulse` | Latest pulse (`?week_ending=` / `?week=YYYY-Www`) |
| `GET /api/pulse.md` | Markdown note |
| `GET /api/meta` | Product name, email subject, default recipient |
| `POST /api/publish-doc` | Append selected week’s pulse to `GOOGLE_DOC_ID` via MCP |

---

## Deploy

### Backend — Railway

- Docker image from [`Dockerfile`](Dockerfile) (slim `requirements-app.txt`, no frontend).
- Serves `python -m src.web --backend-only`.
- Bakes `data/artifacts` (including `history/`) into the image for the read API.
- Health check: `/api/health` ([`railway.toml`](railway.toml)).

```bash
railway link   # project already linked locally
railway up
```

### Frontend — Vercel

- Project root directory: **`frontend`**
- [`frontend/vercel.json`](frontend/vercel.json) rewrites `/api/*` → Railway backend.
- Production alias used in this setup: https://weeklyproductpulse-kappa.vercel.app

```bash
cd frontend   # or deploy from repo root with Root Directory = frontend
npx vercel deploy --prod
```

---

## Weekly automation

Preferred: **GitHub Actions** — [`.github/workflows/weekly-pulse.yml`](.github/workflows/weekly-pulse.yml)

Repository secrets: `GROQ_API_KEY`, `MCP_HTTP_TOKEN`, `GOOGLE_DOC_ID` (and optional `MCP_SERVER_URL` / `PULSE_MODEL`).

Local / Task Scheduler / cron:

```bash
python scripts/run_weekly_pulse.py
python scripts/run_weekly_pulse.py --skip-fetch --skip-publish
```

Details: [`docs/scheduler.md`](docs/scheduler.md).

---

## Project layout

```
src/                 Pipeline + HTTP API
frontend/            Static dashboard (Vercel)
scripts/             Scrape, weekly runner
data/exports/        Review CSVs (gitignored contents)
data/artifacts/      pulse.json / pulse.md / history/
docs/                Architecture, plan, eval, scheduler
prompts/             LLM prompts
tests/               Pytest suite
config.yaml          Non-secret behaviour
Dockerfile           Railway backend image
```

---

## Tests

```bash
pip install -r requirements.txt
pytest
```

---

## Docs

| Doc | Topic |
| --- | --- |
| [`docs/architecture.md`](docs/architecture.md) | System design |
| [`docs/implementation-plan.md`](docs/implementation-plan.md) | Phased build |
| [`docs/scheduler.md`](docs/scheduler.md) | Weekly ops |
| [`docs/eval.md`](docs/eval.md) | Acceptance checks |
| [`docs/edge-case.md`](docs/edge-case.md) | Failure modes |
| [`docs/stitch-prompt.md`](docs/stitch-prompt.md) | Dashboard UI prompt |

---

## Notes

- **Play Store only** — no App Store mixing; no scraping of the Play listing HTML for the pipeline (public review scrape script is separate).
- **Gmail** — drafts only (`create_email_draft`); never `send_email`.
- **Dashboard “Create email draft”** opens Gmail compose in the browser (From = the account signed into Gmail there). Recipient is typed in the UI (`delivery.recipient` defaults blank).
- Do not commit `.env` or secrets.
