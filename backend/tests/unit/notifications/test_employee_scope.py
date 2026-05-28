"""Résolution employé — notifications (délégation API partagée)."""

from unittest.mock import patch

from app.modules.notifications.application import employee_scope


def test_resolve_delegates_to_shared_api():
    with patch.object(
        employee_scope,
        "resolve_employee_id_for_notifications",
        return_value="emp-1",
    ) as mock_resolve:
        assert (
            employee_scope.resolve_employee_id_for_notifications("user-1", "co-1")
            == "emp-1"
        )
        mock_resolve.assert_called_once_with("user-1", "co-1")


def test_resolve_returns_none_when_unlinked():
    with patch.object(
        employee_scope,
        "resolve_employee_id_for_notifications",
        return_value=None,
    ):
        assert (
            employee_scope.resolve_employee_id_for_notifications("user-orphan", "co-1")
            is None
        )
