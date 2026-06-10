"""Tests intégration paie prêts employeur."""

from unittest.mock import patch

from app.modules.employee_loans.application.payroll_integration import (
    inject_loan_benefit_in_kind,
)


@patch(
    "app.modules.employee_loans.infrastructure.payroll_queries.compute_total_loan_benefit_in_kind"
)
def test_inject_loan_benefit_in_kind(mock_compute):
    mock_compute.return_value = 42.5
    contrat = {"remuneration": {"avantages_en_nature": {}}}

    result = inject_loan_benefit_in_kind(contrat, "emp-1", 2026, 6)

    assert result["remuneration"]["avantages_en_nature"]["pret_employeur"] == {
        "montant_mensuel": 42.5
    }


@patch(
    "app.modules.employee_loans.infrastructure.payroll_queries.compute_total_loan_benefit_in_kind"
)
def test_inject_loan_benefit_in_kind_no_amount(mock_compute):
    mock_compute.return_value = 0
    contrat = {"remuneration": {}}

    result = inject_loan_benefit_in_kind(contrat, "emp-1", 2026, 6)

    assert "pret_employeur" not in result.get("remuneration", {}).get(
        "avantages_en_nature", {}
    )
