"""Lit les bulletins déjà générés d'un mois et en fait la revue. Personne n'est recalculé."""

from __future__ import annotations

from app.core.database import supabase
from app.modules.employees.application.queries import get_employees_summary
from app.modules.payslips.domain.revue_du_mois import (
    RevueDunSalarie,
    personnes_a_relire,
    revue_du_mois,
)


def lire_revue_du_mois(company_id: str, annee: int, mois: int) -> list[RevueDunSalarie]:
    salaries = get_employees_summary(company_id, payroll_ready_only=True)
    lus = (
        supabase.table("payslips")
        .select("id, employee_id, payslip_data, updated_at")
        .eq("company_id", company_id)
        .eq("year", annee)
        .eq("month", mois)
        .execute()
    )
    return revue_du_mois(personnes_a_relire(salaries, list(lus.data or [])))
