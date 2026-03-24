"""
Schémas de requête API pour rib_alerts.

Définitions canoniques (ex-routers : api/routers/rib_alerts). Comportement identique.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RibAlertListParams(BaseModel):
    """Paramètres de requête pour GET /api/rib-alerts (query params)."""

    is_read: Optional[bool] = Field(None, description="Filtrer par statut lu")
    is_resolved: Optional[bool] = Field(None, description="Filtrer par statut résolu")
    alert_type: Optional[str] = Field(None, description="rib_modified | rib_duplicate")
    employee_id: Optional[str] = Field(None, description="Filtrer par employé")
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class RibAlertResolve(BaseModel):
    """Body pour PATCH /api/rib-alerts/{alert_id}/resolve. Comportement identique au schéma legacy inline."""

    resolution_note: Optional[str] = None
