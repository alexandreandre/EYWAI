"""Résolution employé pour GET /api/me/payslips."""

from unittest.mock import patch

from app.modules.payslips.application.queries import get_my_payslips_for_user_account


@patch("app.modules.payslips.application.queries._get_my_payslips")
@patch(
    "app.modules.employees.infrastructure.queries.resolve_employee_id_for_user_account"
)
def test_get_my_payslips_for_user_account_uses_resolved_id(
    mock_resolve, mock_list
):
    mock_resolve.return_value = "emp-99"
    mock_list.return_value = [{"id": "ps-1"}]

    result = get_my_payslips_for_user_account("auth-1", "co-1")

    assert result == [{"id": "ps-1"}]
    mock_resolve.assert_called_once_with("auth-1", "co-1")
    mock_list.assert_called_once_with("emp-99")


@patch(
    "app.modules.employees.infrastructure.queries.resolve_employee_id_for_user_account",
    return_value=None,
)
def test_get_my_payslips_for_user_account_empty_when_unlinked(_mock_resolve):
    assert get_my_payslips_for_user_account("auth-x", "co-1") == []
