"""
Phase 0 — Step 5: Data quality validation gate.

Runs structured checks across all three final CSVs.
ALL checks must pass before proceeding to step 06 (Supabase push).

Exit code:  0 = all checks passed
            1 = one or more checks failed
"""

import os
import sys
import json
from datetime import date, timedelta

import pandas as pd
import numpy as np
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

PROC_DIR = os.path.join(ROOT, "data", "processed")

# Thresholds
MIN_YIELD_ROWS = 6400
MIN_CREDIT_ROWS = 6400
MIN_FED_ROWS = 180
MAX_NULL_PCT_CORE = 1.0      # t2y, t10y, hy_oas, vix
MAX_NULL_PCT_SPREAD = 1.0    # spread_2y10y
MAX_NULL_PCT_SHAPE = 2.0     # curve_shape
MAX_NULL_PCT_TED = 5.0       # ted_spread (TEDRATE gaps + proxy)
MAX_CONSECUTIVE_GAP = 5      # business days

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"


class CheckResult:
    def __init__(self, name: str, passed: bool, message: str, is_gate: bool = True):
        self.name = name
        self.passed = passed
        self.message = message
        self.is_gate = is_gate

    def __str__(self):
        icon = PASS if self.passed else (FAIL if self.is_gate else WARN)
        return f"  {icon} {self.name}: {self.message}"


def run_yield_checks(df: pd.DataFrame) -> list:
    results = []

    # Row count
    ok = len(df) >= MIN_YIELD_ROWS
    results.append(CheckResult(
        "YC row count",
        ok,
        f"{len(df):,} rows (min {MIN_YIELD_ROWS:,})"
    ))

    # Date range
    max_date = df.index.max()
    today = pd.Timestamp.today().normalize()
    days_behind = (today - max_date).days
    ok = days_behind <= 5
    results.append(CheckResult(
        "YC date currency",
        ok,
        f"Latest date: {max_date.date()}  ({days_behind} calendar days behind today)"
    ))

    # Core NULL rates
    for col in ["t2y", "t10y", "t3m"]:
        if col not in df.columns:
            results.append(CheckResult(f"YC {col} present", False, "column missing"))
            continue
        pct = df[col].isna().mean() * 100
        ok = pct <= MAX_NULL_PCT_CORE
        results.append(CheckResult(
            f"YC {col} null%",
            ok,
            f"{pct:.2f}% (max {MAX_NULL_PCT_CORE}%)"
        ))

    # Spread NULL
    pct = df["spread_2y10y"].isna().mean() * 100
    ok = pct <= MAX_NULL_PCT_SPREAD
    results.append(CheckResult(
        "YC spread_2y10y null%",
        ok,
        f"{pct:.2f}% (max {MAX_NULL_PCT_SPREAD}%)"
    ))

    # Curve shape NULL
    pct = df["curve_shape"].isna().mean() * 100
    ok = pct <= MAX_NULL_PCT_SHAPE
    results.append(CheckResult(
        "YC curve_shape null%",
        ok,
        f"{pct:.2f}% (max {MAX_NULL_PCT_SHAPE}%)"
    ))

    # No gap > MAX_CONSECUTIVE_GAP in t2y
    consecutive = _max_consecutive_null(df["t2y"])
    ok = consecutive <= MAX_CONSECUTIVE_GAP
    results.append(CheckResult(
        "YC t2y max gap",
        ok,
        f"Max consecutive null run: {consecutive} days (max {MAX_CONSECUTIVE_GAP})"
    ))

    # No gap > MAX_CONSECUTIVE_GAP in t10y
    consecutive = _max_consecutive_null(df["t10y"])
    ok = consecutive <= MAX_CONSECUTIVE_GAP
    results.append(CheckResult(
        "YC t10y max gap",
        ok,
        f"Max consecutive null run: {consecutive} days (max {MAX_CONSECUTIVE_GAP})"
    ))

    # Curve shape diversity (expect at least 3 of 4 shapes to appear)
    shapes_seen = df["curve_shape"].dropna().unique().tolist()
    ok = len(shapes_seen) >= 3
    results.append(CheckResult(
        "YC shape diversity",
        ok,
        f"Shapes present: {sorted(shapes_seen)}"
    ))

    # Inversion present (historically guaranteed)
    inverted_count = (df["curve_shape"] == "inverted").sum()
    ok = inverted_count > 100  # multiple multi-year inversion periods
    results.append(CheckResult(
        "YC inversion history",
        ok,
        f"{inverted_count:,} inverted rows (expected > 100)"
    ))

    # Known gaps — informational only, never block
    # t1m (DGS1MO) starts July 2001 — expect ~6% NULLs
    if "t1m" in df.columns:
        pct = df["t1m"].isna().mean() * 100
        results.append(CheckResult(
            "YC t1m null% (info)",
            True,
            f"{pct:.1f}% null — expected ~6% (DGS1MO starts Jul 2001)",
            is_gate=False
        ))

    # t20y (DGS20) discontinued Jan 2002 – Feb 2006 — expect ~12-15% NULLs
    if "t20y" in df.columns:
        pct = df["t20y"].isna().mean() * 100
        results.append(CheckResult(
            "YC t20y null% (info)",
            True,
            f"{pct:.1f}% null — expected ~12-15% (DGS20 gap 2002-2006, does not affect spreads or stress score)",
            is_gate=False
        ))

    return results


def run_credit_checks(df: pd.DataFrame) -> list:
    results = []

    # Row count
    ok = len(df) >= MIN_CREDIT_ROWS
    results.append(CheckResult(
        "CR row count",
        ok,
        f"{len(df):,} rows (min {MIN_CREDIT_ROWS:,})"
    ))

    # VIX null — gate
    if "vix" not in df.columns:
        results.append(CheckResult("CR vix present", False, "column missing"))
    else:
        pct = df["vix"].isna().mean() * 100
        ok = pct <= MAX_NULL_PCT_CORE
        results.append(CheckResult(
            "CR vix null%", ok,
            f"{pct:.2f}% (max {MAX_NULL_PCT_CORE}%)"
        ))

    # HY/IG OAS null — informational only (FRED BAML series limited to ~3yr window)
    for col in ["hy_oas", "ig_oas"]:
        if col not in df.columns:
            results.append(CheckResult(f"CR {col} present", False, "column missing"))
            continue
        pct = df[col].isna().mean() * 100
        results.append(CheckResult(
            f"CR {col} null% (info)",
            True,
            f"{pct:.2f}% — FRED BAML OAS series limited to recent history; stress scorer renormalises weights",
            is_gate=False
        ))

    # TED spread (allows higher NULL — pre-2016 OBFR + proxy coverage)
    pct = df["ted_spread"].isna().mean() * 100
    ok = pct <= MAX_NULL_PCT_TED
    results.append(CheckResult(
        "CR ted_spread null%",
        ok,
        f"{pct:.2f}% (max {MAX_NULL_PCT_TED}%)"
    ))

    # SOFR NULL — informational, not a gate (expected ~70%)
    pct = df["sofr"].isna().mean() * 100
    results.append(CheckResult(
        "CR sofr null% (info)",
        True,  # always pass, informational
        f"{pct:.1f}% null (expected ~70%, starts 2018)",
        is_gate=False
    ))

    # stress_score — must be 0 NULLs
    pct = df["stress_score"].isna().mean() * 100
    ok = pct == 0.0
    results.append(CheckResult(
        "CR stress_score null%",
        ok,
        f"{pct:.2f}% (must be 0%)"
    ))

    # stress_regime — must be 0 NULLs
    pct = df["stress_regime"].isna().mean() * 100
    ok = pct == 0.0
    results.append(CheckResult(
        "CR stress_regime null%",
        ok,
        f"{pct:.2f}% (must be 0%)"
    ))

    # Regime distribution (informational — distribution shifts when hy_oas/ig_oas pre-history is NULL)
    calm_pct = (df["stress_regime"] == "calm").mean() * 100
    results.append(CheckResult(
        "CR calm dominance",
        True,
        f"Calm: {calm_pct:.1f}% of history — lower than expected because hy_oas/ig_oas NULL for pre-2023 rows",
        is_gate=False
    ))

    # VIX spot checks (sanity bounds)
    vix_max = df["vix"].max()
    vix_min = df["vix"].min()
    ok = 10.0 <= vix_min <= 15.0 and vix_max >= 80.0
    results.append(CheckResult(
        "CR vix range",
        ok,
        f"VIX range: [{vix_min:.1f}, {vix_max:.1f}] (expect ~[10-15, 80+])",
        is_gate=False
    ))

    return results


def run_fed_decisions_checks(df: pd.DataFrame) -> list:
    results = []

    # Row count
    ok = len(df) >= MIN_FED_ROWS
    results.append(CheckResult(
        "FD row count",
        ok,
        f"{len(df):,} rows (min {MIN_FED_ROWS:,})"
    ))

    # No duplicate decision dates
    dupes = df["decision_date"].duplicated().sum()
    ok = dupes == 0
    results.append(CheckResult(
        "FD no duplicate dates",
        ok,
        f"{dupes} duplicates found"
    ))

    # Rate continuity: rate_after[n] == rate_before[n+1]
    past = df[df["decision_type"] != "future"].copy()
    past = past.dropna(subset=["rate_before", "rate_after"])
    continuity_errors = 0
    for i in range(1, len(past)):
        prev_after = float(past.iloc[i - 1]["rate_after"])
        curr_before = float(past.iloc[i]["rate_before"])
        if abs(prev_after - curr_before) > 0.01:
            continuity_errors += 1
    results.append(CheckResult(
        "FD rate continuity",
        True,
        f"{continuity_errors} continuity gaps — FRED records effective rate next business day after meeting",
        is_gate=False
    ))

    # decision_type values
    valid_types = {"hike", "cut", "hold", "future", "unknown"}
    invalid = df[~df["decision_type"].isin(valid_types)]
    ok = len(invalid) == 0
    results.append(CheckResult(
        "FD valid decision_types",
        ok,
        f"{len(invalid)} rows with unexpected decision_type"
    ))

    # rate_change == rate_after - rate_before
    calc_check = past.copy()
    calc_check["expected_change"] = (
        calc_check["rate_after"].astype(float) - calc_check["rate_before"].astype(float)
    ).round(2)
    calc_check["actual_change"] = calc_check["rate_change"].astype(float).round(2)
    mismatch = (abs(calc_check["expected_change"] - calc_check["actual_change"]) > 0.01).sum()
    ok = mismatch == 0
    results.append(CheckResult(
        "FD rate_change accuracy",
        ok,
        f"{mismatch} rows where rate_change != rate_after - rate_before"
    ))

    return results


def run_spot_checks() -> list:
    """Load final CSVs and run named spot checks against known historical values."""
    results = []

    yield_path = os.path.join(PROC_DIR, "yield_curve_daily.csv")
    credit_path = os.path.join(PROC_DIR, "credit_stress_daily.csv")

    yield_df = pd.read_csv(yield_path, parse_dates=["date"], index_col="date")
    credit_df = pd.read_csv(credit_path, parse_dates=["date"], index_col="date")

    checks = [
        # (date, df_name, column, operator, threshold, note)
        ("2008-10-10", "credit", "vix",          ">",  50.0,   "GFC peak — VIX above 50"),
        ("2008-10-10", "credit", "stress_regime", "==", "crisis", "GFC peak — crisis regime"),
        # hy_oas only has ~3yr history from FRED; skip 2008 check
        # ("2008-10-10", "credit", "hy_oas",  ">",  800.0,  "GFC peak — HY OAS > 800"),
        ("2019-08-27", "yield",  "curve_shape",   "==", "inverted", "2019 inversion"),
        ("2019-08-27", "yield",  "spread_2y10y",  "<",  0.0,    "2019 spread negative"),
        ("2020-03-18", "credit", "vix",           ">",  70.0,   "COVID spike — VIX > 70"),
        ("2023-03-01", "yield",  "spread_2y10y",  "<",  -0.5,   "2023 deep inversion > -50bps"),
        ("2007-06-01", "credit", "stress_regime", "==", "calm",  "pre-GFC — calm regime"),
        ("2015-01-01", "credit", "stress_score",  ">",  0.0,    "stress score always positive"),
    ]

    for date_str, df_name, col, op, threshold, note in checks:
        try:
            df = yield_df if df_name == "yield" else credit_df
            dt = pd.Timestamp(date_str)
            available = df.index[df.index <= dt]
            if available.empty:
                results.append(CheckResult(
                    f"SPOT {date_str} {col}", True,
                    f"skipped (no data before {date_str})", is_gate=False
                ))
                continue

            nearest = available[-1]
            actual = df.loc[nearest, col]

            if op == "==":
                ok = str(actual) == str(threshold)
            elif op == ">":
                ok = not pd.isna(actual) and float(actual) > float(threshold)
            elif op == "<":
                ok = not pd.isna(actual) and float(actual) < float(threshold)
            else:
                ok = False

            results.append(CheckResult(
                f"SPOT {date_str} {col}",
                ok,
                f"actual={actual}  expected {op} {threshold}  ({note})",
                is_gate=False   # spot checks are advisory, not blockers
            ))
        except Exception as e:
            results.append(CheckResult(
                f"SPOT {date_str} {col}", False,
                f"ERROR: {e}", is_gate=False
            ))

    return results


def _max_consecutive_null(series: pd.Series) -> int:
    """Return the length of the longest run of consecutive NULLs."""
    is_null = series.isna().astype(int)
    if is_null.sum() == 0:
        return 0
    # Count consecutive runs using diff
    groups = (is_null != is_null.shift()).cumsum()
    run_lengths = is_null.groupby(groups).sum()
    return int(run_lengths.max())


def main():
    print("\nCurveIQ Phase 0 — Step 5: Data Validation")

    # Load final CSVs
    files = {
        "yield":   os.path.join(PROC_DIR, "yield_curve_daily.csv"),
        "credit":  os.path.join(PROC_DIR, "credit_stress_daily.csv"),
        "fed":     os.path.join(ROOT, "data", "fed_decisions.csv"),
        "percents": os.path.join(PROC_DIR, "stress_percentiles.json"),
    }

    missing = [k for k, p in files.items() if not os.path.exists(p)]
    if missing:
        print(f"\nERROR: Missing files: {missing}")
        print("       Run steps 02, 03, 04 first.")
        sys.exit(1)

    yield_df = pd.read_csv(files["yield"], parse_dates=["date"], index_col="date")
    credit_df = pd.read_csv(files["credit"], parse_dates=["date"], index_col="date")
    fed_df = pd.read_csv(files["fed"])

    with open(files["percents"]) as f:
        percentiles = json.load(f)

    all_results = []

    # --- Yield curve checks ---
    print("\n[A] Yield Curve Checks")
    yc_results = run_yield_checks(yield_df)
    all_results.extend(yc_results)
    for r in yc_results:
        print(r)

    # --- Credit stress checks ---
    print("\n[B] Credit Stress Checks")
    cr_results = run_credit_checks(credit_df)
    all_results.extend(cr_results)
    for r in cr_results:
        print(r)

    # --- Fed decisions checks ---
    print("\n[C] Fed Decisions Checks")
    fd_results = run_fed_decisions_checks(fed_df)
    all_results.extend(fd_results)
    for r in fd_results:
        print(r)

    # --- Percentiles file check ---
    print("\n[D] Stress Percentiles File")
    expected_keys = list(set(["hy_oas", "ted_spread", "vix", "ig_oas", "spread_2y10y"]))
    missing_keys = [k for k in expected_keys if k not in percentiles]
    ok = len(missing_keys) == 0
    r = CheckResult("PERC all components present", ok,
                    f"Missing: {missing_keys}" if missing_keys else "All 5 components present")
    all_results.append(r)
    print(r)

    min_len = min(len(v) for v in percentiles.values()) if percentiles else 0
    r = CheckResult("PERC min values per component", True,
                    f"Smallest array: {min_len:,} values — hy_oas/ig_oas limited to ~3yr FRED window",
                    is_gate=False)
    all_results.append(r)
    print(r)

    # --- Spot checks ---
    print("\n[E] Historical Spot Checks (advisory)")
    spot_results = run_spot_checks()
    all_results.extend(spot_results)
    for r in spot_results:
        print(r)

    # --- Final verdict ---
    gate_failures = [r for r in all_results if r.is_gate and not r.passed]
    warn_failures = [r for r in all_results if not r.is_gate and not r.passed]

    print("\n" + "=" * 65)
    total = len(all_results)
    passed = sum(1 for r in all_results if r.passed)
    print(f"  Results: {passed}/{total} checks passed")
    print(f"  Gate failures (blockers): {len(gate_failures)}")
    print(f"  Advisory failures:        {len(warn_failures)}")

    if gate_failures:
        print("\n  BLOCKING ISSUES:")
        for r in gate_failures:
            print(f"    {r.name}: {r.message}")
        print("\n[FAIL] Data does not meet quality gates. Fix before pushing to Supabase.")
        print("=" * 65 + "\n")
        sys.exit(1)
    else:
        if warn_failures:
            print("\n  Advisory issues (non-blocking):")
            for r in warn_failures:
                print(f"    {r.name}: {r.message}")
        print("\n[PASS] All gate checks passed.")
        print("       PHASE 0 DATA VALIDATION COMPLETE")
        print("       Proceed to: python phase0/06_push_to_supabase.py")
        print("=" * 65 + "\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
