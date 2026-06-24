"""Daily refresh job — keep the whole app current.

Order matters: refresh equity into core.curveiq_* FIRST, then re-ingest (which
imports the refreshed equity + pulls fresh FRED rates), recompute L1 metrics,
re-seed crisis key dates / bands, and run every validation gate. Non-zero exit
on any failure so the scheduler surfaces it.

Run locally:  python -m pipeline.refresh_daily
Scheduled:    .github/workflows/daily-refresh.yml (cron, GitHub Actions)
"""
from __future__ import annotations

import sys
import traceback

# Force UTF-8 stdout so non-ASCII status text doesn't crash on a Windows console
# (cp1252). No-op on Linux/GitHub Actions, which are already UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from . import phase0_ingest, phase0_validate, phase1_compute, phase1_validate, phase2_crisis
from .sources import equity


def main() -> int:
    print("=== [1/6] refresh equity (S&P 500 + Nifty 50) ===")
    # Equity sources are secondary and can transiently block (e.g. niftyindices vs
    # a runner IP). Don't fail the whole rates refresh over them — warn and carry on
    # with whatever is already in core.curveiq_*.
    for name, fn in (("S&P 500", equity.refresh_sp500), ("Nifty 50", equity.refresh_nifty50)):
        try:
            print(f"  {name} rows:", fn())
        except Exception as e:
            print(f"  [WARN] {name} refresh failed ({e}); using existing data")

    print("\n=== [2/6] ingest (FRED rates + India + equity -> curveiq) ===")
    phase0_ingest.run()

    print("\n=== [3/6] Phase 0 data validation ===")
    if phase0_validate.run() != 0:
        return 1

    print("\n=== [4/6] L1 compute (computed_metrics) ===")
    phase1_compute.run()

    print("\n=== [5/6] Phase 1 validation ===")
    if phase1_validate.run() != 0:
        return 1

    print("\n=== [6/6] crisis key dates + bands + validation ===")
    phase2_crisis.run()
    if phase2_crisis.validate() != 0:
        return 1

    print("\nDAILY REFRESH: OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
