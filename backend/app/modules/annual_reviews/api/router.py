"""
Router annual_reviews — délègue toute la logique à la couche application.

Comportement HTTP identique au legacy. Aucune logique métier : uniquement
auth (company_id, is_rh), appel application, et traduction des exceptions en HTTP.
"""

from datetime import date
from typing import Any, Dict, List, Optional

import io

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.platform_admin import is_platform_admin
from app.core.security import get_current_user
from app.modules.users.schemas.responses import User

from app.modules.annual_reviews.application import commands, queries, service
from app.modules.annual_reviews.application import planning_suggestions as planning_queries
from app.modules.annual_reviews.infrastructure.mappers import row_to_annual_review_read
from app.modules.annual_reviews.schemas import (
    AnnualReviewCreate,
    AnnualReviewListItem,
    AnnualReviewRead,
    AnnualReviewUpdate,
    PlanningSuggestionRead,
    SendForSignatureBody,
)

router = APIRouter(
    prefix="/api/annual-reviews",
    tags=["Annual Reviews"],
)


def _company_id(user: User) -> str:
    if not user.active_company_id:
        raise HTTPException(
            status_code=400, detail="Aucune entreprise active sélectionnée."
        )
    return user.active_company_id


def _is_rh(user: User) -> bool:
    if is_platform_admin(user):
        return True
    if not user.active_company_id:
        return False
    return user.has_rh_access_in_company(user.active_company_id)


def _repo():
    return service.get_repository()


def _resolve_employee_id_for_current_user(user: User) -> Optional[str]:
    """Id fiche employees pour le compte connecté (user_id, id ou e-mail)."""
    from app.shared.employee_resolution import resolve_employee_id_for_user_account

    cid = _company_id(user)
    return resolve_employee_id_for_user_account(str(user.id), cid)


# --- GET list (RH)
@router.get("", response_model=List[AnnualReviewListItem])
def get_all_annual_reviews(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    return queries.list_all_annual_reviews(
        _company_id(current_user), year=year, status=status, repository=_repo()
    )


# --- GET by employee (RH)
@router.get("/by-employee/{employee_id}", response_model=List[AnnualReviewRead])
def get_employee_annual_reviews(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.list_employee_annual_reviews(
            employee_id, _company_id(current_user), repository=_repo()
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e) or "Employé non trouvé.")


# --- GET my reviews
@router.get("/me", response_model=List[AnnualReviewRead])
def get_my_annual_reviews(current_user: User = Depends(get_current_user)):
    employee_id = _resolve_employee_id_for_current_user(current_user)
    if not employee_id:
        return []
    return queries.get_my_annual_reviews(
        employee_id, _company_id(current_user), repository=_repo()
    )


# --- GET my current
@router.get("/me/current", response_model=Optional[AnnualReviewRead])
def get_my_current_annual_review(current_user: User = Depends(get_current_user)):
    employee_id = _resolve_employee_id_for_current_user(current_user)
    if not employee_id:
        return None
    return queries.get_my_current_annual_review(
        employee_id,
        _company_id(current_user),
        date.today().year,
        repository=_repo(),
    )


# --- GET planning suggestions (RH)
@router.get("/planning-suggestions", response_model=List[PlanningSuggestionRead])
def get_planning_suggestions(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    return planning_queries.list_planning_suggestions(_company_id(current_user), year=year)


# --- GET by id
@router.get("/{review_id}", response_model=AnnualReviewRead)
def get_annual_review(
    review_id: str,
    current_user: User = Depends(get_current_user),
):
    scope_id = (
        _resolve_employee_id_for_current_user(current_user)
        if not _is_rh(current_user)
        else str(current_user.id)
    )
    out = queries.get_annual_review_by_id(
        review_id,
        _company_id(current_user),
        scope_id or "",
        _is_rh(current_user),
        repository=_repo(),
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Entretien non trouvé.")
    return out


# --- POST create (RH)
@router.post("", response_model=AnnualReviewRead, status_code=201)
def create_annual_review(
    data: AnnualReviewCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        row = commands.create_annual_review(
            _company_id(current_user), data.model_dump(), repository=_repo()
        )
        return row_to_annual_review_read(row)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e) or "Employé non trouvé.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(
            status_code=500, detail=str(e) or "Erreur lors de la création."
        )


# --- PUT update
@router.put("/{review_id}", response_model=AnnualReviewRead)
def update_annual_review(
    review_id: str,
    data: AnnualReviewUpdate,
    current_user: User = Depends(get_current_user),
):
    try:
        scope_id = (
            _resolve_employee_id_for_current_user(current_user)
            if not _is_rh(current_user)
            else str(current_user.id)
        )
        updated = commands.update_annual_review(
            review_id,
            _company_id(current_user),
            scope_id or "",
            _is_rh(current_user),
            data.model_dump(exclude_unset=True),
            repository=_repo(),
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Entretien non trouvé.")
        return row_to_annual_review_read(updated)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e) or "Entretien non trouvé.")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e) or "Accès non autorisé.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(
            status_code=500, detail=str(e) or "Erreur lors de la mise à jour."
        )


# --- POST mark completed (RH)
@router.post("/{review_id}/mark-completed", response_model=AnnualReviewRead)
def mark_completed(
    review_id: str,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        row = commands.mark_completed(
            review_id, _company_id(current_user), repository=_repo()
        )
        return row_to_annual_review_read(row)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e) or "Entretien non trouvé.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(
            status_code=500, detail=str(e) or "Erreur lors du marquage comme réalisé."
        )


# --- POST envoi signature Yousign (RH)
@router.post("/{review_id}/send-for-signature", response_model=Dict[str, Any])
def send_annual_review_for_signature(
    review_id: str,
    body: Optional[SendForSignatureBody] = Body(None),
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    payload = body if body is not None else SendForSignatureBody()
    try:
        return commands.send_annual_review_for_signature(
            review_id,
            _company_id(current_user),
            payload.second_signer_email,
            payload.expiration_days,
            repository=_repo(),
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e) or "Entretien non trouvé.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(
            status_code=500, detail=str(e) or "Erreur lors de l'envoi Yousign."
        )


# --- GET PDF
@router.get("/{review_id}/pdf")
def download_annual_review_pdf(
    review_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        scope_id = (
            _resolve_employee_id_for_current_user(current_user)
            if not _is_rh(current_user)
            else str(current_user.id)
        )
        pdf_bytes, filename = service.generate_annual_review_pdf(
            review_id,
            _company_id(current_user),
            scope_id or "",
            _is_rh(current_user),
        )
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e) or "Entretien non trouvé.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e) or "Erreur génération PDF.")


# --- GET convocation PDF
@router.get("/{review_id}/convocation-pdf")
def download_convocation_pdf(
    review_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        scope_id = (
            _resolve_employee_id_for_current_user(current_user)
            if not _is_rh(current_user)
            else str(current_user.id)
        )
        pdf_bytes, filename = service.generate_convocation_pdf(
            review_id,
            _company_id(current_user),
            scope_id or "",
            _is_rh(current_user),
        )
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e) or "Entretien non trouvé.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e) or "Erreur génération PDF convocation.")


# --- DELETE (RH)
@router.delete("/{review_id}", status_code=204)
def delete_annual_review(
    review_id: str,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        commands.delete_annual_review(
            review_id, _company_id(current_user), repository=_repo()
        )
        return None
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e) or "Entretien non trouvé.")
