#!/usr/bin/env python3
"""
Import one-shot des dépôts CET depuis un CSV export Notion.

Colonnes : email_ou_matricule;date;days (séparateur ; ou ,)

Usage :
  python backend/scripts/import_cet_notion_csv.py --company-id UUID --csv file.csv [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase
from app.modules.cet.infrastructure import repository as cet_repo


def _resolve_employee(company_id: str, key: str) -> str | None:
    key = key.strip()
    for field in ("email", "employee_number"):
        q = (
            supabase.table("employees")
            .select("id")
            .eq("company_id", company_id)
            .eq(field, key)
            .limit(1)
            .execute()
        )
        if q.data:
            return str(q.data[0]["id"])
    return None


def import_rows(company_id: str, csv_path: Path, *, dry_run: bool) -> None:
    text = csv_path.read_text(encoding="utf-8-sig")
    delimiter = ";" if ";" in text.splitlines()[0] else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)

    inserted = 0
    skipped = 0
    for row in reader:
        employee_key = (
            row.get("email_ou_matricule")
            or row.get("email")
            or row.get("salarié")
            or row.get("Salarié")
            or ""
        )
        employee_id = _resolve_employee(company_id, employee_key)
        if not employee_id:
            print(f"SKIP: employé introuvable pour {employee_key!r}")
            skipped += 1
            continue
        days = float(row.get("days") or row.get("nombre_de_jour") or row.get("jours") or 0)
        date_str = row.get("date") or row.get("date_de_depot") or row.get("Date de dépôt") or ""
        dt = (
            datetime.fromisoformat(date_str.strip()[:10])
            if date_str.strip()
            else datetime.now()
        )
        payload = {
            "employee_id": employee_id,
            "company_id": company_id,
            "year": dt.year,
            "month": dt.month,
            "movement_type": "deposit_cp",
            "days": days,
            "status": "applied_payroll",
            "workflow_step": "approved_rh",
            "note": "Import Notion",
        }
        if dry_run:
            print(f"DRY-RUN insert {payload}")
        else:
            cet_repo.insert_movement(payload)
        inserted += 1
    print(f"Terminé : {inserted} ligne(s), {skipped} ignorée(s).")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    import_rows(args.company_id, args.csv, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
