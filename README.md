# CurveIQ

Descriptive, retrospective yield-curve analytics over **US** and **Indian**
government rates. It computes the term structure, slope/spread signals,
crisis/regime overlays, real-vs-nominal yields, the curve's principal components,
and the equity–yield relationship — and explains each in plain language. It is
**strictly descriptive**: never advice, never a forecast.

Two layers do the work:

- **L1 — deterministic compute.** Exact, unit-tested, LLM-free. Produces every number.
- **L2 — RAG explainer.** Narrates the L1 numbers from a curated corpus, grounded
  strictly in the numbers it is given. It never computes or invents a figure, and a
  forbidden-language lint blocks prescriptive / forward-looking output.

### The US / India asymmetry
The US is the full-toolkit reference (11-tenor curve, real yields & breakevens,
official spreads, NBER recessions, PCA). India is the honest constrained companion
(10Y benchmark + short rate); panels that need a full curve, an inflation-linked
market, or official recession dates are shown as **absent, each annotated with why**.

## Architecture
```
Python batch layer  ──▶  Supabase Postgres        ──▶  Next.js (Vercel)
 - FRED/OECD/RBI/NSE      - curveiq.rates_timeseries     - reads precomputed data
   ingest + gap-fill      - curveiq.curve_points         - charts (Recharts)
 - L1 deterministic calc  - curveiq.computed_metrics     - /api/explain:
 - embed corpus           - curveiq.regimes                 pgvector retrieve +
                          - curveiq.corpus_chunks (pgvector)  Claude (L2)
```

Authentic data only (no yfinance, except the sanctioned S&P-500 pre-2016 splice).
Reads come from the `bond` (RBI repo) and `core` (equity) schemas; CurveIQ writes
its canonical store + metrics to its own `curveiq` schema. Every fact row carries a
`source` provenance string.

## Data sources
| Series | Source |
|---|---|
| US curve (1M–30Y), spreads, real/breakeven, fed funds, NBER recession | FRED |
| India 10Y G-Sec, call money, 3M interbank | FRED / OECD |
| India repo rate | RBI |
| S&P 500 | FRED `SP500` (2016+) + Yahoo `^GSPC` (1995–2016) |
| Nifty 50 | niftyindices.com (NSE official) |

## Build / run

### Python pipeline (`requirements.txt`)
```bash
pip install -r requirements.txt
python -m pipeline.run_phase0           # schema + ingest + Phase 0 validation gates
python -m pipeline.phase1_compute       # L1 metrics
python -m pipeline.phase1_validate      # Phase 1 validation gates
python -m pipeline.phase2_crisis        # seed crisis key dates + bands + validation gates
python -m pipeline.phase3_rag           # build + embed the RAG corpus
python -m pipeline.refresh_daily        # full daily refresh (equity+rates+compute+gates)
python -m pipeline.bond_reference       # regenerate bond golden vectors
python -m tests.test_compute            # L1 unit tests
python -m tests.test_bond_reference     # bond engine unit tests (Python twin)
```
`.env` (gitignored) needs: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
`FRED_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`.

### Frontend
```bash
cd frontend
cp .env.example .env.local   # fill server-side keys
npm install
npm run dev                  # or: npm run build && npm start
npm test                     # vitest — bond engine + Python parity (golden vectors)
```
Deploy target: Vercel. Set the four server-side env vars in the Vercel project.

## Phases
- **Phase 0** — data foundation: ingest + 40+ validation gates. ✅
- **Phase 1** — L1 compute: spreads, curve-shape classification, real yields,
  equity–yield regime-split correlation, PCA (level ≈ 87%); **bond calculator**
  engine (TS, parity-checked vs Python twin). ✅
- **Phase 2** — Next.js frontend: `/us` (full toolkit, **curve time-scrubber**),
  `/in` (companion), `/calculator` (bond math), **crisis curve-behaviour** panels,
  Explain on every panel. ✅
- **Phase 3** — L2 RAG: corpus → pgvector → `/api/explain` + forbidden-language lint
  + prompt-cached system prompt. ✅
- **Phase 4** — US stretch: PCA + real/breakeven panels. ACM term premium is an
  optional future ingest.

### Surfaces
- `/calculator` — single-bond price↔yield, accrued, clean/dirty, current yield,
  Macaulay/modified duration, convexity, DV01; US Treasury (ACT/ACT) + India G-Sec
  (30/360) presets.
- `/us` — curve scrubber, slope/spreads, real-vs-nominal, PCA factors, equity–yield
  regime split, crisis curve overlays (2008/2013/2020), and a **rates & spread
  timeline** (10Y/2Y/10Y−2Y with all four crisis bands incl. the open-ended
  2026 US–West Asia war — the yields-up counter-case).
- `/in` — 10Y, slope, administered repo, Nifty correlation, crisis trajectories, and
  three annotated "missing" panels.

## Staying current — daily refresh
A scheduled GitHub Actions workflow ([`.github/workflows/daily-refresh.yml`](.github/workflows/daily-refresh.yml))
runs [`pipeline/refresh_daily.py`](pipeline/refresh_daily.py) every day at 23:30 UTC:
refresh equity (S&P 500 via FRED, Nifty 50 via NSE) → re-ingest fresh FRED rates +
India series → recompute L1 metrics → re-seed crisis bands → run **every validation
gate** (non-zero exit fails the run). The Vercel frontend reads Supabase with hourly
ISR, so it picks up new data within ~1h — **no redeploy needed**.

**Setup:** add two repository secrets in GitHub (Settings → Secrets and variables →
Actions): `DATABASE_URL` and `FRED_API_KEY`. Trigger a manual run any time from the
Actions tab (`workflow_dispatch`).

See [`Decisions.md`](Decisions.md) for the architecture decision records.
