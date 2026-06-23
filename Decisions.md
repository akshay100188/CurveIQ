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

## ADR-8: Bond calculator — client-side TS, parity-checked against a Python twin
The single-bond engine runs **client-side in TypeScript** (`frontend/lib/bond.ts`)
for instant feedback with no infra. To keep rigor, an independent **Python reference
twin** (`pipeline/bond_reference.py`) computes the same quantities, emits **golden
vectors** (`frontend/lib/bond.golden.json`), and both test suites assert against
them — so TS == Python to 8 decimals. Textbook checks: a par bond's yield equals its
coupon; price↔yield round-trips to <1e-6; analytic duration/convexity match a
numerical derivative. YTM-from-price uses **Newton–Raphson** (seeded at the coupon,
analytic derivative = −modified-duration × dirty price) with a **bisection fallback**
over [1e-6, 2.0] when NR steps out of range.

## ADR-9: Crisis curve behaviour via key-date snapshots
Rather than animate, the US crisis view **overlays three discrete curve snapshots**
(pre-stress / peak / recovery) per episode (2008, 2013, 2020). Key dates live in
`curveiq.crisis_keydates`, each snapped to the nearest trading day with a complete
11-tenor curve. India has no free curve, so it **degrades by necessity** to a windowed
10Y-level trajectory (with an inline note on why a curve-shift view isn't possible).

## ADR-10: Day-count conventions
**US Treasuries: ACT/ACT (ICMA)**, semi-annual. **India G-Secs: 30/360**, semi-annual
— confirmed via the RBI *Government Securities Market: A Primer* and FIMMDA. The 30/360
implementation uses the US (NASD) bond-basis edge handling (`D1=31 → 30`; `D2=31 & D1∈
{30,31} → 30`), validated against worked half-period accruals. Indian **T-Bills** use
Actual/365 and are **out of scope** for v1 (they would need their own day-count branch);
the ~3-working-day shut period before coupon is a known accrued-interest edge case, noted
but not modelled.

## ADR-7: curveiq schema for writes; bond + core for reads
CurveIQ reads authentic inputs from `bond` (RBI repo) and `core` (equity), and
writes its cleaned canonical store + computed metrics to its own `curveiq` schema
in the same Supabase project. Read grants are issued to `anon`/`authenticated` for
the eventual frontend.
