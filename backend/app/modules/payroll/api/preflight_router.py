"""Router API — Revue des anomalies pré-paie."""

from __future__ import annotations

import traceback

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.access_control.application.service import access_control_service
from app.modules.payroll.application import preflight_anomalies
from app.modules.payroll.domain.permissions import PAYROLL_ANALYTICS_VIEW
from app.modules.payroll.schemas.preflight_requests import (
    PreflightAcknowledgeRequest,
    PreflightResolutionDeleteRequest,
    PreflightResolutionRequest,
)
from app.modules.payroll.schemas.preflight_responses import PreflightAnomaliesResponse
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/payroll", tags=["Revue pré-paie"])


def _require_payroll_preflight_access(current_user: User) -> str:
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active.")
    cid = str(company_id)
    if current_user.is_platform_admin:
        return cid
    role = current_user.get_role_in_company(cid)
    if role in ("admin", "rh", "collaborateur_rh"):
        if current_user.has_rh_access_in_company(cid):
            return cid
    if role == "custom":
        if access_control_service.check_user_has_permission(
            str(current_user.id), cid, PAYROLL_ANALYTICS_VIEW
        ) or access_control_service.has_any_rh_permission(str(current_user.id), cid):
            return cid
    elif current_user.has_rh_access_in_company(cid):
        return cid
    raise HTTPException(status_code=403, detail="Accès réservé au profil RH.")


@router.get("/preflight-anomalies", response_model=PreflightAnomaliesResponse)
def get_preflight_anomalies(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_payroll_preflight_access(current_user)
    try:
        return preflight_anomalies.build_preflight_anomalies(company_id, year, month)
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Erreur lors du chargement de la revue des anomalies.",
        ) from None


@router.post("/preflight-anomalies/resolution")
def justify_preflight_anomaly(
    body: PreflightResolutionRequest,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_payroll_preflight_access(current_user)
    try:
        row = preflight_anomalies.justify_anomaly(
            company_id=company_id,
            employee_id=body.employee_id,
            year=body.year,
            month=body.month,
            anomaly_type=body.anomaly_type,
            motif=body.motif,
            commentaire=body.commentaire,
            resolved_by=str(current_user.id),
        )
        return {"ok": True, "resolution": row}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de l'enregistrement de la justification.",
        ) from None


@router.delete("/preflight-anomalies/resolution")
def delete_preflight_anomaly_resolution(
    body: PreflightResolutionDeleteRequest,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_payroll_preflight_access(current_user)
    try:
        preflight_anomalies.remove_anomaly_justification(
            company_id=company_id,
            employee_id=body.employee_id,
            year=body.year,
            month=body.month,
            anomaly_type=body.anomaly_type,
        )
        return {"ok": True}
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la suppression de la justification.",
        ) from None


@router.post("/preflight-anomalies/acknowledge")
def acknowledge_preflight_anomalies(
    body: PreflightAcknowledgeRequest,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_payroll_preflight_access(current_user)
    try:
        row = preflight_anomalies.acknowledge_preflight_launch(
            company_id=company_id,
            year=body.year,
            month=body.month,
            open_anomalies_count=body.open_anomalies_count,
            anomaly_types_summary=body.anomaly_types_summary,
            commentaire=body.commentaire,
            acknowledged_by=str(current_user.id),
        )
        return {"ok": True, "acknowledgement": row}
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de l'enregistrement de l'acquittement.",
        ) from None
