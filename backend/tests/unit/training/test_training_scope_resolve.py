"""Résolution employé pour le périmètre salarié (formations)."""

from unittest.mock import patch

from app.modules.training.infrastructure.repository import SupabaseTrainingRepository


@patch(
    "app.modules.employees.infrastructure.queries.resolve_employee_id_for_user_account",
    return_value="emp-resolved",
)
def test_training_get_employee_id_for_user_delegates_resolve(mock_resolve):
    repo = SupabaseTrainingRepository()
    assert repo.get_employee_id_for_user("auth-1", "co-1") == "emp-resolved"
    mock_resolve.assert_called_once_with("auth-1", "co-1")
