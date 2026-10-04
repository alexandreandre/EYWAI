"""Supprimer un bulletin ne doit pas emporter l'échéance de prêt ni l'avance.

La migration `employee_delete_cascade` (18/06) a passé toutes les clés vers
`payslips` en cascade : l'échéance réglée par un bulletin disparaissait de
l'échéancier avec lui. La migration du 04/10 les remet en `SET NULL`, seulement
ces deux-là. L'application, elle, détache l'échéance avant de supprimer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "supabase/migrations/20261004120000_bulletin_supprime_garde_echeances_et_avances.sql"
)

CLES = {
    "employee_loan_installments": ("employee_loan_installments_payslip_id_fkey", "payslip_id"),
    "salary_advances": (
        "salary_advances_prime_reconciled_payslip_id_fkey",
        "prime_reconciled_payslip_id",
    ),
}


def _sql_sans_commentaires() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def test_les_deux_cles_repassent_en_set_null_et_la_migration_se_rejoue():
    sql = " ".join(_sql_sans_commentaires().split())
    for table, (contrainte, colonne) in CLES.items():
        retrait = f"ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS {contrainte};"
        ajout = (
            f"ALTER TABLE public.{table} ADD CONSTRAINT {contrainte} FOREIGN KEY ({colonne}) "
            "REFERENCES public.payslips(id) ON DELETE SET NULL;"
        )
        assert retrait in sql and ajout in sql
        assert sql.index(retrait) < sql.index(ajout)


def test_les_lignes_de_retenue_restent_en_cascade():
    sql = _sql_sans_commentaires()
    assert "CASCADE" not in sql
    for table in ("employee_loan_repayments", "salary_advance_repayments", "salary_seizure_deductions"):
        assert table not in sql
