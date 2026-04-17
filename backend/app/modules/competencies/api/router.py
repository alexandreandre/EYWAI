"""Routes REST compétences (référentiel, évaluations, matrice, export)."""

from __future__ import annotations

import traceback
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.security import get_current_user
from app.modules.competencies.application import commands, queries
from app.modules.competencies.infrastructure.repository import competencies_repository
from app.modules.competencies.schemas.requests import (
    CompetencyRefCreate,
    CompetencyRefUpdate,
    EmployeeCompetencyCreate,
)
from app.modules.competencies.schemas.responses import (
    CompetencyMatrix,
    CompetencyRef,
    EmployeeCompetency,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/competencies", tags=["Competencies"])


def _handle_application_errors(e: Exception) -> None:
    traceback.print_exc()
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
    return competencies_repository.get_employee_id_for_user(str(user.id), company_id)


# --- Référentiel ---


@router.get("/refs", response_model=List[CompetencyRef])
def route_list_refs(
    include_archived: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.get_competency_refs(_company_id(current_user), include_archived)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/refs/{ref_id}", response_model=CompetencyRef)
def route_get_ref(ref_id: str, current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        out = queries.get_competency_ref(ref_id, _company_id(current_user))
        if out is None:
            raise HTTPException(status_code=404, detail="Compétence non trouvée.")
        return out
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/refs", response_model=CompetencyRef, status_code=201)
def route_create_ref(
    data: CompetencyRefCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.create_competency_ref(_company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/refs/{ref_id}", response_model=CompetencyRef)
def route_update_ref(
    ref_id: str,
    data: CompetencyRefUpdate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.update_competency_ref(ref_id, _company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/refs/{ref_id}/archive", status_code=204)
def route_archive_ref(ref_id: str, current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        commands.archive_competency_ref(ref_id, _company_id(current_user))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


# --- Évaluations ---


@router.get("/evaluations", response_model=List[EmployeeCompetency])
def route_list_evaluations(
    employee_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _company_id(current_user)
    if _is_rh(current_user):
        try:
            return queries.get_latest_evaluations(cid, employee_id=employee_id)
        except HTTPException:
            raise
        except Exception as e:
            _handle_application_errors(e)
    scope = _employee_scope_id(current_user, cid)
    if not scope:
        raise HTTPException(status_code=403, detail="Profil collaborateur introuvable.")
    if employee_id and employee_id != scope:
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    try:
        return queries.get_latest_evaluations(cid, employee_id=scope)
    except Exception as e:
        _handle_application_errors(e)


@router.post("/evaluations", response_model=EmployeeCompetency, status_code=201)
def route_evaluate(
    data: EmployeeCompetencyCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.evaluate_employee(
            _company_id(current_user), data, str(current_user.id)
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


# --- Matrice ---


@router.get("/matrix/export")
def route_export_matrix(
    service_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        content, fname = commands.export_matrix_excel_bytes(
            _company_id(current_user), service_id=service_id, category=category
        )
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{fname}"',
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/matrix", response_model=CompetencyMatrix)
def route_matrix(
    service_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.get_matrix(
            _company_id(current_user), service_id=service_id, category=category
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)
