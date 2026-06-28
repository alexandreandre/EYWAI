#!/usr/bin/env python3
"""Backfill company_dsn_payroll_totals depuis batches DSN committed."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.dsn_import.application.payroll_totals_recompute import (  # noqa: E402
    recompute_committed_batches,
)


def main() -> int:
    report = recompute_committed_batches(
        search_dirs=[REPO_ROOT, REPO_ROOT / "data" / "dsn"],
        limit=500,
        prefer_dsn_file=True,
    )
    total_periods = report["periods_upserted"]
    for detail in report["details"]:
        print(f"Batch {detail['batch_id']}: {detail['counts']} ({detail['source']})")

    print(f"Terminé — {total_periods} période(s) upsertées.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
