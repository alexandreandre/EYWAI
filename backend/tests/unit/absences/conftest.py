"""Fixtures partagées pour les tests unitaires absences."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

from app.modules.absences.domain.cp_seniority import (
    CpSenioritySettings,
    EmployeeCpSeniorityContext,
)
from app.modules.absences.domain.leave_policy import (
    DEFAULT_LEAVE_POLICY,
    EmployeeLeaveAdjustment,
    RTT_ANNUAL_DAYS_DEFAULT,
)


def default_leave_context():
    return (
        DEFAULT_LEAVE_POLICY,
        EmployeeLeaveAdjustment.empty(),
        RTT_ANNUAL_DAYS_DEFAULT,
        CpSenioritySettings.disabled(),
    )


def default_cp_balance_extras(*_args, **_kwargs):
    return {
        "cp_seniority": CpSenioritySettings.disabled(),
        "employee_ctx": EmployeeCpSeniorityContext(hire_date=None),
    }


@contextmanager
def mock_leave_context():
    """Évite les appels Supabase via le contexte congés dans les queries absences."""
    with (
        patch(
            "app.modules.absences.application.queries._leave_context",
            return_value=default_leave_context(),
        ),
        patch(
            "app.modules.absences.application.queries._cp_balance_extras",
            side_effect=default_cp_balance_extras,
        ),
    ):
        yield
