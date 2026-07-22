"""Importe les participations 2025 depuis les saisies existantes, pour les 5
sociétés de backtest concernées.

Usage (depuis backend/) :
    DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/python \
        scripts/import_participation_2025.py --dry-run
    DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/python \
        scripts/import_participation_2025.py

Idempotent : relancer sans --force ne duplique rien (skip les campagnes déjà
importées). Voir docs/superpowers/specs/2026-07-22-import-participations-saisies-existantes-design.md.
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from app.core.database import supabase  # noqa: E402
from app.modules.participation.application.campaign_import_service import (  # noqa: E402
    import_campaign_from_inputs,
)

YEAR = 2025
PAYROLL_YEAR = 2026
PAYROLL_MONTH = 5

COMPANY_NAMES = [
    "Mont Blanc Composite",
    "Cartol Industrie",
    "LEWIS",
    "Comitech Composite",
    "Colorplast",
]


def _resolve_company_ids() -> dict[str, str]:
    rows = (
        supabase.table("companies")
        .select("id, company_name")
        .in_("company_name", COMPANY_NAMES)
        .execute()
        .data
        or []
    )
    found = {r["company_name"]: r["id"] for r in rows}
    missing = set(COMPANY_NAMES) - set(found)
    if missing:
        raise SystemExit(f"Sociétés introuvables : {missing}")
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    companies = _resolve_company_ids()
    total_bulletins = 0
    for name in COMPANY_NAMES:
        company_id = companies[name]
        result = import_campaign_from_inputs(
            company_id,
            YEAR,
            PAYROLL_YEAR,
            PAYROLL_MONTH,
            dry_run=args.dry_run,
            force=args.force,
        )
        total_bulletins += result.bulletins
        print(
            f"{name:22s} campaign={result.campaign_id} bulletins={result.bulletins:3d} "
            f"(cash={result.full_cash} mixte={result.partial_cash} pee={result.full_pee}) "
            f"linked={result.linked_inputs} skipped={result.skipped} — {result.detail}"
        )
    print(f"\nTOTAL bulletins: {total_bulletins}")


if __name__ == "__main__":
    main()
