"""
Schémas de réponse API pour rib_alerts.

Définitions canoniques (ex-routers + frontend ribAlerts.ts). Comportement identique.
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class RibAlertItem(BaseModel):
    """Un item alerte (champs exposés par l’API, alignés sur le .select() du router legacy)."""

    id: str
    company_id: str
    employee_id: Optional[str] = None
    alert_type: str
    severity: str
    title: str
    message: str
    details: Optional[dict[str, Any]] = None
    is_read: bool
    is_resolved: bool
    resolved_at: Optional[str] = None
    resolution_note: Optional[str] = None
    created_at: Optional[str] = None


class RibAlertsListResponse(BaseModel):
    """Réponse GET /api/rib-alerts : { alerts, total }."""

    alerts: List[RibAlertItem]
    total: int


class RibAlertSuccessResponse(BaseModel):
    """Réponse PATCH /read et PATCH /resolve : { success: true }."""

    success: bool = True
