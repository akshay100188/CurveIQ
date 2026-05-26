"""
Phase 0 — Step 1b: Fetch full HY OAS and IG OAS history from MacroTrends.

FRED's API only serves these ICE BofA series from 2023-05-23 (hard license limit).
MacroTrends hosts the same data via an internal JSON endpoint back to 1996-12-31.

Overwrites:
  data/raw/BAMLH0A0HYM2.csv   (HY OAS, replaces the 794-row FRED version)
  data/raw/BAMLC0A0CM.csv     (IG OAS, replaces the 794-row FRED version)

After this runs, re-execute:
  python phase0/03_clean_merge.py
  python phase0/04_compute_columns.py
  python phase0/05_validate.py
  python phase0/06_push_to_supabase.py
  python phase0/07_verify_integrity.py
"""

import os
import sys
import time
import csv
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")

SERIES = {
    "BAMLH0A0HYM2": {
        "label": "US High Yield OAS",
        "page_id": "3229",
        "referer": "https://www.macrotrends.net/3229/us-high-yield-bond-spread",
    },
    "BAMLC0A0CM": {
        "label": "US Investment Grade OAS",
        "page_id": "3042",
        "referer": "https://www.macrotrends.net/3042/us-corporate-bond-spread",
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}


def fetch_series(page_id: str, referer: str) -> list[tuple[str, float]]:
    url = f"https://www.macrotrends.net/economic-data/{page_id}/D"
    headers = {**HEADERS, "Referer": referer}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()

    payload = r.json()
    raw = payload.get("data", [])
    if not raw:
        raise ValueError(f"Empty data in response — payload keys: {list(payload.keys())}")

    rows = []
    for ts, val in raw:
        if val is None:
            continue
        date_str = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        rows.append((date_str, float(val)))

    rows.sort(key=lambda x: x[0])
    return rows


def save_csv(series_id: str, rows: list[tuple[str, float]]) -> str:
    path = os.path.join(RAW_DIR, f"{series_id}.csv")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "value"])
        writer.writerows(rows)
    return path


def spot_check(rows: list[tuple[str, float]], series_id: str):
    lookup = {d: v for d, v in rows}
    checks = []
    if series_id == "BAMLH0A0HYM2":
        # GFC peak: HY OAS should be > 15 (1500+ bps) in Oct 2008
        checks = [
            ("2008-10-15", ">", 15.0, "GFC peak > 15"),
            ("2020-03-23", ">", 10.0, "COVID peak > 10"),
            ("2007-01-02", "<",  4.0, "pre-GFC calm < 4"),
        ]
    elif series_id == "BAMLC0A0CM":
        # GFC peak: IG OAS should be > 5 (500+ bps) in Oct 2008
        checks = [
            ("2008-10-15", ">", 5.0,  "GFC peak > 5"),
            ("2020-03-23", ">", 2.5,  "COVID peak > 2.5"),
            ("2007-01-02", "<", 1.5,  "pre-GFC calm < 1.5"),
        ]

    all_ok = True
    for date, op, threshold, note in checks:
        # Find nearest date within 5 days
        val = None
        for offset in range(6):
            from datetime import date as ddate, timedelta
            d = (ddate.fromisoformat(date) + timedelta(days=offset)).isoformat()
            if d in lookup:
                val = lookup[d]
                break
            d = (ddate.fromisoformat(date) - timedelta(days=offset)).isoformat()
            if d in lookup:
                val = lookup[d]
                break

        if val is None:
            print(f"    [WARN] {date}: no data near this date — {note}")
            continue

        ok = (op == ">" and val > threshold) or (op == "<" and val < threshold)
        icon = "[OK]" if ok else "[FAIL]"
        print(f"    {icon} {date}: {val:.2f} {op} {threshold}  ({note})")
        if not ok:
            all_ok = False

    return all_ok


def main():
    print("CurveIQ Phase 0 — Step 1b: MacroTrends OAS Collection")
    print("Fetching full HY OAS + IG OAS history (back to 1996)...\n")

    os.makedirs(RAW_DIR, exist_ok=True)
    all_ok = True

    for series_id, cfg in SERIES.items():
        print(f"  [{series_id}] {cfg['label']}")
        try:
            rows = fetch_series(cfg["page_id"], cfg["referer"])
        except Exception as e:
            print(f"    [FAIL] Fetch error: {e}")
            all_ok = False
            continue

        if len(rows) < 1000:
            print(f"    [FAIL] Only {len(rows)} rows — expected 7,000+. Endpoint may have changed.")
            all_ok = False
            continue

        path = save_csv(series_id, rows)
        print(f"    Rows:  {len(rows):,}")
        print(f"    Range: {rows[0][0]} → {rows[-1][0]}")
        print(f"    Spot checks:")
        ok = spot_check(rows, series_id)
        if not ok:
            all_ok = False
        print(f"    Saved: {path}\n")

        time.sleep(1)

    print("=" * 60)
    if all_ok:
        print("[OK] Both OAS series fetched with full history.")
        print("     Next: re-run the processing pipeline:")
        print("       python phase0/03_clean_merge.py")
        print("       python phase0/04_compute_columns.py")
        print("       python phase0/05_validate.py")
        print("       python phase0/06_push_to_supabase.py")
        print("       python phase0/07_verify_integrity.py")
    else:
        print("[FAIL] One or more series failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
