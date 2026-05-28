"""Routes REST pour les modèles de trames d'entretien (RH)."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.platform_admin import is_platform_admin
from app.core.security import get_current_user
from app.modules.interview_templates.application import commands, queries
from app.modules.interview_templates.schemas import (
    InterviewTemplate,
    InterviewTemplateCreate,
    InterviewTemplateUpdate,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/interview-templates", tags=["InterviewTemplates"])


def _handle_application_errors(e: Exception) -> None:
    if isinstance(e, PermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    if isinstance(e, LookupError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if isinstance(e, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Erreur inattendue: {str(e)}",
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


@router.get("", response_model=List[InterviewTemplate])
def list_templates(current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.get_templates(_company_id(current_user))
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/{template_id}", response_model=InterviewTemplate)
def get_template_detail(
    template_id: str,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        out = queries.get_template(template_id, _company_id(current_user))
        if out is None:
            raise HTTPException(status_code=404, detail="Modèle non trouvé.")
        return out
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("", response_model=InterviewTemplate, status_code=201)
def create_template_route(
    data: InterviewTemplateCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.create_template(
            _company_id(current_user), data, str(current_user.id)
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.put("/{template_id}", response_model=InterviewTemplate)
def update_template_route(
    template_id: str,
    data: InterviewTemplateUpdate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.update_template(
            template_id, _company_id(current_user), data
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/{template_id}/archive", status_code=204)
def archive_template_route(
    template_id: str,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        commands.archive_template(template_id, _company_id(current_user))
        return None
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/{template_id}/duplicate", response_model=InterviewTemplate, status_code=201)
def duplicate_template_route(
    template_id: str,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.duplicate_template(
            template_id, _company_id(current_user), str(current_user.id)
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)
