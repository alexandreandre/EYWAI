"""Routes du code PCS-ESE : la liste officielle et la proposition de Martine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.access_control.application.service import access_control_service
from app.modules.pcs_ese.application import queries
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/pcs-ese", tags=["PcsEse"])


@router.get("/referentiel")
def get_referentiel(current_user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """Les 430 codes de la table DSN, avec les métiers Insee de chacun (donnée publique)."""
    return queries.referentiel_pour_ecran()


@router.get("/proposition")
def get_proposition(
    poste: str = Query(""),
    statut: str = Query(""),
    employee_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Le code que Martine propose pour ce poste et ce statut, dans la société active."""
    if not current_user.active_company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    cid = str(current_user.active_company_id)
    if not current_user.is_platform_admin and not current_user.has_rh_access_in_company(cid):
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs et RH")
    if employee_id:
        access_control_service.assert_employee_in_company(cid, employee_id)
    return queries.proposition_en_dict(queries.proposition_pour(cid, poste, statut, employee_id))
