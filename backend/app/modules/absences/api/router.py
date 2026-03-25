"""
Router API du module absences.

Délègue toute la logique à la couche application (commands, queries).
Validation des entrées (schémas), résolution utilisateur (Depends), appel application, retour HTTP.
Comportement HTTP identique à api/routers/absences.py.
"""

import io
import traceback
from typing import List, Literal

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user
from app.modules.users.schemas.responses import User

from app.modules.absences.application import commands, queries
from app.modules.absences.schemas.requests import (
    AbsenceRequestCreate,
    AbsenceRequestStatusUpdate,
)
from app.modules.absences.schemas.responses import (
    AbsenceBalancesResponse,
    AbsencePageData,
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


def _handle_application_errors(e: Exception) -> None:
    """Traduit ValueError/LookupError/RuntimeError en HTTPException."""
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(e, LookupError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, RuntimeError):
        raise HTTPException(status_code=500, detail=str(e))
    raise


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
        return data
    except (ValueError, LookupError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/requests/{request_id}/status", response_model=AbsenceRequest)
async def update_absence_request_status(
    request_id: str,
    status_update: AbsenceRequestStatusUpdate,
    current_user: User = Depends(get_current_user),
):
    """Met à jour le statut d'une demande (utilisateur connecté). Génère l'attestation si nécessaire."""
    try:
        data = commands.update_absence_request_status(
            request_id,
            status_update.status,
            current_user_id=str(current_user.id),
        )
        enriched = queries.update_absence_request_signed_url_single(request_id)
        return enriched if enriched is not None else data
    except (ValueError, LookupError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{request_id}", response_model=AbsenceRequest)
async def update_absence_request(
    request_id: str,
    status_update: AbsenceRequestStatusUpdate,
):
    """Met à jour le statut d'une demande d'absence (pour RH/Admin)."""
    try:
        data = commands.update_absence_request_status(
            request_id, status_update.status, current_user_id=None
        )
        enriched = queries.update_absence_request_signed_url_single(request_id)
        return enriched if enriched is not None else data
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
