"""Résolution employé pour obligations légales (collaborateur)."""

from unittest.mock import patch

from app.modules.legal_obligations.infrastructure.repository import (
    SupabaseLegalObligationsRepository,
)


@patch(
    "app.modules.employees.infrastructure.queries.resolve_employee_id_for_user_account",
    return_value="emp-resolved",
)
def test_legal_get_employee_id_for_user_delegates_resolve(mock_resolve):
    repo = SupabaseLegalObligationsRepository()
    assert repo.get_employee_id_for_user("auth-1", "co-1") == "emp-resolved"
    mock_resolve.assert_called_once_with("auth-1", "co-1")
