"""Résolution employé pour objectifs (collaborateur)."""

from unittest.mock import patch

from app.modules.objectives.infrastructure.repository import SupabaseObjectivesRepository


@patch(
    "app.modules.employees.infrastructure.queries.resolve_employee_id_for_user_account",
    return_value="emp-resolved",
)
def test_objectives_get_employee_id_for_user_delegates_resolve(mock_resolve):
    repo = SupabaseObjectivesRepository()
    assert repo.get_employee_id_for_user("auth-1", "co-1") == "emp-resolved"
    mock_resolve.assert_called_once_with("auth-1", "co-1")
