"""Router API — widget Signatures en attente."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.signatures.application import queries as application_queries
from app.modules.signatures.schemas.responses import PendingSignaturesResponse
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/signatures", tags=["Signatures"])


def _handle_application_errors(e: Exception) -> None:
    """ValueError → 400, LookupError → 404, PermissionError → 403, RuntimeError → 500."""
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(e, LookupError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, PermissionError):
        raise HTTPException(status_code=403, detail=str(e))
    if isinstance(e, RuntimeError):
        raise HTTPException(status_code=500, detail=str(e))
    raise


def _require_active_company(current_user: User) -> str:
    cid = current_user.active_company_id
    if not cid:
        raise HTTPException(status_code=400, detail="Entreprise active requise.")
    return str(cid)


@router.get("/pending", response_model=PendingSignaturesResponse)
def get_pending_signatures_rh(current_user: User = Depends(get_current_user)):
    """Vue RH — toutes les procédures en attente de l'entreprise."""
    company_id = _require_active_company(current_user)
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return application_queries.get_widget_pending_rh(company_id)
    except Exception as e:
        _handle_application_errors(e)


@router.get("/me/pending", response_model=PendingSignaturesResponse)
def get_my_pending_signatures(current_user: User = Depends(get_current_user)):
    """Vue salarié — ses propres procédures en attente."""
    company_id = _require_active_company(current_user)
    try:
        return application_queries.get_widget_pending_for_current_user(
            str(current_user.id), company_id
        )
    except Exception as e:
        _handle_application_errors(e)


@router.post("/{review_id}/remind")
def remind_signature_signer(
    review_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Relance un signataire depuis le widget RH."""
    company_id = _require_active_company(current_user)
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return application_queries.send_signature_reminder(review_id, company_id)
    except Exception as e:
        _handle_application_errors(e)
