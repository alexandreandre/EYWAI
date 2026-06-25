#!/usr/bin/env python3
"""Backfill company_dsn_payroll_totals depuis batches DSN committed."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.dsn_import.application.payroll_totals_persist import (  # noqa: E402
    persist_batch_dsn_payroll_totals,
)
from app.modules.dsn_import.infrastructure import repository as repo  # noqa: E402


def main() -> int:
    batches = repo.list_committed_batches(limit=500)
    total_periods = 0
    for batch in batches:
        batch_id = str(batch["id"])
        items = repo.list_items(batch_id)
        cumul_items = [i for i in items if i.get("item_type") == "cumul"]
        if not cumul_items:
            continue
        company_by_siret: dict[str, str] = {}

        def resolve_company_id(siret: str):
            if siret in company_by_siret:
                return company_by_siret[siret]
            co = repo.find_company_by_siret(siret)
            if co:
                company_by_siret[siret] = str(co["id"])
                return company_by_siret[siret]
            return None

        counts = persist_batch_dsn_payroll_totals(
            cumul_items,
            resolve_company_id=resolve_company_id,
            batch_id=batch_id,
        )
        total_periods += sum(counts.values())
        print(f"Batch {batch_id}: {counts}")

    print(f"Terminé — {total_periods} période(s) upsertées.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
