"""
Task 1 (lien d'activation) : la migration employee_activation_tokens existe
et déclare le contrat attendu (colonnes, RLS sans policy publique, index).

La migration n'est jamais appliquée par la suite de tests (Supabase moqué) :
ce test fige le contrat du fichier SQL que le déploiement appliquera.
"""

from __future__ import annotations

import re
from pathlib import Path

_MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[4] / "supabase" / "migrations"
)


def _migration_text() -> str:
    candidates = sorted(
        _MIGRATIONS_DIR.glob("*_employee_activation_tokens.sql")
    )
    assert candidates, (
        "Aucune migration *_employee_activation_tokens.sql dans "
        f"{_MIGRATIONS_DIR}"
    )
    assert len(candidates) == 1, f"Migrations en double : {candidates}"
    return candidates[0].read_text(encoding="utf-8")


class TestMigrationEmployeeActivationTokens:
    def test_table_et_colonnes(self):
        sql = _migration_text()
        assert "CREATE TABLE IF NOT EXISTS public.employee_activation_tokens" in sql
        for fragment in (
            "employee_id",
            "company_id",
            "token_hash",
            "email_envoye",
            "expires_at",
            "used_at",
            "invalidated_at",
            "created_by",
            "created_at",
        ):
            assert fragment in sql, f"colonne absente : {fragment}"
        # Références d'intégrité vers employees et companies.
        assert re.search(r"REFERENCES\s+public\.employees\s*\(id\)", sql)
        assert re.search(r"REFERENCES\s+public\.companies\s*\(id\)", sql)
        # Le jeton n'est jamais stocké en clair : seule l'empreinte, unique.
        assert re.search(r"token_hash\s+text\s+NOT\s+NULL\s+UNIQUE", sql)

    def test_rls_sans_policy_publique(self):
        sql = _migration_text()
        assert (
            "ALTER TABLE public.employee_activation_tokens ENABLE ROW LEVEL SECURITY"
            in sql
        )
        # Accès service uniquement : aucun droit anon/authenticated, aucune policy.
        assert re.search(
            r"REVOKE\s+ALL\s+ON\s+public\.employee_activation_tokens\s+"
            r"FROM\s+anon,\s*authenticated",
            sql,
        )
        assert "CREATE POLICY" not in sql

    def test_index_employee_id(self):
        sql = _migration_text()
        assert re.search(
            r"CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+\S+\s+"
            r"ON\s+public\.employee_activation_tokens\s*\(employee_id\)",
            sql,
        )


def test_migration_lien_partage_ajoute_la_colonne():
    sql = (
        _MIGRATIONS_DIR / "20260828000000_activation_lien_partage.sql"
    ).read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS lien_partage" in sql
    assert "idx_employee_activation_tokens_lien_partage" in sql
