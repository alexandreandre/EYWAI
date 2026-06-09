"""Tests contrôle d'accès prêts employeur."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.employee_loans.application import access
from app.modules.employee_loans.schemas.responses import EmployeeLoan


def _loan(**kwargs) -> EmployeeLoan:
    data = {
        "id": "loan-1",
        "company_id": "company-1",
        "employee_id": "emp-1",
        "principal_amount": 5000,
        "annual_interest_rate": 0,
        "start_date": "2026-06-01",
        "duration_months": 12,
        "monthly_payment": 416.67,
        "repayment_day": 1,
        "reason": None,
        "status": "active",
        "remaining_capital": 4000,
        "requires_2062_declaration": True,
        "declared_2062": False,
        "contract_file_path": None,
        "notes": None,
        "created_by": None,
        "created_at": None,
        "updated_at": None,
    }
    data.update(kwargs)
    return EmployeeLoan.model_validate(data)


def test_rh_can_access_loan():
    user = MagicMock()
    user.is_platform_admin = False
    user.active_company_id = "company-1"
    user.has_rh_access_in_company.return_value = True
    loan = _loan()
    assert access.user_can_access_loan(user, loan) is True


@patch("app.modules.employee_loans.application.access.resolve_my_employee_id")
def test_employee_can_access_own_loan(mock_resolve):
    mock_resolve.return_value = "emp-1"
    user = MagicMock()
    user.is_platform_admin = False
    user.active_company_id = "company-1"
    user.has_rh_access_in_company.return_value = False
    assert access.user_can_access_loan(user, _loan()) is True


@patch("app.modules.employee_loans.application.access.resolve_my_employee_id")
def test_employee_cannot_access_other_loan(mock_resolve):
    mock_resolve.return_value = "emp-other"
    user = MagicMock()
    user.is_platform_admin = False
    user.active_company_id = "company-1"
    user.has_rh_access_in_company.return_value = False
    assert access.user_can_access_loan(user, _loan()) is False


@patch("app.modules.employee_loans.application.access.queries.get_loan")
def test_require_loan_access_raises_for_other_employee(mock_get):
    mock_get.return_value = _loan()
    user = MagicMock()
    user.is_platform_admin = False
    user.active_company_id = "company-1"
    user.has_rh_access_in_company.return_value = False
    with patch(
        "app.modules.employee_loans.application.access.resolve_my_employee_id",
        return_value="emp-other",
    ):
        with pytest.raises(HTTPException) as exc:
            access.require_loan_access(user, "loan-1")
    assert exc.value.status_code == 403
