"""Phase 0 — ingest authentic data into curveiq.rates_timeseries / curve_points /
regimes.

Sources, all authentic:
  * FRED          — US curve, spreads, real/breakeven, policy, USREC recession.
  * bond schema   — India 10Y G-Sec, call money, 3M interbank, RBI repo (country
                    column overridden; bond.series_catalog mislabels all as 'IN').
  * core schema   — equity (curveiq_sp500, curveiq_nifty50), already vetted.

yfinance-tainted bond series (US_10Y_TREASURY_YF, INR_USD*, GOLD/BRENT) are
deliberately NOT imported. US 10Y comes from FRED here, not the bond copy, so the
whole US curve shares one authentic source and one vintage.
"""
from __future__ import annotations

from psycopg2.extras import execute_values

from . import db
from .config import (BOND_IMPORTS, EQUITY_IMPORTS, FRED_SERIES,
                     INDIA_CRISIS_WINDOWS, USREC_FRED_ID)
from .sources import fred

TENOR_LABEL = {1: "1M", 3: "3M", 6: "6M", 12: "1Y", 24: "2Y", 36: "3Y",
               60: "5Y", 84: "7Y", 120: "10Y", 240: "20Y", 360: "30Y"}


# ---------------------------------------------------------------------------
def ingest_fred(cur) -> int:
    """US toolkit from FRED -> rates_timeseries (+ curve_points for tenors)."""
    total = 0
    for s in FRED_SERIES:
        obs = fred.observations(s.fred_id)
        if not obs:
            print(f"  [warn] FRED {s.fred_id}: no observations")
            continue
        rows = [(s.country, s.series_id, s.role, s.category, d, v, s.source)
                for d, v in obs]
        execute_values(cur,
            "insert into curveiq.rates_timeseries "
            "(country,series_id,role,category,obs_date,value,source) values %s "
            "on conflict (series_id,obs_date) do update set "
            "value=excluded.value, source=excluded.source",
            rows, page_size=2000)
        # Only the US has a full multi-tenor curve. India series are standalone
        # levels (spec: "India has no curve") -> rates_timeseries only.
        if s.country == "US" and s.category == "curve" and s.tenor_months is not None:
            cp = [(s.country, d, s.tenor_months, TENOR_LABEL[s.tenor_months], v, s.source)
                  for d, v in obs]
            execute_values(cur,
                "insert into curveiq.curve_points "
                "(country,obs_date,tenor_months,tenor_label,yield,source) values %s "
                "on conflict (country,obs_date,tenor_months) do update set "
                "yield=excluded.yield, source=excluded.source",
                cp, page_size=2000)
        total += len(rows)
        print(f"  FRED {s.fred_id:9} -> {s.series_id:12} {len(rows):>6} rows "
              f"({obs[0][0]}..{obs[-1][0]})")
    return total


# ---------------------------------------------------------------------------
def ingest_bond(cur) -> int:
    """Authentic India series already in the bond schema (country corrected)."""
    total = 0
    for b in BOND_IMPORTS:
        cur.execute(
            f"select {b.date_col}, value from {b.obs_table} "
            f"where series_id=%s and value is not null order by {b.date_col}",
            (b.src_series_id,))
        obs = cur.fetchall()
        if not obs:
            print(f"  [warn] bond {b.src_series_id}: no rows")
            continue
        rows = [(b.country, b.dst_series_id, b.role, b.category, d, v, b.source)
                for d, v in obs]
        execute_values(cur,
            "insert into curveiq.rates_timeseries "
            "(country,series_id,role,category,obs_date,value,source) values %s "
            "on conflict (series_id,obs_date) do update set "
            "value=excluded.value, source=excluded.source",
            rows, page_size=2000)
        total += len(rows)
        print(f"  bond {b.src_series_id:24} -> {b.dst_series_id:14} {len(rows):>6} rows "
              f"({obs[0][0]}..{obs[-1][0]})  [{b.country}/{b.role}]")
    return total


# ---------------------------------------------------------------------------
def ingest_equity(cur) -> int:
    """Equity closes from core.curveiq_* -> rates_timeseries (category=equity)."""
    total = 0
    for e in EQUITY_IMPORTS:
        cur.execute(f"select date, close from {e.src_table} "
                    f"where close is not null order by date")
        obs = cur.fetchall()
        rows = [(e.country, e.dst_series_id, "market", "equity", d, v, e.source)
                for d, v in obs]
        execute_values(cur,
            "insert into curveiq.rates_timeseries "
            "(country,series_id,role,category,obs_date,value,source) values %s "
            "on conflict (series_id,obs_date) do update set "
            "value=excluded.value, source=excluded.source",
            rows, page_size=2000)
        total += len(rows)
        print(f"  equity {e.src_table:22} -> {e.dst_series_id:12} {len(rows):>6} rows "
              f"({obs[0][0]}..{obs[-1][0]})")
    return total


# ---------------------------------------------------------------------------
def build_regimes(cur) -> None:
    """US recession windows from FRED USREC (NBER) + India manual crisis windows."""
    # --- US: collapse monthly USREC 0/1 into contiguous recession windows ---
    obs = fred.observations(USREC_FRED_ID)
    windows: list[tuple] = []
    start = None
    prev = None
    for d, v in obs:
        if v == 1 and start is None:
            start = d
        if v == 0 and start is not None:
            windows.append(("US", "nber_recession", start, prev, "USREC"))
            start = None
        prev = d
    if start is not None:                       # open recession at series end
        windows.append(("US", "nber_recession", start, None, "USREC"))

    # --- India: manual crisis windows (spec §4 constants) ---
    for name, s, e, src in INDIA_CRISIS_WINDOWS:
        windows.append(("IN", name, s, e, src))

    execute_values(cur,
        "insert into curveiq.regimes (country,regime_name,start_date,end_date,source) "
        "values %s on conflict (country,regime_name,start_date) do update set "
        "end_date=excluded.end_date, source=excluded.source",
        windows, page_size=500)
    us = sum(1 for w in windows if w[0] == "US")
    print(f"  regimes: {us} US NBER recessions + {len(INDIA_CRISIS_WINDOWS)} India crisis windows")


# ---------------------------------------------------------------------------
def run() -> None:
    with db.cursor() as cur:
        # Idempotent rebuild: clear the canonical store before reloading.
        cur.execute("truncate curveiq.rates_timeseries, curveiq.curve_points, "
                    "curveiq.regimes restart identity")
        print("[1/4] FRED toolkit (US full + India levels) …")
        n_fred = ingest_fred(cur)
        print("[2/4] bond-schema India series …")
        n_bond = ingest_bond(cur)
        print("[3/4] equity (core.curveiq_*) …")
        n_eq = ingest_equity(cur)
        print("[4/4] regimes …")
        build_regimes(cur)
        print(f"\nIngest complete: {n_fred + n_bond + n_eq} rows into rates_timeseries.")


if __name__ == "__main__":
    run()
