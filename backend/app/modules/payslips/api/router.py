"""
Router API payslips.

Appelle uniquement l'application du module. Aucune logique métier :
validation des entrées (schémas), construction du contexte utilisateur,
appel du use case, mapping des exceptions applicatives vers HTTP.
"""

from __future__ import annotations

import traceback
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.payslips.application import (
    PayslipBadRequestError,
    PayslipForbiddenError,
    PayslipNotFoundError,
    UserContext,
    delete_payslip,
    generate_payslip,
    get_debug_storage_info,
    get_employee_payslips,
    get_my_payslips,
    get_payslip_details_for_user,
    get_payslip_history_for_user,
    edit_payslip_for_user,
    restore_payslip_for_user,
    GeneratePayslipInput,
)
from app.modules.payslips.schemas import (
    HistoryEntry,
    PayslipDetail,
    PayslipEditRequest,
    PayslipEditResponse,
    PayslipInfo,
    PayslipRequest,
    PayslipRestoreRequest,
    PayslipRestoreResponse,
)
from app.modules.users.schemas.responses import User

router = APIRouter(tags=["Payslips"])

# Exceptions applicatives à mapper vers HTTP (404, 403, 400)
_PAYSLIP_APP_ERRORS = (
    PayslipNotFoundError,
    PayslipForbiddenError,
    PayslipBadRequestError,
)


def _to_user_context(user: User) -> UserContext:
    """Adapte User (couche API) vers UserContext (application)."""
    return UserContext(
        user_id=user.id,
        is_super_admin=user.is_super_admin,
        has_rh_access_in_company=user.has_rh_access_in_company,
        active_company_id=user.active_company_id,
        first_name=user.first_name,
        last_name=user.last_name,
    )


def _map_app_errors(exc: Exception) -> None:
    """Relève HTTPException selon le type d'exception applicative."""
    if isinstance(exc, PayslipNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, PayslipForbiddenError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, PayslipBadRequestError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- Génération ---
@router.post("/api/actions/generate-payslip")
def generate_payslip_route(request: PayslipRequest):
    """Génération d'un bulletin (forfait jour ou heures selon statut employé)."""
    try:
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
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Mes bulletins ---
@router.get("/api/me/payslips", response_model=List[PayslipInfo])
def get_my_payslips_route(current_user: User = Depends(get_current_user)):
    """Liste des bulletins de l'employé connecté."""
    try:
        return get_my_payslips(current_user.id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Bulletins d'un employé ---
@router.get("/api/employees/{employee_id}/payslips", response_model=List[PayslipInfo])
def get_employee_payslips_route(employee_id: str):
    """Liste des bulletins d'un salarié."""
    try:
        return get_employee_payslips(employee_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Suppression ---
@router.delete("/api/payslips/{payslip_id}", status_code=204)
def delete_payslip_route(payslip_id: str):
    """Supprime un bulletin (BDD, storage, recalc COR)."""
    try:
        delete_payslip(payslip_id)
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
def debug_storage_file(employee_id: str, year: int, month: int):
    """Métadonnées Storage pour diagnostic."""
    try:
        return get_debug_storage_info(employee_id, year, month)
    except PayslipNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
