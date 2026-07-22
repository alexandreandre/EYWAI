"""
Router API payslips.

Appelle uniquement l'application du module. Aucune logique métier :
validation des entrées (schémas), construction du contexte utilisateur,
appel du use case, mapping des exceptions applicatives vers HTTP.
"""

from __future__ import annotations

import traceback
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.security import get_current_user
from app.modules.access_control.application.service import access_control_service
from app.modules.audit.application.commands import log_audit_event
from app.modules.webhooks.application.service import trigger_webhook_event
from app.modules.payslips.application.anomalies_report import (
    build_payslips_anomalies_report,
)
from app.shared.employee_resolution import resolve_employee_id_for_user_account
from app.modules.payslips.application import (
    PayslipBadRequestError,
    PayslipCriticalActiveError,
    PayslipForbiddenError,
    PayslipNotFoundError,
    UserContext,
    acquit_payslip_alert_for_user,
    delete_payslip,
    generate_payslip,
    get_debug_storage_info,
    get_employee_payslips,
    get_my_payslips_for_user_account,
    get_payslip_comparison_for_user,
    get_payslip_details_for_user,
    get_payslip_history_for_user,
    get_payslip_trend_for_user,
    edit_payslip_for_user,
    ignore_payslip_alert_for_user,
    restore_payslip_for_user,
    validate_payslip_for_user,
    GeneratePayslipInput,
)
from app.modules.payslips.application.router_queries import get_payslip_meta_for_access
from app.modules.payslips.schemas.anomalies import PayslipsAnomaliesReport
from app.modules.payslips.schemas import (
    AcquitAlertRequest,
    ComparisonResultResponse,
    HistoryEntry,
    PayslipDetail,
    PayslipEditRequest,
    PayslipEditResponse,
    PayslipInfo,
    PayslipRequest,
    PayslipRestoreRequest,
    PayslipRestoreResponse,
    TrendResponse,
)
from app.modules.users.schemas.responses import User

router = APIRouter(tags=["Payslips"])

# Exceptions applicatives à mapper vers HTTP (404, 403, 400)
_PAYSLIP_APP_ERRORS = (
    PayslipNotFoundError,
    PayslipForbiddenError,
    PayslipBadRequestError,
    PayslipCriticalActiveError,
)


def _to_user_context(user: User) -> UserContext:
    """Adapte User (couche API) vers UserContext (application)."""
    company_id = user.active_company_id
    resolved_employee_id = None
    if company_id:
        resolved_employee_id = resolve_employee_id_for_user_account(
            str(user.id), str(company_id)
        )
    return UserContext(
        user_id=user.id,
        is_platform_admin=user.is_platform_admin,
        has_rh_access_in_company=user.has_rh_access_in_company,
        active_company_id=company_id,
        resolved_employee_id=resolved_employee_id,
        first_name=user.first_name,
        last_name=user.last_name,
    )


def _map_app_errors(exc: Exception) -> None:
    """Relève HTTPException selon le type d'exception applicative."""
    if isinstance(exc, PayslipNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, PayslipForbiddenError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, PayslipCriticalActiveError):
        raise HTTPException(
            status_code=400, detail={"critical_alerts": exc.critical_alerts}
        ) from exc
    if isinstance(exc, PayslipBadRequestError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _handle_application_errors(exc: Exception) -> None:
    """Alias explicite pour le mapping des erreurs applicatives payslips."""
    _map_app_errors(exc)


def _require_rh_company_context(current_user: User) -> str:
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return str(company_id)


def _require_payslip_scope(
    current_user: User, payslip_id: str, permission_code: str
) -> dict:
    """Résout le bulletin puis masque un salarié hors périmètre par une 404."""
    meta = get_payslip_meta_for_access(payslip_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Bulletin introuvable")
    company_id = str(meta.get("company_id") or "")
    employee_id = str(meta.get("employee_id") or "")
    if not company_id or not employee_id:
        raise HTTPException(status_code=404, detail="Bulletin introuvable")
    if company_id != str(current_user.active_company_id or ""):
        raise HTTPException(status_code=404, detail="Bulletin introuvable")
    access_control_service.require_employee_access(
        current_user, company_id, permission_code, employee_id
    )
    return meta


# --- Rapport anomalies (RH) ---
@router.get("/api/payslips/anomalies", response_model=PayslipsAnomaliesReport)
def get_payslips_anomalies_route(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    current_user: User = Depends(get_current_user),
):
    """Contrôles métier sur tous les bulletins du mois (entreprise active)."""
    company_id = _require_rh_company_context(current_user)
    today = date.today()
    y = year if year is not None else today.year
    m = month if month is not None else today.month
    try:
        return build_payslips_anomalies_report(company_id, y, m)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


# --- Génération ---
@router.post("/api/actions/generate-payslip")
def generate_payslip_route(
    request: PayslipRequest,
    current_user: User = Depends(get_current_user),
):
    """Génération d'un bulletin (forfait jour ou heures selon statut employé)."""
    try:
        _require_rh_company_context(current_user)
        result = generate_payslip(
            GeneratePayslipInput(
                employee_id=request.employee_id,
                year=request.year,
                month=request.month,
            )
        )
        return {
            "status": result.status,
            "message": result.message,
            "download_url": result.download_url,
            "payslip_id": result.payslip_id,
            "warnings": result.warnings or [],
        }
    except HTTPException:
        raise
    except _PAYSLIP_APP_ERRORS as exc:
        _handle_application_errors(exc)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Mes bulletins ---
@router.get("/api/me/payslips", response_model=List[PayslipInfo])
def get_my_payslips_route(current_user: User = Depends(get_current_user)):
    """Liste des bulletins de l'employé connecté."""
    try:
        return get_my_payslips_for_user_account(
            str(current_user.id), current_user.active_company_id
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Bulletins d'un employé ---
@router.get("/api/employees/{employee_id}/payslips", response_model=List[PayslipInfo])
def get_employee_payslips_route(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Liste des bulletins d'un salarié."""
    try:
        company_id = _require_rh_company_context(current_user)
        access_control_service.require_employee_access(
            current_user, company_id, "payslips.view_all", employee_id
        )
        return get_employee_payslips(employee_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Suppression ---
@router.delete("/api/payslips/{payslip_id}", status_code=204)
def delete_payslip_route(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Supprime un bulletin (BDD, storage, recalc COR)."""
    try:
        _require_rh_company_context(current_user)
        delete_payslip(payslip_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Comparaison N vs N-1 ---
@router.get(
    "/api/payslips/{payslip_id}/comparison",
    response_model=ComparisonResultResponse,
)
def get_payslip_comparison_route(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Comparaison du bulletin N avec le dernier bulletin N-1 validé."""
    try:
        return get_payslip_comparison_for_user(
            payslip_id, _to_user_context(current_user)
        )
    except _PAYSLIP_APP_ERRORS as e:
        _handle_application_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/payslips/{payslip_id}/trend", response_model=TrendResponse)
def get_payslip_trend_route(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Tendance sur les 12 derniers bulletins validés avant la période du bulletin."""
    try:
        return get_payslip_trend_for_user(payslip_id, _to_user_context(current_user))
    except _PAYSLIP_APP_ERRORS as e:
        _handle_application_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/payslips/{payslip_id}/alerts/{rule_id}/acquit")
def acquit_payslip_alert_route(
    payslip_id: str,
    rule_id: str,
    body: AcquitAlertRequest = AcquitAlertRequest(),
    current_user: User = Depends(get_current_user),
):
    """Acquitte une alerte (RH / admin entreprise)."""
    try:
        acquit_payslip_alert_for_user(
            payslip_id,
            rule_id,
            _to_user_context(current_user),
            body.comment,
        )
        return {"ok": True, "rule_id": rule_id, "status": "acquittee"}
    except _PAYSLIP_APP_ERRORS as e:
        _handle_application_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/payslips/{payslip_id}/alerts/{rule_id}/ignore")
def ignore_payslip_alert_route(
    payslip_id: str,
    rule_id: str,
    body: AcquitAlertRequest = AcquitAlertRequest(),
    current_user: User = Depends(get_current_user),
):
    """Ignore une alerte (RH / admin entreprise)."""
    try:
        ignore_payslip_alert_for_user(
            payslip_id,
            rule_id,
            _to_user_context(current_user),
            body.comment,
        )
        return {"ok": True, "rule_id": rule_id, "status": "ignoree"}
    except _PAYSLIP_APP_ERRORS as e:
        _handle_application_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/payslips/{payslip_id}/validate", response_model=PayslipDetail)
def validate_payslip_route(
    payslip_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Valide le bulletin si aucune alerte critique active."""
    try:
        meta = _require_payslip_scope(
            current_user, payslip_id, "payslips.validate"
        )
        validate_payslip_for_user(payslip_id, _to_user_context(current_user))
        cid = str(meta.get("company_id") or "") if meta else ""
        if cid:
            log_audit_event(
                company_id=cid,
                user_id=str(current_user.id),
                user_email=current_user.email,
                action="payslip.validate",
                resource_type="payslip",
                resource_id=payslip_id,
                details={
                    "employee_id": str(meta.get("employee_id") or ""),
                },
                ip_address=request.client.host if request.client else None,
            )
            trigger_webhook_event(
                cid,
                "payslip.validated",
                {
                    "payslip_id": payslip_id,
                    "employee_id": str(meta.get("employee_id") or ""),
                },
            )
        return get_payslip_details_for_user(payslip_id, _to_user_context(current_user))
    except _PAYSLIP_APP_ERRORS as e:
        _handle_application_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Détail ---
@router.get("/api/payslips/{payslip_id}", response_model=PayslipDetail)
def get_payslip_details_route(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Détail d'un bulletin (cumuls, historique, URL signée)."""
    try:
        return get_payslip_details_for_user(payslip_id, _to_user_context(current_user))
    except _PAYSLIP_APP_ERRORS as e:
        _map_app_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Édition ---
@router.post("/api/payslips/{payslip_id}/edit", response_model=PayslipEditResponse)
def edit_payslip_route(
    payslip_id: str,
    edit_request: PayslipEditRequest,
    current_user: User = Depends(get_current_user),
):
    """Modifie un bulletin (RH/Admin/Super Admin)."""
    try:
        result = edit_payslip_for_user(
            payslip_id,
            edit_request.payslip_data,
            edit_request.changes_summary,
            _to_user_context(current_user),
            pdf_notes=edit_request.pdf_notes,
            internal_note=edit_request.internal_note,
        )
        return PayslipEditResponse(
            status="success",
            message="Bulletin modifié avec succès",
            payslip=result["payslip"],
            new_pdf_url=result["new_pdf_url"],
        )
    except _PAYSLIP_APP_ERRORS as e:
        _map_app_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Historique ---
@router.get("/api/payslips/{payslip_id}/history", response_model=List[HistoryEntry])
def get_payslip_history_route(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Historique des modifications d'un bulletin."""
    try:
        return get_payslip_history_for_user(payslip_id, _to_user_context(current_user))
    except _PAYSLIP_APP_ERRORS as e:
        _map_app_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Restauration ---
@router.post(
    "/api/payslips/{payslip_id}/restore", response_model=PayslipRestoreResponse
)
def restore_payslip_route(
    payslip_id: str,
    restore_request: PayslipRestoreRequest,
    current_user: User = Depends(get_current_user),
):
    """Restaure une version précédente (RH/Admin/Super Admin)."""
    try:
        result = restore_payslip_for_user(
            payslip_id,
            restore_request.version,
            _to_user_context(current_user),
        )
        return PayslipRestoreResponse(
            status="success",
            message=f"Version {restore_request.version} restaurée avec succès",
            payslip=result["payslip"],
            restored_version=restore_request.version,
        )
    except _PAYSLIP_APP_ERRORS as e:
        _map_app_errors(e)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Debug storage ---
@router.get("/api/debug-storage/{employee_id}/{year}/{month}")
def debug_storage_file(
    employee_id: str,
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
):
    """Métadonnées Storage pour diagnostic (RH uniquement)."""
    try:
        _require_rh_company_context(current_user)
        return get_debug_storage_info(employee_id, year, month)
    except PayslipNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
