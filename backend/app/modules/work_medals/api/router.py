"""Router API médailles du travail."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.users.schemas.responses import User
from app.modules.work_medals.application import commands, detection, queries
from app.modules.work_medals.schemas.requests import (
    WorkMedalApproveRequest,
    WorkMedalDismissRequest,
    WorkMedalSettingsUpdate,
)
from app.modules.work_medals.schemas.responses import (
    WorkMedalCase,
    WorkMedalScanResult,
    WorkMedalSettings,
    WorkMedalSummary,
)
from app.shared.employee_resolution import resolve_employee_id_for_user_account

router = APIRouter(prefix="/api/work-medals", tags=["WorkMedals"])
settings_router = APIRouter(prefix="/api/work-medal-settings", tags=["WorkMedals"])


def _can_write(user: User, company_id: str) -> bool:
    if user.is_platform_admin:
        return True
    return user.get_role_in_company(company_id) in ("admin", "rh")


def _require_company(user: User) -> str:
    company_id = user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    cid = str(company_id)
    if not user.has_access_to_company(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return cid


@settings_router.get("/", response_model=WorkMedalSettings)
def get_settings_route(current_user: User = Depends(get_current_user)) -> WorkMedalSettings:
    return queries.get_work_medal_settings(_require_company(current_user))


@settings_router.put("/", response_model=WorkMedalSettings)
def put_settings_route(
    body: WorkMedalSettingsUpdate,
    current_user: User = Depends(get_current_user),
) -> WorkMedalSettings:
    cid = _require_company(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Modification réservée aux RH")
    try:
        return commands.save_work_medal_settings(cid, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/", response_model=List[WorkMedalCase])
def list_cases_route(
    status: Optional[str] = Query(default=None),
    medal_level: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> List[WorkMedalCase]:
    cid = _require_company(current_user)
    return queries.list_work_medal_cases(cid, status=status, medal_level=medal_level)


@router.get("/summary", response_model=WorkMedalSummary)
def summary_route(current_user: User = Depends(get_current_user)) -> WorkMedalSummary:
    return queries.get_work_medal_summary(_require_company(current_user))


@router.post("/scan", response_model=WorkMedalScanResult)
def scan_route(current_user: User = Depends(get_current_user)) -> WorkMedalScanResult:
    cid = _require_company(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Scan réservé aux RH")
    return detection.scan_company_work_medals(cid)


@router.get("/employees/{employee_id}", response_model=List[WorkMedalCase])
def employee_cases_route(
    employee_id: str,
    current_user: User = Depends(get_current_user),
) -> List[WorkMedalCase]:
    cid = _require_company(current_user)
    cases = queries.list_employee_work_medal_cases(employee_id)
    if cases and cases[0].company_id != cid:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return cases


@router.post("/{case_id}/employee-confirm", response_model=WorkMedalCase)
def employee_confirm_route(
    case_id: str,
    current_user: User = Depends(get_current_user),
) -> WorkMedalCase:
    cid = _require_company(current_user)
    employee_id = resolve_employee_id_for_user_account(str(current_user.id), cid)
    if not employee_id:
        raise HTTPException(status_code=403, detail="Profil employé introuvable")
    try:
        return commands.employee_confirm_case(case_id, employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{case_id}/approve", response_model=WorkMedalCase)
def approve_route(
    case_id: str,
    body: WorkMedalApproveRequest,
    current_user: User = Depends(get_current_user),
) -> WorkMedalCase:
    cid = _require_company(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Validation réservée aux RH")
    try:
        return commands.approve_work_medal_case(
            case_id, cid, str(current_user.id), body
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{case_id}/dismiss", response_model=WorkMedalCase)
def dismiss_route(
    case_id: str,
    body: WorkMedalDismissRequest,
    current_user: User = Depends(get_current_user),
) -> WorkMedalCase:
    cid = _require_company(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Action réservée aux RH")
    try:
        return commands.dismiss_work_medal_case(case_id, cid, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
