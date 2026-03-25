"""
Router API rib_alerts : délégation à la couche application uniquement.

Aucune logique métier : validation entrée (FastAPI), appel application, mapping exceptions → HTTP.
Comportement HTTP identique au legacy (403, 404, 500).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.rib_alerts.application.commands import (
    mark_rib_alert_read,
    resolve_rib_alert,
)
from app.modules.rib_alerts.application.dto import RibAlertListFilters
from app.modules.rib_alerts.application.queries import get_rib_alerts
from app.modules.rib_alerts.domain.exceptions import MissingCompanyContextError
from app.modules.rib_alerts.schemas import (
    RibAlertResolve,
    RibAlertsListResponse,
    RibAlertSuccessResponse,
)
from app.modules.users.schemas.responses import User

router = APIRouter(
    prefix="/api/rib-alerts",
    tags=["RIB Alerts"],
)


@router.get("", response_model=RibAlertsListResponse)
def list_rib_alerts(
    is_read: Optional[bool] = Query(None, description="Filtrer par statut lu"),
    is_resolved: Optional[bool] = Query(None, description="Filtrer par statut résolu"),
    alert_type: Optional[str] = Query(None, description="rib_modified | rib_duplicate"),
    employee_id: Optional[str] = Query(None, description="Filtrer par employé"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """Liste les alertes RIB de l'entreprise active."""
    try:
        filters = RibAlertListFilters(
            is_read=is_read,
            is_resolved=is_resolved,
            alert_type=alert_type,
            employee_id=employee_id,
            limit=limit,
            offset=offset,
        )
        result = get_rib_alerts(
            company_id=current_user.active_company_id, filters=filters
        )
        return RibAlertsListResponse(alerts=result.alerts, total=result.total)
    except MissingCompanyContextError:
        raise HTTPException(status_code=403, detail="Aucune entreprise active.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")


@router.patch("/{alert_id}/read", response_model=RibAlertSuccessResponse)
def patch_mark_rib_alert_read(
    alert_id: str,
    current_user: User = Depends(get_current_user),
):
    """Marque une alerte RIB comme lue."""
    try:
        ok = mark_rib_alert_read(
            alert_id=alert_id, company_id=current_user.active_company_id
        )
    except MissingCompanyContextError:
        raise HTTPException(status_code=403, detail="Aucune entreprise active.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")
    if not ok:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")
    return RibAlertSuccessResponse()


@router.patch("/{alert_id}/resolve", response_model=RibAlertSuccessResponse)
def patch_resolve_rib_alert(
    alert_id: str,
    body: RibAlertResolve,
    current_user: User = Depends(get_current_user),
):
    """Marque une alerte RIB comme résolue."""
    try:
        ok = resolve_rib_alert(
            alert_id=alert_id,
            company_id=current_user.active_company_id,
            resolved_by=current_user.id,
            resolution_note=body.resolution_note,
        )
    except MissingCompanyContextError:
        raise HTTPException(status_code=403, detail="Aucune entreprise active.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")
    if not ok:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")
    return RibAlertSuccessResponse()
