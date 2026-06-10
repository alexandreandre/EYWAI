"""Tests unitaires requêtes versements/remboursements par période."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.saisies_avances.infrastructure import queries as infra_queries

pytestmark = pytest.mark.unit

ADVANCES = [
    {
        "id": "adv-1",
        "company_id": "co-1",
        "employee_id": "emp-1",
        "advance_type": "acompte_salaire",
        "accounting_account": "4251",
        "status": "paid",
        "prime_label": None,
    }
]

PAYMENTS = [
    {
        "id": "pay-1",
        "advance_id": "adv-1",
        "payment_amount": 500,
        "payment_date": "2026-06-15",
    }
]

REPAYMENTS = [
    {
        "id": "rep-1",
        "advance_id": "adv-1",
        "repayment_amount": 500,
        "year": 2026,
        "month": 6,
        "payslip_id": "ps-1",
    }
]


def _mock_table_chain(data):
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.in_.return_value = mock
    mock.gte.return_value = mock
    mock.lte.return_value = mock
    mock.order.return_value = mock
    mock.is_.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = MagicMock(data=data)
    return mock


class TestListAdvancePaymentsByPeriod:
    @patch.object(infra_queries, "supabase")
    @patch.object(infra_queries, "_load_employees_map", return_value={"emp-1": "Jean Dupont"})
    @patch.object(infra_queries, "_load_company_advances_map", return_value={"adv-1": ADVANCES[0]})
    def test_returns_enriched_payments(self, _adv_map, _emp_map, mock_supabase):
        mock_supabase.table.return_value = _mock_table_chain(PAYMENTS)

        result = infra_queries.list_advance_payments_by_period("co-1", "2026-06")

        assert len(result) == 1
        assert result[0]["employee_name"] == "Jean Dupont"
        assert result[0]["event_type"] == "versement"
        assert result[0]["amount_paid"] == 500.0
        assert result[0]["accounting_account"] == "4251"


class TestListAdvanceRepaymentsByPeriod:
    @patch.object(infra_queries, "supabase")
    @patch.object(infra_queries, "_load_employees_map", return_value={"emp-1": "Jean Dupont"})
    @patch.object(infra_queries, "_load_company_advances_map", return_value={"adv-1": ADVANCES[0]})
    def test_returns_enriched_repayments(self, _adv_map, _emp_map, mock_supabase):
        mock_supabase.table.return_value = _mock_table_chain(REPAYMENTS)

        result = infra_queries.list_advance_repayments_by_period("co-1", "2026-06")

        assert len(result) == 1
        assert result[0]["employee_name"] == "Jean Dupont"
        assert result[0]["event_type"] == "remboursement"
        assert result[0]["amount_repaid"] == 500.0
