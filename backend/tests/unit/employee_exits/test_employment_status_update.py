"""Tests unitaires de update_employee_employment_status."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.infrastructure.queries import (
    update_employee_employment_status,
)

pytestmark = pytest.mark.unit


@patch("app.modules.employee_exits.infrastructure.queries.supabase")
def test_update_employment_status_sets_exit_id(mock_sb):
    table = MagicMock()
    mock_sb.table.return_value = table
    chain = table.update.return_value
    chain.eq.return_value.execute.return_value = None

    update_employee_employment_status("emp-1", "en_sortie", "exit-1")

    table.update.assert_called_once_with(
        {"employment_status": "en_sortie", "current_exit_id": "exit-1"}
    )
    chain.eq.assert_called_once_with("id", "emp-1")


@patch("app.modules.employee_exits.infrastructure.queries.supabase")
def test_update_employment_status_clears_exit_id_when_none(mock_sb):
    table = MagicMock()
    mock_sb.table.return_value = table
    chain = table.update.return_value
    chain.eq.return_value.execute.return_value = None

    update_employee_employment_status("emp-1", "parti", None)

    table.update.assert_called_once_with(
        {"employment_status": "parti", "current_exit_id": None}
    )


@patch("app.modules.employee_exits.infrastructure.queries.supabase")
def test_update_employment_status_omits_exit_id_when_not_provided(mock_sb):
    table = MagicMock()
    mock_sb.table.return_value = table
    chain = table.update.return_value
    chain.eq.return_value.execute.return_value = None

    update_employee_employment_status("emp-1", "actif")

    table.update.assert_called_once_with({"employment_status": "actif"})
