"""Résolution employé pour évaluations compétences (collaborateur)."""

from unittest.mock import patch

from app.modules.competencies.infrastructure.repository import SupabaseCompetenciesRepository


@patch(
    "app.modules.employees.infrastructure.queries.resolve_employee_id_for_user_account",
    return_value="emp-resolved",
)
def test_competencies_get_employee_id_for_user_delegates_resolve(mock_resolve):
    repo = SupabaseCompetenciesRepository()
    assert repo.get_employee_id_for_user("auth-1", "co-1") == "emp-resolved"
    mock_resolve.assert_called_once_with("auth-1", "co-1")
