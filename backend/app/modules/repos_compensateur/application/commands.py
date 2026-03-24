"""
Commandes applicatives (write) pour repos_compensateur.

Délèguent au ReposCompensateurService. Logique métier dans le service.
Comportement identique aux anciens routeurs / services.
"""
from __future__ import annotations

from app.modules.repos_compensateur.application.dto import CalculerCreditsResult
from app.modules.repos_compensateur.application.service import (
    calculer_credits_repos,
    recalculer_credits_repos_employe,
)


def recalculer_credits_repos_employe_command(
    employee_id: str, company_id: str, year: int
) -> int:
    """
    Recalcule les crédits COR pour un employé sur toute l'année.
    Appelé par payslips / payslip_generator / payslip_editor après création/modification/suppression bulletin.
    """
    return recalculer_credits_repos_employe(employee_id, company_id, year)


def calculer_credits_repos_command(
    year: int,
    month: int,
    target_company_id: str,
) -> CalculerCreditsResult:
    """
    Calcule les crédits COR pour tous les employés de l'entreprise sur le mois donné.
    Le router fournit target_company_id (company_id ou active_company_id) après validation.
    """
    return calculer_credits_repos(
        year=year,
        month=month,
        target_company_id=target_company_id,
    )
