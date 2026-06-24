#!/usr/bin/env python3
"""
Génère les PDF « Identifiants de connexion » manquants pour Comitech Composite.

Ne réinitialise pas les mots de passe : le PDF indique de contacter les RH ou
d'utiliser « Mot de passe oublié » si le compte existe déjà.

Usage (depuis backend/, venv activé) :
  python scripts/backfill_credentials_pdfs.py
  python scripts/backfill_credentials_pdfs.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from setup_comitech_composite import find_company  # noqa: E402

from app.core.database import supabase
from app.modules.employees.application.credentials_pdf import (
    CREDENTIALS_PASSWORD_UNAVAILABLE,
    find_credentials_pdf_path,
    store_credentials_pdf_for_employee,
)
from app.modules.employees.infrastructure.providers import get_storage_provider


def _list_employees(company_id: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    page_size = 500
    while True:
        resp = (
            supabase.table("employees")
            .select("id, first_name, last_name, company_id, user_id, username, employee_folder_name")
            .eq("company_id", company_id)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def backfill_company(company_id: str, *, dry_run: bool = False) -> dict[str, int]:
    storage = get_storage_provider()
    employees = _list_employees(company_id)
    stats = {"total": len(employees), "skipped": 0, "created": 0, "failed": 0}

    for emp in employees:
        employee_id = str(emp["id"])
        user_id = str(emp.get("user_id") or "").strip() or None
        folder_name = str(emp.get("employee_folder_name") or "").strip() or None
        name = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()

        existing = find_credentials_pdf_path(
            storage,
            company_id,
            employee_id,
            user_id,
            folder_name,
        )
        if existing:
            stats["skipped"] += 1
            continue

        if dry_run:
            print(f"[dry-run] manquant : {name} ({employee_id})")
            stats["created"] += 1
            continue

        path = store_credentials_pdf_for_employee(
            employee_id,
            company_id,
            password=CREDENTIALS_PASSWORD_UNAVAILABLE,
        )
        if path:
            print(f"OK  : {name} → {path}")
            stats["created"] += 1
        else:
            print(f"KO  : {name} ({employee_id})")
            stats["failed"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill PDF identifiants de connexion — Comitech Composite uniquement",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lister les salariés sans PDF sans écrire en storage",
    )
    args = parser.parse_args()

    company = find_company(supabase)
    if not company:
        print(
            "Entreprise Comitech Composite introuvable — "
            "lancer setup_comitech_composite.py d'abord."
        )
        return 1

    company_id = str(company["id"])
    print(f"Entreprise : {company.get('company_name')} ({company_id})")
    if args.dry_run:
        print("Mode dry-run — aucun fichier ne sera créé.\n")

    stats = backfill_company(company_id, dry_run=args.dry_run)
    print(
        f"\nRésumé : {stats['total']} salariés — "
        f"{stats['created']} créés, {stats['skipped']} déjà présents, {stats['failed']} échecs"
    )
    return 0 if stats["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
