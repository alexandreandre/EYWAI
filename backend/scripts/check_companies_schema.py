#!/usr/bin/env python3
"""
Vérifie que les colonnes companies attendues par Mon Entreprise existent sur Supabase.

Si des colonnes manquent, affiche la migration associée et le lien SQL Editor.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
MIGRATIONS = ROOT / "supabase" / "migrations"

# Colonnes utilisées par PATCH /api/company/details (CompanyDetailsUpdate)
COLUMN_MIGRATIONS: dict[str, str] = {
    "nom_signataire_rh": "20260604120000_company_signatory.sql",
    "qualite_signataire_rh": "20260604120000_company_signatory.sql",
    "service_sante_travail_nom": "20260617120000_companies_service_sante_travail.sql",
    "service_sante_travail_adresse_rue": "20260617120000_companies_service_sante_travail.sql",
    "service_sante_travail_adresse_code_postal": "20260617120000_companies_service_sante_travail.sql",
    "service_sante_travail_adresse_ville": "20260617120000_companies_service_sante_travail.sql",
    "service_sante_travail_telephone": "20260617120000_companies_service_sante_travail.sql",
    "service_sante_travail_email": "20260617120000_companies_service_sante_travail.sql",
    "dsn_sync_mode": "20260616130000_companies_dsn_sync_mode.sql",
}


def _dashboard_sql_url(supabase_url: str) -> str | None:
    match = re.search(r"https://([a-z0-9]+)\.supabase\.co", supabase_url)
    if not match:
        return None
    ref = match.group(1)
    return f"https://supabase.com/dashboard/project/{ref}/sql/new"


def main() -> int:
    sys.path.insert(0, str(BACKEND))
    try:
        from dotenv import load_dotenv

        load_dotenv(BACKEND / ".env")
    except ImportError:
        pass

    from app.core.database import get_supabase_admin_client
    from postgrest.exceptions import APIError

    client = get_supabase_admin_client()
    missing: list[str] = []

    for column in COLUMN_MIGRATIONS:
        try:
            client.table("companies").select(column).limit(1).execute()
            print(f"OK  companies.{column}")
        except APIError as exc:
            if exc.code == "PGRST204":
                missing.append(column)
                print(f"MANQUANT  companies.{column}")
            else:
                print(
                    f"ERREUR  companies.{column}: "
                    f"{exc.json() if hasattr(exc, 'json') else exc}"
                )
                return 2

    if not missing:
        print("\nSchéma companies (Mon Entreprise) présent.")
        return 0

    from app.core.settings import require_supabase_env

    url, _ = require_supabase_env()
    sql_url = _dashboard_sql_url(url)

    migration_files = sorted({COLUMN_MIGRATIONS[c] for c in missing})

    print("\n--- Action requise ---")
    for migration_file in migration_files:
        print(f"Migration : {MIGRATIONS / migration_file}")
    if sql_url:
        print(f"SQL Editor : {sql_url}")
    print(
        "\nAppliquez les migrations manquantes (SQL Editor ou MCP Supabase), "
        "attendez quelques secondes (cache PostgREST), puis relancez :\n"
        "  python backend/scripts/check_companies_schema.py"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
