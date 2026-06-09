"""Tests des commandes prêts employeur."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_loans.application.commands import create_loan
from app.modules.employee_loans.schemas.requests import EmployeeLoanCreate


@pytest.fixture
def loan_create_payload():
    return EmployeeLoanCreate(
        employee_id="emp-1",
        principal_amount=6000,
        annual_interest_rate=0,
        start_date=date(2026, 6, 1),
        duration_months=12,
        reason="Aide logement",
        activate=True,
    )


@patch("app.modules.employee_loans.application.commands.employee_loan_installments_repository")
@patch("app.modules.employee_loans.application.commands.employee_loans_repository")
@patch("app.modules.employee_loans.application.commands._get_employee_company_id")
def test_create_loan_generates_schedule(
    mock_company, mock_loans_repo, mock_installments_repo, loan_create_payload
):
    mock_company.return_value = "company-1"
    mock_loans_repo.create.return_value = {
        "id": "loan-1",
        "company_id": "company-1",
        "employee_id": "emp-1",
        "principal_amount": 6000,
        "annual_interest_rate": 0,
        "start_date": "2026-06-01",
        "duration_months": 12,
        "monthly_payment": 500,
        "repayment_day": 1,
        "reason": "Aide logement",
        "status": "active",
        "remaining_capital": 6000,
        "requires_2062_declaration": True,
        "declared_2062": False,
        "contract_file_path": None,
        "notes": None,
        "created_by": "user-1",
        "created_at": None,
        "updated_at": None,
    }

    result = create_loan("company-1", loan_create_payload, "user-1")

    assert result.id == "loan-1"
    assert result.requires_2062_declaration is True
    mock_installments_repo.bulk_create.assert_called_once()
    rows = mock_installments_repo.bulk_create.call_args[0][0]
    assert len(rows) == 12
    assert rows[0]["loan_id"] == "loan-1"


@patch("app.modules.employee_loans.application.commands._get_employee_company_id")
def test_create_loan_wrong_company(mock_company, loan_create_payload):
    mock_company.return_value = "other-company"
    with pytest.raises(ValueError, match="n'appartient pas"):
        create_loan("company-1", loan_create_payload, "user-1")
