"""
Phase 0 — Step 2: Build data/fed_decisions.csv.

Strategy:
  1. Hardcode all known FOMC decision dates (2000-2026), including emergency meetings.
  2. Fetch DFEDTAR (pre-Dec 2008, single target rate) and DFEDTARU (Dec 2008+,
     upper bound of target range) from FRED.
  3. For each meeting date, determine rate_after from FRED data.
  4. Compute rate_before, rate_change, decision_type.
  5. Write: decision_date, rate_before, rate_after, rate_change,
            decision_type, statement_summary.

statement_summary is left empty — fill manually if needed.
rate_after for the range era (post-2008) uses the upper bound (DFEDTARU).
"""

import os
import sys
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from fredapi import Fred

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

OUT_PATH = os.path.join(ROOT, "data", "fed_decisions.csv")

# All FOMC decision dates (last day of meeting = announcement date).
# Includes scheduled meetings and emergency inter-meeting actions.
FOMC_DATES = [
    # 2000
    "2000-02-02", "2000-03-21", "2000-05-16", "2000-06-28",
    "2000-08-22", "2000-10-03", "2000-11-15", "2000-12-19",
    # 2001 (3 emergency cuts)
    "2001-01-03",   # emergency
    "2001-01-31", "2001-03-20",
    "2001-04-18",   # emergency
    "2001-05-15", "2001-06-27", "2001-08-21",
    "2001-09-17",   # emergency post-9/11
    "2001-10-02", "2001-11-06", "2001-12-11",
    # 2002
    "2002-01-30", "2002-03-19", "2002-05-07", "2002-06-26",
    "2002-08-13", "2002-09-24", "2002-11-06", "2002-12-10",
    # 2003
    "2003-01-29", "2003-03-18", "2003-05-06", "2003-06-25",
    "2003-08-12", "2003-09-16", "2003-10-28", "2003-12-09",
    # 2004
    "2004-01-28", "2004-03-16", "2004-05-04", "2004-06-30",
    "2004-08-10", "2004-09-21", "2004-11-10", "2004-12-14",
    # 2005
    "2005-02-02", "2005-03-22", "2005-05-03", "2005-06-30",
    "2005-08-09", "2005-09-20", "2005-11-01", "2005-12-13",
    # 2006
    "2006-01-31", "2006-03-28", "2006-05-10", "2006-06-29",
    "2006-08-08", "2006-09-20", "2006-10-25", "2006-12-12",
    # 2007
    "2007-01-31", "2007-03-21", "2007-05-09", "2007-06-28",
    "2007-08-07", "2007-09-18", "2007-10-31", "2007-12-11",
    # 2008 (2 emergency cuts)
    "2008-01-22",   # emergency -75bp
    "2008-01-30", "2008-03-18", "2008-04-30", "2008-06-25", "2008-08-05",
    "2008-09-16",
    "2008-10-08",   # emergency coordinated global cut
    "2008-10-29",
    "2008-12-16",   # first zero lower bound meeting; range era begins
    # 2009
    "2009-01-28", "2009-03-18", "2009-04-29", "2009-06-24",
    "2009-08-12", "2009-09-23", "2009-11-04", "2009-12-16",
    # 2010
    "2010-01-27", "2010-03-16", "2010-04-28", "2010-06-23",
    "2010-08-10", "2010-09-21", "2010-11-03", "2010-12-14",
    # 2011
    "2011-01-26", "2011-03-15", "2011-04-27", "2011-06-22",
    "2011-08-09", "2011-09-21", "2011-11-02", "2011-12-13",
    # 2012
    "2012-01-25", "2012-03-13", "2012-04-25", "2012-06-20",
    "2012-08-01", "2012-09-13", "2012-10-24", "2012-12-12",
    # 2013
    "2013-01-30", "2013-03-20", "2013-05-01", "2013-06-19",
    "2013-07-31", "2013-09-18", "2013-10-30", "2013-12-18",
    # 2014
    "2014-01-29", "2014-03-19", "2014-04-30", "2014-06-18",
    "2014-07-30", "2014-09-17", "2014-10-29", "2014-12-17",
    # 2015
    "2015-01-28", "2015-03-18", "2015-04-29", "2015-06-17",
    "2015-07-29", "2015-09-17", "2015-10-28", "2015-12-16",
    # 2016
    "2016-01-27", "2016-03-16", "2016-04-27", "2016-06-15",
    "2016-07-27", "2016-09-21", "2016-11-02", "2016-12-14",
    # 2017
    "2017-02-01", "2017-03-15", "2017-05-03", "2017-06-14",
    "2017-07-26", "2017-09-20", "2017-11-01", "2017-12-13",
    # 2018
    "2018-01-31", "2018-03-21", "2018-05-02", "2018-06-13",
    "2018-08-01", "2018-09-26", "2018-11-08", "2018-12-19",
    # 2019
    "2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19",
    "2019-07-31", "2019-09-18", "2019-10-30", "2019-12-11",
    # 2020 (2 emergency cuts)
    "2020-01-29",
    "2020-03-03",   # emergency -50bp
    "2020-03-15",   # emergency -100bp (Sunday, ZLB)
    "2020-04-29", "2020-06-10", "2020-07-29", "2020-09-16",
    "2020-11-05", "2020-12-16",
    # 2021
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16",
    "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    # 2022 (aggressive hiking cycle)
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15",
    "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    # 2023
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14",
    "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    # 2024
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
    "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    # 2026 (through 2026-05-25 — future dates included for completeness)
    "2026-01-29", "2026-03-19", "2026-05-07",
    "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]


def build_rate_series(fred: Fred) -> pd.Series:
    """
    Build a unified daily rate series:
      - DFEDTAR for 2000-01-01 to 2008-12-15 (single target)
      - DFEDTARU for 2008-12-16 onward (upper bound of target range)
    Returns a pandas Series indexed by date with rate values.
    """
    print("  Fetching DFEDTAR (2000–2008)...", end="", flush=True)
    tar = fred.get_series("DFEDTAR", observation_start="2000-01-01",
                          observation_end="2008-12-15")
    print(f" {len(tar)} rows")

    print("  Fetching DFEDTARU (2008–present)...", end="", flush=True)
    taru = fred.get_series("DFEDTARU", observation_start="2008-12-16")
    print(f" {len(taru)} rows")

    combined = pd.concat([tar, taru])
    combined = combined[~combined.index.duplicated(keep="last")]
    combined = combined.sort_index()
    combined.index = pd.to_datetime(combined.index)
    return combined


def get_rate_on_or_after(rate_series: pd.Series, date: pd.Timestamp) -> float:
    """Return the rate that became effective on or immediately after `date`."""
    future = rate_series[rate_series.index >= date]
    if future.empty:
        return float("nan")
    return round(float(future.iloc[0]), 2)


def get_rate_before(rate_series: pd.Series, date: pd.Timestamp) -> float:
    """Return the rate that was in effect just before `date`."""
    past = rate_series[rate_series.index < date]
    if past.empty:
        return float("nan")
    return round(float(past.iloc[-1]), 2)


def classify_decision(rate_change: float) -> str:
    if pd.isna(rate_change):
        return "unknown"
    if rate_change > 0.01:
        return "hike"
    elif rate_change < -0.01:
        return "cut"
    else:
        return "hold"


def build_decisions(rate_series: pd.Series) -> pd.DataFrame:
    today = pd.Timestamp.today()
    rows = []

    for date_str in FOMC_DATES:
        dt = pd.Timestamp(date_str)
        if dt > today:
            # Future meeting — include as placeholder with NaN rates
            rows.append({
                "decision_date": date_str,
                "rate_before": None,
                "rate_after": None,
                "rate_change": None,
                "decision_type": "future",
                "statement_summary": "",
            })
            continue

        rate_after = get_rate_on_or_after(rate_series, dt)
        rate_before = get_rate_before(rate_series, dt)

        if pd.isna(rate_before):
            # First meeting in series — no prior rate
            rate_change = float("nan")
        else:
            rate_change = round(rate_after - rate_before, 2)

        rows.append({
            "decision_date": date_str,
            "rate_before": rate_before if not pd.isna(rate_before) else None,
            "rate_after": rate_after if not pd.isna(rate_after) else None,
            "rate_change": rate_change if not pd.isna(rate_change) else None,
            "decision_type": classify_decision(rate_change),
            "statement_summary": "",
        })

    return pd.DataFrame(rows)


def validate_decisions(df: pd.DataFrame):
    """Print validation checks on the decisions DataFrame."""
    print("\n  Validation:")
    past = df[df["decision_type"] != "future"].copy()

    # Check: rate_after[n] == rate_before[n+1] for consecutive rows
    consistency_errors = 0
    for i in range(1, len(past)):
        prev_after = past.iloc[i - 1]["rate_after"]
        curr_before = past.iloc[i]["rate_before"]
        if pd.isna(prev_after) or pd.isna(curr_before):
            continue
        if abs(float(prev_after) - float(curr_before)) > 0.01:
            consistency_errors += 1
            if consistency_errors <= 5:
                print(f"    [WARN] Consistency gap at {past.iloc[i]['decision_date']}: "
                      f"prev_after={prev_after} curr_before={curr_before}")

    hikes = (past["decision_type"] == "hike").sum()
    cuts = (past["decision_type"] == "cut").sum()
    holds = (past["decision_type"] == "hold").sum()

    print(f"    Total decisions (past): {len(past)}")
    print(f"    Hikes: {hikes}  Cuts: {cuts}  Holds: {holds}")
    if consistency_errors:
        print(f"    [WARN] {consistency_errors} rate-continuity gaps detected (check FRED data)")
    else:
        print(f"    [OK] Rate continuity: all consecutive meetings have matching rates")

    # Spot-check known events
    checks = [
        ("2001-01-03", "cut"),    # emergency post-dot-com
        ("2008-12-16", "cut"),    # ZLB
        ("2015-12-16", "hike"),   # first hike post-ZLB
        ("2020-03-15", "cut"),    # COVID emergency
        ("2022-06-15", "hike"),   # 75bp hike
    ]
    print("\n  Spot checks:")
    for date_str, expected_type in checks:
        row = df[df["decision_date"] == date_str]
        if row.empty:
            print(f"    [WARN] {date_str} not found in decisions")
            continue
        actual_type = row.iloc[0]["decision_type"]
        status = "OK" if actual_type == expected_type else "FAIL"
        chg = row.iloc[0]["rate_change"]
        print(f"    [{status}] {date_str}: expected={expected_type} actual={actual_type} "
              f"change={chg}")


def main():
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        print("ERROR: FRED_API_KEY not set in .env")
        sys.exit(1)

    print("\nCurveIQ Phase 0 — Step 2: Fed Decisions")
    print(f"Building {OUT_PATH}...\n")

    fred = Fred(api_key=api_key)
    rate_series = build_rate_series(fred)

    print(f"\n  Rate series: {len(rate_series)} rows, "
          f"{rate_series.index.min().date()} to {rate_series.index.max().date()}")
    print(f"  FOMC dates to process: {len(FOMC_DATES)}")

    df = build_decisions(rate_series)
    validate_decisions(df)

    df.to_csv(OUT_PATH, index=False)
    print(f"\n[OK] Written {len(df)} rows to {OUT_PATH}")
    print("     Proceed to: python phase0/03_clean_merge.py")


if __name__ == "__main__":
    main()
