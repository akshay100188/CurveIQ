"""Phase 2 — crisis curve-behaviour key dates.

Creates curveiq.crisis_keydates and seeds the US episodes (2008 GFC, 2013 taper,
2020 COVID) with pre_stress / peak / recovery snapshot dates, each snapped to the
nearest trading day that has a complete 11-tenor curve in curve_points. The
frontend overlays the curve at these dates to show the reshape directly.

India has no free curve, so it has no key dates — its crisis panel uses the
regime windows to slice the 10Y level + 10Y-short spread instead.

Run: python -m pipeline.phase2_crisis
"""
from __future__ import annotations

import sys
from datetime import date

from psycopg2.extras import execute_values

from . import db

DDL = """
create table if not exists curveiq.crisis_keydates (
    id            bigserial primary key,
    country       text not null check (country in ('US','IN')),
    crisis_name   text not null,
    crisis_label  text not null,                 -- display name of the episode
    label         text not null,                 -- pre_stress | peak | recovery
    target_date   date not null,                 -- intended date
    snapshot_date date not null,                 -- nearest full-curve trading day
    unique (country, crisis_name, label)
);
grant usage on schema curveiq to anon, authenticated, service_role;
grant select on curveiq.crisis_keydates to anon, authenticated;
grant all on curveiq.crisis_keydates to service_role;

-- US crisis curves: each key date joined to its full curve (for overlay charts).
create or replace view curveiq.v_crisis_curves as
select k.crisis_name, k.crisis_label, k.label, k.snapshot_date,
       c.tenor_months, c.tenor_label, c.yield
from curveiq.crisis_keydates k
join curveiq.curve_points c
  on c.country = k.country and c.obs_date = k.snapshot_date
where k.country = 'US';
grant select on curveiq.v_crisis_curves to anon, authenticated, service_role;
"""

# (crisis_name, display label, [(label, target_date), ...])
US_EPISODES = [
    # GFC is the cleanest bull-steepening case and is US-only (Indian G-Sec data
    # starts ~2011-12). Anchors per spec §6: flat/inverted -> post-Lehman -> steep.
    ("gfc_2008", "Global Financial Crisis (2008)", [
        ("pre_stress", "2007-06-15"), ("peak", "2008-10-15"), ("recovery", "2009-06-15")]),
    ("taper_2013", "Taper Tantrum (2013)", [
        ("pre_stress", "2013-04-30"), ("peak", "2013-09-05"), ("recovery", "2013-12-31")]),
    ("covid_2020", "COVID shock (2020)", [
        ("pre_stress", "2020-01-02"), ("peak", "2020-03-09"), ("recovery", "2020-08-31")]),
]
N_TENORS = 11


def _snap_to_full_curve(cur, target: str) -> date:
    """Nearest US trading day to `target` that has all 11 tenors."""
    cur.execute("""
        select obs_date from curveiq.curve_points
        where country='US'
        group by obs_date having count(*) = %s
        order by abs(obs_date - %s::date) asc
        limit 1""", (N_TENORS, target))
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"no full curve near {target}")
    return row[0]


def run() -> None:
    with db.cursor() as cur:
        cur.execute(DDL)
        cur.execute("truncate curveiq.crisis_keydates restart identity")
        rows = []
        for crisis_name, label, keydates in US_EPISODES:
            for kd_label, target in keydates:
                snap = _snap_to_full_curve(cur, target)
                rows.append(("US", crisis_name, label, kd_label, target, snap))
        execute_values(cur,
            "insert into curveiq.crisis_keydates "
            "(country,crisis_name,crisis_label,label,target_date,snapshot_date) values %s",
            rows, page_size=100)
        cur.execute("notify pgrst, 'reload schema'")
    print(f"crisis_keydates: seeded {len(rows)} US key dates")
    for r in rows:
        print(f"  {r[1]:12} {r[3]:10} target={r[4]} -> snapshot={r[5]}")


def validate() -> int:
    """Spec §6 gate: each US crisis has >=3 key dates returning non-empty curves;
    each India crisis window returns non-empty 10Y + spread slices."""
    fails = []
    with db.cursor() as cur:
        # Explicit guard: the US-only GFC 2008 episode must be present and complete
        # — it must never silently fall through behind the India-capable pair (spec §6).
        cur.execute("""select count(distinct k.label)
                       from curveiq.crisis_keydates k
                       join curveiq.curve_points c
                         on c.country='US' and c.obs_date=k.snapshot_date
                       where k.crisis_name='gfc_2008'""")
        gfc_ok = cur.fetchone()[0] >= 3
        print(f"  [{'PASS' if gfc_ok else 'FAIL'}] US GFC 2008 explicitly present (US-only crisis)")
        if not gfc_ok:
            fails.append("gfc_2008 missing")
        for crisis_name, label, _ in US_EPISODES:
            cur.execute("""select k.label, count(c.*)
                           from curveiq.crisis_keydates k
                           left join curveiq.curve_points c
                             on c.country='US' and c.obs_date=k.snapshot_date
                           where k.crisis_name=%s
                           group by k.label""", (crisis_name,))
            byd = cur.fetchall()
            ok = len(byd) >= 3 and all(n == N_TENORS for _, n in byd)
            print(f"  [{'PASS' if ok else 'FAIL'}] US {crisis_name}: "
                  f"{len(byd)} key dates, curves={[n for _, n in byd]}")
            if not ok:
                fails.append(crisis_name)
        # India windows: non-empty 10Y + spread within taper_tantrum / covid
        for win in ("taper_tantrum", "covid"):
            cur.execute("""select start_date, end_date from curveiq.regimes
                           where country='IN' and regime_name=%s""", (win,))
            r = cur.fetchone()
            if not r:
                fails.append(f"IN window {win} missing"); continue
            s, e = r
            cur.execute("""select count(*) from curveiq.rates_timeseries
                           where series_id='IN_10Y_GSEC' and obs_date between %s and %s""", (s, e))
            n10 = cur.fetchone()[0]
            cur.execute("""select count(*) from curveiq.computed_metrics
                           where country='IN' and metric_name='spread_10y_short'
                             and obs_date between %s and %s""", (s, e))
            nsp = cur.fetchone()[0]
            ok = n10 > 0 and nsp > 0
            print(f"  [{'PASS' if ok else 'FAIL'}] IN {win}: 10Y rows={n10}, spread rows={nsp}")
            if not ok:
                fails.append(f"IN {win}")

        # --- US rates & spread timeline gate (spec §6) ---
        # All four named bands present; 10Y/2Y/spread non-empty since 2006; and the
        # open-ended 2026 war band actually has data (catches stale 2026 data).
        cur.execute("""select regime_name, end_date from curveiq.regimes
                       where country='US' and regime_name in
                       ('gfc_2008','taper_tantrum','covid','westasia_war_2026')""")
        band = dict(cur.fetchall())
        for b in ("gfc_2008", "taper_tantrum", "covid", "westasia_war_2026"):
            present = b in band
            print(f"  [{'PASS' if present else 'FAIL'}] US timeline band {b} present")
            if not present:
                fails.append(f"timeline band {b}")
        war_open = "westasia_war_2026" in band and band["westasia_war_2026"] is None
        print(f"  [{'PASS' if war_open else 'FAIL'}] 2026 war band is open-ended (end_date NULL)")
        if not war_open:
            fails.append("war band not open-ended")
        for sid in ("US_DGS10", "US_DGS2", "US_T10Y2Y"):
            cur.execute("""select count(*), max(obs_date) from curveiq.rates_timeseries
                           where series_id=%s and obs_date >= '2006-01-01'""", (sid,))
            n, mx = cur.fetchone()
            ok = n > 0
            print(f"  [{'PASS' if ok else 'FAIL'}] timeline series {sid}: {n} rows since 2006 (latest {mx})")
            if not ok:
                fails.append(f"timeline {sid}")
        # war band must extend into available data, not sit beyond the latest date
        cur.execute("select max(obs_date) from curveiq.rates_timeseries where series_id='US_DGS10'")
        latest = cur.fetchone()[0]
        war_has_data = latest is not None and str(latest) >= "2026-02-28"
        print(f"  [{'PASS' if war_has_data else 'FAIL'}] 2026 war band covered by data "
              f"(latest DGS10 {latest} >= war start 2026-02-28)")
        if not war_has_data:
            fails.append("war band has no data (stale 2026 data)")

    print(f"\nCRISIS VALIDATION: {len(fails)} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    run()
    print("\n=== crisis validation ===")
    sys.exit(validate())
