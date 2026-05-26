#!/usr/bin/env python3
"""
Vérifie que les tables badgeuse existent sur le projet Supabase configuré dans backend/.env.

Si elles manquent, affiche le lien SQL Editor et le chemin de la migration à exécuter.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
MIGRATION = ROOT / "supabase" / "migrations" / "20260525120000_badgeuse_qr.sql"

TABLES = (
    "employee_time_entries",
    "employee_time_entries_validations",
    "employee_badge_credentials",
)


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

    for table in TABLES:
        try:
            client.table(table).select("id").limit(1).execute()
            print(f"OK  {table}")
        except APIError as exc:
            if exc.code == "PGRST205":
                missing.append(table)
                print(f"MANQUANT  {table}")
            else:
                print(f"ERREUR  {table}: {exc.json() if hasattr(exc, 'json') else exc}")
                return 2

    if not missing:
        print("\nSchéma badgeuse présent.")
        return 0

    from app.core.settings import require_supabase_env

    url, _ = require_supabase_env()
    sql_url = _dashboard_sql_url(url)

    print("\n--- Action requise ---")
    print(f"Migration : {MIGRATION}")
    if sql_url:
        print(f"SQL Editor : {sql_url}")
    print(
        "\nCopiez-collez le contenu du fichier SQL dans l'éditeur Supabase, "
        "puis exécutez. Attendez quelques secondes (cache PostgREST), "
        "relancez ce script."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
