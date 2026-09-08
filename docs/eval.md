# Evaluation — Weekly Review Pulse

How to evaluate the project against [`implementation-plan.md`](implementation-plan.md) and the problem-statement deliverable. Use this as a gate: a phase is **Pass** only when every required check in that phase is Pass. Do not start Phase 6 until Phase 5 is Pass.

**Related docs:** [`problemStatement.md`](problemStatement.md) · [`architecture.md`](architecture.md) · [`edge-case.md`](edge-case.md)

---

## 1. Purpose of this eval

| Question | Answer |
| --- | --- |
| What are we scoring? | Whether `python -m src` produces a valid weekly pulse and delivers it via **Docs MCP** + **Gmail draft**, within constraints. |
| What are we not scoring? | UI polish, App Store coverage, auto-send email, Google REST clients, hosted scheduling. |
| Who runs it? | Builder (per phase) and reviewer (Phase 7 close-out). |
| Pass bar | All **Required** checks Pass. **Quality** checks may be Soft Fail without blocking if noted. |

---

## 2. Scoring legend

| Result | Meaning |
| --- | --- |
| **Pass** | Meets the acceptance criteria in the implementation plan |
| **Fail** | Blocks the phase / overall done |
| **Soft Fail** | Quality issue; note it; do not invent data to “fix” it |
| **N/A** | Not applicable yet (later phase) |
| **Blocked** | Dependency phase not Pass |

**Phase score**

- **Pass** — all Required checks Pass  
- **Fail** — any Required check Fail  
- Soft Fails do not flip a phase to Fail unless marked Required

**Overall project score**

| Grade | Rule |
| --- | --- |
| **Complete** | Phases 0–7 Pass and §7 definition-of-done table all Pass |
| **Incomplete** | Any Required Fail in Phases 0–7 |
| **Disqualified** | Scraping, App Store ingest in production path, Google REST/OAuth client as primary publish path, or auto-sent email |

---

## 3. Eval environments

| Layer | When | Command / method |
| --- | --- | --- |
| **Unit / offline** | Phases 0–5 | `pytest` with fixtures + stubbed chat model; no live Google |
| **Live LLM smoke** | Phase 4+ | One run with real API key on fixture or small export |
| **MCP manual** | Phase 6–7 | Real Docs + Gmail MCP; draft only — verify in inbox UI |
| **Close-out** | Phase 7 | Real public Play export + full checklist |

Never put raw exports or `.env` in the eval report.

---

## 4. Global constraints (eval every phase)

Run these as a standing audit. Any Fail here is **Disqualified** or phase Fail.

| ID | Check | Required | How to verify | Pass if |
| --- | --- | --- | --- | --- |
| G1 | Groww Play Store only (`com.nextbillion.groww`) | Yes | Code + ingest report; no App Store rows | Only `play_store` |
| G2 | No scraping / store login automation (incl. Groww listing) | Yes | No HTTP fetch of Play Store in `src/` | Local files only |
| G3 | No Google REST/OAuth client libraries | Yes | `requirements.txt` + imports | No `google-api-python-client`, `google-auth`, etc. |
| G4 | MCP-first Docs & Gmail | Yes | `publish.py` binds MCP tools only | No hand-rolled Google HTTP |
| G5 | LLM sees redacted text only | Yes | Cluster/generate inputs | Path is `reviews.redacted.json` |
| G6 | Quotes by `review_id`, not invented text | Yes | Generate schema + render | Model does not type quote body |
| G7 | Draft never auto-sent | Yes | Gmail MCP call + inbox | Status is draft |
| G8 | Publish only after validate (or Docs-down degrade) | Yes | Graph edges | Failed validate → no publish |

---

## 5. Phase-by-phase evaluation

Copy the tables into a run log (`eval-run-YYYYMMDD.md`) and tick results.

### Phase 0 — Scaffold

**Plan goal:** Empty-but-runnable project; no pipeline logic.

| ID | Check | Required | Method | Result |
| --- | --- | --- | --- | --- |
| P0.1 | Directory tree matches plan (`src/agent/`, `prompts/`, `data/*`, `tests/fixtures/`) | Yes | `ls` / tree | ☐ |
| P0.2 | `.gitignore` covers exports, artifacts, `.env` | Yes | Read `.gitignore` | ☐ |
| P0.3 | `doc_registry.json` tracked as `{}` | Yes | File content | ☐ |
| P0.4 | `requirements.txt` has LangChain stack; no Google clients | Yes | Read file | ☐ |
| P0.5 | `config.yaml` has windows, themes, note, delivery, limits | Yes | Read file | ☐ |
| P0.6 | `.env.example` present; secrets not committed | Yes | Repo search | ☐ |
| P0.7 | `python -m src` exits 0 without model key | Yes | Run command | ☐ |
| P0.8 | `pytest` collects | Yes | `pytest --collect-only` | ☐ |
| P0.9 | Fixture has ~12 weeks Play rows + planted PII + App Store file | Yes | Open fixtures | ☐ |
| P0.10 | No LLM or MCP calls in scaffold | Yes | Code review | ☐ |

**Phase 0 verdict:** ☐ Pass · ☐ Fail

---

### Phase 1 — Ingest

**Plan goal:** `reviews.normalized.json` + ingest report; Play-only; 12-week corpus.

| ID | Check | Required | Method | Result |
| --- | --- | --- | --- | --- |
| P1.1 | Play fixture → normalized reviews | Yes | Run ingest / pytest | ☐ |
| P1.2 | No identity fields in normalized artifact | Yes | `test_ingest_drops_identity_columns` | ☐ |
| P1.3 | App Store fixture skipped and reported | Yes | `test_ingest_rejects_appstore` | ☐ |
| P1.4 | Reviews older than 12 weeks dropped | Yes | `test_ingest_window` | ☐ |
| P1.5 | `week_ending` = max date in file | Yes | Same + assert | ☐ |
| P1.6 | Empty corpus aborts (no fake pulse) | Yes | Empty fixture test | ☐ |
| P1.7 | No HTTP in `ingest.py` | Yes | Code review | ☐ |
| P1.8 | Ingest report lists in/kept/dropped/skips/min/max date | Yes | Artifact | ☐ |
| P1.9 | Thin week prepares fallback window / note hook | Soft | Config + code | ☐ |

**Phase 1 verdict:** ☐ Pass · ☐ Fail · ☐ Blocked

---

### Phase 2 — Redact

**Plan goal:** `reviews.redacted.json` is the only text later stages may see.

| ID | Check | Required | Method | Result |
| --- | --- | --- | --- | --- |
| P2.1 | Planted emails/phones/handles/URLs/IDs masked | Yes | `test_redact_patterns` | ☐ |
| P2.2 | `₹500`, `5 stars`, `4.2`, `v3.4.1` preserved | Yes | `test_redact_preserves_amounts` | ☐ |
| P2.3 | Raw title/text not written to any artifact | Yes | Inspect artifacts | ☐ |
| P2.4 | Downstream modules import redacted file only | Yes | Import / path review | ☐ |

**Phase 2 verdict:** ☐ Pass · ☐ Fail · ☐ Blocked

---

### Phase 3 — Theme math, quote pool, render

**Plan goal:** Deterministic ranking, trends, quote pool, `pulse.md` shape — no LLM.

| ID | Check | Required | Method | Result |
| --- | --- | --- | --- | --- |
| P3.1 | Ranking deterministic (volume → rating pain → id) | Yes | `test_ranking_is_deterministic` | ☐ |
| P3.2 | Trend thresholds at 1.25 / 0.75 | Yes | `test_trend_calculation` | ☐ |
| P3.3 | Thin week → 4-week rollup + `window_note` | Yes | `test_thin_week_fallback` | ☐ |
| P3.4 | Quote pool returns `review_id`s only | Yes | Unit test | ☐ |
| P3.5 | Near-duplicates filtered (similarity ≥ 0.8) | Soft | Unit test | ☐ |
| P3.6 | Word-count rule excludes headings/metadata | Yes | `test_word_count_rule` | ☐ |
| P3.7 | Render has Top themes / What users said / Action ideas | Yes | `test_render` vs worked example | ☐ |
| P3.8 | No model calls in this phase’s modules | Yes | Code review | ☐ |

**Phase 3 verdict:** ☐ Pass · ☐ Fail · ☐ Blocked

---

### Phase 4 — Cluster + generate (LangChain)

**Plan goal:** ≤5 themes; pulse with 3 themes, 3 quotes, 3 actions; structured output.

| ID | Check | Required | Method | Result |
| --- | --- | --- | --- | --- |
| P4.1 | Stubbed cluster → `themes.json` with ≤5 themes | Yes | Stub unit test | ☐ |
| P4.2 | >5 themes rejected / merged per plan | Yes | Stub returning 6 themes | ☐ |
| P4.3 | Unassigned reviews → `other` | Yes | Partial-batch stub | ☐ |
| P4.4 | Pulse has exactly 3 top themes, 3 quotes, 3 actions | Yes | Stub generate + schema | ☐ |
| P4.5 | Quotes in `pulse.md` are substrings of redacted text | Yes | Stub + provenance assert | ☐ |
| P4.6 | Model returns `review_id`s, not quote strings | Yes | Schema / code review | ☐ |
| P4.7 | Prompts never receive `reviews.normalized.json` | Yes | Code review | ☐ |
| P4.8 | Live LLM smoke on fixture (optional but recommended) | Soft | Manual one run | ☐ |
| P4.9 | `body_word_count` ≤ 250 on smoke (or validate catches) | Soft until P5 | Manual / validate | ☐ |

**Phase 4 verdict:** ☐ Pass · ☐ Fail · ☐ Blocked

---

### Phase 5 — Validate + LangGraph

**Plan goal:** Gates, capped retry, PII abort; still no Google.

| ID | Check | Required | Method | Result |
| --- | --- | --- | --- | --- |
| P5.1 | All architecture §15 non-MCP tests Pass | Yes | `pytest` | ☐ |
| P5.2 | Tampered quote → `QUOTE_NOT_VERBATIM` (+ retry or abort at 3) | Yes | `test_quote_provenance` | ☐ |
| P5.3 | Email in note → `PII_DETECTED`, no publish hook | Yes | `test_pii_gate_aborts` | ☐ |
| P5.4 | Over-250 words → `WORD_LIMIT` retry / fail closed | Yes | Stub long pulse | ☐ |
| P5.5 | Graph order: ingest → redact → cluster → generate → validate | Yes | Graph definition | ☐ |
| P5.6 | Fixable failures retry only while `attempts < 3` | Yes | Integration stub | ☐ |
| P5.7 | Retry never re-sends unredacted text | Yes | Prompt construction review | ☐ |
| P5.8 | `python -m src` prints status block through validate | Yes | Manual run | ☐ |
| P5.9 | Artifacts persisted per node | Yes | `data/artifacts/` after run | ☐ |

**Phase 5 verdict:** ☐ Pass · ☐ Fail · ☐ Blocked

---

### Phase 6 — Docs + Gmail MCP

**Plan goal:** Doc create/update + Gmail **draft**; MCP-first.

| ID | Check | Required | Method | Result |
| --- | --- | --- | --- | --- |
| P6.1 | MCP tools listed at startup; unresolved draft tool fails fast | Yes | Startup without tools | ☐ |
| P6.2 | Fake-tool tests: create vs update + draft args | Yes | pytest fakes | ☐ |
| P6.3 | Manual: Doc created/updated with pulse body | Yes | Open Google Doc | ☐ |
| P6.4 | Manual: Gmail **draft** to configured recipient | Yes | Gmail Drafts folder | ☐ |
| P6.5 | Draft contains full note and/or clear Doc link | Yes | Read draft | ☐ |
| P6.6 | Second run same `week_ending` updates same Doc (registry) | Yes | Rerun + registry | ☐ |
| P6.7 | Draft was not sent | Yes | Sent folder empty for this message | ☐ |
| P6.8 | Docs down → draft full note, `doc_url: null`, warn | Yes | Fake Docs failure | ☐ |
| P6.9 | Gmail down → hard fail; Doc/local note kept | Yes | Fake Gmail failure | ☐ |
| P6.10 | Still no Google client libs in requirements | Yes | Audit | ☐ |

**Phase 6 verdict:** ☐ Pass · ☐ Fail · ☐ Blocked

---

### Phase 7 — Close-out (definition of done)

**Plan goal:** Prove end-to-end with a real public Play export.

| ID | Check | Required | Method | Result |
| --- | --- | --- | --- | --- |
| P7.1 | Real Groww Play export in `data/exports/` (Console / public dataset — not scraped) | Yes | File present | ☐ |
| P7.2 | Full `python -m src` run succeeds or degrades per policy | Yes | Run log | ☐ |
| P7.3 | Artifacts: normalized, redacted, themes, pulse.json/md, validation | Yes | List dir | ☐ |
| P7.4 | Spot-check 3 quotes vs redacted `review_id` rows | Yes | Manual | ☐ |
| P7.5 | Status `body_word_count` ≤ 250 and matches pulse | Yes | Compare | ☐ |
| P7.6 | No names/emails/device IDs in Doc, draft, artifacts | Yes | Manual scan | ☐ |
| P7.7 | ≤5 themes; note has top 3 / 3 quotes / 3 actions | Yes | Open pulse + themes | ☐ |
| P7.8 | Doc via Docs MCP; draft via Gmail MCP | Yes | MCP + UI | ☐ |
| P7.9 | Traceability: quote → `review_id` → redacted review | Yes | Join artifacts | ☐ |
| P7.10 | LangSmith off unless operator accepts review text in traces | Soft | Env | ☐ |

**Phase 7 verdict:** ☐ Pass · ☐ Fail · ☐ Blocked

---

## 6. Definition-of-done scorecard (final)

Mirror of implementation-plan Phase 7 table. All eight must Pass for **Complete**.

| # | Criterion | Evidence | Result |
| --- | --- | --- | --- |
| 1 | Groww Play Store export, 8–12 week corpus, no App Store rows | Ingest report + `store` field | ☐ Pass · ☐ Fail |
| 2 | Redacted before model call; identity columns never persisted | Code path + artifacts | ☐ Pass · ☐ Fail |
| 3 | ≤5 themes via LangChain cluster chain | `themes.json` | ☐ Pass · ☐ Fail |
| 4 | Top 3 themes, 3 verbatim quotes, 3 actions, ≤250 words | `pulse.md` + validate | ☐ Pass · ☐ Fail |
| 5 | Note in Google Docs via Docs MCP | Doc URL + MCP logs | ☐ Pass · ☐ Fail |
| 6 | Gmail draft to self/alias with note or pointer; not sent | Draft UI | ☐ Pass · ☐ Fail |
| 7 | PII gate passed on published artifacts | Validate + manual scan | ☐ Pass · ☐ Fail |
| 8 | `pulse.json` / `themes.json` / validation on disk; quotes traceable | Artifacts | ☐ Pass · ☐ Fail |

**Overall:** ☐ Complete · ☐ Incomplete · ☐ Disqualified

---

## 7. Automated test map

| Implementation-plan test | Eval IDs |
| --- | --- |
| `test_ingest_window` | P1.4, P1.5 |
| `test_ingest_rejects_appstore` | P1.3, G1 |
| `test_ingest_drops_identity_columns` | P1.2 |
| `test_redact_patterns` | P2.1 |
| `test_redact_preserves_amounts` | P2.2 |
| `test_ranking_is_deterministic` | P3.1 |
| `test_trend_calculation` | P3.2 |
| `test_thin_week_fallback` | P3.3 |
| `test_word_count_rule` | P3.6 |
| `test_render` (worked example shape) | P3.7 |
| Stub cluster / generate | P4.1–P4.6 |
| `test_quote_provenance` | P5.2 |
| `test_pii_gate_aborts` | P5.3, G8 |
| Fake MCP publish/draft | P6.2, P6.8, P6.9 |

CI expectation: offline tests Pass on every PR; live MCP checks are manual and recorded in the run log.

---

## 8. Deliverable quality rubric (Soft)

Use after Required checks Pass. Soft Fail does not block **Complete** unless the note is unusable.

| Dimension | Pass | Soft Fail | Fail (treat as Required Fail) |
| --- | --- | --- | --- |
| Scannability | One page, clear sections | Dense but ≤250 words | Missing a required section |
| Themes | Top 3 match volume/pain ranking | Ranking odd but ≤5 themes | Invented themes / >5 |
| Quotes | Verbatim, one per theme when possible | Two from same theme | Paraphrased / fabricated |
| Actions | Concrete, tied to `theme_id` | Vague but present | Missing / wrong count |
| Audience fit | Useful for Product, Support, Leadership | Useful for one audience only | Generic fluff only |

---

## 9. Suggested eval run log template

```markdown
# Eval run — YYYY-MM-DD

Operator:
Export source: (Play Console CSV / public dataset name)
Model:
MCP Docs server:
MCP Gmail server:

## Global G1–G8
...

## Phase verdicts
0: Pass/Fail
1: ...
7: ...

## Definition of done 1–8
...

## Overall
Complete / Incomplete / Disqualified

## Notes / Soft Fails
-
```

---

## 10. What “Pass” does not allow

Even if Docs and Gmail look fine, mark **Disqualified** if any of these appear during eval:

- Scraping the Groww listing `https://play.google.com/store/apps/details?id=com.nextbillion.groww&hl=en_IN` or automating a logged-in console  
- Ingesting App Store / iOS reviews into the pulse  
- Publishing via Google REST or a bespoke OAuth client as the primary path  
- Auto-sending the email instead of leaving a draft  
- Shipping a pulse with invented quotes or unredacted reviewer PII  

These match the implementation plan’s cross-phase rules and out-of-scope list.
