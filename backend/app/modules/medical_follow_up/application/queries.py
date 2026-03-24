# app/modules/medical_follow_up/application/queries.py
"""
Requêtes du module suivi médical : liste obligations, KPIs, obligations par employé, « moi », settings.

Délègue à l’infrastructure (repository) et au service (provider, compute_obligations).
Comportement identique au legacy.
"""

from typing import Any, List, Optional

from fastapi import HTTPException

from app.modules.medical_follow_up.application.dto import KPIsDTO, ObligationListDTO
from app.modules.medical_follow_up.application.service import (
    compute_obligations_for_employee,
    get_company_medical_setting,
    get_obligation_repository,
    resolve_company_id_for_medical,
)


def list_obligations(
    company_id: str,
    current_user: Any,
    employee_id: Optional[str] = None,
    visit_type: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[int] = None,
    due_from: Optional[str] = None,
    due_to: Optional[str] = None,
) -> List[ObligationListDTO]:
    """Liste des obligations avec filtres (RH). Comportement identique au legacy."""
    repo = get_obligation_repository()
    rows = repo.list_for_company(
        company_id,
        employee_id=employee_id,
        visit_type=visit_type,
        status=status,
        priority=priority,
        due_from=due_from,
        due_to=due_to,
    )
    return [ObligationListDTO.from_row(r) for r in rows]


def get_kpis(company_id: str, current_user: Any) -> KPIsDTO:
    """KPIs : en retard, à échéance < 30 j, total actives, réalisées ce mois. Comportement identique au legacy."""
    repo = get_obligation_repository()
    data = repo.get_kpis(company_id)
    return KPIsDTO(
        overdue_count=data["overdue_count"],
        due_within_30_count=data["due_within_30_count"],
        active_total=data["active_total"],
        completed_this_month=data["completed_this_month"],
    )


def list_obligations_for_employee(
    company_id: str,
    employee_id: str,
    current_user: Any,
) -> List[ObligationListDTO]:
    """Obligations d’un collaborateur (fiche RH). Vérifie employé, recalcule obligations, puis liste. Comportement identique au legacy."""
    repo = get_obligation_repository()
    if not repo.employee_exists(employee_id, company_id):
        raise HTTPException(status_code=404, detail="Salarié non trouvé")
    compute_obligations_for_employee(company_id, employee_id)
    rows = repo.list_for_employee(company_id, employee_id)
    return [ObligationListDTO.from_row(r) for r in rows]


def my_obligations(company_id: str, current_user: Any) -> List[ObligationListDTO]:
    """Obligations du collaborateur connecté (espace « Mon suivi médical »). Comportement identique au legacy."""
    repo = get_obligation_repository()
    employee_id = repo.get_employee_id_by_user_id(str(current_user.id), company_id)
    if not employee_id:
        raise HTTPException(status_code=404, detail="Profil collaborateur non trouvé")
    compute_obligations_for_employee(company_id, employee_id)
    rows = repo.list_for_employee_no_join(company_id, employee_id)
    return [ObligationListDTO.from_row(r) for r in rows]


def get_medical_settings(company_id: Optional[str], current_user: Any) -> dict:
    """Indique si le module est activé pour l’entreprise active. Retourne {"enabled": bool}. Comportement identique au legacy."""
    if not company_id:
        return {"enabled": False}
    return {"enabled": get_company_medical_setting(company_id)}


def get_my_obligations_with_guards(current_user: Any) -> List[ObligationListDTO]:
    """
    Obligations du collaborateur connecté (/me) avec gardes : 400 si pas d’entreprise, 403 si module désactivé.
    Lève HTTPException côté application ; le router n’a qu’à appeler et retourner.
    """
    from fastapi import HTTPException

    company_id = resolve_company_id_for_medical(current_user)
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not get_company_medical_setting(company_id):
        raise HTTPException(status_code=403, detail="Module suivi médical non activé")
    return my_obligations(company_id, current_user)
