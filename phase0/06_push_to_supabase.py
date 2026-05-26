"""
Phase 0 — Step 6: Push validated CSVs to Supabase.

Prerequisites:
  1. Run schema_data_tables.sql in your Supabase SQL editor FIRST.
     (Supabase dashboard → SQL Editor → paste contents → Run)
  2. All validation checks in step 05 must have passed.

What this does:
  - Inserts ciq_yield_curve_daily      (~6,500 rows) in 1,000-row batches
  - Inserts ciq_credit_stress_daily    (~6,500 rows) in 1,000-row batches
  - Inserts ciq_fed_decisions          (~215 rows) in a single batch
  - Uses upsert on primary key (date / decision_date) — idempotent

Tables targeted:
  curveiq.ciq_yield_curve_daily
  curveiq.ciq_credit_stress_daily
  curveiq.ciq_fed_decisions

All NUMERIC columns are rounded before insert. NULL values are preserved.
"""

import os
import sys
import math
import json

import pandas as pd
import numpy as np
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

PROC_DIR = os.path.join(ROOT, "data", "processed")
BATCH_SIZE = 1000


def get_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(url, key).schema("curveiq")


def verify_tables_exist(client) -> bool:
    """Check that the 3 required tables are present in curveiq schema."""
    tables = ["ciq_yield_curve_daily", "ciq_credit_stress_daily", "ciq_fed_decisions"]
    missing = []
    for table in tables:
        try:
            client.table(table).select("*").limit(1).execute()
        except Exception as e:
            if "does not exist" in str(e) or "relation" in str(e):
                missing.append(table)
    if missing:
        print(f"\n[FAIL] Tables not found in curveiq schema: {missing}")
        print("\n  ACTION REQUIRED:")
        print("  1. Open Supabase dashboard → SQL Editor")
        print("  2. Paste the contents of: phase0/schema_data_tables.sql")
        print("  3. Click Run")
        print("  4. Re-run this script")
        return False
    return True


def clean_row(row: dict) -> dict:
    """Convert NaN/inf to None for JSON serialisation."""
    cleaned = {}
    for k, v in row.items():
        if v is None:
            cleaned[k] = None
        elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            cleaned[k] = None
        elif isinstance(v, (np.integer,)):
            cleaned[k] = int(v)
        elif isinstance(v, (np.floating,)):
            cleaned[k] = None if math.isnan(float(v)) else float(v)
        else:
            cleaned[k] = v
    return cleaned


def batch_upsert(client, table: str, records: list, on_conflict: str) -> int:
    """Upsert records in batches. Returns total rows upserted."""
    total = 0
    batches = math.ceil(len(records) / BATCH_SIZE)
    for i in range(batches):
        chunk = records[i * BATCH_SIZE: (i + 1) * BATCH_SIZE]
        client.table(table).upsert(chunk, on_conflict=on_conflict).execute()
        total += len(chunk)
        print(f"    batch {i+1}/{batches}  ({total:,}/{len(records):,} rows)", end="\r")
    print()  # newline after progress
    return total


def push_yield_curve(client) -> int:
    path = os.path.join(PROC_DIR, "yield_curve_daily.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path}")

    df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    # Round all numeric columns to schema precision (NUMERIC(8,4))
    numeric_cols = [c for c in df.columns if c not in ("date", "curve_shape")]
    df[numeric_cols] = df[numeric_cols].round(4)

    records = [clean_row(r) for r in df.to_dict(orient="records")]
    print(f"\n  Upserting ciq_yield_curve_daily: {len(records):,} rows...")
    return batch_upsert(client, "ciq_yield_curve_daily", records, on_conflict="date")


def push_credit_stress(client) -> int:
    path = os.path.join(PROC_DIR, "credit_stress_daily.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path}")

    df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    numeric_cols = [c for c in df.columns if c not in ("date", "stress_regime")]
    df[numeric_cols] = df[numeric_cols].round(4)
    # stress_score gets rounded to 2dp
    if "stress_score" in df.columns:
        df["stress_score"] = df["stress_score"].round(2)

    records = [clean_row(r) for r in df.to_dict(orient="records")]
    print(f"\n  Upserting ciq_credit_stress_daily: {len(records):,} rows...")
    return batch_upsert(client, "ciq_credit_stress_daily", records, on_conflict="date")


def push_fed_decisions(client) -> int:
    path = os.path.join(ROOT, "data", "fed_decisions.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path}")

    df = pd.read_csv(path)
    # Exclude future meetings (no real data)
    df = df[df["decision_type"] != "future"].copy()
    df["decision_date"] = df["decision_date"].astype(str)

    numeric_cols = ["rate_before", "rate_after", "rate_change"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

    records = [clean_row(r) for r in df.to_dict(orient="records")]
    print(f"\n  Upserting ciq_fed_decisions: {len(records):,} rows...")
    return batch_upsert(client, "ciq_fed_decisions", records, on_conflict="decision_date")


def main():
    print("\nCurveIQ Phase 0 — Step 6: Push to Supabase")

    # Pre-flight checks
    url = os.environ.get("SUPABASE_URL", "")
    if not url:
        print("ERROR: SUPABASE_URL not set in .env")
        sys.exit(1)

    print(f"\n  Target: {url[:50]}...")

    print("\n  Connecting to Supabase...")
    try:
        client = get_client()
    except Exception as e:
        print(f"[FAIL] Cannot connect to Supabase: {e}")
        sys.exit(1)

    print("  Verifying tables exist...")
    if not verify_tables_exist(client):
        sys.exit(1)
    print("  [OK] All 3 tables present in curveiq schema")

    # Push each table
    results = {}
    try:
        results["ciq_yield_curve_daily"] = push_yield_curve(client)
        results["ciq_credit_stress_daily"] = push_credit_stress(client)
        results["ciq_fed_decisions"] = push_fed_decisions(client)
    except FileNotFoundError as e:
        print(f"\n[FAIL] {e}")
        print("       Run phase0/03_clean_merge.py and phase0/04_compute_columns.py first.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Supabase insert error: {e}")
        sys.exit(1)

    print("\n" + "=" * 55)
    print("  PUSH COMPLETE")
    for table, count in results.items():
        print(f"    {table:<28} {count:>6,} rows upserted")
    print("\n  Proceed to: python phase0/07_verify_integrity.py")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
