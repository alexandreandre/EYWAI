"""
Résolution evolution_salaire_mois pour la génération de bulletins.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict

from app.core.database import supabase
from app.core.logging import get_logger
from app.modules.employees.application.commands import sync_employee_salaire_actif
from app.modules.employees.domain.salary_timeline import construire_evolution_salaire_mois
from app.modules.employees.infrastructure.repository import EmployeeRepository
from app.modules.payroll.engine.lectures import lire_ou_arreter
from app.modules.payroll.engine.salaire_paye import (
    base_mensuelle_du_bulletin,
    heures_base_mensuelles,
)

logger = get_logger("modules.payroll.application.salary_evolution_payroll")


def _lire_bulletins_anterieurs(employee_id: str, company_id: str) -> list[dict[str, Any]]:
    """Bulletins déjà générés du salarié : période et ce qu'il faut pour relire
    le salaire de base appliqué (paramètres mémorisés, ligne « Salaire de base »)."""
    resp = (
        supabase.table("payslips")
        .select(
            "year, month, parametres:payslip_data->parametres, "
            "calcul_du_brut:payslip_data->calcul_du_brut"
        )
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .execute()
    )
    return resp.data or []


def _bases_des_bulletins(
    employee_id: str, company_id: str, year: int, month: int, duree_hebdo: Any
) -> Dict[tuple[int, int], float] | None:
    """Salaire de base mensuel sur lequel chaque bulletin ANTÉRIEUR a été établi.

    Sert au rappel de salaire : un mois déjà payé au nouveau taux n'est pas
    rappelé (salarié 086, juillet 2026 : 16,69 € rappelés pour un juin déjà payé
    au SMIC revalorisé, et à nouveau chaque mois suivant). Une lecture ratée
    arrête le calcul : sans elle, le rappel repayait des mois déjà payés.
    """
    rows = lire_ou_arreter(
        lambda: _lire_bulletins_anterieurs(employee_id, company_id),
        "Les bulletins précédents du salarié n'ont pas pu être lus",
    )
    heures = heures_base_mensuelles(duree_hebdo)
    bases: Dict[tuple[int, int], float] = {}
    for row in rows:
        try:
            cle = (int(row.get("year")), int(row.get("month")))
        except (TypeError, ValueError):
            continue
        if cle >= (year, month):
            continue
        base = base_mensuelle_du_bulletin(
            {"parametres": row.get("parametres"), "calcul_du_brut": row.get("calcul_du_brut")},
            heures,
        )
        if base:
            bases[cle] = base
    return bases


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
    persister: bool = True,
) -> Dict[str, Any]:
    """
    Synchronise le salaire actif et construit evolution_salaire_mois pour contrat.json.

    En bac à sable (`persister=False`), rien n'est écrit : la fiche relue reçoit
    en mémoire le salaire que la synchronisation y aurait écrit, pour que le
    calcul reste celui d'une vraie génération (spec 2026-09-24).
    """
    repo = EmployeeRepository()
    illisible = "Le salaire du salarié et son historique n'ont pas pu être lus"
    if persister:
        lire_ou_arreter(
            lambda: sync_employee_salaire_actif(employee_id, company_id, date.today()), illisible
        )

    emp = lire_ou_arreter(lambda: repo.get_by_id(employee_id, company_id), illisible)
    if emp is None:
        return {}
    if not persister:
        synchronise = lire_ou_arreter(
            lambda: repo.salaire_de_base_a_date(employee_id, company_id, date.today()), illisible
        )
        if synchronise is not None:
            emp = {**emp, "salaire_de_base": synchronise}

    timeline = lire_ou_arreter(lambda: repo.get_salary_history(employee_id, company_id), illisible)
    fallback = _valeur_salaire(emp.get("salaire_de_base"))
    bases = _bases_des_bulletins(
        employee_id, company_id, year, month, emp.get("duree_hebdomadaire")
    )
    evolution = construire_evolution_salaire_mois(
        timeline, year, month, fallback, bases_des_bulletins=bases
    )

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
