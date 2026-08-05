"""API des périodes d'essai."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.employees.domain.trial_period_bareme import resolve_trial_proposal
from app.modules.trial_periods.api import access
from app.modules.trial_periods.application import commands, queries
from app.modules.trial_periods.infrastructure.repository import repository
from app.modules.trial_periods.schemas.requests import (
    TrialPeriodApplyBareme,
    TrialPeriodCreate,
    TrialPeriodRenew,
    TrialPeriodUpdate,
)
from app.modules.trial_periods.schemas.responses import TrialPeriodTracking
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/trial-periods", tags=["TrialPeriods"])


def _contract_duration_months(employee: Dict[str, Any]) -> Optional[float]:
    """Durée du contrat en mois, pour la règle légale des CDD courts."""
    hire = employee.get("hire_date")
    end = employee.get("contract_end_date")
    if not hire or not end:
        return None
    try:
        d1 = date.fromisoformat(str(hire)[:10])
        d2 = date.fromisoformat(str(end)[:10])
    except ValueError:
        return None
    return max(0.0, (d2 - d1).days / 30.44)


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
    user_id = str(current_user.id) or None

    settings = queries.fetch_company_settings(company_id)
    employees = {str(e["id"]): e for e in queries.fetch_employees(company_id)}

    created: List[str] = []
    skipped: List[Dict[str, str]] = []
    for employee_id in body.employee_ids:
        emp = employees.get(employee_id)
        if emp is None:
            skipped.append({"employee_id": employee_id, "raison": "salarié introuvable"})
            continue
        if repository.get_active_for_employee(employee_id):
            skipped.append({"employee_id": employee_id, "raison": "période déjà active"})
            continue
        hire = emp.get("hire_date")
        if not hire:
            skipped.append(
                {"employee_id": employee_id, "raison": "date d'entrée manquante"}
            )
            continue
        proposal = resolve_trial_proposal(
            settings,
            str(emp.get("contract_type") or ""),
            str(emp.get("statut") or ""),
            _contract_duration_months(emp),
        )
        if proposal is None:
            skipped.append(
                {"employee_id": employee_id, "raison": "contrat sans période d'essai"}
            )
            continue
        commands.create_trial_period(
            company_id=company_id,
            employee_id=employee_id,
            start_date=date.fromisoformat(str(hire)[:10]),
            duration_value=proposal.duration_value,
            duration_unit=proposal.duration_unit,
            renewal_allowed=proposal.renewal_allowed,
            created_by=user_id,
        )
        created.append(employee_id)

    return {"created": created, "skipped": skipped}
