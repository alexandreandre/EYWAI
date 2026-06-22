"""Router API CET."""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.access_control.application.service import access_control_service
from app.modules.cet.application import queries, service as cet_service
from app.modules.cet.schemas.requests import (
    CetAdjustmentCreate,
    CetDepositCpRequest,
    CetDepositRequest,
    CetManagerApprovalRequest,
    CetMovementDetail,
    CetMovementValidateRequest,
    CetOpeningBalanceCreate,
    CetOverviewRow,
    CetPendingManagerItem,
    CetSettingsResponse,
    CetSettingsUpdate,
    CetSummaryResponse,
    CetWithdrawalRequest,
)
from app.shared.employee_resolution import resolve_employee_id_for_user_account
from app.shared.team_manager import (
    get_employee_ids_managed_by_manager,
    get_team_manager_employee_id,
)


class CetUserContext(Protocol):
    id: str
    active_company_id: str | None

    def has_access_to_company(self, company_id: str) -> bool: ...
    def has_rh_access_in_company(self, company_id: str) -> bool: ...


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


def _is_rh(user: CetUserContext, company_id: str) -> bool:
    return bool(user.has_rh_access_in_company(company_id))


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


@router.get("/overview", response_model=list[CetOverviewRow])
async def get_cet_overview(
    year: int | None = Query(None, ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: CetUserContext = Depends(get_current_user),
) -> list[CetOverviewRow]:
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    return [CetOverviewRow(**row) for row in cet_service.get_cet_overview(cid, year=year)]


@router.get("/pending", response_model=list[CetMovementDetail])
async def list_cet_pending(
    company_id: str | None = Query(None),
    current_user: CetUserContext = Depends(get_current_user),
) -> list[CetMovementDetail]:
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    return [CetMovementDetail(**row) for row in cet_service.list_company_pending(cid)]


@router.get("/pending-manager-approval", response_model=list[CetPendingManagerItem])
async def list_pending_manager_approval(
    company_id: str | None = Query(None),
    current_user: CetUserContext = Depends(get_current_user),
) -> list[CetPendingManagerItem]:
    cid = _resolve_company_id(company_id, current_user)
    if _is_rh(current_user, cid):
        rows = cet_service.list_pending_manager_approval(cid)
    else:
        me = resolve_employee_id_for_user_account(str(current_user.id), cid)
        if not me:
            raise HTTPException(status_code=404, detail="Profil employé introuvable.")
        managed = set(get_employee_ids_managed_by_manager(me, cid))
        rows = [
            r
            for r in cet_service.list_pending_manager_approval(cid)
            if str(r.get("employee_id")) in managed
        ]
    return [CetPendingManagerItem(**row) for row in rows]


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


@router.get("/me/movements", response_model=list[CetMovementDetail])
async def get_my_cet_movements(
    year: int | None = Query(None, ge=2000, le=2100),
    current_user: CetUserContext = Depends(get_current_user),
) -> list[CetMovementDetail]:
    cid = _resolve_company_id(None, current_user)
    employee_id = resolve_employee_id_for_user_account(str(current_user.id), cid)
    if not employee_id:
        raise HTTPException(status_code=404, detail="Profil employé introuvable.")
    rows = cet_service.list_employee_movements(employee_id, year=year)
    return [CetMovementDetail(**row) for row in rows]


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


@router.get("/employees/{employee_id}/movements", response_model=list[CetMovementDetail])
async def get_employee_cet_movements(
    employee_id: str,
    year: int | None = Query(None, ge=2000, le=2100),
    company_id: str | None = Query(None),
    current_user: CetUserContext = Depends(get_current_user),
) -> list[CetMovementDetail]:
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    rows = cet_service.list_employee_movements(employee_id, year=year)
    return [CetMovementDetail(**row) for row in rows]


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
            rejection_reason=body.rejection_reason,
        )
    except (ValueError, LookupError) as exc:
        status = 404 if isinstance(exc, LookupError) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/movements/{movement_id}/manager-approve")
async def manager_approve_cet_movement(
    movement_id: str,
    body: CetManagerApprovalRequest,
    company_id: str | None = Query(None),
    current_user: CetUserContext = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    mvt = queries.list_pending_manager_approval(cid)
    target = next((m for m in mvt if str(m.get("id")) == movement_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Mouvement introuvable.")

    if not _is_rh(current_user, cid):
        me = resolve_employee_id_for_user_account(str(current_user.id), cid)
        if not me:
            raise HTTPException(status_code=403, detail="Accès non autorisé.")
        employee_id = str(target.get("employee_id"))
        if get_team_manager_employee_id(employee_id) != me:
            raise HTTPException(status_code=403, detail="Accès non autorisé.")

    try:
        return cet_service.approve_by_manager(
            movement_id,
            cid,
            str(current_user.id),
            approved=body.approved,
            rejection_reason=body.rejection_reason,
        )
    except (ValueError, LookupError) as exc:
        status = 404 if isinstance(exc, LookupError) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/opening-balances")
async def create_cet_opening_balance(
    body: CetOpeningBalanceCreate,
    company_id: str | None = Query(None),
    current_user: CetUserContext = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    try:
        return cet_service.create_opening_balance(
            body.employee_id,
            cid,
            body.hours,
            created_by=str(current_user.id),
            note=body.note,
        )
    except (ValueError, LookupError) as exc:
        status = 404 if isinstance(exc, LookupError) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/adjustments")
async def create_cet_adjustment(
    body: CetAdjustmentCreate,
    company_id: str | None = Query(None),
    current_user: CetUserContext = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    _require_rh(current_user, cid)
    try:
        return cet_service.create_adjustment(
            body.employee_id,
            cid,
            hours=body.hours,
            days=body.days,
            created_by=str(current_user.id),
            note=body.note,
        )
    except (ValueError, LookupError) as exc:
        status = 404 if isinstance(exc, LookupError) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
