# CurveIQ — Decisions (ADRs)

Architecture decision records. Each entry states the decision, the reasoning, and
the trade-off — so it can be defended in interview.

---

## ADR-0: Fresh rebuild on a clean branch
The prior `D:\CurveIQ` codebase was scrapped (preserved in git commit `ca5d072`)
and rebuilt from the locked spec on branch `phase0-rebuild`. Reason: the old code
was US-only and structurally divergent from the spec; a clean build is cheaper
than reconciling it.

---

## ADR-1: Authentic sources only — no yfinance
All data must originate from official sources (FRED/Fed/US Treasury, OECD, RBI,
NSE, S&P DJI). **Trade-off accepted:** the genuinely-official S&P 500 daily feed
(FRED `SP500`) only reaches 2016; longer history is paid. So US equity is a
**splice** — FRED `SP500` (official) from 2016-06-20 onward + Yahoo `^GSPC` for
1995–2016, with a per-row `source` column recording provenance. Yahoo is the sole
sanctioned exception, scoped to S&P pre-2016 only. The splice was verified to be
continuous (no level jump at the handoff).

## ADR-2: India rates pulled live from FRED, not the bond-schema copy
The `bond` schema held India 10Y / call money / 3M interbank, but stale (call
money to 2025-12). The same series are available live from FRED/OECD
(`INDIRLTLT01STM`, `IRSTCI01INM156N`, `INDIR3TIB01STM`) to 2026-05 — fresher and
spec-designated. RBI repo stays a `bond` import (RBI-local daily, fresh, no clean
FRED daily equivalent). US 10Y comes from FRED here too (not the `bond` copy) so
the entire US curve shares one source and one vintage.

## ADR-3: Country tag overridden at ingest
`bond.series_catalog.country` mislabels **every** series as `IN`, including US
Treasuries. The canonical store (`curveiq.rates_timeseries`) sets country from our
own catalog (`US_*` -> US, `IN_*` -> IN) and a validation gate enforces it.

## ADR-4: Administered vs market separation enforced at ingestion
Every series carries `role` (`market` | `administered`). Policy rates (fed funds,
target range, RBI repo, OECD call-money composite) are `administered` and a
validation gate forbids any administered series from carrying a market-axis
category (curve/spread/real/breakeven/equity). This stops a policy rate from ever
being rendered as market movement downstream.

## ADR-5: India has no curve — `curve_points` is US-only
India free data gives a 10Y level + a short rate, not a curve. So `curve_points`
(tenor-keyed) is populated for the US only; India levels live in
`rates_timeseries`. The absence is intentional and is part of the portfolio
narrative (US = full toolkit, India = constrained companion).

## ADR-6: Provenance column on every fact table
`rates_timeseries`, `curve_points`, and `regimes` each carry a `source` string so
the authenticity of any row is auditable. Driven by the "this is a data-heavy app,
we cannot be wrong on data" requirement.

## ADR-7: curveiq schema for writes; bond + core for reads
CurveIQ reads authentic inputs from `bond` (RBI repo) and `core` (equity), and
writes its cleaned canonical store + computed metrics to its own `curveiq` schema
in the same Supabase project. Read grants are issued to `anon`/`authenticated` for
the eventual frontend.
