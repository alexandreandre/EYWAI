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
    OvertimeRoutingDecisionUpdate,
    OvertimeRoutingRow,
    WeekTemplateSchema,
    WorkTimePeriodSchema,
    WorkTimePeriodUpdate,
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
    try:
        result = commands.update_modulation_settings(
            str(cid), body.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        team_id=row.get("team_id"),
        description=row.get("description"),
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
        team_id=row.get("team_id"),
        description=row.get("description"),
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
        result = commands.apply_modulation_preset(str(cid), preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ModulationSettingsResponse(**result)


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
        "hs_routing_policy": settings.hs_routing_policy,
    }


@router.get("/work-time-periods", response_model=list[WorkTimePeriodSchema])
async def list_work_time_periods(
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    from app.modules.modulation.application.reference_resolution import (
        list_work_time_periods as list_periods,
    )

    cid = _resolve_company_id(company_id, current_user)
    periods = list_periods(str(cid))
    return [
        WorkTimePeriodSchema(
            id=p.id,
            label=p.label,
            start_date=p.start_date,
            end_date=p.end_date,
            daily_reference_hours=p.daily_reference_hours,
            weekly_reference_hours=p.weekly_reference_hours,
            affects_payroll=p.affects_payroll,
            affects_planning=p.affects_planning,
            default_week_template_id=p.default_week_template_id,
            is_active=p.is_active,
        )
        for p in periods
    ]


@router.post("/work-time-periods", response_model=WorkTimePeriodSchema)
async def create_work_time_period(
    body: WorkTimePeriodSchema,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    from app.modules.modulation.application import reference_period_commands as period_cmds

    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    try:
        row = period_cmds.create_period(str(cid), body.model_dump(exclude={"id"}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkTimePeriodSchema(
        id=str(row.get("id")),
        label=row.get("label") or "",
        start_date=row.get("start_date"),
        end_date=row.get("end_date"),
        daily_reference_hours=row.get("daily_reference_hours"),
        weekly_reference_hours=row.get("weekly_reference_hours"),
        affects_payroll=bool(row.get("affects_payroll", True)),
        affects_planning=bool(row.get("affects_planning", False)),
        default_week_template_id=row.get("default_week_template_id"),
        is_active=bool(row.get("is_active", True)),
    )


@router.patch("/work-time-periods/{period_id}", response_model=WorkTimePeriodSchema)
async def update_work_time_period(
    period_id: str,
    body: WorkTimePeriodUpdate,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    from app.modules.modulation.application import reference_period_commands as period_cmds

    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    try:
        row = period_cmds.update_period(
            str(cid), period_id, body.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkTimePeriodSchema(
        id=str(row.get("id")),
        label=row.get("label") or "",
        start_date=row.get("start_date"),
        end_date=row.get("end_date"),
        daily_reference_hours=row.get("daily_reference_hours"),
        weekly_reference_hours=row.get("weekly_reference_hours"),
        affects_payroll=bool(row.get("affects_payroll", True)),
        affects_planning=bool(row.get("affects_planning", False)),
        default_week_template_id=row.get("default_week_template_id"),
        is_active=bool(row.get("is_active", True)),
    )


@router.delete("/work-time-periods/{period_id}")
async def delete_work_time_period(
    period_id: str,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    from app.modules.modulation.application import reference_period_commands as period_cmds

    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    try:
        period_cmds.delete_period(str(cid), period_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}


@router.get("/overtime-routing", response_model=list[OvertimeRoutingRow])
async def get_overtime_routing(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    from app.modules.modulation.application import overtime_routing_queries as otr_q

    cid = _resolve_company_id(company_id, current_user)
    rows = otr_q.list_overtime_routing(str(cid), year, month)
    return [OvertimeRoutingRow(**r) for r in rows]


@router.put(
    "/overtime-routing/{employee_id}",
    response_model=OvertimeRoutingRow,
)
async def put_overtime_routing(
    employee_id: str,
    body: OvertimeRoutingDecisionUpdate,
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    from app.modules.modulation.application import overtime_routing_queries as otr_q

    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    try:
        row = otr_q.upsert_overtime_routing_decision(
            str(cid),
            employee_id,
            year,
            month,
            body.hours_to_pay,
            body.hours_to_account,
            decided_by=str(current_user.id),
            note=body.note,
            validate=body.submit_validated,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OvertimeRoutingRow(**row)
