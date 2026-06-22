"""Résolution employé pour les routes notes de frais collaborateur."""

from unittest.mock import patch

from app.modules.expenses.application.queries import (
    get_my_expenses_for_user_account,
    resolve_employee_id_for_expense_account,
)


@patch(
    "app.modules.employees.infrastructure.queries.resolve_employee_id_for_user_account",
    return_value="emp-resolved",
)
def test_resolve_employee_id_for_expense_account_uses_company(mock_resolve):
    assert resolve_employee_id_for_expense_account("auth-1", "co-1") == "emp-resolved"
    mock_resolve.assert_called_once_with("auth-1", "co-1")


def test_resolve_employee_id_for_expense_account_none_without_company():
    assert resolve_employee_id_for_expense_account("auth-1", None) is None


@patch("app.modules.expenses.application.queries.get_my_expenses")
@patch(
    "app.modules.expenses.application.queries.resolve_employee_id_for_expense_account",
    return_value="emp-resolved",
)
def test_get_my_expenses_for_user_account_uses_resolved_id(
    _mock_resolve, mock_get_my
):
    mock_get_my.return_value = [{"id": "exp-1"}]
    result = get_my_expenses_for_user_account("auth-1", "co-1")
    mock_get_my.assert_called_once_with("emp-resolved")
    assert result == [{"id": "exp-1"}]


@patch(
    "app.modules.expenses.application.queries.resolve_employee_id_for_expense_account",
    return_value=None,
)
def test_get_my_expenses_for_user_account_empty_when_unlinked(_mock_resolve):
    assert get_my_expenses_for_user_account("auth-x", "co-1") == []
