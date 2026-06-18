"""Router API modulation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.modulation.application import commands, queries
from app.modules.modulation.schemas.requests import (
    ModulationOverviewRow,
    ModulationSettingsResponse,
    ModulationSettingsUpdate,
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
