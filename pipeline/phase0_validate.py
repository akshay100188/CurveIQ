"""Phase 0 — data validation gates.

Hard gates (FAIL -> non-zero exit): authenticity, country/role correctness,
administered/market separation, null/duplicate integrity, value-range sanity,
and domain spot-checks (2019 US inversion, India crisis windows, curve
completeness). Staleness is reported as WARN, since some authentic sources
(OECD/RBI monthly) publish with a lag we don't control.

Run: python -m pipeline.phase0_validate
"""
from __future__ import annotations

import sys
from datetime import date

from . import db

FAILS: list[str] = []
WARNS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    """Hard gate. `detail` describes the failure and prints only when failing."""
    if ok:
        print(f"  [PASS] {name}")
    else:
        FAILS.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} -- {detail}")


def warn(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  [PASS] {name}")
    else:
        WARNS.append(f"{name}: {detail}")
        print(f"  [WARN] {name} -- {detail}")


def run() -> int:
    today = date.today()
    with db.cursor() as cur:

        # ---- 1. Authenticity: no yfinance/Yahoo except approved US_SP500 ----
        print("\n[1] Authenticity of sources")
        cur.execute("""select distinct series_id, source from curveiq.rates_timeseries
                       where source ilike '%yfinance%'""")
        yf = cur.fetchall()
        check("no yfinance-sourced rows", not yf, f"found {yf}")
        cur.execute("""select distinct series_id from curveiq.rates_timeseries
                       where source ilike '%yahoo%' and series_id <> 'US_SP500'""")
        yh = [r[0] for r in cur.fetchall()]
        check("Yahoo only in approved US_SP500", not yh, f"unexpected Yahoo in {yh}")

        # ---- 2. Country correctness (bond.series_catalog mislabels all IN) ----
        print("\n[2] Country tagging")
        cur.execute("""select count(*) from curveiq.rates_timeseries
                       where series_id like 'US\\_%' and country <> 'US'""")
        check("US_* series tagged US", cur.fetchone()[0] == 0)
        cur.execute("""select count(*) from curveiq.rates_timeseries
                       where series_id like 'IN\\_%' and country <> 'IN'""")
        check("IN_* series tagged IN", cur.fetchone()[0] == 0)
        cur.execute("select distinct country from curveiq.rates_timeseries")
        ctys = sorted(r[0] for r in cur.fetchall())
        check("countries are exactly {US,IN}", ctys == ["IN", "US"], str(ctys))

        # ---- 3. Administered/market separation ----
        print("\n[3] Administered vs market separation")
        cur.execute("""select distinct series_id, category from curveiq.rates_timeseries
                       where role='administered'
                         and category in ('curve','spread','real','breakeven','equity')""")
        bad = cur.fetchall()
        check("no administered series on a market-axis category", not bad, str(bad))
        cur.execute("""select distinct series_id from curveiq.rates_timeseries
                       where role='administered' and category <> 'policy'""")
        check("administered series are all policy", not cur.fetchall())

        # ---- 4. Integrity: nulls + duplicates ----
        print("\n[4] Integrity")
        cur.execute("select count(*) from curveiq.rates_timeseries where value is null")
        check("no null values", cur.fetchone()[0] == 0)
        cur.execute("""select series_id, obs_date, count(*) from curveiq.rates_timeseries
                       group by series_id, obs_date having count(*) > 1 limit 1""")
        check("no duplicate (series_id,obs_date)", not cur.fetchone())
        cur.execute("select count(*) from curveiq.curve_points where yield is null")
        check("no null curve-point yields", cur.fetchone()[0] == 0)

        # ---- 5. Value-range sanity ----
        print("\n[5] Value-range sanity")
        cur.execute("""select series_id, min(value), max(value) from curveiq.rates_timeseries
                       where category in ('curve','policy','real') group by series_id""")
        for sid, lo, hi in cur.fetchall():
            ok = -5 <= float(lo) and float(hi) <= 25
            check(f"yield range {sid}", ok, f"[{lo}, {hi}] outside [-5,25]")
        cur.execute("""select series_id, min(value), max(value) from curveiq.rates_timeseries
                       where category='spread' group by series_id""")
        for sid, lo, hi in cur.fetchall():
            ok = -6 <= float(lo) and float(hi) <= 6
            check(f"spread range {sid}", ok, f"[{lo}, {hi}] outside [-6,6]")
        cur.execute("""select series_id, min(value) from curveiq.rates_timeseries
                       where category='equity' group by series_id""")
        for sid, lo in cur.fetchall():
            check(f"equity positive {sid}", float(lo) > 0, f"min={lo}")

        # ---- 6. Domain spot-checks ----
        print("\n[6] Domain spot-checks")
        # 2019 US curve inverted (Aug 2019: 10Y-2Y went negative)
        cur.execute("""select min(value) from curveiq.rates_timeseries
                       where series_id='US_T10Y2Y'
                         and obs_date between '2019-01-01' and '2019-12-31'""")
        m = cur.fetchone()[0]
        check("2019 US 10Y-2Y inverted", m is not None and float(m) < 0, f"min 2019 = {m}")
        # 10Y-2Y reconstructed from curve agrees with FRED's T10Y2Y on a date
        cur.execute("""select (d10.value - d2.value) as recon, sp.value as fred
                       from curveiq.rates_timeseries d10
                       join curveiq.rates_timeseries d2 on d2.obs_date=d10.obs_date
                       join curveiq.rates_timeseries sp on sp.obs_date=d10.obs_date
                       where d10.series_id='US_DGS10' and d2.series_id='US_DGS2'
                         and sp.series_id='US_T10Y2Y' and d10.obs_date='2019-08-28'""")
        row = cur.fetchone()
        if row:
            check("DGS10-DGS2 ~= FRED T10Y2Y (2019-08-28)",
                  abs(float(row[0]) - float(row[1])) <= 0.03,
                  f"recon={row[0]} fred={row[1]}")
        # India crisis windows present
        cur.execute("""select count(*) from curveiq.regimes
                       where country='IN' and regime_name in ('taper_tantrum','covid')""")
        check("India crisis windows present", cur.fetchone()[0] == 2)
        # US recessions present incl. COVID (2020)
        cur.execute("""select count(*) from curveiq.regimes
                       where country='US' and start_date <= '2020-04-01'
                         and (end_date is null or end_date >= '2020-02-01')""")
        check("US 2020 recession window present", cur.fetchone()[0] >= 1)
        # US curve completeness: 11 tenors on a recent trading day
        cur.execute("""select obs_date, count(*) from curveiq.curve_points
                       where country='US' group by obs_date
                       order by obs_date desc limit 1""")
        d, n = cur.fetchone()
        check("US curve has 11 tenors (latest day)", n == 11, f"{d}: {n} tenors")

        # ---- 7. Staleness (WARN only) ----
        print("\n[7] Freshness (warn-only)")
        cur.execute("""select series_id, max(obs_date) from curveiq.rates_timeseries
                       where category in ('curve','spread','equity') and country='US'
                       group by series_id""")
        for sid, mx in cur.fetchall():
            age = (today - mx).days
            warn(f"US daily fresh {sid}", age <= 10, f"last={mx} ({age}d old)")
        cur.execute("select series_id, max(obs_date) from curveiq.rates_timeseries "
                    "where country='IN' group by series_id")
        for sid, mx in cur.fetchall():
            age = (today - mx).days
            warn(f"IN fresh {sid}", age <= 75, f"last={mx} ({age}d old)")

    # ---- summary ----
    print("\n" + "=" * 60)
    print(f"VALIDATION: {len(FAILS)} failures, {len(WARNS)} warnings")
    if FAILS:
        print("FAILURES:")
        for f in FAILS:
            print("  -", f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
