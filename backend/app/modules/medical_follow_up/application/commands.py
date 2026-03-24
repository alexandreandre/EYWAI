# app/modules/medical_follow_up/application/commands.py
"""
Commandes du module suivi médical : marquer planifiée, marquer réalisée, créer à la demande.

Délègue à l’infrastructure (repository). Comportement identique au legacy.
"""

from typing import Any

from fastapi import HTTPException

from app.modules.medical_follow_up.application.service import get_obligation_repository
from app.modules.medical_follow_up.schemas.requests import (
    CreateOnDemandBody,
    MarkCompletedBody,
    MarkPlanifiedBody,
)


def mark_planified(
    obligation_id: str,
    body: MarkPlanifiedBody,
    company_id: str,
    current_user: Any,
) -> dict:
    """Marque une obligation comme planifiée. 404 si obligation non trouvée. Comportement identique au legacy."""
    repo = get_obligation_repository()
    if not repo.obligation_exists(obligation_id, company_id):
        raise HTTPException(status_code=404, detail="Obligation non trouvée")
    repo.mark_planified(
        obligation_id, company_id, body.planned_date, body.justification
    )
    return {"ok": True}


def mark_completed(
    obligation_id: str,
    body: MarkCompletedBody,
    company_id: str,
    current_user: Any,
) -> dict:
    """Marque une obligation comme réalisée. 404 si obligation non trouvée. Comportement identique au legacy."""
    repo = get_obligation_repository()
    if not repo.obligation_exists(obligation_id, company_id):
        raise HTTPException(status_code=404, detail="Obligation non trouvée")
    repo.mark_completed(
        obligation_id, company_id, body.completed_date, body.justification
    )
    return {"ok": True}


def create_on_demand(
    body: CreateOnDemandBody,
    company_id: str,
    current_user: Any,
) -> dict:
    """Crée une obligation « visite à la demande ». 404 si salarié non trouvé. Comportement identique au legacy."""
    repo = get_obligation_repository()
    if not repo.employee_exists(body.employee_id, company_id):
        raise HTTPException(status_code=404, detail="Salarié non trouvé")
    repo.create_on_demand(
        company_id,
        body.employee_id,
        body.request_motif,
        body.request_date,
    )
    return {"ok": True}
