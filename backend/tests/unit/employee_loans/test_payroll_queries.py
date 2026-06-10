"""Tests requêtes paie prêts employeur."""

from unittest.mock import MagicMock, patch

from app.modules.employee_loans.infrastructure import payroll_queries


@patch.object(payroll_queries, "supabase")
def test_get_unsettled_installments_returns_oldest_partial(mock_supabase):
    loan_table = MagicMock()
    inst_table = MagicMock()
    mock_supabase.table.side_effect = lambda name: (
        loan_table if name == payroll_queries.TABLE_EMPLOYEE_LOANS else inst_table
    )

    loan_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "loan-1",
                "employee_id": "emp-1",
                "status": "active",
                "remaining_capital": 4800,
            }
        ]
    )

    inst_chain = inst_table.select.return_value.eq.return_value.in_.return_value
    inst_chain.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "inst-1",
                "installment_number": 1,
                "year": 2026,
                "month": 6,
                "capital_part": 410.97,
                "interest_part": 12.5,
                "capital_paid": 175.5,
                "interest_paid": 5.34,
                "status": "partial",
            }
        ]
    )

    result = payroll_queries.get_unsettled_installments_for_payroll(
        "emp-1", 2026, 7
    )

    assert len(result) == 1
    assert result[0]["installment"]["status"] == "partial"
    assert result[0]["installment"]["capital_paid"] == 175.5


@patch.object(payroll_queries, "supabase")
def test_get_unsettled_skips_future_installment(mock_supabase):
    loan_table = MagicMock()
    inst_table = MagicMock()
    mock_supabase.table.side_effect = lambda name: (
        loan_table if name == payroll_queries.TABLE_EMPLOYEE_LOANS else inst_table
    )

    loan_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "loan-1", "remaining_capital": 5000}]
    )

    inst_chain = inst_table.select.return_value.eq.return_value.in_.return_value
    inst_chain.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "inst-2",
                "installment_number": 2,
                "year": 2026,
                "month": 8,
                "capital_part": 412,
                "interest_part": 11,
                "capital_paid": 0,
                "interest_paid": 0,
                "status": "pending",
            }
        ]
    )

    result = payroll_queries.get_unsettled_installments_for_payroll(
        "emp-1", 2026, 7
    )

    assert result == []
