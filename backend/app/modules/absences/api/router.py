"""
Router API du module absences.

Délègue toute la logique à la couche application (commands, queries).
Validation des entrées (schémas), résolution utilisateur (Depends), appel application, retour HTTP.
Comportement HTTP identique à api/routers/absences.py.
"""

import io
import logging
import traceback
from typing import List, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user
from app.modules.employees.api.deps import assert_can_read_employee_profile
from app.modules.absences.application import router_support as absence_router
from app.modules.audit.application.commands import log_audit_event
from app.modules.webhooks.application.service import trigger_webhook_event
from app.modules.users.schemas.responses import User

from app.modules.absences.schemas.fractionnement import (
    FractionnementInputUpdate,
    FractionnementPreviewRow,
    FractionnementSettingsResponse,
    FractionnementSettingsUpdate,
    FractionnementValidateResult,
    LeaveCampaignDashboard,
)
from app.modules.absences.schemas.cp_seniority import (
    CpSeniorityGrantOverride,
    CpSeniorityPreviewRow,
    CpSenioritySettingsResponse,
    CpSenioritySettingsUpdate,
    CpSeniorityValidateResult,
)
from app.modules.absences.application import (
    commands,
    cp_seniority_commands,
    cp_seniority_queries,
    fractionnement_queries,
    leave_campaign_queries,
    leave_notification_settings,
    leave_settings_commands,
    leave_settings_queries,
    notifications as absence_notif,
    queries,
)
from app.modules.absences.domain.enums import SALARY_CERTIFICATE_ABSENCE_TYPES
from app.modules.absences.schemas.leave_settings import (
    EmployeeLeaveAdjustmentUpdate,
    EmployeeRttSoldeUpdate,
    LeaveAdjustmentImportRequest,
    LeaveNotificationSettingsUpdate,
    LeaveSettingsUpdate,
    RttYearEndCloseRequest,
)
from app.modules.absences.schemas.leave_settings_responses import (
    EmployeeLeaveAdjustmentResponse,
    JtcAnnualRunResponse,
    LeaveAdjustmentImportResult,
    LeaveBalancesOverviewResponse,
    LeaveNotificationSettingsResponse,
    LeaveSettingsResponse,
    RttYearEndCloseResult,
    RttYearEndOverviewResponse,
)
from app.modules.absences.schemas.requests import (
    AbsenceRequestCreate,
    AbsenceRequestStatusUpdate,
    ManagerApprovalRequest,
    SalaryCertificateTransmissionUpdate,
)
from app.modules.absences.schemas.responses import (
    AbsenceBalancesResponse,
    AbsencePageData,
    AbsencePendingManagerItem,
    AbsenceRequest,
    AbsenceRequestWithEmployee,
    EvenementFamilialEvent,
    EvenementFamilialQuotaResponse,
    MonthlyCalendarResponse,
    SignedUploadURL,
)

router = APIRouter(
    prefix="/api/absences",
    tags=["Absences"],
)

_log = logging.getLogger(__name__)


def _notify_rh_status_change(req: dict, new_status: str) -> None:
    """Best effort — après validation / refus RH."""
    if new_status not in ("validated", "rejected"):
        return
    try:
        d0, d1 = absence_notif.absence_date_range_iso(req)
        eid = str(req["employee_id"])
        cid = str(req["company_id"])
        at = str(req.get("type") or "")
        if new_status == "validated":
            absence_notif.notify_absence_approved(eid, cid, at, d0, d1)
        else:
            absence_notif.notify_absence_rejected(eid, cid, at, d0, d1, None)
    except Exception:
        _log.exception("[absences] notification RH (statut) ignorée")


def _handle_application_errors(e: Exception) -> None:
    """Traduit ValueError/LookupError/RuntimeError/PermissionError en HTTPException."""
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(e, LookupError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, PermissionError):
        raise HTTPException(status_code=403, detail=str(e))
    if isinstance(e, RuntimeError):
        raise HTTPException(status_code=500, detail=str(e))
    raise


def _require_active_company_absences(current_user: User) -> str:
    cid = current_user.active_company_id
    if not cid:
        raise HTTPException(status_code=400, detail="Entreprise active requise.")
    return str(cid)


def _require_rh_company_context(current_user: User) -> str:
    """Entreprise active + droits RH (ou super admin)."""
    company_id = _require_active_company_absences(current_user)
    if current_user.is_platform_admin:
        return company_id
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return company_id


def _require_leave_notification_settings_write(current_user: User) -> str:
    company_id = _require_rh_company_context(current_user)
    if current_user.is_platform_admin:
        return company_id
    role = current_user.get_role_in_company(company_id)
    if role not in ("admin", "rh"):
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return company_id


def _ensure_absence_in_active_company(request_id: str, company_id: str) -> dict:
    row = absence_router.get_absence_by_id(request_id)
    if not row:
        raise LookupError(f"Demande {request_id} non trouvée.")
    if str(row.get("company_id") or "") != company_id:
        raise HTTPException(
            status_code=403, detail="Demande hors périmètre entreprise."
        )
    return row


def _enrich_single_absence_row(row: dict) -> dict:
    r = {k: v for k, v in row.items() if k != "employee"}
    queries._enrich_absence_certificate_fields(r)
    queries._enrich_with_signed_urls([r])
    return r


def _enrich_absence_row_keep_employee(row: dict) -> dict:
    r = dict(row)
    emp = r.get("employee")
    if isinstance(emp, list) and emp:
        r["employee"] = emp[0]
    queries._enrich_absence_certificate_fields(r)
    queries._enrich_with_signed_urls([r])
    return r


def _resolve_employee_id_for_current_user(current_user: User) -> str:
    """Résout employees.id pour le compte connecté (user_id ou id = auth uid)."""
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="Aucune entreprise active.",
        )
    employee_id = absence_router.resolve_employee_id_for_user(
        str(current_user.id), str(company_id)
    )
    if not employee_id:
        raise HTTPException(
            status_code=404,
            detail="Profil collaborateur sans employé associé.",
        )
    return employee_id


def _resolve_create_absence_employee_id(
    current_user: User, requested_employee_id: str
) -> str:
    """
    Collaborateur : uniquement sa fiche (accepte encore employee_id = auth uid).
    RH / super admin : employé de l'entreprise active.
    """
    target = str(requested_employee_id)
    company_id = current_user.active_company_id
    is_rh = current_user.is_platform_admin or (
        company_id is not None
        and current_user.has_rh_access_in_company(str(company_id))
    )
    if is_rh:
        emp_company = absence_router.employee_company_id(target)
        if not emp_company:
            raise HTTPException(status_code=404, detail="Employé non trouvé.")
        if (
            company_id
            and str(emp_company) != str(company_id)
            and not current_user.is_platform_admin
        ):
            raise HTTPException(
                status_code=403, detail="Employé hors périmètre entreprise."
            )
        return target

    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active.")
    my_id = absence_router.resolve_employee_id_for_user(
        str(current_user.id), str(company_id)
    )
    if not my_id:
        raise HTTPException(
            status_code=404,
            detail="Profil collaborateur sans employé associé.",
        )
    uid = str(current_user.id)
    if target not in (str(my_id), uid):
        raise HTTPException(
            status_code=403,
            detail="Vous ne pouvez créer une demande que pour votre propre fiche.",
        )
    return str(my_id)


# ----- Upload URL -----


@router.post("/get-upload-url", response_model=SignedUploadURL)
def get_upload_url(
    filename: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
):
    """Génère une URL signée pour uploader un justificatif de congé."""
    try:
        result = queries.get_upload_url_signed(str(current_user.id), filename)
        return SignedUploadURL(**result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur de stockage Supabase: {e}")


# ----- Création / mise à jour demandes -----


@router.post("/requests", response_model=AbsenceRequest, status_code=201)
def create_absence_request(
    request_data: AbsenceRequestCreate,
    current_user: User = Depends(get_current_user),
):
    """Crée une nouvelle demande d'absence à partir d'une liste de jours."""
    try:
        company_id = current_user.active_company_id
        is_rh = current_user.is_platform_admin or (
            company_id is not None
            and current_user.has_rh_access_in_company(str(company_id))
        )
        if not is_rh and request_data.type in SALARY_CERTIFICATE_ABSENCE_TYPES:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Les arrêts maladie, accidents du travail, congés maternité et "
                    "paternité (délais selon la convention collective) et maladies "
                    "professionnelles ne se déclarent pas par le salarié. Contactez "
                    "votre employeur ou remettez vos justificatifs : c'est lui qui "
                    "enregistre l'absence."
                ),
            )

        employee_id = _resolve_create_absence_employee_id(
            current_user, request_data.employee_id
        )
        if employee_id != request_data.employee_id:
            request_data = request_data.model_copy(update={"employee_id": employee_id})
        data = commands.create_absence_request(
            request_data,
            enforce_conge_paye_balance=not is_rh,
        )
        rid = str(data["id"])
        eid = str(data["employee_id"])
        # Toute saisie RH est validée immédiatement (arrêt comme congé) :
        # la RH enregistre un fait déjà accordé, pas une demande à s'auto-approuver.
        if is_rh:
            req_before = dict(data)
            data = commands.update_absence_request_status(
                rid,
                "validated",
                current_user_id=str(current_user.id),
            )
            data2 = absence_router.update_absence(rid, {"workflow_step": "approved_rh"})
            data = data2 or data
            try:
                _notify_rh_status_change(req_before, "validated")
            except Exception:
                _log.exception("[absences] notifications saisie directe RH ignorées")
        else:
            mgr = absence_router.get_team_manager_employee_id(eid)
            wf = "pending_manager" if mgr else "pending"
            data2 = absence_router.update_absence(rid, {"workflow_step": wf})
            data = data2 or data
            try:
                d0, d1 = absence_notif.absence_date_range_iso(data)
                absence_notif.notify_absence_submitted(
                    eid,
                    str(data["company_id"]),
                    str(data.get("type") or ""),
                    d0,
                    d1,
                )
                if wf == "pending_manager" and mgr:
                    absence_notif.notify_manager_new_request(
                        str(mgr),
                        str(data["company_id"]),
                        absence_notif.employee_display_name(eid),
                        str(data.get("type") or ""),
                        d0,
                        d1,
                    )
                absence_notif.notify_leave_request_email(
                    data,
                    event="employee_request",
                )
            except Exception:
                _log.exception("[absences] notifications création ignorées")
        r = _enrich_single_absence_row(dict(data))
        return r
    except HTTPException:
        raise
    except (ValueError, LookupError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/requests/{request_id}/status", response_model=AbsenceRequest)
def update_absence_request_status(
    request_id: str,
    http_request: Request,
    status_update: AbsenceRequestStatusUpdate,
    current_user: User = Depends(get_current_user),
):
    """Met à jour le statut d'une demande (utilisateur connecté). Génère l'attestation si nécessaire."""
    try:
        company_id = _require_active_company_absences(current_user)
        if status_update.status in ("validated", "rejected"):
            _require_rh_company_context(current_user)
            req_before = _ensure_absence_in_active_company(request_id, company_id)
        else:
            req_before = absence_router.get_absence_by_id(request_id)
        if (
            req_before
            and req_before.get("workflow_step") == "pending_manager"
            and req_before.get("status") == "pending"
            and status_update.status in ("validated", "rejected")
        ):
            raise HTTPException(
                status_code=400,
                detail="La demande doit d'abord être validée par le manager.",
            )
        data = commands.update_absence_request_status(
            request_id,
            status_update.status,
            current_user_id=str(current_user.id),
            subrogation_active=status_update.subrogation_active,
        )
        extra_ws: dict = {}
        if status_update.status == "validated":
            extra_ws["workflow_step"] = "approved_rh"
        elif status_update.status == "rejected":
            extra_ws["workflow_step"] = "rejected_rh"
        if extra_ws:
            merged = absence_router.update_absence(request_id, extra_ws)
            if merged:
                data = merged
        _notify_rh_status_change(req_before, status_update.status)
        enriched = queries.update_absence_request_signed_url_single(request_id)
        out = enriched if enriched is not None else data
        cid = str((out or data).get("company_id") or "")
        if cid and status_update.status in ("validated", "rejected"):
            log_audit_event(
                company_id=cid,
                user_id=str(current_user.id),
                user_email=current_user.email,
                action=(
                    "absence.validate"
                    if status_update.status == "validated"
                    else "absence.reject"
                ),
                resource_type="absence_request",
                resource_id=str(request_id),
                details={"employee_id": str((out or data).get("employee_id") or "")},
                ip_address=http_request.client.host if http_request.client else None,
            )
        if status_update.status == "validated" and cid:
            trigger_webhook_event(
                cid,
                "absence.approved",
                {
                    "request_id": str(request_id),
                    "employee_id": str((out or data).get("employee_id") or ""),
                },
            )
        return out
    except HTTPException:
        raise
    except (ValueError, LookupError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{request_id}", response_model=AbsenceRequest)
async def update_absence_request(
    request_id: str,
    http_request: Request,
    status_update: AbsenceRequestStatusUpdate,
    current_user: User = Depends(get_current_user),
):
    """Met à jour le statut d'une demande d'absence (RH). Alias de PATCH .../requests/{id}/status."""
    if status_update.status in ("validated", "rejected"):
        _require_rh_company_context(current_user)
    return await update_absence_request_status(
        request_id, http_request, status_update, current_user
    )


# ----- Liste globale (RH) -----


@router.get("/", response_model=List[AbsenceRequestWithEmployee])
def get_absence_requests(
    status: Literal["pending", "validated", "rejected", "cancelled"] | None = None,
    current_user: User = Depends(get_current_user),
):
    """Récupère les demandes d'absence de l'entreprise active (RH)."""
    try:
        company_id = _require_rh_company_context(current_user)
        return queries.get_absence_requests(status, company_id=company_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending-manager-approval", response_model=List[AbsencePendingManagerItem])
def list_pending_manager_approval(
    current_user: User = Depends(get_current_user),
):
    """Demandes en attente de validation manager (périmètre RH ou équipe du manager)."""
    try:
        company_id = _require_active_company_absences(current_user)
        rows = absence_router.list_pending_manager_approval(company_id)
        if not current_user.has_rh_access_in_company(company_id):
            me = absence_router.resolve_employee_id_for_user(
                str(current_user.id), str(company_id)
            )
            if not me:
                raise HTTPException(
                    status_code=403,
                    detail="Profil employé requis pour consulter ces demandes.",
                )
            managed = absence_router.list_employee_ids_managed_by_manager(
                me, company_id
            )
            managed_set = set(managed)
            rows = [r for r in rows if r.get("employee_id") in managed_set]
        out: List[dict] = []
        for row in rows:
            out.append(_enrich_absence_row_keep_employee(dict(row)))
        return out
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{absence_id}/manager-approve", response_model=AbsenceRequest)
def manager_approve_absence(
    absence_id: str,
    body: ManagerApprovalRequest,
    current_user: User = Depends(get_current_user),
):
    """Approuve ou refuse au niveau manager (avant validation RH)."""
    try:
        company_id = _require_active_company_absences(current_user)
        if not body.approved:
            if body.rejection_reason is None or not str(body.rejection_reason).strip():
                raise ValueError("Un motif de refus est requis.")

        if not current_user.has_rh_access_in_company(company_id):
            me = absence_router.resolve_employee_id_for_user(
                str(current_user.id), str(company_id)
            )
            if not me:
                raise HTTPException(
                    status_code=403,
                    detail="Profil employé requis pour cette action.",
                )
            row = absence_router.get_absence_by_id(absence_id)
            if not row:
                raise LookupError("Demande introuvable.")
            mgr = absence_router.get_team_manager_employee_id(str(row["employee_id"]))
            if mgr != me:
                raise HTTPException(
                    status_code=403,
                    detail="Vous n'êtes pas le manager de l'équipe de ce collaborateur.",
                )

        data = absence_router.approve_absence_by_manager(
            absence_id,
            company_id,
            str(current_user.id),
            body.approved,
            body.rejection_reason.strip() if body.rejection_reason else None,
        )
        try:
            d0, d1 = absence_notif.absence_date_range_iso(data)
            eid = str(data["employee_id"])
            cid = str(data["company_id"])
            at = str(data.get("type") or "")
            if body.approved:
                absence_notif.notify_absence_approved(eid, cid, at, d0, d1)
                absence_notif.notify_leave_request_email(
                    data,
                    event="manager_approval",
                )
            else:
                absence_notif.notify_absence_rejected(
                    eid,
                    cid,
                    at,
                    d0,
                    d1,
                    body.rejection_reason.strip() if body.rejection_reason else None,
                )
        except Exception:
            _log.exception("[absences] notifications manager-approve ignorées")
        enriched = queries.update_absence_request_signed_url_single(absence_id)
        if enriched is not None:
            return enriched
        return _enrich_single_absence_row(dict(data))
    except HTTPException:
        raise
    except (ValueError, LookupError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ----- Employé spécifique (RH) -----


@router.get("/employees/{employee_id}", response_model=List[AbsenceRequest])
def get_absences_for_employee(
    employee_id: str, current_user: User = Depends(get_current_user)
):
    """Demandes d'absence d'un salarié (arrêts maladie, justificatifs signés).

    RH de la société, ou le salarié lui-même — le contrôle précède la
    génération des URLs signées des justificatifs.
    """
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(
            status_code=403, detail="Impossible de déterminer l'entreprise."
        )
    assert_can_read_employee_profile(current_user, employee_id, str(company_id))
    try:
        return queries.get_absences_for_employee(employee_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Erreur interne du serveur: {str(e)}"
        )


# ----- Routes "me" (utilisateur connecté) -----


@router.get(
    "/employees/me/evenements-familiaux",
    response_model=EvenementFamilialQuotaResponse,
)
def get_my_evenements_familiaux(
    current_user: User = Depends(get_current_user),
):
    """Récupère la liste des événements familiaux disponibles avec quota et solde restant."""
    try:
        company_id = _require_active_company_absences(current_user)
        events = queries.get_my_evenements_familiaux(
            str(current_user.id), str(company_id)
        )
        return EvenementFamilialQuotaResponse(
            events=[EvenementFamilialEvent(**e) for e in events]
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/employees/me/balances", response_model=AbsenceBalancesResponse)
def get_my_absence_balances(
    current_user: User = Depends(get_current_user),
):
    """Récupère les soldes de congés calculés pour l'utilisateur connecté."""
    try:
        employee_id = _resolve_employee_id_for_current_user(current_user)
        balances = queries.get_my_absence_balances(employee_id)
        return AbsenceBalancesResponse(balances=balances)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur lors du calcul des soldes.")


@router.get("/employees/me/calendar", response_model=MonthlyCalendarResponse)
def get_my_monthly_calendar(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
):
    """Récupère le calendrier planifié pour un mois donné pour l'utilisateur connecté."""
    try:
        employee_id = _resolve_employee_id_for_current_user(current_user)
        days = queries.get_my_monthly_calendar(employee_id, year, month)
        return MonthlyCalendarResponse(days=days)
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la récupération du calendrier.",
        )


@router.get("/employees/me/history", response_model=List[AbsenceRequest])
def get_my_absences_history(
    current_user: User = Depends(get_current_user),
):
    """Récupère l'historique des demandes d'absence pour l'utilisateur connecté avec URLs des justificatifs."""
    try:
        employee_id = _resolve_employee_id_for_current_user(current_user)
        return queries.get_my_absences_history(employee_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du serveur: {str(e)}",
        )


@router.get("/employees/me/page-data", response_model=AbsencePageData)
def get_my_absences_page_data(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
):
    """Récupère toutes les données pour la page absences (soldes, calendrier, historique)."""
    try:
        employee_id = _resolve_employee_id_for_current_user(current_user)
        data = queries.get_my_absences_page_data(employee_id, year, month)
        return AbsencePageData(**data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur de récupération des données."
        )


@router.get(
    "/employees/{employee_id}/balances",
    response_model=AbsenceBalancesResponse,
)
def get_employee_absence_balances_route(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Soldes de congés d'un collaborateur (vue RH — fiche employé)."""
    cid = _require_rh_company_context(current_user)
    try:
        balances = queries.get_employee_absence_balances_for_rh(str(cid), employee_id)
        return AbsenceBalancesResponse(balances=balances)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur lors du calcul des soldes.")


# ----- Aperçu maintien de salaire -----


@router.get("/{absence_id}/maintenance-preview")
def get_absence_maintenance_preview(
    absence_id: str,
    subrogation_active: bool | None = Query(
        None,
        description="Surcharge subrogation (ex. mode entreprise « par cas »).",
    ),
    current_user: User = Depends(get_current_user),
):
    """Calcule un aperçu maintien / IJSS pour une absence d'arrêt qualifiée."""
    try:
        return queries.get_absence_maintenance_preview(
            absence_id,
            current_user,
            subrogation_active=subrogation_active,
        )
    except (ValueError, LookupError, RuntimeError, PermissionError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{absence_id}/regularisation-at")
def post_absence_regularisation_at(
    absence_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Compare maintien / IJSS maladie simple vs AT pour une absence déjà requalifiée en AT (RH uniquement).
    """
    try:
        return queries.get_absence_regularisation_at(absence_id, current_user)
    except (ValueError, LookupError, RuntimeError, PermissionError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ----- Attestations de salaire -----


@router.post("/{absence_id}/generate-certificate")
def generate_salary_certificate(
    absence_id: str,
    current_user: User = Depends(get_current_user),
):
    """Génère manuellement une attestation de salaire pour un arrêt validé."""
    try:
        cert_id = commands.generate_salary_certificate(
            absence_id, generated_by=str(current_user.id)
        )
        return {
            "certificate_id": cert_id,
            "message": "Attestation générée avec succès",
        }
    except (ValueError, LookupError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{absence_id}/certificate/download")
def download_salary_certificate(
    absence_id: str,
    current_user: User = Depends(get_current_user),
):
    """Télécharge le PDF de l'attestation de salaire."""
    try:
        result = queries.download_salary_certificate(absence_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail="Aucune attestation trouvée pour cet arrêt.",
            )
        pdf_bytes, filename = result
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{absence_id}/certificate")
def get_salary_certificate(
    absence_id: str,
    current_user: User = Depends(get_current_user),
):
    """Récupère les informations de l'attestation de salaire pour un arrêt."""
    try:
        cert_data = queries.get_salary_certificate_info(absence_id)
        if not cert_data:
            raise HTTPException(
                status_code=404,
                detail="Aucune attestation trouvée pour cet arrêt.",
            )
        return cert_data
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{absence_id}/certificate/transmission")
def mark_salary_certificate_transmitted(
    absence_id: str,
    body: SalaryCertificateTransmissionUpdate,
    current_user: User = Depends(get_current_user),
):
    """Marque l'attestation comme transmise à la CPAM (Net-Entreprises)."""
    try:
        _require_rh_company_context(current_user)
        return commands.mark_salary_certificate_transmitted(
            absence_id,
            transmitted=body.transmitted_to_cpam,
            user_id=str(current_user.id),
        )
    except (ValueError, LookupError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ----- Paramètres congés / RTT -----


@router.get(
    "/leave-notification-settings",
    response_model=LeaveNotificationSettingsResponse,
)
def get_leave_notification_settings_route(
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    return leave_notification_settings.get_settings(str(cid))


@router.put(
    "/leave-notification-settings",
    response_model=LeaveNotificationSettingsResponse,
)
def update_leave_notification_settings_route(
    body: LeaveNotificationSettingsUpdate,
    current_user: User = Depends(get_current_user),
):
    cid = _require_leave_notification_settings_write(current_user)
    try:
        return leave_notification_settings.update_settings(
            str(cid),
            body,
            updated_by=str(current_user.id),
        )
    except (ValueError, LookupError, RuntimeError) as e:
        _handle_application_errors(e)


@router.get("/leave-settings", response_model=LeaveSettingsResponse)
def get_leave_settings_route(
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = company_id or _require_active_company_absences(current_user)
    if company_id and not current_user.is_platform_admin:
        _require_rh_company_context(current_user)
    return leave_settings_queries.get_leave_settings(str(cid))


@router.patch("/leave-settings", response_model=LeaveSettingsResponse)
def update_leave_settings_route(
    body: LeaveSettingsUpdate,
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    try:
        return leave_settings_commands.update_leave_settings(str(cid), body)
    except (ValueError, LookupError) as e:
        _handle_application_errors(e)


@router.get("/leave-settings/jtc/annual-run", response_model=JtcAnnualRunResponse)
def get_jtc_annual_run_route(
    year: int = Query(..., ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Aperçu des droits JTC de l'année, calculés sur l'année précédente."""
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    return leave_settings_queries.get_jtc_annual_run(str(cid), year)


@router.post("/leave-settings/jtc/annual-run", response_model=JtcAnnualRunResponse)
def apply_jtc_annual_run_route(
    year: int = Query(..., ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Écrit les droits JTC de l'année. Renvoie ce qui a été appliqué."""
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    try:
        leave_settings_commands.apply_jtc_annual_run(str(cid), year)
    except (ValueError, LookupError) as e:
        _handle_application_errors(e)
    return leave_settings_queries.get_jtc_annual_run(str(cid), year)


@router.get(
    "/leave-settings/balances-overview",
    response_model=LeaveBalancesOverviewResponse,
)
def get_leave_balances_overview_route(
    year: int | None = Query(None, ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    return leave_settings_queries.get_leave_balances_overview(str(cid), year)


@router.get(
    "/leave-settings/employees/{employee_id}/adjustment",
    response_model=EmployeeLeaveAdjustmentResponse,
)
def get_employee_leave_adjustment_route(
    employee_id: str,
    year: int = Query(..., ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    try:
        return leave_settings_queries.get_employee_leave_adjustment(
            str(cid), employee_id, year
        )
    except LookupError as e:
        _handle_application_errors(e)


@router.patch(
    "/leave-settings/employees/{employee_id}/adjustment",
    response_model=EmployeeLeaveAdjustmentResponse,
)
def update_employee_leave_adjustment_route(
    employee_id: str,
    body: EmployeeLeaveAdjustmentUpdate,
    year: int = Query(..., ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    try:
        return leave_settings_commands.update_employee_leave_adjustment(
            str(cid), employee_id, year, body
        )
    except (ValueError, LookupError) as e:
        _handle_application_errors(e)


@router.patch(
    "/leave-settings/employees/{employee_id}/rtt-solde",
    response_model=EmployeeLeaveAdjustmentResponse,
)
def update_employee_rtt_solde_route(
    employee_id: str,
    body: EmployeeRttSoldeUpdate,
    year: int = Query(..., ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    try:
        return leave_settings_commands.apply_rtt_solde_manual(
            str(cid),
            employee_id,
            year,
            rtt_solde=body.rtt_solde,
            note=body.note,
        )
    except (ValueError, LookupError) as e:
        _handle_application_errors(e)


@router.post(
    "/leave-settings/adjustments/import",
    response_model=LeaveAdjustmentImportResult,
)
def import_leave_adjustments_route(
    body: LeaveAdjustmentImportRequest,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    return leave_settings_commands.import_leave_adjustments(str(cid), body)


@router.get("/rtt-year-end/overview", response_model=RttYearEndOverviewResponse)
def get_rtt_year_end_overview_route(
    year: int | None = Query(None, ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    return leave_settings_queries.get_rtt_year_end_overview(str(cid), year)


@router.post("/rtt-year-end/close", response_model=RttYearEndCloseResult)
def close_rtt_year_end_route(
    body: RttYearEndCloseRequest,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    return leave_settings_commands.close_rtt_year_end(
        str(cid), body, str(current_user.id)
    )


@router.get(
    "/fractionnement/settings",
    response_model=FractionnementSettingsResponse,
)
def get_fractionnement_settings(
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = company_id or _require_active_company_absences(current_user)
    return FractionnementSettingsResponse(
        **fractionnement_queries.get_fractionnement_settings(str(cid))
    )


@router.put(
    "/fractionnement/settings",
    response_model=FractionnementSettingsResponse,
)
def update_fractionnement_settings(
    body: FractionnementSettingsUpdate,
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    payload = body.model_dump(exclude_unset=True)
    return FractionnementSettingsResponse(
        **fractionnement_queries.update_fractionnement_settings(str(cid), payload)
    )


@router.get(
    "/fractionnement/preview",
    response_model=list[FractionnementPreviewRow],
)
def get_fractionnement_preview(
    grant_year: int = Query(..., ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    rows = fractionnement_queries.list_fractionnement_preview(str(cid), grant_year)
    return [FractionnementPreviewRow(**r) for r in rows]


@router.put("/fractionnement/inputs/{employee_id}")
def upsert_fractionnement_input(
    employee_id: str,
    body: FractionnementInputUpdate,
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    return fractionnement_queries.upsert_fractionnement_input(
        str(cid),
        employee_id,
        body.grant_year,
        body.cp_reported_june_ouvres,
        body.cp_seniority_deduction_ouvres,
        report_june_manual_override=body.report_june_manual_override,
        seniority_manual_override=body.seniority_manual_override,
        manual_solde_ouvrables=body.manual_solde_ouvrables,
    )


@router.post(
    "/fractionnement/inputs/{employee_id}/reset-auto",
)
def reset_fractionnement_input_auto(
    employee_id: str,
    grant_year: int = Query(..., ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    return fractionnement_queries.reset_fractionnement_input_to_auto(
        str(cid), employee_id, grant_year
    )


@router.post(
    "/fractionnement/validate",
    response_model=FractionnementValidateResult,
)
def validate_fractionnement_route(
    grant_year: int = Query(..., ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    return FractionnementValidateResult(
        **fractionnement_queries.validate_fractionnement_grants(
            str(cid), grant_year, validated_by=str(current_user.id)
        )
    )


@router.get(
    "/leave-campaign/dashboard",
    response_model=LeaveCampaignDashboard,
)
def get_leave_campaign_dashboard_route(
    grant_year: int | None = Query(None, ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    return LeaveCampaignDashboard(
        **leave_campaign_queries.get_leave_campaign_dashboard(
            str(cid), grant_year=grant_year
        )
    )


@router.get(
    "/cp-seniority-settings",
    response_model=CpSenioritySettingsResponse,
)
def get_cp_seniority_settings_route(
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = company_id or _require_active_company_absences(current_user)
    return CpSenioritySettingsResponse(
        **cp_seniority_queries.get_cp_seniority_settings(str(cid))
    )


@router.patch(
    "/cp-seniority-settings",
    response_model=CpSenioritySettingsResponse,
)
def update_cp_seniority_settings_route(
    body: CpSenioritySettingsUpdate,
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    payload = body.model_dump(exclude_unset=True)
    return CpSenioritySettingsResponse(
        **cp_seniority_commands.update_cp_seniority_settings(str(cid), payload)
    )


@router.post(
    "/cp-seniority-settings/apply-preset/{preset}",
    response_model=CpSenioritySettingsResponse,
)
def apply_cp_seniority_preset_route(
    preset: str,
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    try:
        return CpSenioritySettingsResponse(
            **cp_seniority_commands.apply_cp_seniority_preset(str(cid), preset)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/cp-seniority-settings/preview",
    response_model=list[CpSeniorityPreviewRow],
)
def get_cp_seniority_preview_route(
    grant_year: int = Query(..., ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    rows = cp_seniority_queries.list_cp_seniority_preview(str(cid), grant_year)
    return [CpSeniorityPreviewRow(**r) for r in rows]


@router.post(
    "/cp-seniority-settings/validate",
    response_model=CpSeniorityValidateResult,
)
def validate_cp_seniority_route(
    grant_year: int = Query(..., ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    return CpSeniorityValidateResult(
        **cp_seniority_commands.validate_cp_seniority_grants(
            str(cid), grant_year, validated_by=str(current_user.id)
        )
    )


@router.patch("/cp-seniority-grants/{employee_id}")
def override_cp_seniority_grant_route(
    employee_id: str,
    body: CpSeniorityGrantOverride,
    company_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh_company_context(current_user)
    if company_id and str(company_id) != str(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    return cp_seniority_commands.override_cp_seniority_grant(
        str(cid),
        employee_id,
        body.grant_year,
        body.days_granted,
        validated_by=str(current_user.id),
        note=body.note,
    )


@router.get("/{absence_id}", response_model=AbsenceRequest)
def get_absence_request_detail_for_user(
    absence_id: str,
    current_user: User = Depends(get_current_user),
):
    """Détail d'une absence (collaborateur) avec statut attestation IJSS."""
    try:
        company_id = _require_active_company_absences(current_user)
        return queries.get_absence_request_detail(
            str(current_user.id), str(company_id), absence_id
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
