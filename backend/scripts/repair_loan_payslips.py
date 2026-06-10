#!/usr/bin/env python3
"""
Rattrapage enrichissement prêts employeur sur bulletins déjà générés.

Usage (depuis backend/) :
  python scripts/repair_loan_payslips.py
  python scripts/repair_loan_payslips.py --employee-id UUID --year 2026 --month 7
  python scripts/repair_loan_payslips.py --dry-run

Repère les bulletins sans remboursements_prets alors qu'un prêt actif a une
échéance partial/pending collectible, puis ré-applique enrich_payslip_loans.

Prérequis : migration 20260610260000_employee_loan_installment_partial.sql appliquée.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase
from app.modules.employee_loans.application.enrichment import enrich_payslip_loans
from app.modules.employee_loans.infrastructure.payroll_queries import (
    get_unsettled_installments_for_payroll,
)


def _needs_repair(payslip: dict) -> bool:
    pd = payslip.get("payslip_data") or {}
    rp = pd.get("remboursements_prets") or {}
    if rp.get("total_rembourse", 0) > 0:
        return False
    employee_id = payslip["employee_id"]
    year = payslip["year"]
    month = payslip["month"]
    due = get_unsettled_installments_for_payroll(employee_id, year, month)
    return len(due) > 0


def repair_payslip(payslip: dict, *, dry_run: bool = False, force: bool = False) -> bool:
    payslip_id = payslip["id"]
    employee_id = payslip["employee_id"]
    year = payslip["year"]
    month = payslip["month"]
    pd = dict(payslip.get("payslip_data") or {})

    if not force and not _needs_repair(payslip):
        return False

    if force or (pd.get("remboursements_prets") or {}).get("total_rembourse", 0) > 0:
        old_total = Decimal(str((pd.get("remboursements_prets") or {}).get("total_rembourse", 0)))
        if old_total > 0:
            pd["net_a_payer"] = float(
                Decimal(str(pd.get("net_a_payer", 0))) + old_total
            )
        pd.pop("remboursements_prets", None)

    if dry_run:
        print(
            f"[dry-run] Would repair payslip {payslip_id} "
            f"emp={employee_id} {year}-{month:02d}"
        )
        return True

    enriched = enrich_payslip_loans(
        pd, employee_id, year, month, payslip_id=payslip_id
    )
    supabase.table("payslips").update({"payslip_data": enriched}).eq(
        "id", payslip_id
    ).execute()

    total = (enriched.get("remboursements_prets") or {}).get("total_rembourse", 0)
    print(
        f"Repaired payslip {payslip_id} emp={employee_id} "
        f"{year}-{month:02d} → remboursement {total:.2f} €"
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Rattrapage prêts sur bulletins")
    parser.add_argument("--employee-id", help="Filtrer par employé")
    parser.add_argument("--year", type=int, help="Filtrer par année")
    parser.add_argument("--month", type=int, help="Filtrer par mois")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ré-enrichir même si remboursements_prets déjà présents",
    )
    args = parser.parse_args()

    query = supabase.table("payslips").select(
        "id, employee_id, year, month, payslip_data"
    )
    if args.employee_id:
        query = query.eq("employee_id", args.employee_id)
    if args.year:
        query = query.eq("year", args.year)
    if args.month:
        query = query.eq("month", args.month)

    res = query.order("year").order("month").execute()
    payslips = res.data or []

    repaired = 0
    for payslip in payslips:
        if repair_payslip(payslip, dry_run=args.dry_run, force=args.force):
            repaired += 1

    print(f"Done: {repaired} bulletin(s) {'à réparer' if args.dry_run else 'réparé(s)'}.")


if __name__ == "__main__":
    main()
