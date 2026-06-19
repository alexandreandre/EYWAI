"""Router API modulation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.modulation.application import commands, queries
from app.modules.modulation.application import hour_account_commands, hour_account_queries
from app.modules.modulation.schemas.requests import (
    ManualAdjustmentCreate,
    ModulationBalanceResponse,
    ModulationMovementSchema,
    ModulationOverviewRow,
    ModulationSettingsResponse,
    ModulationSettingsUpdate,
    OpeningBalanceCreate,
    WeekTemplateSchema,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/modulation", tags=["Modulation"])


def _resolve_company_id(company_id: str | None, current_user: User) -> str:
    target = company_id or current_user.active_company_id
    if not target:
        raise HTTPException(status_code=400, detail="company_id requis.")
    return target


def _require_rh(user: User) -> None:
    if user.role not in ("admin", "rh", "collaborateur_rh"):
        raise HTTPException(status_code=403, detail="Accès RH requis.")


@router.get("/settings", response_model=ModulationSettingsResponse)
async def get_settings(
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    return queries.get_modulation_settings(str(cid))


@router.patch("/settings", response_model=ModulationSettingsResponse)
async def update_settings(
    body: ModulationSettingsUpdate,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    result = commands.update_modulation_settings(
        str(cid), body.model_dump(exclude_unset=True)
    )
    return ModulationSettingsResponse(**result)


@router.get("/week-templates", response_model=list[WeekTemplateSchema])
async def list_templates(
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    return queries.list_week_templates(str(cid))


@router.post("/week-templates", response_model=WeekTemplateSchema)
async def create_template(
    body: WeekTemplateSchema,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    row = commands.save_week_template(str(cid), body.model_dump())
    return WeekTemplateSchema(
        id=str(row.get("id")),
        name=row.get("name") or "",
        weekly_hours=float(row.get("weekly_hours") or 35),
        day_configs=row.get("day_configs") or [],
        modulation_tier=row.get("modulation_tier") or "neutral",
        is_active=bool(row.get("is_active", True)),
    )


@router.put("/week-templates/{template_id}", response_model=WeekTemplateSchema)
async def update_template(
    template_id: str,
    body: WeekTemplateSchema,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    row = commands.save_week_template(
        str(cid), body.model_dump(), template_id=template_id
    )
    return WeekTemplateSchema(
        id=str(row.get("id")),
        name=row.get("name") or "",
        weekly_hours=float(row.get("weekly_hours") or 35),
        day_configs=row.get("day_configs") or [],
        modulation_tier=row.get("modulation_tier") or "neutral",
        is_active=bool(row.get("is_active", True)),
    )


@router.delete("/week-templates/{template_id}")
async def remove_template(
    template_id: str,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    commands.delete_week_template(str(cid), template_id)
    return {"status": "ok"}


@router.get("/overview", response_model=list[ModulationOverviewRow])
async def get_overview(
    year: int | None = Query(None),
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    return queries.get_modulation_overview(str(cid), year)


@router.get(
    "/employees/{employee_id}/balance",
    response_model=ModulationBalanceResponse,
)
async def get_employee_balance(
    employee_id: str,
    year: int | None = Query(None),
    month: int | None = Query(None, ge=1, le=12),
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    return hour_account_queries.get_employee_account_balance(
        str(cid), employee_id, year, month=month
    )


@router.get(
    "/employees/{employee_id}/movements",
    response_model=list[ModulationMovementSchema],
)
async def get_employee_movements(
    employee_id: str,
    year: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
):
    return hour_account_queries.list_employee_movements(
        employee_id, year, limit=limit, offset=offset
    )


@router.post(
    "/employees/{employee_id}/opening-balance",
    response_model=ModulationMovementSchema,
)
async def post_opening_balance(
    employee_id: str,
    body: OpeningBalanceCreate,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    return hour_account_commands.create_opening_balance(
        str(cid),
        employee_id,
        body.hours,
        note=body.note,
        validated_by=str(current_user.id),
    )


@router.post("/adjustments", response_model=ModulationMovementSchema)
async def post_adjustment(
    body: ManualAdjustmentCreate,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    return hour_account_commands.create_manual_adjustment(
        str(cid),
        body.employee_id,
        body.hours,
        note=body.note,
        validated_by=str(current_user.id),
        year=body.year,
    )


@router.post(
    "/settings/apply-preset/{preset}",
    response_model=ModulationSettingsResponse,
)
async def apply_preset(
    preset: str,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    try:
        return commands.apply_modulation_preset(str(cid), preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workflow-status")
async def get_workflow_status(
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    """Indicateurs pour l'étape workflow paie Modulation."""
    from app.modules.modulation.infrastructure import repository as repo

    from datetime import date

    cid = _resolve_company_id(company_id, current_user)
    ref_year = date.today().year
    pending = repo.count_pending_movements(str(cid))
    over_balance = repo.count_employees_over_balance_cap(str(cid), ref_year)
    settings = repo.get_modulation_settings(str(cid))
    return {
        "pending_movements": pending,
        "over_balance_employees": over_balance,
        "alert_count": pending + over_balance,
        "hour_account_enabled": settings.hour_account_enabled,
        "modulation_enabled": settings.enabled,
    }
