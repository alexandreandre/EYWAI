# app/modules/medical_follow_up/api/router.py
"""
Router du module Suivi médical.

Préfixe attendu à l’inclusion : /api/medical-follow-up.
Appelle uniquement la couche application (queries, commands, service).
Aucune logique métier ni accès DB. Comportement HTTP identique au legacy.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.modules.medical_follow_up.application import commands, queries
from app.modules.medical_follow_up.application.dto import ObligationListDTO
from app.modules.medical_follow_up.application.service import (
    ensure_module_enabled,
    ensure_rh_access,
    resolve_company_id_for_medical,
)
from app.modules.medical_follow_up.schemas import (
    CreateOnDemandBody,
    KPIsResponse,
    MarkCompletedBody,
    MarkPlanifiedBody,
    ObligationListItem,
    SettingsResponse,
)
from app.modules.users.schemas.responses import User

router = APIRouter(tags=["Medical Follow-up"])


def _company_id_rh(current_user: User = Depends(get_current_user)) -> str:
    """Dépendance : module activé + accès RH ; retourne company_id."""
    company_id = ensure_module_enabled(current_user)
    ensure_rh_access(current_user, company_id)
    return company_id


def _to_list_item(d: ObligationListDTO) -> ObligationListItem:
    """Conversion DTO → schéma de réponse (sans logique métier)."""
    return ObligationListItem(
        id=d.id,
        company_id=d.company_id,
        employee_id=d.employee_id,
        visit_type=d.visit_type,
        trigger_type=d.trigger_type,
        due_date=d.due_date,
        priority=d.priority,
        status=d.status,
        justification=d.justification,
        planned_date=d.planned_date,
        completed_date=d.completed_date,
        rule_source=d.rule_source,
        collective_agreement_idcc=d.collective_agreement_idcc,
        request_motif=d.request_motif,
        request_date=d.request_date,
        employee_first_name=d.employee_first_name,
        employee_last_name=d.employee_last_name,
    )


# --- GET /obligations (liste avec filtres, RH)
@router.get("/obligations", response_model=List[ObligationListItem])
def list_obligations(
    employee_id: Optional[str] = Query(None),
    visit_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[int] = Query(None),
    due_from: Optional[str] = Query(None),
    due_to: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Liste des obligations avec filtres. Réservé RH."""
    return [
        _to_list_item(d)
        for d in queries.list_obligations(
            company_id,
            current_user,
            employee_id=employee_id,
            visit_type=visit_type,
            status=status,
            priority=priority,
            due_from=due_from,
            due_to=due_to,
        )
    ]


# --- GET /kpis (RH)
@router.get("/kpis", response_model=KPIsResponse)
def get_kpis(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """KPIs : en retard, à échéance < 30 j, total actives, réalisées ce mois."""
    kpis = queries.get_kpis(company_id, current_user)
    return KPIsResponse(
        overdue_count=kpis.overdue_count,
        due_within_30_count=kpis.due_within_30_count,
        active_total=kpis.active_total,
        completed_this_month=kpis.completed_this_month,
    )


# --- PATCH /obligations/{obligation_id}/planified
@router.patch("/obligations/{obligation_id}/planified")
def mark_planified(
    obligation_id: str,
    body: MarkPlanifiedBody,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Marquer une obligation comme planifiée."""
    return commands.mark_planified(obligation_id, body, company_id, current_user)


# --- PATCH /obligations/{obligation_id}/completed
@router.patch("/obligations/{obligation_id}/completed")
def mark_completed(
    obligation_id: str,
    body: MarkCompletedBody,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Marquer une obligation comme réalisée."""
    return commands.mark_completed(obligation_id, body, company_id, current_user)


# --- POST /obligations/on-demand
@router.post("/obligations/on-demand")
def create_on_demand(
    body: CreateOnDemandBody,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Créer une obligation « visite à la demande »."""
    return commands.create_on_demand(body, company_id, current_user)


# --- GET /obligations/employee/{employee_id} (RH)
@router.get(
    "/obligations/employee/{employee_id}", response_model=List[ObligationListItem]
)
def list_obligations_for_employee(
    employee_id: str,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(_company_id_rh),
):
    """Obligations d'un collaborateur (fiche collaborateur). Réservé RH."""
    return [
        _to_list_item(d)
        for d in queries.list_obligations_for_employee(
            company_id,
            employee_id,
            current_user,
        )
    ]


# --- GET /me (obligations du collaborateur connecté)
@router.get("/me", response_model=List[ObligationListItem])
def my_obligations(current_user: User = Depends(get_current_user)):
    """Obligations du collaborateur connecté (espace « Mon suivi médical »)."""
    return [
        _to_list_item(d) for d in queries.get_my_obligations_with_guards(current_user)
    ]


# --- GET /settings
@router.get("/settings", response_model=SettingsResponse)
def get_medical_settings(current_user: User = Depends(get_current_user)):
    """Indique si le module est activé pour l'entreprise active (pour le front)."""
    company_id = resolve_company_id_for_medical(current_user)
    result = queries.get_medical_settings(company_id, current_user)
    return SettingsResponse(enabled=result["enabled"])
