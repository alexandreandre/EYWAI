"""Tests des commandes prêts employeur."""

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.employee_loans.application.commands import (
    activate_loan,
    cancel_loan,
    create_loan,
    mark_loan_defaulted,
    record_early_repayment,
    update_loan,
)
from app.modules.employee_loans.schemas.requests import EmployeeLoanCreate, EmployeeLoanUpdate


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


@pytest.fixture
def active_loan_row():
    return {
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


@patch("app.modules.employee_loans.application.commands.employee_loans_repository")
def test_activate_loan_from_draft(mock_loans_repo, active_loan_row):
    draft = {**active_loan_row, "status": "draft", "remaining_capital": 0}
    mock_loans_repo.get_by_id.return_value = draft
    mock_loans_repo.update.return_value = {**draft, "status": "active", "remaining_capital": 6000}

    result = activate_loan("loan-1")

    assert result.status == "active"
    mock_loans_repo.update.assert_called_once()


@patch("app.modules.employee_loans.application.commands.employee_loan_installments_repository")
@patch("app.modules.employee_loans.application.commands.employee_loans_repository")
def test_cancel_loan_skips_pending_installments(
    mock_loans_repo, mock_installments_repo, active_loan_row
):
    mock_loans_repo.get_by_id.return_value = active_loan_row
    mock_loans_repo.update.return_value = {
        **active_loan_row,
        "status": "cancelled",
        "remaining_capital": 0,
    }

    result = cancel_loan("loan-1")

    assert result.status == "cancelled"
    mock_installments_repo.skip_pending_for_loan.assert_called_once_with("loan-1")


@patch("app.modules.employee_loans.application.commands.employee_loan_installments_repository")
@patch("app.modules.employee_loans.application.commands.employee_loans_repository")
def test_mark_loan_defaulted(mock_loans_repo, mock_installments_repo, active_loan_row):
    mock_loans_repo.get_by_id.return_value = active_loan_row
    mock_loans_repo.update.return_value = {**active_loan_row, "status": "defaulted"}

    result = mark_loan_defaulted("loan-1")

    assert result.status == "defaulted"
    mock_installments_repo.skip_pending_for_loan.assert_called_once_with("loan-1")


@patch("app.modules.employee_loans.application.commands.employee_loan_repayments_repository")
@patch("app.modules.employee_loans.application.commands.employee_loan_installments_repository")
@patch("app.modules.employee_loans.application.commands.employee_loans_repository")
def test_record_early_repayment_full(
    mock_loans_repo,
    mock_installments_repo,
    mock_repayments_repo,
    active_loan_row,
):
    mock_loans_repo.get_by_id.return_value = active_loan_row
    mock_loans_repo.update.return_value = {
        **active_loan_row,
        "status": "repaid",
        "remaining_capital": 0,
    }

    result = record_early_repayment("loan-1", 6000, date(2026, 8, 1))

    assert result.status == "repaid"
    mock_installments_repo.mark_pending_paid_for_loan.assert_called_once_with("loan-1")
    mock_repayments_repo.create.assert_called_once()


@patch("app.modules.employee_loans.application.commands.employee_loans_repository")
def test_update_loan_rejects_invalid_transition(mock_loans_repo, active_loan_row):
    repaid = {**active_loan_row, "status": "repaid"}
    mock_loans_repo.get_by_id.return_value = repaid

    with pytest.raises(ValueError, match="Transition"):
        update_loan("loan-1", EmployeeLoanUpdate(status="active"))


# --- Un compte par prêt (OD de paie, 04/11/2026) ----------------------------


@patch("app.modules.employee_loans.application.commands.employee_loan_installments_repository")
@patch("app.modules.employee_loans.application.commands.employee_loans_repository")
@patch("app.modules.employee_loans.application.commands._get_employee_company_id")
def test_le_compte_du_pret_est_enregistre(
    mock_company, mock_loans_repo, mock_installments_repo, loan_create_payload, active_loan_row
):
    mock_company.return_value = "company-1"
    mock_loans_repo.create.return_value = {**active_loan_row, "accounting_account": "42511000"}
    payload = loan_create_payload.model_copy(update={"accounting_account": "42511000"})

    result = create_loan("company-1", payload, "user-1")

    assert mock_loans_repo.create.call_args[0][0]["accounting_account"] == "42511000"
    assert result.accounting_account == "42511000"


@patch("app.modules.employee_loans.application.commands.employee_loan_installments_repository")
@patch("app.modules.employee_loans.application.commands.employee_loans_repository")
@patch("app.modules.employee_loans.application.commands._get_employee_company_id")
def test_sans_compte_la_colonne_n_est_pas_ecrite(
    mock_company, mock_loans_repo, mock_installments_repo, loan_create_payload, active_loan_row
):
    """Un prêt sans compte se crée même avant la migration de la colonne."""
    mock_company.return_value = "company-1"
    mock_loans_repo.create.return_value = active_loan_row

    create_loan("company-1", loan_create_payload, "user-1")

    assert "accounting_account" not in mock_loans_repo.create.call_args[0][0]


@pytest.mark.parametrize("saisi, attendu", [(" 4251 1000 ", "42511000"), ("", None), (None, None)])
def test_le_compte_saisi_est_nettoye(saisi, attendu):
    assert EmployeeLoanUpdate(accounting_account=saisi).accounting_account == attendu


@pytest.mark.parametrize("saisi", ["4251-1000", "compte courant", "1" * 21])
def test_un_compte_illisible_est_refuse(saisi):
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="compte"):
        EmployeeLoanUpdate(accounting_account=saisi)


@patch("app.modules.employee_loans.application.commands.employee_loans_repository")
def test_le_compte_se_pose_sur_un_pret_existant(mock_loans_repo, active_loan_row):
    mock_loans_repo.get_by_id.return_value = active_loan_row
    mock_loans_repo.update.return_value = {**active_loan_row, "accounting_account": "42590009"}

    result = update_loan("loan-1", EmployeeLoanUpdate(accounting_account="42590009"))

    mock_loans_repo.update.assert_called_once_with("loan-1", {"accounting_account": "42590009"})
    assert result.accounting_account == "42590009"
