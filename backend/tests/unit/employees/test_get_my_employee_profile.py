"""Fiche employé /me : résolution compte auth → employees.id."""

from unittest.mock import patch

from app.modules.employees.application import queries


@patch("app.modules.employees.application.queries.get_employee_by_id")
@patch(
    "app.modules.employees.application.queries.resolve_employee_id_for_user_account"
)
def test_get_my_employee_profile_uses_resolved_id(mock_resolve, mock_get_by_id):
    mock_resolve.return_value = "emp-99"
    mock_get_by_id.return_value = {"id": "emp-99", "first_name": "Ada"}

    result = queries.get_my_employee_profile("auth-1", "co-1")

    assert result == {"id": "emp-99", "first_name": "Ada"}
    mock_resolve.assert_called_once_with("auth-1", "co-1")
    mock_get_by_id.assert_called_once_with("emp-99", "co-1")


@patch(
    "app.modules.employees.application.queries.resolve_employee_id_for_user_account",
    return_value=None,
)
def test_get_my_employee_profile_returns_none_when_unlinked(_mock_resolve):
    assert queries.get_my_employee_profile("auth-x", "co-1") is None
