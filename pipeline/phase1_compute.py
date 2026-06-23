"""Phase 1 — L1 deterministic computation.

Reads the canonical curveiq store, computes every metric exactly (LLM-free), and
writes long-format results to curveiq.computed_metrics. All knobs are module
constants so they can be defended/tuned.

Metrics produced:
  US (daily):   spread_10y_2y, spread_10y_3m, curve_shape (+label), real_yield_10y
  US (monthly): eq_yield_corr_24m / _12m, eq_yield_corr_(in|out)_recession
  US (PCA):     pca_var_level/slope/curvature (explained variance, daily scores)
  IN (monthly): spread_10y_short, eq_yield_corr_24m / _12m,
                eq_yield_corr_(in|out)_crisis

Run: python -m pipeline.phase1_compute
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import db

# --- tunable knobs (spec §6) ------------------------------------------------
THETA = 0.10        # +/- band (pp, =10bps) for 'flat'; |slope|<=THETA -> flat
THETA_C = 0.10      # butterfly curvature (pp) above which a curve is 'humped'
CORR_WINDOWS = [24, 12]   # rolling correlation windows (months)

# PCA is run on the *coupon* curve (1Y–30Y), excluding the money-market T-bill
# tenors (1M/3M/6M). Those are policy-pinned short rates, not part of the bond
# curve; including them splits off a spurious front-end factor and drags the
# level share to ~68%. On the coupon curve the level factor explains ~87%
# (Litterman–Scheinkman), as expected.
PCA_TENORS = [12, 24, 36, 60, 84, 120, 240, 360]


# ---------------------------------------------------------------------------
def _load_series() -> pd.DataFrame:
    """All rates_timeseries as a (obs_date x series_id) wide frame."""
    with db.cursor() as cur:
        cur.execute("select obs_date, series_id, value from curveiq.rates_timeseries")
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["obs_date", "series_id", "value"])
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    df["value"] = df["value"].astype(float)
    return df.pivot_table(index="obs_date", columns="series_id", values="value").sort_index()


def _load_regimes() -> dict[str, list[tuple]]:
    with db.cursor() as cur:
        cur.execute("select country, start_date, end_date from curveiq.regimes")
        out: dict[str, list[tuple]] = {"US": [], "IN": []}
        for cty, s, e in cur.fetchall():
            out[cty].append((pd.Timestamp(s), pd.Timestamp(e) if e else pd.Timestamp.max))
    return out


def _in_regime(idx: pd.DatetimeIndex, windows: list[tuple]) -> pd.Series:
    mask = pd.Series(False, index=idx)
    for s, e in windows:
        mask |= (idx >= s) & (idx <= e)
    return mask


# ---------------------------------------------------------------------------
def classify_curve(s10_2: float, s10_3m: float, butterfly: float) -> str:
    """Rule-based US curve shape. Priority: inverted, flat, humped, else normal.

    `inverted` fires when EITHER the 10Y-2Y or the 10Y-3M anchor falls below -THETA.
    The 10Y-3M is the Fed's preferred recession signal and inverts earlier/deeper;
    in 2019 the 10Y-2Y only grazed -4bps (inside the flat band) while the 10Y-3M
    inverted ~50bps, so a 2Y-only rule would miss a textbook inversion.
    """
    if min(s10_2, s10_3m) < -THETA:
        return "inverted"
    if abs(s10_2) <= THETA:
        return "flat"
    if butterfly > THETA_C:
        return "humped"
    return "normal"


def compute_us(df: pd.DataFrame, regimes) -> list[tuple]:
    out: list[tuple] = []
    g = df.dropna(subset=["US_DGS10", "US_DGS2", "US_DGS3MO"], how="any")

    # daily spreads (computed from the curve, self-consistent)
    s10_2 = (df["US_DGS10"] - df["US_DGS2"]).dropna()
    s10_3m = (df["US_DGS10"] - df["US_DGS3MO"]).dropna()
    for d, v in s10_2.items():
        out.append(("US", "spread_10y_2y", d.date(), float(v), None, None))
    for d, v in s10_3m.items():
        out.append(("US", "spread_10y_3m", d.date(), float(v), None, None))

    # daily curve-shape classification (needs 2/3M/5/10)
    cls = df.dropna(subset=["US_DGS2", "US_DGS3MO", "US_DGS5", "US_DGS10"])
    butterfly = 2 * cls["US_DGS5"] - cls["US_DGS2"] - cls["US_DGS10"]
    slope = cls["US_DGS10"] - cls["US_DGS2"]
    slope_3m = cls["US_DGS10"] - cls["US_DGS3MO"]
    for d in cls.index:
        label = classify_curve(float(slope[d]), float(slope_3m[d]), float(butterfly[d]))
        out.append(("US", "curve_shape", d.date(), float(slope[d]), label, None))

    # daily 10Y real yield = nominal 10Y - 10Y breakeven inflation
    real = (df["US_DGS10"] - df["US_T10YIE"]).dropna()
    for d, v in real.items():
        out.append(("US", "real_yield_10y", d.date(), float(v), None, None))

    # equity-yield correlation (monthly) + recession regime split
    out += _equity_yield_corr(df, "US", "US_DGS10", "US_SP500",
                              regimes["US"], "recession")
    return out


def compute_in(df: pd.DataFrame, regimes) -> list[tuple]:
    out: list[tuple] = []
    # India slope = 10Y G-Sec - call money (short). Monthly.
    spread = (df["IN_10Y_GSEC"] - df["IN_CALL_MONEY"]).dropna()
    for d, v in spread.items():
        out.append(("IN", "spread_10y_short", d.date(), float(v), None, None))
    out += _equity_yield_corr(df, "IN", "IN_10Y_GSEC", "IN_NIFTY50",
                              regimes["IN"], "crisis")
    return out


def _equity_yield_corr(df, country, yield_id, equity_id, windows, regime_tag) -> list[tuple]:
    """Rolling Pearson of monthly Δyield vs monthly Δlog(equity) + regime split."""
    out: list[tuple] = []
    m = df[[yield_id, equity_id]].dropna(how="all")
    # resample to month-end last observation, then monthly changes
    me = m.resample("ME").last().dropna()
    d_yield = me[yield_id].diff()
    d_logeq = np.log(me[equity_id]).diff()
    pair = pd.DataFrame({"dy": d_yield, "de": d_logeq}).dropna()
    if len(pair) < 13:
        return out

    for w in CORR_WINDOWS:
        roll = pair["dy"].rolling(w).corr(pair["de"]).dropna()
        for d, v in roll.items():
            if np.isfinite(v):
                out.append((country, f"eq_yield_corr_{w}m", d.date(), float(v), None, None))

    # regime-conditional correlation (single value, dated at the latest obs)
    inmask = _in_regime(pair.index, windows)
    last = pair.index[-1].date()
    for label, sub in (("in", pair[inmask]), ("out", pair[~inmask])):
        if len(sub) >= 3:
            c = sub["dy"].corr(sub["de"])
            if np.isfinite(c):
                out.append((country, f"eq_yield_corr_{label}_{regime_tag}",
                            last, float(c), f"n={len(sub)}", regime_tag))
    return out


# ---------------------------------------------------------------------------
def compute_pca(country: str = "US") -> tuple[list[tuple], dict]:
    """Litterman–Scheinkman PCA on daily curve *changes*. Returns metric rows +
    explained-variance summary. Level factor should explain ~80–90%."""
    with db.cursor() as cur:
        cur.execute("""select obs_date, tenor_months, yield from curveiq.curve_points
                       where country=%s order by obs_date, tenor_months""", (country,))
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["obs_date", "tenor", "yield"])
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    wide = df.pivot(index="obs_date", columns="tenor", values="yield").astype(float)
    wide = wide[PCA_TENORS]                             # coupon curve only
    wide = wide.dropna(how="any")                      # full-curve days only
    changes = wide.diff().dropna()

    X = changes.values
    X = X - X.mean(axis=0)
    cov = np.cov(X, rowvar=False)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    evals, evecs = evals[order], evecs[:, order]
    ratio = evals / evals.sum()
    scores = X @ evecs[:, :3]                           # level, slope, curvature

    names = ["level", "slope", "curvature"]
    out: list[tuple] = []
    last = changes.index[-1].date()
    for i, nm in enumerate(names):
        out.append((country, f"pca_var_{nm}", last, float(ratio[i]), None, None))
    for j, nm in enumerate(names):
        for d, val in zip(changes.index, scores[:, j]):
            out.append((country, f"pca_score_{nm}", d.date(), float(val), None, None))
    summary = {"explained": {nm: float(ratio[i]) for i, nm in enumerate(names)},
               "n_days": len(changes), "n_tenors": wide.shape[1]}
    return out, summary


# ---------------------------------------------------------------------------
def write_metrics(rows: list[tuple]) -> None:
    from psycopg2.extras import execute_values
    with db.cursor() as cur:
        execute_values(cur,
            "insert into curveiq.computed_metrics "
            "(country,metric_name,obs_date,value,label,regime) values %s "
            "on conflict (country,metric_name,obs_date) do update set "
            "value=excluded.value, label=excluded.label, regime=excluded.regime",
            rows, page_size=2000)


def run() -> dict:
    df = _load_series()
    regimes = _load_regimes()
    with db.cursor() as cur:
        cur.execute("truncate curveiq.computed_metrics restart identity")
    rows = compute_us(df, regimes) + compute_in(df, regimes)
    pca_rows, pca_summary = compute_pca("US")
    rows += pca_rows
    write_metrics(rows)
    print(f"computed_metrics: wrote {len(rows)} rows")
    print(f"PCA(US) explained variance: {pca_summary['explained']} "
          f"(n={pca_summary['n_days']} days, {pca_summary['n_tenors']} tenors)")
    return pca_summary


if __name__ == "__main__":
    run()
