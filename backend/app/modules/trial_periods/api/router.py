"""API des périodes d'essai."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.trial_periods.api import access
from app.modules.trial_periods.application import commands, queries
from app.modules.trial_periods.schemas.requests import (
    TrialPeriodApplyBareme,
    TrialPeriodCreate,
    TrialPeriodRenew,
    TrialPeriodUpdate,
)
from app.modules.trial_periods.schemas.responses import TrialPeriodTracking
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/trial-periods", tags=["TrialPeriods"])


@router.get("/tracking", response_model=TrialPeriodTracking)
def get_tracking(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    company_id = access.require_rh_or_admin(current_user)
    return queries.get_tracking_page(company_id)


@router.post("")
def create(
    body: TrialPeriodCreate,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    company_id = access.require_rh_or_admin(current_user)
    try:
        return commands.create_trial_period(
            company_id=company_id,
            employee_id=body.employee_id,
            start_date=body.start_date,
            duration_value=body.duration_value,
            duration_unit=body.duration_unit,
            renewal_allowed=body.renewal_allowed,
            created_by=str(current_user.id) or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{trial_period_id}")
def update(
    trial_period_id: str,
    body: TrialPeriodUpdate,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    access.require_rh_or_admin(current_user)
    try:
        return commands.update_trial_period(
            trial_period_id,
            start_date=body.start_date,
            duration_value=body.duration_value,
            duration_unit=body.duration_unit,
            renewal_allowed=body.renewal_allowed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{trial_period_id}/confirm")
def confirm(
    trial_period_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    access.require_rh_or_admin(current_user)
    return commands.confirm_trial_period(trial_period_id, str(current_user.id) or None)


@router.post("/{trial_period_id}/renew")
def renew(
    trial_period_id: str,
    body: TrialPeriodRenew,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    access.require_rh_or_admin(current_user)
    try:
        return commands.renew_trial_period(
            trial_period_id,
            renewed_at=body.renewed_at,
            renewal_duration_value=body.duration_value,
            renewal_duration_unit=body.duration_unit,
            renewed_by=str(current_user.id) or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/apply-bareme")
def apply_bareme(
    body: TrialPeriodApplyBareme,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Crée les périodes d'essai proposées par le barème, sans écraser l'existant."""
    company_id = access.require_rh_or_admin(current_user)
    return commands.apply_bareme_to_employees(
        company_id,
        body.employee_ids,
        str(current_user.id) or None,
    )
