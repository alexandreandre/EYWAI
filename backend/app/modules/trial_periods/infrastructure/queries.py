"""Table et projections des périodes d'essai."""

from __future__ import annotations

TABLE_TRIAL_PERIODS = "trial_periods"

SELECT_TRIAL_WITH_EMPLOYEE = (
    "*, employee:employees(id, first_name, last_name, hire_date, "
    "contract_type, statut, employment_status)"
)

__all__ = ["SELECT_TRIAL_WITH_EMPLOYEE", "TABLE_TRIAL_PERIODS"]
