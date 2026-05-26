"""
Phase 0 — Step 7: Integrity verification — DB vs CSV.

Compares Supabase row counts against local CSV counts, then
spot-checks 10 random date values for each table.

Prints "PHASE 0 COMPLETE" on success.
Exit code 0 = verified, 1 = mismatch found.
"""

import os
import sys
import random

import pandas as pd
import numpy as np
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

PROC_DIR = os.path.join(ROOT, "data", "processed")

# Columns to spot-check per table (sample from these)
YIELD_SPOT_COLS = ["t2y", "t10y", "spread_2y10y", "curve_shape"]
CREDIT_SPOT_COLS = ["hy_oas", "vix", "stress_score", "stress_regime"]
FED_SPOT_COLS = ["rate_before", "rate_after", "decision_type"]


def get_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(url, key).schema("curveiq")


def get_db_count(client, table: str) -> int:
    """Get row count from Supabase table using count()."""
    result = client.table(table).select("*", count="exact").limit(1).execute()
    return result.count


def check_counts(client) -> tuple:
    """Returns (all_match, summary_list)."""
    tables = {
        "ciq_yield_curve_daily": os.path.join(PROC_DIR, "yield_curve_daily.csv"),
        "ciq_credit_stress_daily": os.path.join(PROC_DIR, "credit_stress_daily.csv"),
        "ciq_fed_decisions": os.path.join(ROOT, "data", "fed_decisions.csv"),
    }

    results = []
    all_match = True

    for table, csv_path in tables.items():
        if not os.path.exists(csv_path):
            results.append((table, "MISSING", "N/A", False))
            all_match = False
            continue

        csv_df = pd.read_csv(csv_path)
        # For ciq_fed_decisions, exclude future rows
        if table == "ciq_fed_decisions":
            csv_df = csv_df[csv_df["decision_type"] != "future"]

        csv_count = len(csv_df)

        try:
            db_count = get_db_count(client, table)
        except Exception as e:
            results.append((table, csv_count, f"ERROR: {e}", False))
            all_match = False
            continue

        match = csv_count == db_count
        if not match:
            all_match = False
        results.append((table, csv_count, db_count, match))

    return all_match, results


def spot_check_table(client, table: str, csv_path: str,
                     date_col: str, check_cols: list,
                     n_samples: int = 10) -> list:
    """
    Pick n_samples random dates from CSV, fetch from DB, compare values.
    Returns list of (date, col, csv_val, db_val, match) tuples.
    """
    csv_df = pd.read_csv(csv_path, parse_dates=[date_col], index_col=date_col)
    if table == "ciq_fed_decisions":
        csv_df = csv_df[csv_df["decision_type"] != "future"]

    # Sample dates that have non-null values in at least one check column
    valid_idx = csv_df[check_cols].dropna(how="all").index.tolist()
    if not valid_idx:
        return []

    sample_dates = random.sample(valid_idx, min(n_samples, len(valid_idx)))
    results = []

    for dt in sample_dates:
        date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]

        # Fetch from DB
        try:
            resp = client.table(table).select(", ".join(check_cols)) \
                .eq(date_col, date_str).limit(1).execute()
            db_row = resp.data[0] if resp.data else None
        except Exception as e:
            for col in check_cols:
                results.append((date_str, col, "N/A", f"ERROR: {e}", False))
            continue

        if db_row is None:
            for col in check_cols:
                results.append((date_str, col, csv_df.loc[dt, col], "NOT FOUND", False))
            continue

        for col in check_cols:
            if col not in csv_df.columns:
                continue
            csv_val = csv_df.loc[dt, col]
            db_val = db_row.get(col)

            # Normalise for comparison
            csv_v = None if pd.isna(csv_val) else csv_val
            db_v = db_val

            # Numeric comparison with tolerance
            if csv_v is not None and db_v is not None:
                try:
                    match = abs(float(csv_v) - float(db_v)) < 0.001
                except (ValueError, TypeError):
                    match = str(csv_v).strip() == str(db_v).strip()
            else:
                match = (csv_v is None) == (db_v is None)

            results.append((date_str, col, csv_v, db_v, match))

    return results


def main():
    random.seed(42)  # reproducible samples

    print("\nCurveIQ Phase 0 — Step 7: Integrity Verification")

    print("\n  Connecting to Supabase...")
    try:
        client = get_client()
    except Exception as e:
        print(f"[FAIL] {e}")
        sys.exit(1)

    # --- Row count comparison ---
    print("\n[A] Row Count Comparison (CSV vs Supabase)")
    counts_ok, count_results = check_counts(client)

    print(f"\n  {'Table':<26} {'CSV Rows':>10} {'DB Rows':>10}  Match")
    print(f"  {'-'*55}")
    for table, csv_count, db_count, match in count_results:
        icon = "[OK]" if match else "[FAIL]"
        print(f"  {icon} {table:<22} {str(csv_count):>10} {str(db_count):>10}")

    # --- Spot checks ---
    spot_config = [
        ("ciq_yield_curve_daily",
         os.path.join(PROC_DIR, "yield_curve_daily.csv"),
         "date", YIELD_SPOT_COLS),
        ("ciq_credit_stress_daily",
         os.path.join(PROC_DIR, "credit_stress_daily.csv"),
         "date", CREDIT_SPOT_COLS),
        ("ciq_fed_decisions",
         os.path.join(ROOT, "data", "fed_decisions.csv"),
         "decision_date", FED_SPOT_COLS),
    ]

    spot_failures = 0
    spot_total = 0

    for table, csv_path, date_col, check_cols in spot_config:
        if not os.path.exists(csv_path):
            print(f"\n[B] Spot checks — {table}: CSV not found, skipping")
            continue

        print(f"\n[B] Spot Checks — {table}")
        spot_results = spot_check_table(client, table, csv_path, date_col, check_cols)

        if not spot_results:
            print("  (no valid rows to sample)")
            continue

        for date_str, col, csv_v, db_v, match in spot_results:
            icon = "[OK]  " if match else "[FAIL]"
            if not match:
                spot_failures += 1
            spot_total += 1
            if not match or True:  # always print for visibility
                print(f"  {icon} {date_str}  {col:<18}  csv={str(csv_v):<15}  db={str(db_v)}")

    # --- Final verdict ---
    print("\n" + "=" * 60)
    total_failures = (0 if counts_ok else 1) + spot_failures

    if total_failures == 0:
        print("  PHASE 0 COMPLETE — DB row counts match CSVs 100%")
        print(f"  Spot checks: {spot_total}/{spot_total} passed")
        print("")
        print("  ✔ Data foundation is verified and ready.")
        print("  Next step: Phase 1 — run db/schema.sql in Supabase")
        print("             then begin building the application.")
        print("=" * 60 + "\n")
        sys.exit(0)
    else:
        print(f"  [FAIL] {total_failures} integrity issues found")
        if not counts_ok:
            print("         Row count mismatches — re-run 06_push_to_supabase.py")
        if spot_failures:
            print(f"         {spot_failures}/{spot_total} spot checks failed — check data pipeline")
        print("=" * 60 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
