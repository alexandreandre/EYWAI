"""Tests activation compte salarié importé."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.dsn_import.application.service import activate_imported_employee


def test_activate_imported_employee_delegates():
    with patch(
        "app.modules.employees.application.commands.activate_imported_employee_account"
    ) as mock_activate:
        mock_activate.return_value = {
            "employee_id": "e1",
            "user_id": "u1",
            "email": "jean@test.fr",
            "generated_password": "Secret123!",
        }
        result = activate_imported_employee(
            "e1", "c1", "jean@test.fr", granted_by_user_id="admin-1"
        )
        mock_activate.assert_called_once_with(
            employee_id="e1",
            company_id="c1",
            email="jean@test.fr",
            granted_by_user_id="admin-1",
        )
        assert result["generated_password"] == "Secret123!"
