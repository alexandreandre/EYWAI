"""Routes REST objectifs & KPI."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.platform_admin import is_platform_admin
from app.core.security import get_current_user
from app.modules.access_control.application.service import access_control_service
from app.modules.objectives.application import commands, queries
from app.modules.objectives.schemas.requests import (
    CheckinCreate,
    CompanyServiceCreate,
    MilestoneCreate,
    MilestoneUpdate,
    ObjectiveCreate,
    ObjectiveEvaluate,
    ObjectiveUpdate,
)
from app.modules.objectives.schemas.responses import (
    AchievementRateResponse,
    CompanyService,
    DeclineToTeamResult,
    EmployeeObjective,
    ObjectiveCheckin,
    ObjectiveMilestone,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/objectives", tags=["Objectives"])


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


def _employee_scope_id(user: User, company_id: str) -> Optional[str]:
    return queries.get_employee_id_for_user_scope(str(user.id), company_id)


_OBJECTIVES_VIEW = "view_objectives_reporting"
_OBJECTIVES_CREATE = "create_individual_objective"
_OBJECTIVES_EVALUATE = "evaluate_objective"
_OBJECTIVES_CANCEL = "cancel_objective"
_OBJECTIVES_MILESTONE = "update_objective_milestone"


def _require_objective_employee_access(
    current_user: User, company_id: str, permission_code: str, employee_id: str
) -> None:
    access_control_service.require_employee_access(
        current_user, company_id, permission_code, employee_id
    )


def _filter_objectives_in_scope(
    current_user: User, company_id: str, objectives: List[EmployeeObjective]
) -> List[EmployeeObjective]:
    if current_user.is_platform_admin:
        return objectives
    employee_ids = [str(obj.employee_id or "") for obj in objectives if obj.employee_id]
    allowed = set(
        access_control_service.filter_allowed_employee_ids(
            str(current_user.id), company_id, _OBJECTIVES_VIEW, employee_ids
        )
    )
    if not allowed and current_user.has_rh_access_in_company(company_id):
        return objectives
    return [
        obj
        for obj in objectives
        if not obj.employee_id or str(obj.employee_id) in allowed
    ]


def _require_objective_scope(
    current_user: User,
    company_id: str,
    objective_id: str,
    permission_code: str,
) -> EmployeeObjective:
    obj = queries.get_objective(objective_id, company_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Objectif non trouvé.")
    if obj.employee_id:
        _require_objective_employee_access(
            current_user, company_id, permission_code, obj.employee_id
        )
    return obj


@router.get("/achievement-rate", response_model=AchievementRateResponse)
def route_achievement_rate(
    period_year: int,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        rate = queries.get_achievement_rate(_company_id(current_user), period_year)
        return AchievementRateResponse(rate=rate)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/services", response_model=List[CompanyService])
def route_list_services(current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.list_company_services(_company_id(current_user))
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/services", response_model=CompanyService, status_code=201)
def route_create_service(
    data: CompanyServiceCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        row = commands.create_company_service(_company_id(current_user), data.name)
        return CompanyService.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("", response_model=List[EmployeeObjective])
def route_list_objectives(
    employee_id: Optional[str] = None,
    service_id: Optional[str] = None,
    period_year: Optional[int] = None,
    status: Optional[str] = None,
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
):
    cid = _company_id(current_user)
    try:
        if _is_rh(current_user):
            rows = queries.get_objectives(
                cid,
                employee_id=employee_id,
                service_id=service_id,
                period_year=period_year,
                status=status,
                include_inactive_employees=include_inactive,
            )
            if employee_id:
                _require_objective_employee_access(
                    current_user, cid, _OBJECTIVES_VIEW, employee_id
                )
            return _filter_objectives_in_scope(current_user, cid, rows)
        my_emp = _employee_scope_id(current_user, cid)
        if not my_emp:
            raise HTTPException(
                status_code=403,
                detail="Aucun profil collaborateur lié à votre compte pour cette entreprise.",
            )
        return queries.get_objectives(
            cid,
            employee_id=my_emp,
            service_id=None,
            period_year=period_year,
            status=status,
            include_inactive_employees=include_inactive,
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("", response_model=EmployeeObjective, status_code=201)
def route_create_objective(
    data: ObjectiveCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    if data.employee_id:
        _require_objective_employee_access(
            current_user, cid, _OBJECTIVES_CREATE, data.employee_id
        )
    try:
        return commands.create_objective(cid, data, str(current_user.id))
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/{objective_id}/previous-year", response_model=List[EmployeeObjective])
def route_previous_year(objective_id: str, current_user: User = Depends(get_current_user)):
    cid = _company_id(current_user)
    try:
        if not _is_rh(current_user):
            obj = queries.get_objective(objective_id, cid)
            if obj is None:
                raise HTTPException(status_code=404, detail="Objectif non trouvé.")
            my_emp = _employee_scope_id(current_user, cid)
            if not my_emp or obj.employee_id != my_emp:
                raise HTTPException(status_code=403, detail="Accès refusé.")
        else:
            _require_objective_scope(
                current_user, cid, objective_id, _OBJECTIVES_VIEW
            )
        return queries.get_previous_year_objectives_for_objective(objective_id, cid)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/{objective_id}", response_model=EmployeeObjective)
def route_get_objective(objective_id: str, current_user: User = Depends(get_current_user)):
    cid = _company_id(current_user)
    try:
        out = queries.get_objective(objective_id, cid)
        if out is None:
            raise HTTPException(status_code=404, detail="Objectif non trouvé.")
        if not _is_rh(current_user):
            my_emp = _employee_scope_id(current_user, cid)
            if not my_emp:
                raise HTTPException(status_code=403, detail="Accès refusé.")
            if out.employee_id and out.employee_id != my_emp:
                raise HTTPException(status_code=403, detail="Accès refusé.")
        elif out.employee_id:
            _require_objective_employee_access(
                current_user, cid, _OBJECTIVES_VIEW, out.employee_id
            )
        return out
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.put("/{objective_id}", response_model=EmployeeObjective)
def route_update_objective(
    objective_id: str,
    data: ObjectiveUpdate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    try:
        _require_objective_scope(current_user, cid, objective_id, _OBJECTIVES_CREATE)
        return commands.update_objective(
            objective_id, cid, data, str(current_user.id)
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/{objective_id}/cancel", status_code=204)
def route_cancel_objective(
    objective_id: str, current_user: User = Depends(get_current_user)
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    try:
        _require_objective_scope(current_user, cid, objective_id, _OBJECTIVES_CANCEL)
        commands.cancel_objective(objective_id, cid)
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.delete("/{objective_id}", status_code=204)
def route_delete_objective(
    objective_id: str, current_user: User = Depends(get_current_user)
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    try:
        _require_objective_scope(current_user, cid, objective_id, _OBJECTIVES_CANCEL)
        commands.delete_objective(objective_id, cid)
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/{objective_id}/evaluate", response_model=EmployeeObjective)
def route_evaluate(
    objective_id: str,
    data: ObjectiveEvaluate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    try:
        _require_objective_scope(current_user, cid, objective_id, _OBJECTIVES_EVALUATE)
        return commands.evaluate_objective(objective_id, cid, data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/{objective_id}/decline-to-team", response_model=DeclineToTeamResult)
def route_decline_to_team(
    objective_id: str, current_user: User = Depends(get_current_user)
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    try:
        _require_objective_scope(current_user, cid, objective_id, _OBJECTIVES_CREATE)
        return commands.decline_to_team(
            objective_id, cid, str(current_user.id)
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/{objective_id}/milestones", response_model=ObjectiveMilestone, status_code=201)
def route_add_milestone(
    objective_id: str,
    data: MilestoneCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    try:
        _require_objective_scope(current_user, cid, objective_id, _OBJECTIVES_MILESTONE)
        row = commands.add_milestone(
            objective_id, cid, data, str(current_user.id)
        )
        return queries.objective_milestone_from_row(row)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.put("/{objective_id}/milestones/{milestone_id}", response_model=ObjectiveMilestone)
def route_update_milestone(
    objective_id: str,
    milestone_id: str,
    data: MilestoneUpdate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    try:
        _require_objective_scope(current_user, cid, objective_id, _OBJECTIVES_MILESTONE)
        row = commands.update_milestone(
            objective_id,
            milestone_id,
            cid,
            data,
            str(current_user.id),
        )
        return queries.objective_milestone_from_row(row)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.delete("/{objective_id}/milestones/{milestone_id}", status_code=204)
def route_delete_milestone(
    objective_id: str,
    milestone_id: str,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    try:
        _require_objective_scope(current_user, cid, objective_id, _OBJECTIVES_MILESTONE)
        commands.delete_milestone(objective_id, milestone_id, cid)
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/{objective_id}/checkins", response_model=ObjectiveCheckin, status_code=201)
def route_add_checkin(
    objective_id: str,
    data: CheckinCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    try:
        _require_objective_scope(current_user, cid, objective_id, _OBJECTIVES_CREATE)
        row = commands.add_checkin(
            objective_id, cid, data, str(current_user.id)
        )
        return queries.objective_checkin_from_row(row)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)
