"""
La lecture directe des contrats passés et des profils BOETH est réservée à la RH.

Le serveur lit ces tables avec la clé de service : la policy ne protège que
l'accès direct par l'API Supabase, avec le jeton d'un utilisateur. Un salarié
(rôle `collaborateur`) ne doit pas y lire les données de ses collègues.

La migration n'est jamais appliquée par la suite de tests : ce test fige le
contrat du fichier SQL que le déploiement appliquera.
"""

from __future__ import annotations

import re
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "supabase" / "migrations"

_TABLES = (
    "employee_contract_periods",
    "employee_boeth_profiles",
    "employee_boeth_status_history",
)


def _migration_text() -> str:
    candidates = sorted(_MIGRATIONS_DIR.glob("*_lecture_rh_contrats_et_boeth.sql"))
    assert len(candidates) == 1, f"Migration attendue une fois : {candidates}"
    return candidates[0].read_text(encoding="utf-8")


def _policy_select(sql: str, table: str) -> str:
    match = re.search(
        rf"CREATE POLICY {table}_select ON public\.{table}(.*?);",
        sql,
        flags=re.DOTALL,
    )
    assert match, f"Policy de lecture absente pour {table}"
    return match.group(1)


def test_chaque_table_remplace_sa_policy_de_lecture():
    sql = _migration_text()
    for table in _TABLES:
        assert f"DROP POLICY IF EXISTS {table}_select ON public.{table};" in sql


def test_la_lecture_exige_un_role_rh():
    sql = _migration_text()
    for table in _TABLES:
        policy = _policy_select(sql, table)
        assert "FOR SELECT TO authenticated" in policy
        assert "uca.role IN ('admin', 'rh', 'collaborateur_rh')" in policy
        assert "collaborateur'" not in policy.replace("collaborateur_rh'", "")
