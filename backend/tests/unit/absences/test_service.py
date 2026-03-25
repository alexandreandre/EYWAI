"""
Tests unitaires du service applicatif du module absences (application/service.py).

Le service délègue à l'infrastructure (resolve_employee_id_for_user).
Dépendances mockées.
"""
from unittest.mock import patch


from app.modules.absences.application import service


class TestResolveEmployeeIdForUser:
    """Service resolve_employee_id_for_user (délégation infrastructure)."""

    def test_returns_employee_id_when_found(self):
        """Infrastructure retourne un employee_id → même valeur."""
        with patch(
            "app.modules.absences.application.service._resolve",
            return_value="emp-uuid-123",
        ):
            result = service.resolve_employee_id_for_user("user-uuid-456")
        assert result == "emp-uuid-123"

    def test_returns_none_when_not_found(self):
        """Infrastructure retourne None → None."""
        with patch(
            "app.modules.absences.application.service._resolve",
            return_value=None,
        ):
            result = service.resolve_employee_id_for_user("user-unknown")
        assert result is None

    def test_calls_infrastructure_with_user_id(self):
        """Vérifie que l'infrastructure est appelée avec le user_id passé."""
        with patch(
            "app.modules.absences.application.service._resolve"
        ) as resolve_mock:
            resolve_mock.return_value = "emp-1"
            service.resolve_employee_id_for_user("user-42")
            resolve_mock.assert_called_once_with("user-42")
