# app/modules/medical_follow_up/schemas/responses.py
"""Schémas de réponse pour le module suivi médical (comportement identique au legacy)."""

from typing import Optional

from pydantic import BaseModel


class ObligationListItem(BaseModel):
    """Une obligation de suivi médical (liste / détail)."""

    id: str
    company_id: str
    employee_id: str
    visit_type: str
    trigger_type: str
    due_date: str
    priority: int
    status: str
    justification: Optional[str] = None
    planned_date: Optional[str] = None
    completed_date: Optional[str] = None
    rule_source: str
    collective_agreement_idcc: Optional[str] = None
    request_motif: Optional[str] = None
    request_date: Optional[str] = None
    employee_first_name: Optional[str] = None
    employee_last_name: Optional[str] = None


class KPIsResponse(BaseModel):
    """Indicateurs suivi médical (en retard, à échéance < 30 j, total actives, réalisées ce mois)."""

    overdue_count: int
    due_within_30_count: int
    active_total: int
    completed_this_month: int


class SettingsResponse(BaseModel):
    """Réponse GET /settings : module activé ou non pour l'entreprise active."""

    enabled: bool
