"""
Phase 0 — Step 1: Fetch all 17 FRED series to data/raw/<SERIES_ID>.csv.
Each CSV has two columns: date, value.
Run time: ~2-3 minutes on first run.
Idempotent: re-running overwrites existing files.
"""

import os
import sys
import time

import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

RAW_DIR = os.path.join(ROOT, "data", "raw")
START_DATE = "2000-01-01"

# All 17 series: (fred_id, description, table_column)
SERIES = [
    # Module 1 — Rate series
    ("DGS1MO",        "1-Month Treasury Yield",             "t1m"),
    ("DGS3MO",        "3-Month Treasury Yield",             "t3m"),
    ("DGS6MO",        "6-Month Treasury Yield",             "t6m"),
    ("DGS1",          "1-Year Treasury Yield",              "t1y"),
    ("DGS2",          "2-Year Treasury Yield",              "t2y"),
    ("DGS3",          "3-Year Treasury Yield",              "t3y"),
    ("DGS5",          "5-Year Treasury Yield",              "t5y"),
    ("DGS7",          "7-Year Treasury Yield",              "t7y"),
    ("DGS10",         "10-Year Treasury Yield",             "t10y"),
    ("DGS20",         "20-Year Treasury Yield",             "t20y"),
    ("DGS30",         "30-Year Treasury Yield",             "t30y"),
    # Module 2 — Credit/stress series
    ("BAMLH0A0HYM2",  "High Yield OAS",                     "hy_oas"),
    ("BAMLC0A0CM",    "Investment Grade OAS",               "ig_oas"),
    ("TEDRATE",       "TED Spread",                         "ted_spread"),
    ("VIXCLS",        "VIX Close",                          "vix"),
    ("SOFR",          "SOFR Rate",                          "sofr"),
    ("OBFR",          "Overnight Bank Funding Rate",        "obfr"),
]

# Series with known limited history — used for informational reporting only
KNOWN_SHORT_SERIES = {
    "SOFR":   "2018-04-02",
    "OBFR":   "2016-03-01",
    "TEDRATE": None,          # ends 2023-04-28 (discontinued)
}


def fetch_series(fred: Fred, series_id: str, description: str, column: str) -> dict:
    """Fetch a single FRED series. Returns a summary dict."""
    out_path = os.path.join(RAW_DIR, f"{series_id}.csv")
    summary = {
        "series_id": series_id,
        "column": column,
        "description": description,
        "rows": 0,
        "first_date": None,
        "last_date": None,
        "null_count": 0,
        "null_pct": 0.0,
        "status": "OK",
    }

    try:
        s = fred.get_series(series_id, observation_start=START_DATE)
        if s is None or len(s) == 0:
            summary["status"] = "EMPTY"
            return summary

        df = s.reset_index()
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"]).dt.date

        # FRED uses . for missing — fredapi returns NaN for those
        null_mask = df["value"].isna()
        summary["rows"] = len(df)
        summary["null_count"] = int(null_mask.sum())
        summary["null_pct"] = round(summary["null_count"] / summary["rows"] * 100, 2)
        summary["first_date"] = str(df["date"].min())
        summary["last_date"] = str(df["date"].max())

        df.to_csv(out_path, index=False)

    except Exception as e:
        summary["status"] = f"ERROR: {e}"

    return summary


def print_summary_table(summaries: list):
    print("\n" + "-" * 90)
    print(f"{'Series':<18} {'Column':<14} {'Rows':>6} {'First Date':<12} {'Last Date':<12} {'NULLs':>6} {'NULL%':>6}  Status")
    print("-" * 90)
    for s in summaries:
        flag = ""
        if s["series_id"] in KNOWN_SHORT_SERIES:
            flag = " *"
        print(
            f"{s['series_id']:<18} {s['column']:<14} {s['rows']:>6} "
            f"{str(s['first_date']):<12} {str(s['last_date']):<12} "
            f"{s['null_count']:>6} {s['null_pct']:>5.1f}%  {s['status']}{flag}"
        )
    print("-" * 90)
    print("  * = known limited history (SOFR from 2018, OBFR from 2016, TEDRATE ends 2023)")


def main():
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        print("ERROR: FRED_API_KEY not set in .env")
        sys.exit(1)

    os.makedirs(RAW_DIR, exist_ok=True)
    fred = Fred(api_key=api_key)

    print(f"\nCurveIQ Phase 0 — Step 1: FRED Data Collection")
    print(f"Fetching {len(SERIES)} series from {START_DATE} to today...")
    print(f"Output: {RAW_DIR}\n")

    summaries = []
    for i, (series_id, description, column) in enumerate(SERIES, 1):
        print(f"  [{i:02d}/{len(SERIES)}] {series_id:<18} {description}...", end="", flush=True)
        summary = fetch_series(fred, series_id, description, column)
        summaries.append(summary)

        if summary["status"] == "OK":
            print(f" {summary['rows']} rows  ({summary['null_pct']:.1f}% null)")
        else:
            print(f" {summary['status']}")

        # Be polite to FRED's free tier — small delay
        time.sleep(0.3)

    print_summary_table(summaries)

    # Gate check
    errors = [s for s in summaries if s["status"].startswith("ERROR")]
    empty = [s for s in summaries if s["status"] == "EMPTY"]
    if errors:
        print(f"\n[FAIL] {len(errors)} series had errors. Fix before proceeding.")
        for s in errors:
            print(f"       {s['series_id']}: {s['status']}")
        sys.exit(1)

    files_written = [s for s in summaries if s["status"] == "OK"]
    print(f"\n[OK] {len(files_written)}/{len(SERIES)} series written to data/raw/")
    if empty:
        print(f"[WARN] {len(empty)} series returned empty (check FRED availability)")
    print("      Proceed to: python phase0/02_fed_decisions.py")


if __name__ == "__main__":
    main()
