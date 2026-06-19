"""Queries compte d'heures modulation."""

from __future__ import annotations

from datetime import date

from app.modules.modulation.domain.hour_account_rules import (
    compute_acquired_and_taken,
    compute_balance_from_movements,
)
from app.modules.modulation.infrastructure import repository as repo
from app.modules.modulation.schemas.requests import (
    ModulationBalanceResponse,
    ModulationMovementSchema,
)


def get_employee_account_balance(
    company_id: str,
    employee_id: str,
    year: int | None = None,
    *,
    month: int | None = None,
) -> ModulationBalanceResponse:
    ref_year = year or date.today().year
    movements = repo.list_movements_for_employee_year(employee_id, ref_year)
    balance = compute_balance_from_movements(movements)
    acquired, taken = compute_acquired_and_taken(movements)

    settings = repo.get_modulation_settings(company_id)
    franchise = float(settings.hs_franchise_hours_per_period or 0)
    franchise_consumed = 0.0
    if month is not None and franchise > 0:
        franchise_consumed = repo.get_franchise_consumed_in_period(
            employee_id, ref_year, month
        )
    franchise_remaining = max(0.0, round(franchise - franchise_consumed, 2))

    return ModulationBalanceResponse(
        employee_id=employee_id,
        year=ref_year,
        account_balance_hours=balance,
        acquired_hours=acquired,
        taken_hours=taken,
        franchise_remaining_hours=franchise_remaining,
    )


def list_employee_movements(
    employee_id: str,
    year: int | None = None,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[ModulationMovementSchema]:
    rows = repo.list_movements(employee_id, year, limit=limit, offset=offset)
    return [_movement_row_to_schema(r) for r in rows]


def _movement_row_to_schema(row: dict) -> ModulationMovementSchema:
    return ModulationMovementSchema(
        id=str(row["id"]),
        employee_id=str(row["employee_id"]),
        year=int(row["year"]),
        month=int(row["month"]) if row.get("month") is not None else None,
        movement_type=str(row.get("movement_type") or ""),
        hours=float(row.get("hours") or 0),
        status=str(row.get("status") or ""),
        source=str(row.get("source") or ""),
        reference_id=str(row["reference_id"]) if row.get("reference_id") else None,
        metadata=row.get("metadata") or {},
        note=row.get("note"),
        created_at=row.get("created_at"),
    )


def sync_account_balance_cache(
    company_id: str,
    employee_id: str,
    year: int,
) -> float:
    """Recalcule le solde compte depuis les mouvements et met à jour le cache compteur."""
    movements = repo.list_movements_for_employee_year(employee_id, year)
    balance = compute_balance_from_movements(movements)
    counters = repo.list_employee_counters(company_id, year)
    existing = next(
        (c for c in counters if str(c.get("employee_id")) == employee_id),
        None,
    )
    if existing:
        repo.upsert_employee_counter(
            company_id,
            employee_id,
            year,
            float(existing.get("theoretical_hours") or 0),
            float(existing.get("actual_hours") or 0),
            float(existing.get("balance_hours") or 0),
            account_balance_hours=balance,
        )
    else:
        repo.upsert_employee_counter(
            company_id,
            employee_id,
            year,
            0.0,
            0.0,
            0.0,
            account_balance_hours=balance,
        )
    return balance
