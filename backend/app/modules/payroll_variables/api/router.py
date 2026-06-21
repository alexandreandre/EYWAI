"""Router API variables paie."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.payroll_variables.application.generate_monthly import (
    generate_monthly_variables,
)
from app.modules.payroll_variables.application.preset_astreinte_equipes import (
    apply_astreinte_equipes_preset,
)
from app.modules.payroll_variables.application.preset_shift_teams_payroll import (
    apply_shift_teams_payroll_preset,
)
from app.modules.payroll_variables.infrastructure import repository as repo
from app.modules.payroll_variables.schemas.requests import (
    AstreintePresetResponse,
    PayrollVariableGenerateResponse,
    PayrollVariablePreviewItem,
    PayrollVariableRuleSchema,
    SpecialPayrollDaySchema,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/payroll-variables", tags=["Variables paie"])


def _resolve_company_id(company_id: str | None, current_user: User) -> str:
    target = company_id or current_user.active_company_id
    if not target:
        raise HTTPException(status_code=400, detail="company_id requis.")
    return target


def _require_rh(user: User) -> None:
    if user.role not in ("admin", "rh", "collaborateur_rh"):
        raise HTTPException(status_code=403, detail="Accès RH requis.")


@router.get("/rules", response_model=list[PayrollVariableRuleSchema])
async def list_rules(
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    rows = repo.list_rules(str(cid))
    return [PayrollVariableRuleSchema(**r) for r in rows]


@router.post("/rules", response_model=PayrollVariableRuleSchema)
async def create_rule(
    body: PayrollVariableRuleSchema,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    data = body.model_dump(exclude={"id"}, exclude_unset=True)
    row = repo.upsert_rule(str(cid), data)
    return PayrollVariableRuleSchema(**row)


@router.put("/rules/{rule_id}", response_model=PayrollVariableRuleSchema)
async def update_rule(
    rule_id: str,
    body: PayrollVariableRuleSchema,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    data = body.model_dump(exclude={"id"}, exclude_unset=True)
    row = repo.upsert_rule(str(cid), data, rule_id=rule_id)
    return PayrollVariableRuleSchema(**row)


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    repo.delete_rule(str(cid), rule_id)
    return {"status": "ok"}


@router.post("/rules/preset/astreinte-equipes", response_model=AstreintePresetResponse)
async def preset_astreinte_equipes(
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    result = apply_astreinte_equipes_preset(str(cid))
    return AstreintePresetResponse(**result)


@router.post("/rules/preset/shift-teams-payroll", response_model=AstreintePresetResponse)
async def preset_shift_teams_payroll(
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    result = apply_shift_teams_payroll_preset(str(cid))
    return AstreintePresetResponse(**result)


@router.get("/special-days", response_model=list[SpecialPayrollDaySchema])
async def list_special_days(
    year: int | None = Query(None),
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    cid = _resolve_company_id(company_id, current_user)
    rows = repo.list_all_special_days(str(cid), year=year)
    return [SpecialPayrollDaySchema(**r) for r in rows]


@router.post("/special-days", response_model=SpecialPayrollDaySchema)
async def create_special_day(
    body: SpecialPayrollDaySchema,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    data = body.model_dump(exclude={"id"}, exclude_unset=True)
    row = repo.create_special_day(str(cid), data)
    return SpecialPayrollDaySchema(**row)


@router.delete("/special-days/{day_id}")
async def delete_special_day(
    day_id: str,
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    repo.delete_special_day(str(cid), day_id)
    return {"status": "ok"}


@router.post("/generate", response_model=PayrollVariableGenerateResponse)
async def generate_variables(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    dry_run: bool = Query(False),
    company_id: str | None = None,
    current_user: User = Depends(get_current_user),
):
    _require_rh(current_user)
    cid = _resolve_company_id(company_id, current_user)
    result = generate_monthly_variables(str(cid), year, month, dry_run=dry_run)
    return PayrollVariableGenerateResponse(
        company_id=result["company_id"],
        year=result["year"],
        month=result["month"],
        dry_run=result["dry_run"],
        preview=[PayrollVariablePreviewItem(**p) for p in result["preview"]],
        written_count=result["written_count"],
    )
