"""
Commandes paramètres contingent et ajustements salarié.
"""

from __future__ import annotations

from typing import Any

from app.modules.repos_compensateur.application.contingent_queries import (
    _settings_to_api,
)
from app.modules.repos_compensateur.infrastructure.settings_repository import (
    upsert_adjustment,
    upsert_contingent_settings,
)


def update_contingent_settings_command(
    company_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    row = upsert_contingent_settings(company_id, payload)
    return _settings_to_api(row)


def update_employee_adjustment_command(
    company_id: str,
    employee_id: str,
    year: int,
    opening_balance_hours: float,
    note: str | None = None,
) -> dict[str, Any]:
    row = upsert_adjustment(
        company_id,
        employee_id,
        year,
        opening_balance_hours,
        note,
    )
    return {
        "employee_id": employee_id,
        "year": year,
        "opening_balance_hours": float(row.get("opening_balance_hours") or 0),
        "note": row.get("note"),
    }
