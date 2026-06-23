"""Phase 0 end-to-end: schema -> ingest -> validate.

Idempotent: safe to re-run. Exits non-zero if any validation gate fails.

    python -m pipeline.run_phase0
"""
from __future__ import annotations

import sys

from . import phase0_ingest, phase0_schema, phase0_validate


def main() -> int:
    print("=== Phase 0.1 — schema ===")
    phase0_schema.run()
    print("\n=== Phase 0.2 — ingest ===")
    phase0_ingest.run()
    print("\n=== Phase 0.3 — validate ===")
    rc = phase0_validate.run()
    print("\nPhase 0 " + ("PASSED" if rc == 0 else "FAILED"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
