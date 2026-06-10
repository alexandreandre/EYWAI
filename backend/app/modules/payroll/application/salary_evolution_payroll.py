"""
Résolution evolution_salaire_mois pour la génération de bulletins.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict

from app.modules.employees.application.commands import sync_employee_salaire_actif
from app.modules.employees.domain.salary_timeline import construire_evolution_salaire_mois
from app.modules.employees.infrastructure.repository import EmployeeRepository


def _valeur_salaire(salaire_de_base: Any) -> float:
    if isinstance(salaire_de_base, dict):
        try:
            return float(salaire_de_base.get("valeur") or 0)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(salaire_de_base or 0)
    except (TypeError, ValueError):
        return 0.0


def prepare_salary_evolution_for_payslip(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
) -> Dict[str, Any]:
    """
    Synchronise le salaire actif et construit evolution_salaire_mois pour contrat.json.
    """
    repo = EmployeeRepository()
    sync_employee_salaire_actif(employee_id, company_id, date.today())

    emp = repo.get_by_id(employee_id, company_id)
    if emp is None:
        return {}

    timeline = repo.get_salary_history(employee_id, company_id)
    fallback = _valeur_salaire(emp.get("salaire_de_base"))
    evolution = construire_evolution_salaire_mois(timeline, year, month, fallback)

    prorata = evolution.get("prorata")
    salaire_contrat = (
        float(prorata["montant_mois"])
        if prorata
        else float(evolution["salaire_fin_mois"])
    )

    sb = emp.get("salaire_de_base")
    if isinstance(sb, dict):
        salaire_payload = dict(sb)
        salaire_payload["valeur"] = salaire_contrat
    else:
        salaire_payload = {"valeur": salaire_contrat}

    return {
        "salaire_de_base": salaire_payload,
        "evolution_salaire_mois": evolution,
    }


__all__ = ["prepare_salary_evolution_for_payslip"]
