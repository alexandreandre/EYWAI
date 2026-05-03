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
from app.modules.audit.infrastructure.repository import audit_repository
from app.modules.webhooks.infrastructure.repository import webhook_repository
from app.modules.users.schemas.responses import User

from app.modules.absences.application import commands, notifications as absence_notif, queries
from app.modules.absences.infrastructure.queries import resolve_employee_id_for_user
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.absences.schemas.requests import (
    AbsenceRequestCreate,
    AbsenceRequestStatusUpdate,
    ManagerApprovalRequest,
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


# ----- Upload URL -----


@router.post("/get-upload-url", response_model=SignedUploadURL)
async def get_upload_url(
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
async def create_absence_request(request_data: AbsenceRequestCreate):
    """Crée une nouvelle demande d'absence à partir d'une liste de jours."""
    try:
        data = commands.create_absence_request(request_data)
        rid = str(data["id"])
        eid = str(data["employee_id"])
        mgr = absence_repository.get_team_manager_employee_id_for_employee(eid)
        wf = "pending_manager" if mgr else "pending"
        data2 = absence_repository.update(rid, {"workflow_step": wf})
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
        except Exception:
            _log.exception("[absences] notifications création ignorées")
        r = _enrich_single_absence_row(dict(data))
        return r
    except (ValueError, LookupError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/requests/{request_id}/status", response_model=AbsenceRequest)
async def update_absence_request_status(
    request_id: str,
    http_request: Request,
    status_update: AbsenceRequestStatusUpdate,
    current_user: User = Depends(get_current_user),
):
    """Met à jour le statut d'une demande (utilisateur connecté). Génère l'attestation si nécessaire."""
    try:
        req_before = absence_repository.get_by_id(request_id)
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
        )
        extra_ws: dict = {}
        if status_update.status == "validated":
            extra_ws["workflow_step"] = "approved_rh"
        elif status_update.status == "rejected":
            extra_ws["workflow_step"] = "rejected_rh"
        if extra_ws:
            merged = absence_repository.update(request_id, extra_ws)
            if merged:
                data = merged
        _notify_rh_status_change(req_before, status_update.status)
        enriched = queries.update_absence_request_signed_url_single(request_id)
        out = enriched if enriched is not None else data
        cid = str((out or data).get("company_id") or "")
        if cid and status_update.status in ("validated", "rejected"):
            audit_repository.log(
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
            webhook_repository.trigger_event(
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
):
    """Met à jour le statut d'une demande d'absence (pour RH/Admin)."""
    try:
        req_before = absence_repository.get_by_id(request_id)
        if (
            req_before
            and req_before.get("workflow_step") == "pending_manager"
            and req_before.get("status") == "pending"
        ):
            raise HTTPException(
                status_code=400,
                detail="La demande doit d'abord être validée par le manager.",
            )
        data = commands.update_absence_request_status(
            request_id, status_update.status, current_user_id=None
        )
        extra: dict = {}
        if status_update.status == "validated":
            extra["workflow_step"] = "approved_rh"
        elif status_update.status == "rejected":
            extra["workflow_step"] = "rejected_rh"
        if extra:
            merged = absence_repository.update(request_id, extra)
            if merged:
                data = merged
        _notify_rh_status_change(req_before, status_update.status)
        enriched = queries.update_absence_request_signed_url_single(request_id)
        out = enriched if enriched is not None else data
        cid = str((out or data).get("company_id") or "")
        if cid and status_update.status in ("validated", "rejected"):
            audit_repository.log(
                company_id=cid,
                user_id=None,
                user_email=None,
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
            webhook_repository.trigger_event(
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


# ----- Liste globale (RH) -----


@router.get("/", response_model=List[AbsenceRequestWithEmployee])
async def get_absence_requests(
    status: Literal["pending", "validated", "rejected", "cancelled"] | None = None,
):
    """Récupère les demandes d'absence, enrichies avec détails et soldes par employé."""
    try:
        return queries.get_absence_requests(status)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending-manager-approval", response_model=List[AbsencePendingManagerItem])
async def list_pending_manager_approval(
    current_user: User = Depends(get_current_user),
):
    """Demandes en attente de validation manager (périmètre RH ou équipe du manager)."""
    try:
        company_id = _require_active_company_absences(current_user)
        rows = absence_repository.get_pending_manager_approval(company_id)
        if not current_user.has_rh_access_in_company(company_id):
            me = resolve_employee_id_for_user(str(current_user.id))
            if not me:
                raise HTTPException(
                    status_code=403,
                    detail="Profil employé requis pour consulter ces demandes.",
                )
            managed = absence_repository.get_employee_ids_managed_by_manager(
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
async def manager_approve_absence(
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
            me = resolve_employee_id_for_user(str(current_user.id))
            if not me:
                raise HTTPException(
                    status_code=403,
                    detail="Profil employé requis pour cette action.",
                )
            row = absence_repository.get_by_id(absence_id)
            if not row:
                raise LookupError("Demande introuvable.")
            mgr = absence_repository.get_team_manager_employee_id_for_employee(
                str(row["employee_id"])
            )
            if mgr != me:
                raise HTTPException(
                    status_code=403,
                    detail="Vous n'êtes pas le manager de l'équipe de ce collaborateur.",
                )

        data = absence_repository.approve_by_manager(
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
async def get_absences_for_employee(employee_id: str):
    """Récupère toutes les demandes d'absence pour un employé avec URLs des justificatifs."""
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
async def get_my_evenements_familiaux(
    current_user: User = Depends(get_current_user),
):
    """Récupère la liste des événements familiaux disponibles avec quota et solde restant."""
    try:
        events = queries.get_my_evenements_familiaux(str(current_user.id))
        return EvenementFamilialQuotaResponse(
            events=[EvenementFamilialEvent(**e) for e in events]
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/employees/me/balances", response_model=AbsenceBalancesResponse)
async def get_my_absence_balances(
    current_user: User = Depends(get_current_user),
):
    """Récupère les soldes de congés calculés pour l'utilisateur connecté."""
    try:
        balances = queries.get_my_absence_balances(str(current_user.id))
        return AbsenceBalancesResponse(balances=balances)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur lors du calcul des soldes.")


@router.get("/employees/me/calendar", response_model=MonthlyCalendarResponse)
async def get_my_monthly_calendar(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
):
    """Récupère le calendrier planifié pour un mois donné pour l'utilisateur connecté."""
    try:
        days = queries.get_my_monthly_calendar(str(current_user.id), year, month)
        return MonthlyCalendarResponse(days=days)
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la récupération du calendrier.",
        )


@router.get("/employees/me/history", response_model=List[AbsenceRequest])
async def get_my_absences_history(
    current_user: User = Depends(get_current_user),
):
    """Récupère l'historique des demandes d'absence pour l'utilisateur connecté avec URLs des justificatifs."""
    try:
        return queries.get_my_absences_history(str(current_user.id))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du serveur: {str(e)}",
        )


@router.get("/employees/me/page-data", response_model=AbsencePageData)
async def get_my_absences_page_data(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
):
    """Récupère toutes les données pour la page absences (soldes, calendrier, historique)."""
    try:
        data = queries.get_my_absences_page_data(str(current_user.id), year, month)
        return AbsencePageData(**data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur de récupération des données."
        )


# ----- Aperçu maintien de salaire -----


@router.get("/{absence_id}/maintenance-preview")
async def get_absence_maintenance_preview(
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
async def post_absence_regularisation_at(
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
async def generate_salary_certificate(
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
async def download_salary_certificate(
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
async def get_salary_certificate(
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


@router.get("/{absence_id}", response_model=AbsenceRequest)
async def get_absence_request_detail_for_user(
    absence_id: str,
    current_user: User = Depends(get_current_user),
):
    """Détail d'une absence (collaborateur) avec statut attestation IJSS."""
    try:
        return queries.get_absence_request_detail(str(current_user.id), absence_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
