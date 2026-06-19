"""Service applicatif CET — façade vers commands et queries."""

from __future__ import annotations

from typing import Any

from app.modules.cet.application import commands
from app.modules.cet.application import queries
from app.modules.cet.infrastructure import repository as cet_repo

_settings_to_api = queries.settings_to_api


def get_settings(company_id: str) -> dict[str, Any]:
    return queries.get_settings(company_id)


def update_settings(company_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = cet_repo.upsert_cet_settings(company_id, payload)
    return _settings_to_api(row)


build_employee_summary = queries.build_employee_summary
compute_conjonctural_overtime_hours = queries.compute_conjonctural_overtime_hours
create_deposit = commands.create_deposit
create_deposit_cp = commands.create_deposit_cp
create_withdrawal = commands.create_withdrawal
validate_movement = commands.validate_movement
approve_by_manager = commands.approve_by_manager
create_opening_balance = commands.create_opening_balance
create_adjustment = commands.create_adjustment
get_cet_overview = queries.get_cet_overview
list_employee_movements = queries.list_employee_movements
list_company_pending = queries.list_company_pending
list_pending_manager_approval = queries.list_pending_manager_approval
count_company_pending = queries.count_company_pending
