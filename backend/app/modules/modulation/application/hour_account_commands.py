"""Commands compte d'heures modulation."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.modules.modulation.application.hour_account_queries import (
    sync_account_balance_cache,
    _movement_row_to_schema,
)
from app.modules.modulation.infrastructure import repository as repo
from app.modules.modulation.schemas.requests import ModulationMovementSchema


def create_opening_balance(
    company_id: str,
    employee_id: str,
    hours: float,
    *,
    note: str | None = None,
    validated_by: str | None = None,
    year: int | None = None,
) -> ModulationMovementSchema:
    ref_year = year or date.today().year
    row = repo.insert_movement(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "year": ref_year,
            "month": None,
            "movement_type": "opening_balance",
            "hours": round(float(hours), 2),
            "status": "validated",
            "source": "manual_rh",
            "note": note,
            "validated_by": validated_by,
        }
    )
    sync_account_balance_cache(company_id, employee_id, ref_year)
    return _movement_row_to_schema(row)


def create_manual_adjustment(
    company_id: str,
    employee_id: str,
    hours: float,
    *,
    note: str | None = None,
    validated_by: str | None = None,
    year: int | None = None,
) -> ModulationMovementSchema:
    ref_year = year or date.today().year
    row = repo.insert_movement(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "year": ref_year,
            "month": date.today().month,
            "movement_type": "adjustment",
            "hours": round(float(hours), 2),
            "status": "validated",
            "source": "manual_rh",
            "note": note,
            "validated_by": validated_by,
        }
    )
    sync_account_balance_cache(company_id, employee_id, ref_year)
    return _movement_row_to_schema(row)


def create_credit_hs_movement(
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    hours: float,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return repo.insert_movement(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "year": year,
            "month": month,
            "movement_type": "credit_hs",
            "hours": round(float(hours), 2),
            "status": "validated",
            "source": "payroll_auto",
            "metadata": metadata or {},
        }
    )


def create_debit_recovery_movement(
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    hours: float,
    *,
    reference_id: str,
    note: str | None = None,
) -> dict[str, Any]:
    row = repo.insert_movement(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "year": year,
            "month": month,
            "movement_type": "debit_recovery",
            "hours": round(float(hours), 2),
            "status": "validated",
            "source": "absence",
            "reference_id": reference_id,
            "note": note,
        }
    )
    sync_account_balance_cache(company_id, employee_id, year)
    return row
