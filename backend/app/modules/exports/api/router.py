# Router exports — délégation à la couche application uniquement.
# Comportement HTTP identique à api/routers/exports.py (prefix=/api/exports).
import traceback
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.access_control.application.service import access_control_service
from app.modules.users.schemas.responses import User
from app.modules.exports.api.dependencies import get_active_company_id
from app.modules.exports.application import service as export_service
from app.modules.exports.application import scheduled_exports as scheduled_export_service
from app.modules.exports.application import dispatch as dispatch_service
from app.modules.exports.schemas import (
    ExportPreviewRequest,
    ExportPreviewResponse,
    ExportGenerateRequest,
    ExportGenerateResponse,
    ExportHistoryResponse,
    DSNGenerateResponse,
)
from app.modules.exports.schemas.scheduled_exports import (
    ScheduledExportCreate,
    ScheduledExportOut,
    ScheduledExportRunNowResponse,
    ScheduledExportUpdate,
)
from app.modules.exports.application import accounting_mappings as accounting_mappings_service
from app.modules.exports.infrastructure.payroll_ledger import LedgerImbalanceError
from app.modules.exports.schemas.accounting_mappings import (
    AccountingMappingOut,
    AccountingMappingUpsert,
    AccountingMappingsListResponse,
)
from app.modules.exports.schemas.dispatch import (
    DispatchBanqueRequest,
    DispatchComptaRequest,
    DispatchHistoryResponse,
    DispatchResultResponse,
    DispatchSchedulesResponse,
    DispatchScheduleOut,
    DispatchScheduleRunResponse,
    DispatchScheduleUpsert,
    DispatchStatusResponse,
    MarkDispatchTransmittedRequest,
    MarkDispatchTransmittedResponse,
)

router = APIRouter(
    prefix="/api/exports",
    tags=["Exports"],
)


def _require_rh_exports(current_user: User, company_id: str) -> None:
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH.")


def _require_exports_company_access(current_user: User, company_id: str) -> None:
    """Vérifie l'accès RH et l'alignement entreprise active / header."""
    _require_rh_exports(current_user, company_id)
    if current_user.is_platform_admin:
        return
    if str(current_user.active_company_id or "") != str(company_id):
        raise HTTPException(status_code=404, detail="Ressource introuvable")


def _require_bank_dispatch_permission(current_user: User, company_id: str) -> None:
    """Protège l'envoi banque par le droit explicite dédié."""
    if current_user.is_platform_admin:
        return
    if not access_control_service.check_user_has_permission(
        str(current_user.id), company_id, "bank_dispatch.send"
    ):
        raise HTTPException(
            status_code=403,
            detail="Permission d'envoi bancaire requise.",
        )


def _value_error_to_http(e: ValueError) -> HTTPException:
    """Traduit les ValueError du service en HTTPException (400, 404 ou 422)."""
    msg = str(e)
    # Une OD déséquilibrée n'est pas une requête invalide : les données sont
    # correctes, il manque un paramétrage comptable. 422 permet à l'écran de
    # présenter la liste des comptes à renseigner plutôt qu'une erreur générique.
    if isinstance(e, LedgerImbalanceError):
        return HTTPException(status_code=422, detail=msg)
    if "non trouvé" in msg.lower() or "aucun fichier" in msg.lower():
        return HTTPException(status_code=404, detail=msg)
    return HTTPException(status_code=400, detail=msg)


@router.post("/preview", response_model=ExportPreviewResponse)
def preview_export(
    request: ExportPreviewRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Prévisualise un export sans générer de fichier."""
    try:
        _require_exports_company_access(current_user, company_id)
        return export_service.preview_export(company_id, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/generate", response_model=Union[ExportGenerateResponse, DSNGenerateResponse]
)
def generate_export(
    request: ExportGenerateRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Génère un export et retourne les fichiers."""
    try:
        _require_exports_company_access(current_user, company_id)
        return export_service.generate_export(company_id, current_user.id, request)
    except HTTPException:
        raise
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=ExportHistoryResponse)
def get_export_history(
    export_type: Optional[str] = None,
    period: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Récupère l'historique des exports."""
    try:
        _require_exports_company_access(current_user, company_id)
        return export_service.get_export_history(company_id, export_type, period)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{export_id}")
def download_export(
    export_id: str,
    file_index: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Retourne l'URL signée d'un fichier export (file_index) ou la liste de tous les fichiers."""
    try:
        _require_exports_company_access(current_user, company_id)
        if file_index is None:
            files = export_service.get_export_download_files(company_id, export_id)
            return {"files": files}
        download_url = export_service.get_export_download_url(
            company_id, export_id, file_index
        )
        return {"download_url": download_url}
    except HTTPException:
        raise
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Exports planifiés (RH) ---


@router.get("/scheduled", response_model=List[ScheduledExportOut])
def list_scheduled_exports(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return scheduled_export_service.list_scheduled(company_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduled", response_model=ScheduledExportOut)
def create_scheduled_export(
    body: ScheduledExportCreate,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return scheduled_export_service.create_scheduled(
            company_id, body, created_by=str(current_user.id)
        )
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/scheduled/{schedule_id}/history",
    response_model=ExportHistoryResponse,
)
def scheduled_export_history(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return scheduled_export_service.history_for_schedule(schedule_id, company_id)
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/scheduled/{schedule_id}/run-now",
    response_model=ScheduledExportRunNowResponse,
)
def run_scheduled_export_now(
    schedule_id: str,
    period: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return scheduled_export_service.run_scheduled_now(
            schedule_id, company_id, str(current_user.id), period=period
        )
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/scheduled/{schedule_id}", response_model=ScheduledExportOut)
def update_scheduled_export(
    schedule_id: str,
    body: ScheduledExportUpdate,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return scheduled_export_service.update_scheduled(schedule_id, company_id, body)
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scheduled/{schedule_id}", status_code=204)
def delete_scheduled_export(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        scheduled_export_service.delete_scheduled(schedule_id, company_id)
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Envois compta / banque (dispatch) ---


@router.get("/dispatch/status", response_model=DispatchStatusResponse)
def get_dispatch_status(
    period: str,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return dispatch_service.get_dispatch_status(company_id, period)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dispatch/compta", response_model=DispatchResultResponse)
def dispatch_compta(
    body: DispatchComptaRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return dispatch_service.dispatch_compta(company_id, str(current_user.id), body)
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dispatch/banque", response_model=DispatchResultResponse)
def dispatch_banque(
    body: DispatchBanqueRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    _require_bank_dispatch_permission(current_user, company_id)
    try:
        return dispatch_service.dispatch_banque(company_id, str(current_user.id), body)
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/dispatch/{dispatch_id}/mark-transmitted",
    response_model=MarkDispatchTransmittedResponse,
)
def mark_dispatch_transmitted(
    dispatch_id: str,
    body: MarkDispatchTransmittedRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return dispatch_service.mark_transmitted(
            dispatch_id, company_id, str(current_user.id), body.note
        )
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dispatch/history", response_model=DispatchHistoryResponse)
def get_dispatch_history(
    channel: Optional[str] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return dispatch_service.get_dispatch_history(company_id, channel, limit)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dispatch/schedules", response_model=DispatchSchedulesResponse)
def list_dispatch_schedules(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return scheduled_export_service.list_channel_schedules(company_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/dispatch/schedules/{channel}", response_model=DispatchScheduleOut)
def upsert_dispatch_schedule(
    channel: str,
    body: DispatchScheduleUpsert,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return scheduled_export_service.upsert_channel_schedule(
            company_id, channel, body, created_by=str(current_user.id)
        )
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/dispatch/schedules/{channel}/run-now",
    response_model=DispatchScheduleRunResponse,
)
def run_dispatch_schedule_now(
    channel: str,
    period: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return scheduled_export_service.run_channel_schedule_now(
            company_id, channel, str(current_user.id), period
        )
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounting-mappings", response_model=AccountingMappingsListResponse)
def list_accounting_mappings(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return accounting_mappings_service.list_accounting_mappings(company_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/accounting-mappings", response_model=AccountingMappingOut)
def upsert_accounting_mapping(
    body: AccountingMappingUpsert,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        return accounting_mappings_service.upsert_company_mapping(company_id, body)
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/accounting-mappings/{rubrique_code}")
def delete_accounting_mapping(
    rubrique_code: str,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    _require_exports_company_access(current_user, company_id)
    try:
        accounting_mappings_service.delete_company_mapping(company_id, rubrique_code)
        return {"status": "deleted", "rubrique_code": rubrique_code}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
