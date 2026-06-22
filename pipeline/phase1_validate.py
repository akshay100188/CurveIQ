"""Phase 1 — validation gates for L1 computed metrics (spec §6).

Gates: spread math, curve-shape classification (2019 inverted), real-yield
sanity, equity-yield regime split fires, and the PCA level-factor variance gate.

Run: python -m pipeline.phase1_validate
"""
from __future__ import annotations

import sys

from . import db

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  [PASS] {name}")
    else:
        FAILS.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} -- {detail}")


def run() -> int:
    with db.cursor() as cur:

        print("\n[1] Spread math")
        # computed spread_10y_2y must equal DGS10-DGS2 to the penny
        cur.execute("""select max(abs(m.value - (d10.value - d2.value)))
                       from curveiq.computed_metrics m
                       join curveiq.rates_timeseries d10
                         on d10.series_id='US_DGS10' and d10.obs_date=m.obs_date
                       join curveiq.rates_timeseries d2
                         on d2.series_id='US_DGS2' and d2.obs_date=m.obs_date
                       where m.metric_name='spread_10y_2y'""")
        mx = cur.fetchone()[0]
        check("spread_10y_2y == DGS10-DGS2", mx is not None and float(mx) < 1e-9, f"max diff {mx}")
        # and agrees with FRED's own T10Y2Y within rounding
        cur.execute("""select max(abs(m.value - f.value))
                       from curveiq.computed_metrics m
                       join curveiq.rates_timeseries f
                         on f.series_id='US_T10Y2Y' and f.obs_date=m.obs_date
                       where m.metric_name='spread_10y_2y'""")
        mx = cur.fetchone()[0]
        check("spread_10y_2y ~= FRED T10Y2Y", mx is not None and float(mx) <= 0.03, f"max diff {mx}")

        print("\n[2] Curve-shape classification")
        cur.execute("""select count(*) from curveiq.computed_metrics
                       where metric_name='curve_shape' and label='inverted'
                         and obs_date between '2019-01-01' and '2019-12-31'""")
        check("2019 has inverted days", cur.fetchone()[0] > 0)
        cur.execute("""select distinct label from curveiq.computed_metrics
                       where metric_name='curve_shape'""")
        labels = {r[0] for r in cur.fetchall()}
        check("labels within {inverted,flat,normal,humped}",
              labels <= {"inverted", "flat", "normal", "humped"}, str(labels))
        # 2020-2021 ZLB era should show 'normal'/'flat' steep curve, not inverted everywhere
        cur.execute("""select count(*) from curveiq.computed_metrics
                       where metric_name='curve_shape' and label='normal'""")
        check("normal regime present in history", cur.fetchone()[0] > 1000)

        print("\n[3] Real-yield sanity")
        # 10Y real (nominal - breakeven) should track TIPS real yield (DFII10) closely
        cur.execute("""select avg(abs(m.value - r.value))
                       from curveiq.computed_metrics m
                       join curveiq.rates_timeseries r
                         on r.series_id='US_DFII10' and r.obs_date=m.obs_date
                       where m.metric_name='real_yield_10y'""")
        avg = cur.fetchone()[0]
        check("real_yield_10y ~= DFII10 (TIPS)", avg is not None and float(avg) <= 0.15, f"avg diff {avg}")

        print("\n[4] Equity-yield correlation regime split")
        for cty, tag in (("US", "recession"), ("IN", "crisis")):
            cur.execute("""select metric_name, value from curveiq.computed_metrics
                           where country=%s and metric_name in
                           (%s,%s)""", (cty, f"eq_yield_corr_in_{tag}", f"eq_yield_corr_out_{tag}"))
            d = dict(cur.fetchall())
            both = f"eq_yield_corr_in_{tag}" in d and f"eq_yield_corr_out_{tag}" in d
            check(f"{cty} regime split computed", both, str(d))
            if both:
                diff = abs(float(d[f"eq_yield_corr_in_{tag}"]) - float(d[f"eq_yield_corr_out_{tag}"]))
                check(f"{cty} in/out correlation materially differ", diff >= 0.10,
                      f"in={d[f'eq_yield_corr_in_{tag}']:.3f} out={d[f'eq_yield_corr_out_{tag}']:.3f}")
        # rolling series exists
        cur.execute("""select count(*) from curveiq.computed_metrics
                       where metric_name='eq_yield_corr_24m'""")
        check("rolling 24m correlation series present", cur.fetchone()[0] > 100)

        print("\n[5] PCA level-factor gate")
        cur.execute("""select metric_name, value from curveiq.computed_metrics
                       where metric_name in ('pca_var_level','pca_var_slope','pca_var_curvature')""")
        p = dict(cur.fetchall())
        lvl = float(p.get("pca_var_level", 0)); slp = float(p.get("pca_var_slope", 0))
        crv = float(p.get("pca_var_curvature", 0))
        check("level factor explains ~80-90%", 0.80 <= lvl <= 0.92, f"level={lvl:.3f}")
        check("level > slope > curvature", lvl > slp > crv, f"{lvl:.3f},{slp:.3f},{crv:.3f}")
        check("top-3 factors explain >95%", lvl + slp + crv > 0.95, f"sum={lvl+slp+crv:.3f}")

        print("\n[6] India metrics present")
        cur.execute("""select count(*) from curveiq.computed_metrics
                       where country='IN' and metric_name='spread_10y_short'""")
        check("India spread_10y_short present", cur.fetchone()[0] > 100)

    print("\n" + "=" * 60)
    print(f"PHASE 1 VALIDATION: {len(FAILS)} failures")
    for f in FAILS:
        print("  -", f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
