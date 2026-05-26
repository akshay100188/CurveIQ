"""
Phase 0 — Step 3: Merge raw FRED CSVs, clean, and gap-fill.

Inputs:  data/raw/<SERIES_ID>.csv  (17 files from step 01)
Outputs:
  data/processed/yield_curve_raw.csv   — 11 tenor columns, business-day aligned
  data/processed/credit_stress_raw.csv — 6 indicator columns, business-day aligned

Processing:
  - Reindex to US business day calendar from 2000-01-03 to today
  - Forward-fill gaps up to 3 consecutive business days (market practice)
  - TEDRATE proxy for dates > 2023-04-28: ted_spread = OBFR - (DGS3MO / 100)
    (LIBOR discontinued; OBFR is the closest available interbank rate proxy)
  - Columns with known limited start dates (SOFR, OBFR) remain NULL before their
    first available observation — this is expected and handled downstream
"""

import os
import sys
import pandas as pd
import numpy as np
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

RAW_DIR = os.path.join(ROOT, "data", "raw")
PROC_DIR = os.path.join(ROOT, "data", "processed")

# TEDRATE was last published 2023-04-28 (LIBOR discontinuation)
TEDRATE_END = pd.Timestamp("2023-04-28")

# Column mappings for each output table
YIELD_CURVE_COLS = {
    "DGS1MO": "t1m",
    "DGS3MO": "t3m",
    "DGS6MO": "t6m",
    "DGS1":   "t1y",
    "DGS2":   "t2y",
    "DGS3":   "t3y",
    "DGS5":   "t5y",
    "DGS7":   "t7y",
    "DGS10":  "t10y",
    "DGS20":  "t20y",
    "DGS30":  "t30y",
}

CREDIT_COLS = {
    "BAMLH0A0HYM2": "hy_oas",
    "BAMLC0A0CM":   "ig_oas",
    "TEDRATE":      "ted_spread",
    "VIXCLS":       "vix",
    "SOFR":         "sofr",
    "OBFR":         "obfr",
}

FFILL_LIMIT = 3  # max consecutive business days to forward-fill


def load_raw_series(series_id: str, column_name: str) -> pd.Series:
    """Load a single raw CSV as a Series indexed by date."""
    path = os.path.join(RAW_DIR, f"{series_id}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Missing {path}. Run phase0/01_collect_fred.py first."
        )
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.set_index("date")["value"].rename(column_name)
    df.index = pd.to_datetime(df.index)
    return df


def build_business_day_index() -> pd.DatetimeIndex:
    """US business day calendar from 2000-01-03 to today."""
    today = pd.Timestamp.today().normalize()
    return pd.bdate_range(start="2000-01-03", end=today, freq="B")


def merge_and_fill(series_map: dict, bday_index: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Load all series in series_map, merge onto business day index,
    forward-fill up to FFILL_LIMIT days.
    """
    frames = {}
    for series_id, col_name in series_map.items():
        try:
            s = load_raw_series(series_id, col_name)
            frames[col_name] = s
        except FileNotFoundError as e:
            print(f"  [WARN] {e}")

    df = pd.DataFrame(index=bday_index)
    for col_name, series in frames.items():
        df[col_name] = series.reindex(bday_index)

    # Forward-fill missing values (up to FFILL_LIMIT consecutive days)
    df = df.ffill(limit=FFILL_LIMIT)

    return df


def apply_tedrate_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """
    For rows where date > TEDRATE_END and ted_spread is NULL,
    compute ted_spread = obfr - t3m  (i.e. OBFR minus DGS3MO).

    Both OBFR and DGS3MO are in percent (e.g. 5.31, 5.25).
    Result is in percent points (e.g. 0.06 = 6bps), matching TEDRATE series units.
    Do NOT divide by 100 — both inputs are already in the same percent units.
    """
    if "ted_spread" not in df.columns or "obfr" not in df.columns:
        return df

    # Load DGS3MO from yield curve data for the proxy computation
    try:
        t3m = load_raw_series("DGS3MO", "t3m")
        t3m = t3m.reindex(df.index).ffill(limit=FFILL_LIMIT)
    except FileNotFoundError:
        print("  [WARN] DGS3MO not found — TEDRATE proxy cannot be computed")
        return df

    proxy_mask = (df.index > TEDRATE_END) & df["ted_spread"].isna()
    proxy_vals = df.loc[proxy_mask, "obfr"] - t3m.loc[proxy_mask]
    df.loc[proxy_mask, "ted_spread"] = proxy_vals

    proxy_count = proxy_mask.sum()
    if proxy_count > 0:
        print(f"  [OK] TEDRATE proxy applied to {proxy_count} rows "
              f"(post-{TEDRATE_END.date()}): obfr - DGS3MO")

    return df


def print_coverage(df: pd.DataFrame, label: str):
    """Print NULL coverage stats per column."""
    print(f"\n  {label} — {len(df)} rows, "
          f"{df.index.min().date()} to {df.index.max().date()}")
    print(f"  {'Column':<16} {'Non-null':>9} {'Null':>7} {'Null%':>7}  Note")
    print(f"  {'-'*60}")
    for col in df.columns:
        non_null = df[col].notna().sum()
        null_ct = df[col].isna().sum()
        null_pct = null_ct / len(df) * 100
        note = ""
        if col == "sofr" and null_pct > 50:
            note = "expected (starts 2018)"
        elif col == "obfr" and null_pct > 30:
            note = "expected (starts 2016)"
        elif col == "ted_spread" and null_pct > 0:
            note = "partial (TEDRATE ended 2023, proxy applied post-2023)"
        print(f"  {col:<16} {non_null:>9,} {null_ct:>7,} {null_pct:>6.1f}%  {note}")


def main():
    os.makedirs(PROC_DIR, exist_ok=True)

    print("\nCurveIQ Phase 0 — Step 3: Clean & Merge")

    bday_index = build_business_day_index()
    print(f"\n  Business day calendar: {len(bday_index)} days, "
          f"{bday_index[0].date()} to {bday_index[-1].date()}")

    # --- Yield curve ---
    print("\n  [A] Merging yield curve series...")
    yield_df = merge_and_fill(YIELD_CURVE_COLS, bday_index)
    print_coverage(yield_df, "yield_curve_raw")

    yield_path = os.path.join(PROC_DIR, "yield_curve_raw.csv")
    yield_df.index.name = "date"
    yield_df.to_csv(yield_path)
    print(f"\n  [OK] Written: {yield_path}")

    # --- Credit stress ---
    print("\n  [B] Merging credit stress series...")
    credit_df = merge_and_fill(CREDIT_COLS, bday_index)
    credit_df = apply_tedrate_proxy(credit_df)
    print_coverage(credit_df, "credit_stress_raw")

    credit_path = os.path.join(PROC_DIR, "credit_stress_raw.csv")
    credit_df.index.name = "date"
    credit_df.to_csv(credit_path)
    print(f"\n  [OK] Written: {credit_path}")

    # Summary gate
    yield_core_null = yield_df[["t2y", "t10y"]].isna().any(axis=1).mean() * 100
    credit_core_null = credit_df[["hy_oas", "vix"]].isna().any(axis=1).mean() * 100

    print("\n  Core series null rates:")
    print(f"    t2y/t10y any-null: {yield_core_null:.2f}%  (gate: < 2%)")
    print(f"    hy_oas/vix any-null: {credit_core_null:.2f}%  (gate: < 2%)")

    if yield_core_null > 2.0 or credit_core_null > 2.0:
        print("\n[WARN] Core null rates above threshold — investigate raw data before step 04")
    else:
        print("\n[OK] Core coverage within acceptable range")

    print("     Proceed to: python phase0/04_compute_columns.py")


if __name__ == "__main__":
    main()
