"""Tests enrichissement bulletin prêts employeur — remboursement glissant."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.modules.employee_loans.application.enrichment import (
    enrich_payslip_loans,
    process_suspended_loan_installments,
)


def _loan_item(
    *,
    inst_id="inst-1",
    loan_id="loan-1",
    capital_part=500,
    interest_part=0,
    capital_paid=0,
    interest_paid=0,
    remaining_capital=5000,
    installment_number=1,
    inst_year=2026,
    inst_month=6,
):
    return {
        "id": loan_id,
        "remaining_capital": remaining_capital,
        "annual_interest_rate": 0,
        "reason": "Test",
        "installment": {
            "id": inst_id,
            "installment_number": installment_number,
            "year": inst_year,
            "month": inst_month,
            "capital_part": capital_part,
            "interest_part": interest_part,
            "capital_paid": capital_paid,
            "interest_paid": interest_paid,
            "status": "partial" if capital_paid > 0 else "pending",
        },
    }


@patch("app.modules.employee_loans.application.enrichment.get_suspended_loans_with_pending_installment")
@patch("app.modules.employee_loans.application.enrichment.employee_loans_repository")
@patch("app.modules.employee_loans.application.enrichment.employee_loan_installments_repository")
@patch("app.modules.employee_loans.application.enrichment.employee_loan_repayments_repository")
@patch("app.modules.employee_loans.application.enrichment.get_unsettled_installments_for_payroll")
@patch("app.modules.employee_loans.application.enrichment.get_legal_interest_rate")
def test_enrich_payslip_loans_deducts_from_net(
    mock_legal_rate,
    mock_due,
    mock_repayments_repo,
    mock_installments_repo,
    mock_loans_repo,
    mock_suspended,
):
    mock_legal_rate.return_value = Decimal("0.0352")
    mock_suspended.return_value = []
    mock_repayments_repo.get_existing.return_value = None
    mock_due.return_value = [_loan_item(capital_part=400, interest_part=0)]

    payslip = {"net_a_payer": 2500.0, "salaire_brut": 3000.0}
    result = enrich_payslip_loans(
        payslip, "emp-1", 2026, 6, payslip_id="payslip-1"
    )

    assert result["remboursements_prets"]["total_rembourse"] == 400.0
    assert result["net_a_payer"] == 2100.0
    mock_repayments_repo.create.assert_called_once()
    mock_loans_repo.update.assert_called_once()
    mock_installments_repo.increment_paid.assert_called_once()
    call_args = mock_installments_repo.increment_paid.call_args
    assert call_args[0][3] == "paid"


@patch("app.modules.employee_loans.application.enrichment.get_suspended_loans_with_pending_installment")
@patch("app.modules.employee_loans.application.enrichment.employee_loans_repository")
@patch("app.modules.employee_loans.application.enrichment.employee_loan_installments_repository")
@patch("app.modules.employee_loans.application.enrichment.employee_loan_repayments_repository")
@patch("app.modules.employee_loans.application.enrichment.get_unsettled_installments_for_payroll")
@patch("app.modules.employee_loans.application.enrichment.get_legal_interest_rate")
def test_enrich_payslip_loans_caps_by_remaining_capital(
    mock_legal_rate,
    mock_due,
    mock_repayments_repo,
    mock_installments_repo,
    mock_loans_repo,
    mock_suspended,
):
    mock_legal_rate.return_value = Decimal("0")
    mock_suspended.return_value = []
    mock_repayments_repo.get_existing.return_value = None
    mock_due.return_value = [
        _loan_item(capital_part=500, interest_part=0, remaining_capital=150)
    ]

    payslip = {"net_a_payer": 2500.0}
    result = enrich_payslip_loans(
        payslip, "emp-1", 2026, 6, payslip_id="payslip-1"
    )

    assert result["remboursements_prets"]["total_capital"] == 150.0
    assert result["net_a_payer"] == 2350.0
    mock_installments_repo.increment_paid.assert_called_once()
    assert mock_installments_repo.increment_paid.call_args[0][3] == "paid"


@patch("app.modules.employee_loans.application.enrichment.get_suspended_loans_with_pending_installment")
@patch("app.modules.employee_loans.application.enrichment.employee_loans_repository")
@patch("app.modules.employee_loans.application.enrichment.employee_loan_installments_repository")
@patch("app.modules.employee_loans.application.enrichment.employee_loan_repayments_repository")
@patch("app.modules.employee_loans.application.enrichment.get_unsettled_installments_for_payroll")
@patch("app.modules.employee_loans.application.enrichment.get_legal_interest_rate")
def test_enrich_payslip_loans_partial_marks_partial_status(
    mock_legal_rate,
    mock_due,
    mock_repayments_repo,
    mock_installments_repo,
    mock_loans_repo,
    mock_suspended,
):
    mock_legal_rate.return_value = Decimal("0")
    mock_suspended.return_value = []
    mock_repayments_repo.get_existing.return_value = None
    mock_due.return_value = [_loan_item(capital_part=500, interest_part=0)]

    payslip = {"net_a_payer": 700.0}
    result = enrich_payslip_loans(
        payslip, "emp-1", 2026, 6, payslip_id="payslip-1"
    )

    assert result["remboursements_prets"]["total_capital"] < 500.0
    assert result["remboursements_prets"]["total_capital"] > 0
    mock_installments_repo.increment_paid.assert_called_once()
    assert mock_installments_repo.increment_paid.call_args[0][3] == "partial"
    prets = result["remboursements_prets"]["prets"][0]
    assert "reliquat_apres" in prets
    assert prets["reliquat_apres"] > 0


@patch("app.modules.employee_loans.application.enrichment.get_suspended_loans_with_pending_installment")
@patch("app.modules.employee_loans.application.enrichment.employee_loans_repository")
@patch("app.modules.employee_loans.application.enrichment.employee_loan_installments_repository")
@patch("app.modules.employee_loans.application.enrichment.employee_loan_repayments_repository")
@patch("app.modules.employee_loans.application.enrichment.get_unsettled_installments_for_payroll")
@patch("app.modules.employee_loans.application.enrichment.get_legal_interest_rate")
def test_enrich_payslip_loans_continues_partial_installment(
    mock_legal_rate,
    mock_due,
    mock_repayments_repo,
    mock_installments_repo,
    mock_loans_repo,
    mock_suspended,
):
    """Mois 2 : reprise de la même échéance partial avec reliquat."""
    mock_legal_rate.return_value = Decimal("0")
    mock_suspended.return_value = []
    mock_repayments_repo.get_existing.return_value = None
    mock_due.return_value = [
        _loan_item(
            capital_part=500,
            interest_part=0,
            capital_paid=200,
            interest_paid=0,
            remaining_capital=4800,
            inst_month=6,
        )
    ]

    payslip = {"net_a_payer": 2500.0}
    result = enrich_payslip_loans(
        payslip, "emp-1", 2026, 7, payslip_id="payslip-2"
    )

    assert result["remboursements_prets"]["total_capital"] == 300.0
    mock_installments_repo.increment_paid.assert_called_once()
    assert mock_installments_repo.increment_paid.call_args[0][3] == "paid"
    prets = result["remboursements_prets"]["prets"][0]
    assert prets["installment_number"] == 1


@patch("app.modules.employee_loans.application.enrichment.get_suspended_loans_with_pending_installment")
@patch("app.modules.employee_loans.application.enrichment.employee_loan_repayments_repository")
@patch("app.modules.employee_loans.application.enrichment.get_unsettled_installments_for_payroll")
@patch("app.modules.employee_loans.application.enrichment.get_legal_interest_rate")
def test_enrich_payslip_loans_idempotent_on_regeneration(
    mock_legal_rate,
    mock_due,
    mock_repayments_repo,
    mock_suspended,
):
    mock_legal_rate.return_value = Decimal("0")
    mock_suspended.return_value = []
    mock_repayments_repo.get_existing.return_value = {
        "capital_amount": 175.5,
        "interest_amount": 5.34,
        "avantage_nature_amount": 0.93,
        "remaining_after": 4824.5,
        "installment_id": "inst-1",
    }
    mock_due.return_value = [_loan_item()]

    payslip = {"net_a_payer": 1446.66}
    result = enrich_payslip_loans(
        payslip, "emp-1", 2026, 6, payslip_id="payslip-1"
    )

    assert result["remboursements_prets"]["total_rembourse"] == 180.84
    mock_repayments_repo.create.assert_not_called()


@patch("app.modules.employee_loans.application.enrichment.employee_loan_installments_repository")
@patch("app.modules.employee_loans.application.enrichment.get_suspended_loans_with_pending_installment")
def test_process_suspended_loan_installments_marks_skipped(
    mock_suspended,
    mock_installments_repo,
):
    mock_suspended.return_value = [
        {
            "id": "loan-1",
            "installment": {"id": "inst-1"},
        }
    ]

    process_suspended_loan_installments("emp-1", 2026, 6)

    mock_installments_repo.update.assert_called_once_with(
        "inst-1", {"status": "skipped"}
    )
