"""Tests enrichissement bulletin prêts employeur."""

from decimal import Decimal
from unittest.mock import patch

from app.modules.employee_loans.application.enrichment import enrich_payslip_loans


@patch("app.modules.employee_loans.application.enrichment.employee_loans_repository")
@patch("app.modules.employee_loans.application.enrichment.employee_loan_installments_repository")
@patch("app.modules.employee_loans.application.enrichment.employee_loan_repayments_repository")
@patch("app.modules.employee_loans.application.enrichment.get_loans_due_for_period")
@patch("app.modules.employee_loans.application.enrichment.get_legal_interest_rate")
def test_enrich_payslip_loans_deducts_from_net(
    mock_legal_rate,
    mock_due,
    mock_repayments_repo,
    mock_installments_repo,
    mock_loans_repo,
):
    mock_legal_rate.return_value = Decimal("0.0352")
    mock_repayments_repo.get_existing.return_value = None
    mock_due.return_value = [
        {
            "id": "loan-1",
            "remaining_capital": 5000,
            "annual_interest_rate": 0,
            "reason": "Test",
            "installment": {
                "id": "inst-1",
                "capital_part": 400,
                "interest_part": 0,
            },
        }
    ]

    payslip = {"net_a_payer": 2500.0, "salaire_brut": 3000.0}
    result = enrich_payslip_loans(
        payslip, "emp-1", 2026, 6, payslip_id="payslip-1"
    )

    assert result["remboursements_prets"]["total_rembourse"] == 400.0
    assert result["net_a_payer"] == 2100.0
    mock_repayments_repo.create.assert_called_once()
    mock_loans_repo.update.assert_called_once()
