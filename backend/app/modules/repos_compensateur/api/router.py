"""
Router API repos_compensateur.

Rôle strict : validation des entrées (query params), auth, appel de l'application, format réponse.
"""

from __future__ import annotations

import traceback
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.repos_compensateur.api.dependencies import (
    ReposCompensateurUserContext,
    get_current_user,
)
from app.modules.repos_compensateur.application import calculer_credits_repos_command
from app.modules.repos_compensateur.application.contingent_queries import (
    _settings_to_api,
    get_contingent_employee_detail,
    get_contingent_overview,
)
from app.modules.repos_compensateur.application.settings_commands import (
    update_contingent_settings_command,
    update_employee_adjustment_command,
)
from app.modules.repos_compensateur.infrastructure.settings_repository import (
    get_contingent_settings_row,
)
from app.modules.repos_compensateur.schemas import (
    CalculerCreditsResponse,
    ContingentEmployeeDetailResponse,
    ContingentOverviewResponse,
    ContingentSettingsResponse,
    ContingentSettingsUpdate,
    EmployeeAdjustmentUpdate,
)
from app.modules.repos_compensateur.schemas.responses import EmployeeAdjustmentResponse

router = APIRouter(
    prefix="/api/repos-compensateur",
    tags=["Repos Compensateur"],
)


def _resolve_company_id(
    company_id: str | None, current_user: ReposCompensateurUserContext
) -> str:
    target = company_id or current_user.active_company_id
    if not target:
        raise HTTPException(status_code=400, detail="company_id requis.")
    return target


def _parse_reference_date(value: str | None, year: int) -> date:
    if value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="reference_date invalide (YYYY-MM-DD)."
            ) from exc
    today = date.today()
    if today.year == year:
        return today
    return date(year, 12, 31)


@router.get("/settings", response_model=ContingentSettingsResponse)
def get_contingent_settings_endpoint(
    company_id: str | None = Query(None),
    current_user: ReposCompensateurUserContext = Depends(get_current_user),
) -> ContingentSettingsResponse:
    target_company_id = _resolve_company_id(company_id, current_user)
    row = get_contingent_settings_row(target_company_id)
    return ContingentSettingsResponse(**_settings_to_api(row))


@router.put("/settings", response_model=ContingentSettingsResponse)
def update_contingent_settings_endpoint(
    body: ContingentSettingsUpdate,
    company_id: str | None = Query(None),
    current_user: ReposCompensateurUserContext = Depends(get_current_user),
) -> ContingentSettingsResponse:
    target_company_id = _resolve_company_id(company_id, current_user)
    payload = body.model_dump(exclude_unset=True)
    result = update_contingent_settings_command(target_company_id, payload)
    return ContingentSettingsResponse(**result)


@router.get("/overview", response_model=ContingentOverviewResponse)
def get_contingent_overview_endpoint(
    year: int = Query(..., ge=2020, le=2030),
    reference_date: str | None = Query(None),
    company_id: str | None = Query(None),
    current_user: ReposCompensateurUserContext = Depends(get_current_user),
) -> ContingentOverviewResponse:
    target_company_id = _resolve_company_id(company_id, current_user)
    ref = _parse_reference_date(reference_date, year)
    try:
        data = get_contingent_overview(target_company_id, year, ref)
        return ContingentOverviewResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/employees/{employee_id}",
    response_model=ContingentEmployeeDetailResponse,
)
def get_contingent_employee_detail_endpoint(
    employee_id: str,
    year: int = Query(..., ge=2020, le=2030),
    reference_date: str | None = Query(None),
    company_id: str | None = Query(None),
    current_user: ReposCompensateurUserContext = Depends(get_current_user),
) -> ContingentEmployeeDetailResponse:
    target_company_id = _resolve_company_id(company_id, current_user)
    ref = _parse_reference_date(reference_date, year)
    try:
        data = get_contingent_employee_detail(
            target_company_id, employee_id, year, ref
        )
        if not data:
            raise HTTPException(status_code=404, detail="Employé introuvable.")
        return ContingentEmployeeDetailResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put(
    "/employees/{employee_id}/adjustment",
    response_model=EmployeeAdjustmentResponse,
)
def update_employee_adjustment_endpoint(
    employee_id: str,
    body: EmployeeAdjustmentUpdate,
    year: int = Query(..., ge=2020, le=2030),
    company_id: str | None = Query(None),
    current_user: ReposCompensateurUserContext = Depends(get_current_user),
) -> EmployeeAdjustmentResponse:
    target_company_id = _resolve_company_id(company_id, current_user)
    try:
        result = update_employee_adjustment_command(
            target_company_id,
            employee_id,
            year,
            body.opening_balance_hours,
            body.note,
        )
        return EmployeeAdjustmentResponse(
            opening_balance_hours=result["opening_balance_hours"],
            note=result.get("note"),
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/calculer-credits", response_model=CalculerCreditsResponse)
def calculer_credits_repos(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    company_id: str | None = Query(None),
    current_user: ReposCompensateurUserContext = Depends(get_current_user),
) -> CalculerCreditsResponse:
    """
    Calcule les crédits COR pour tous les employés de l'entreprise sur le mois donné.
    """
    target_company_id = _resolve_company_id(company_id, current_user)

    try:
        result = calculer_credits_repos_command(
            year=year,
            month=month,
            target_company_id=target_company_id,
        )
        return CalculerCreditsResponse(
            company_id=result.company_id,
            year=result.year,
            month=result.month,
            employees_processed=result.employees_processed,
            credits_created=result.credits_created,
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e
