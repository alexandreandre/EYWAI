"""Router API CET."""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.access_control.application.service import access_control_service
from app.modules.cet.application import service as cet_service
from app.modules.cet.schemas.requests import (
    CetDepositCpRequest,
    CetDepositRequest,
    CetMovementValidateRequest,
    CetSettingsResponse,
    CetSettingsUpdate,
    CetSummaryResponse,
    CetWithdrawalRequest,
)
from app.shared.employee_resolution import resolve_employee_id_for_user_account


class CetUserContext(Protocol):
    id: str
    active_company_id: str | None

    def has_access_to_company(self, company_id: str) -> bool: ...


router = APIRouter(prefix="/api/cet", tags=["CET"])


def _resolve_company_id(company_id: str | None, user: CetUserContext) -> str:
    target = company_id or user.active_company_id
    if not target:
        raise HTTPException(status_code=400, detail="company_id requis.")
    if not user.has_access_to_company(target):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    return target


def _require_rh(user: CetUserContext, company_id: str) -> None:
    if not access_control_service.can_access_company_as_rh(user, company_id):
        raise HTTPException(status_code=403, detail="Accès RH requis.")


@router.get("/settings", response_model=CetSettingsResponse)
async def get_cet_settings(
    company_id: str | None = Query(None),
    current_user: CetUserContext = Depends(get_current_user),
) -> CetSettingsResponse:
    cid = _resolve_company_id(company_id, current_user)
    return CetSettingsResponse(**cet_service.get_settings(cid))


@router.put("/settings", response_model=CetSettingsResponse)
async def update_cet_settings(
    body: CetSettingsUpdate,
    company_id: str | None = Query(None),
    current_user: CetUserContext = Depends(get_current_user),
) -> CetSettingsResponse:
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    payload = body.model_dump(exclude_unset=True)
    return CetSettingsResponse(**cet_service.update_settings(cid, payload))


@router.get("/me/summary", response_model=CetSummaryResponse)
async def get_my_cet_summary(
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    current_user: CetUserContext = Depends(get_current_user),
) -> CetSummaryResponse:
    cid = _resolve_company_id(None, current_user)
    employee_id = resolve_employee_id_for_user_account(str(current_user.id), cid)
    if not employee_id:
        raise HTTPException(status_code=404, detail="Profil employé introuvable.")
    try:
        summary = cet_service.build_employee_summary(
            employee_id, year=year, month=month
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CetSummaryResponse(**summary)


@router.post("/me/deposits")
async def create_my_cet_deposit(
    body: CetDepositRequest,
    current_user: CetUserContext = Depends(get_current_user),
):
    cid = _resolve_company_id(None, current_user)
    employee_id = resolve_employee_id_for_user_account(str(current_user.id), cid)
    if not employee_id:
        raise HTTPException(status_code=404, detail="Profil employé introuvable.")
    try:
        return cet_service.create_deposit(
            employee_id,
            cid,
            body.hours,
            requested_by=str(current_user.id),
            year=body.year,
            month=body.month,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/deposits/cp")
async def create_my_cet_deposit_cp(
    body: CetDepositCpRequest,
    current_user: CetUserContext = Depends(get_current_user),
):
    cid = _resolve_company_id(None, current_user)
    employee_id = resolve_employee_id_for_user_account(str(current_user.id), cid)
    if not employee_id:
        raise HTTPException(status_code=404, detail="Profil employé introuvable.")
    try:
        return cet_service.create_deposit_cp(
            employee_id,
            cid,
            body.days,
            requested_by=str(current_user.id),
            year=body.year,
            month=body.month,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/withdrawals")
async def create_my_cet_withdrawal(
    body: CetWithdrawalRequest,
    current_user: CetUserContext = Depends(get_current_user),
):
    cid = _resolve_company_id(None, current_user)
    employee_id = resolve_employee_id_for_user_account(str(current_user.id), cid)
    if not employee_id:
        raise HTTPException(status_code=404, detail="Profil employé introuvable.")
    try:
        return cet_service.create_withdrawal(
            employee_id,
            cid,
            body.hours,
            requested_by=str(current_user.id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/employees/{employee_id}/summary", response_model=CetSummaryResponse)
async def get_employee_cet_summary(
    employee_id: str,
    company_id: str | None = Query(None),
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    current_user: CetUserContext = Depends(get_current_user),
) -> CetSummaryResponse:
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    try:
        summary = cet_service.build_employee_summary(
            employee_id, year=year, month=month
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CetSummaryResponse(**summary)


@router.patch("/movements/{movement_id}")
async def validate_cet_movement(
    movement_id: str,
    body: CetMovementValidateRequest,
    company_id: str | None = Query(None),
    current_user: CetUserContext = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    try:
        return cet_service.validate_movement(
            movement_id,
            cid,
            approved=body.approved,
            validated_by=str(current_user.id),
        )
    except (ValueError, LookupError) as exc:
        status = 404 if isinstance(exc, LookupError) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
