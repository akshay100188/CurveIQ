"""
Phase 0 — Step 4: Compute all derived columns and produce final CSVs.

Inputs:
  data/processed/yield_curve_raw.csv
  data/processed/credit_stress_raw.csv

Outputs:
  data/processed/yield_curve_daily.csv   — adds spread_2y10y, spread_3m10y, curve_shape
  data/processed/credit_stress_daily.csv — adds stress_score, stress_regime
  data/processed/stress_percentiles.json — sorted value arrays for each stress component
                                           (used by skills/stress_scorer.py at runtime)

Curve classifier rules (self-contained, no skills/ dependency):
  inverted → spread_2y10y < 0
  flat     → |spread_2y10y| <= 0.15
  humped   → t3y or t5y is the maximum across all available tenors
  normal   → everything else (spread_2y10y > 0.15)

Stress scorer (self-contained, no skills/ dependency):
  Components and weights:
    hy_oas        30%  (higher percentile = more stress)
    ted_spread    20%  (higher percentile = more stress)
    vix           20%  (higher percentile = more stress)
    ig_oas        15%  (higher percentile = more stress)
    spread_2y10y  15%  (INVERTED: lower value = more stress → stress pct = 100 - percentile)

  Normalisation: percentile rank within the full non-null history of each series.
  Weights are renormalised when a component is NULL (e.g. pre-2016 obfr not in scorer).
  Regime: 0-25=calm, 25-50=watch, 50-75=stress, 75-100=crisis.
"""

import os
import sys
import json
import bisect

import pandas as pd
import numpy as np
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

PROC_DIR = os.path.join(ROOT, "data", "processed")

TENOR_ORDER = ["t1m", "t3m", "t6m", "t1y", "t2y", "t3y", "t5y", "t7y", "t10y", "t20y", "t30y"]

STRESS_WEIGHTS = {
    "hy_oas":       0.30,
    "ted_spread":   0.20,
    "vix":          0.20,
    "ig_oas":       0.15,
    "spread_2y10y": 0.15,
}


# ---------------------------------------------------------------------------
# Curve classifier
# ---------------------------------------------------------------------------

def classify_curve_shape(row: pd.Series) -> str | None:
    t2y = row.get("t2y")
    t10y = row.get("t10y")

    if pd.isna(t2y) or pd.isna(t10y):
        return None

    spread = float(t10y) - float(t2y)

    if spread < 0:
        return "inverted"
    if abs(spread) <= 0.15:
        return "flat"

    # Check humped: t3y or t5y is the max across all available tenors
    tenor_vals = {t: row.get(t) for t in TENOR_ORDER}
    valid_vals = {t: float(v) for t, v in tenor_vals.items() if not pd.isna(v)}
    if valid_vals:
        max_tenor = max(valid_vals, key=valid_vals.get)
        if max_tenor in ("t3y", "t5y"):
            return "humped"

    return "normal"


def compute_yield_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Spreads — NULL if either component is NULL
    mask_2y10y = df["t2y"].notna() & df["t10y"].notna()
    df["spread_2y10y"] = np.where(
        mask_2y10y,
        df["t10y"] - df["t2y"],
        np.nan
    )

    mask_3m10y = df["t3m"].notna() & df["t10y"].notna()
    df["spread_3m10y"] = np.where(
        mask_3m10y,
        df["t10y"] - df["t3m"],
        np.nan
    )

    # Round spreads to 4 decimal places
    df["spread_2y10y"] = df["spread_2y10y"].round(4)
    df["spread_3m10y"] = df["spread_3m10y"].round(4)

    # Curve shape
    df["curve_shape"] = df.apply(classify_curve_shape, axis=1)

    return df


# ---------------------------------------------------------------------------
# Stress scorer
# ---------------------------------------------------------------------------

def build_percentile_lookup(credit_df: pd.DataFrame, yield_df: pd.DataFrame) -> dict:
    """
    Build sorted value arrays for each stress component.
    Excludes NULL values. spread_2y10y is sourced from yield_df.
    Returns: {component: sorted_list_of_floats}
    """
    lookup = {}
    components = list(STRESS_WEIGHTS.keys())

    for comp in components:
        if comp == "spread_2y10y":
            series = yield_df["spread_2y10y"].dropna()
        else:
            if comp not in credit_df.columns:
                continue
            series = credit_df[comp].dropna()

        sorted_vals = sorted(series.tolist())
        lookup[comp] = sorted_vals
        print(f"  Percentile lookup [{comp}]: {len(sorted_vals):,} non-null values, "
              f"range [{sorted_vals[0]:.2f}, {sorted_vals[-1]:.2f}]")

    return lookup


def percentile_rank(value: float, sorted_vals: list) -> float:
    """Percentile rank of value in a sorted list (0-100)."""
    if not sorted_vals:
        return 50.0
    pos = bisect.bisect_left(sorted_vals, value)
    return round(pos / len(sorted_vals) * 100, 2)


def compute_stress_score(row: pd.Series,
                         percentiles: dict,
                         spread_2y10y: float) -> tuple:
    """
    Returns (stress_score, stress_regime, component_scores_dict).
    Weights are renormalised if any component is NULL.
    """
    component_scores = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for comp, weight in STRESS_WEIGHTS.items():
        if comp == "spread_2y10y":
            value = spread_2y10y
        else:
            value = row.get(comp)

        if pd.isna(value) or comp not in percentiles:
            continue

        sorted_vals = percentiles[comp]
        pct = percentile_rank(float(value), sorted_vals)

        # Invert spread_2y10y: lower (more negative) = more stress
        if comp == "spread_2y10y":
            pct = 100.0 - pct

        component_scores[comp] = round(pct, 2)
        weighted_sum += pct * weight
        total_weight += weight

    if total_weight == 0:
        return None, None, {}

    # Renormalise so weights always sum to 100%
    score = round(weighted_sum / total_weight, 2)

    if score < 25:
        regime = "calm"
    elif score < 50:
        regime = "watch"
    elif score < 75:
        regime = "stress"
    else:
        regime = "crisis"

    return score, regime, component_scores


def compute_credit_derived(credit_df: pd.DataFrame,
                           yield_df: pd.DataFrame,
                           percentiles: dict) -> pd.DataFrame:
    df = credit_df.copy()

    # Align spread_2y10y from yield curve onto credit index
    spread_series = yield_df["spread_2y10y"].reindex(df.index)

    scores = []
    regimes = []
    for idx in df.index:
        row = df.loc[idx]
        spread_val = spread_series.get(idx, float("nan"))
        score, regime, _ = compute_stress_score(row, percentiles, spread_val)
        scores.append(score)
        regimes.append(regime)

    df["stress_score"] = scores
    df["stress_regime"] = regimes

    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(PROC_DIR, exist_ok=True)

    print("\nCurveIQ Phase 0 — Step 4: Compute Derived Columns")

    # --- Load cleaned CSVs ---
    yield_raw_path = os.path.join(PROC_DIR, "yield_curve_raw.csv")
    credit_raw_path = os.path.join(PROC_DIR, "credit_stress_raw.csv")

    for path in [yield_raw_path, credit_raw_path]:
        if not os.path.exists(path):
            print(f"ERROR: {path} not found. Run phase0/03_clean_merge.py first.")
            sys.exit(1)

    print("\n  Loading processed CSVs...")
    yield_df = pd.read_csv(yield_raw_path, parse_dates=["date"], index_col="date")
    credit_df = pd.read_csv(credit_raw_path, parse_dates=["date"], index_col="date")
    print(f"  yield_curve_raw:   {len(yield_df):,} rows")
    print(f"  credit_stress_raw: {len(credit_df):,} rows")

    # --- Yield curve derived columns ---
    print("\n  [A] Computing yield curve spreads and curve shape...")
    yield_final = compute_yield_derived(yield_df)

    shape_counts = yield_final["curve_shape"].value_counts(dropna=False)
    print(f"\n  Curve shape distribution:")
    for shape, count in shape_counts.items():
        pct = count / len(yield_final) * 100
        print(f"    {str(shape):<12} {count:>6,}  ({pct:.1f}%)")

    spread_null = yield_final["spread_2y10y"].isna().sum()
    print(f"\n  spread_2y10y NULLs: {spread_null:,} ({spread_null/len(yield_final)*100:.1f}%)")

    yield_out = os.path.join(PROC_DIR, "yield_curve_daily.csv")
    yield_final.index.name = "date"
    yield_final.to_csv(yield_out)
    print(f"\n  [OK] Written: {yield_out}")

    # --- Stress percentile lookup ---
    print("\n  [B] Building stress percentile lookup table...")
    percentiles = build_percentile_lookup(credit_df, yield_final)

    percentiles_path = os.path.join(PROC_DIR, "stress_percentiles.json")
    with open(percentiles_path, "w") as f:
        json.dump(percentiles, f, indent=2)
    print(f"\n  [OK] Written: {percentiles_path}")

    # --- Credit stress derived columns ---
    print("\n  [C] Computing stress scores for all rows...")
    credit_final = compute_credit_derived(credit_df, yield_final, percentiles)

    null_scores = credit_final["stress_score"].isna().sum()
    regime_counts = credit_final["stress_regime"].value_counts(dropna=False)

    print(f"\n  Stress score NULLs: {null_scores:,} (gate: should be 0)")
    print(f"\n  Stress regime distribution:")
    for regime, count in regime_counts.items():
        pct = count / len(credit_final) * 100
        print(f"    {str(regime):<10} {count:>6,}  ({pct:.1f}%)")

    credit_out = os.path.join(PROC_DIR, "credit_stress_daily.csv")
    credit_final.index.name = "date"
    credit_final.to_csv(credit_out)
    print(f"\n  [OK] Written: {credit_out}")

    # --- Spot checks ---
    print("\n  [D] Spot checks on known dates:")
    spot_checks = [
        ("2008-10-10", "credit", "stress_regime", "crisis",    "GFC peak stress"),
        ("2019-08-27", "yield",  "curve_shape",   "inverted",  "2019 brief inversion"),
        ("2020-03-18", "credit", "stress_regime", "stress",    "COVID spike"),
        ("2023-03-01", "yield",  "spread_2y10y",  "< -0.5",    "2023 deep inversion"),
        ("2007-06-01", "credit", "stress_regime", "calm",      "pre-GFC calm"),
    ]

    all_spot_ok = True
    for date_str, table, col, expected, note in spot_checks:
        try:
            dt = pd.Timestamp(date_str)
            if table == "credit":
                df_check = credit_final
            else:
                df_check = yield_final

            # Find nearest available date
            available = df_check.index[df_check.index <= dt]
            if available.empty:
                print(f"  [SKIP] {date_str} ({note}): no data before this date")
                continue
            nearest = available[-1]
            actual = df_check.loc[nearest, col]

            if expected.startswith("<"):
                threshold = float(expected.split("<")[1].strip())
                ok = (not pd.isna(actual)) and float(actual) < threshold
            else:
                ok = str(actual) == expected

            status = "OK" if ok else "WARN"
            if not ok:
                all_spot_ok = False
            print(f"  [{status}] {date_str} {col}: expected={expected} "
                  f"actual={actual}  ({note})")
        except Exception as e:
            print(f"  [WARN] {date_str} check failed: {e}")

    # Final gate
    print("\n" + "=" * 60)
    if null_scores > 0:
        print(f"[WARN] {null_scores} rows have NULL stress_score — investigate")
    elif not all_spot_ok:
        print("[WARN] Some spot checks failed — review data before proceeding")
    else:
        print("[OK] All derived columns computed successfully")
    print("     Proceed to: python phase0/05_validate.py")


if __name__ == "__main__":
    main()
