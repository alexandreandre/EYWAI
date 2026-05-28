"""
Tests unitaires du service applicatif du module absences (application/service.py).

Le service délègue à la résolution employé partagée.
"""

from unittest.mock import patch

from app.modules.absences.application import service


class TestResolveEmployeeIdForUser:
    """Service resolve_employee_id_for_user (délégation API partagée)."""

    def test_returns_employee_id_when_found(self):
        with patch(
            "app.modules.absences.application.service.resolve_employee_id_for_user_account",
            return_value="emp-uuid-123",
        ):
            result = service.resolve_employee_id_for_user("user-uuid-456", "co-1")
        assert result == "emp-uuid-123"

    def test_returns_none_when_not_found(self):
        with patch(
            "app.modules.absences.application.service.resolve_employee_id_for_user_account",
            return_value=None,
        ):
            result = service.resolve_employee_id_for_user("user-unknown", "co-1")
        assert result is None

    def test_returns_none_without_company_id(self):
        assert service.resolve_employee_id_for_user("user-42", None) is None

    def test_calls_shared_api_with_user_and_company(self):
        with patch(
            "app.modules.absences.application.service.resolve_employee_id_for_user_account",
        ) as resolve_mock:
            resolve_mock.return_value = "emp-1"
            service.resolve_employee_id_for_user("user-42", "co-1")
            resolve_mock.assert_called_once_with("user-42", "co-1")
