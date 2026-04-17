"""Routes REST catalogue formations."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.security import get_current_user
from app.modules.training.application import commands, queries
from app.modules.training.infrastructure.repository import training_repository
from app.modules.training.schemas.requests import (
    TrainingCatalogCreate,
    TrainingCatalogUpdate,
    TrainingEnrollmentCreate,
    TrainingEnrollmentUpdate,
)
from app.modules.training.schemas.responses import (
    TotalConsumedResponse,
    TrainingCatalog,
    TrainingEnrollment,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/training", tags=["Training"])


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
    if getattr(user, "is_super_admin", False):
        return True
    if not user.active_company_id:
        return False
    return user.has_rh_access_in_company(user.active_company_id)


def _employee_scope_id(user: User, company_id: str) -> Optional[str]:
    return training_repository.get_employee_id_for_user(str(user.id), company_id)


@router.get("/consumed/{year}", response_model=TotalConsumedResponse)
def route_consumed(year: int, current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        total = queries.get_total_consumed(_company_id(current_user), year)
        return TotalConsumedResponse(year=year, total_ht=total)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/catalog", response_model=List[TrainingCatalog])
def route_list_catalog(
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
):
    try:
        return queries.get_trainings(_company_id(current_user), include_archived=include_archived)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/catalog/{training_id}", response_model=TrainingCatalog)
def route_get_catalog(training_id: str, current_user: User = Depends(get_current_user)):
    cid = _company_id(current_user)
    try:
        out = queries.get_training(training_id, cid)
        if out is None:
            raise HTTPException(status_code=404, detail="Formation non trouvée.")
        return out
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/catalog", response_model=TrainingCatalog, status_code=201)
def route_create_catalog(
    data: TrainingCatalogCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.create_training(_company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.put("/catalog/{training_id}", response_model=TrainingCatalog)
def route_update_catalog(
    training_id: str,
    data: TrainingCatalogUpdate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.update_training(training_id, _company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/catalog/{training_id}/archive", status_code=204)
def route_archive_catalog(
    training_id: str, current_user: User = Depends(get_current_user)
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        commands.archive_training(training_id, _company_id(current_user))
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/enrollments", response_model=List[TrainingEnrollment])
def route_list_enrollments(
    training_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    cid = _company_id(current_user)
    try:
        if _is_rh(current_user):
            return queries.get_enrollments(
                cid,
                training_id=training_id,
                employee_id=employee_id,
                status=status,
            )
        my_emp = _employee_scope_id(current_user, cid)
        if not my_emp:
            raise HTTPException(
                status_code=403,
                detail="Aucun profil collaborateur lié à votre compte pour cette entreprise.",
            )
        if not employee_id or employee_id != my_emp:
            raise HTTPException(status_code=403, detail="Accès non autorisé.")
        return queries.get_enrollments(
            cid,
            training_id=training_id,
            employee_id=my_emp,
            status=status,
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/enrollments/{enrollment_id}", response_model=TrainingEnrollment)
def route_get_enrollment(enrollment_id: str, current_user: User = Depends(get_current_user)):
    cid = _company_id(current_user)
    try:
        out = queries.get_enrollment(enrollment_id, cid)
        if out is None:
            raise HTTPException(status_code=404, detail="Inscription non trouvée.")
        if not _is_rh(current_user):
            my_emp = _employee_scope_id(current_user, cid)
            if not my_emp or out.employee_id != my_emp:
                raise HTTPException(status_code=403, detail="Accès refusé.")
        return out
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/enrollments", response_model=TrainingEnrollment, status_code=201)
def route_create_enrollment(
    data: TrainingEnrollmentCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.create_enrollment(_company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.put("/enrollments/{enrollment_id}", response_model=TrainingEnrollment)
def route_update_enrollment(
    enrollment_id: str,
    data: TrainingEnrollmentUpdate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.update_enrollment(enrollment_id, _company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/enrollments/{enrollment_id}/cancel", status_code=204)
def route_cancel_enrollment(
    enrollment_id: str, current_user: User = Depends(get_current_user)
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        commands.cancel_enrollment(enrollment_id, _company_id(current_user))
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)
