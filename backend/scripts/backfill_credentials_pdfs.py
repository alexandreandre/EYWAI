#!/usr/bin/env python3
"""
Crée/répare les comptes collaborateurs et leurs PDF « Identifiants de connexion ».

Pour chaque salarié ciblé :
- sans compte Auth : crée le compte, le profil, l'accès entreprise et le PDF ;
- avec compte Auth : régénère un mot de passe temporaire et remplace le PDF.

Usage (depuis backend/, venv activé) :
  python scripts/backfill_credentials_pdfs.py
  python scripts/backfill_credentials_pdfs.py --company-id <uuid>
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

from app.core.database import supabase
from app.modules.employees.application.account_provisioning import (
    provision_collaborator_account,
    reset_collaborator_credentials,
)
from app.modules.employees.application.credentials_pdf import (
    _is_unavailable_password_pdf,
    find_credentials_pdf_path,
)
from app.modules.employees.infrastructure.providers import get_storage_provider


def _list_companies(company_id: str | None = None) -> list[dict]:
    query = supabase.table("companies").select("id, company_name, raison_sociale")
    if company_id:
        query = query.eq("id", company_id)
    resp = query.order("company_name").execute()
    return [dict(row) for row in (resp.data or [])]


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
        has_bad_pdf = bool(
            user_id
            and existing
            and _is_unavailable_password_pdf(storage, existing)
        )

        if user_id and existing and not has_bad_pdf:
            stats["skipped"] += 1
            continue

        if dry_run:
            action = (
                "remplacer PDF incomplet"
                if has_bad_pdf
                else "créer compte + PDF"
            )
            print(f"[dry-run] {action} : {name} ({employee_id})")
            stats["created"] += 1
            continue

        try:
            result = (
                reset_collaborator_credentials(employee_id, company_id)
                if has_bad_pdf
                else provision_collaborator_account(employee_id, company_id)
            )
            path = result.get("credentials_pdf_path")
            print(f"OK  : {name} → {path}")
            stats["created"] += 1
        except Exception as exc:
            print(f"KO  : {name} ({employee_id}) — {exc}")
            stats["failed"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill comptes collaborateurs + PDF identifiants de connexion",
    )
    parser.add_argument(
        "--company-id",
        help="Limiter le rattrapage à une entreprise précise",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lister les salariés sans PDF sans écrire en storage",
    )
    args = parser.parse_args()

    companies = _list_companies(args.company_id)
    if not companies:
        print("Aucune entreprise trouvée pour ce périmètre.")
        return 1

    total = {"total": 0, "created": 0, "skipped": 0, "failed": 0}
    if args.dry_run:
        print("Mode dry-run — aucun fichier ne sera créé.\n")

    for company in companies:
        company_id = str(company["id"])
        name = company.get("company_name") or company.get("raison_sociale") or "Entreprise"
        print(f"\nEntreprise : {name} ({company_id})")
        stats = backfill_company(company_id, dry_run=args.dry_run)
        for key in total:
            total[key] += stats[key]
        print(
            f"Résumé entreprise : {stats['total']} salariés — "
            f"{stats['created']} réparés, {stats['skipped']} ignorés, {stats['failed']} échecs"
        )

    print(
        f"\nRésumé global : {total['total']} salariés — "
        f"{total['created']} réparés, {total['skipped']} ignorés, {total['failed']} échecs"
    )
    return 0 if total["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
