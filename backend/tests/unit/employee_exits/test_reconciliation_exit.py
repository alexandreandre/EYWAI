"""Tests create_reconciliation_exit (clôture rapide DSN)."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.application.commands import create_reconciliation_exit

pytestmark = pytest.mark.unit

COMPANY_ID = "co-exit"
EMPLOYEE_ID = "emp-exit"
USER_ID = "user-1"


@patch("app.modules.employee_exits.application.commands.create_default_checklist_sync")
@patch("app.modules.employee_exits.application.commands.update_exit_status")
@patch("app.modules.employee_exits.application.commands.update_employee_employment_status")
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
@patch("app.modules.employee_exits.application.commands.get_employee_by_id")
def test_create_reconciliation_exit_fast_archive_demission(
    mock_get_employee,
    mock_exit_repo_cls,
    mock_update_status,
    mock_update_exit_status,
    mock_checklist,
):
    mock_get_employee.return_value = {
        "id": EMPLOYEE_ID,
        "company_id": COMPANY_ID,
        "employment_status": "actif",
        "first_name": "Alex",
        "last_name": "Jolly",
    }
    exit_repo = MagicMock()
    mock_exit_repo_cls.return_value = exit_repo
    lwd = date.today() - timedelta(days=10)
    exit_repo.create.return_value = {"id": "exit-1", "status": "demission_recue"}
    exit_repo.get_by_id.return_value = {"id": "exit-1", "status": "archivee"}

    result = create_reconciliation_exit(
        EMPLOYEE_ID,
        COMPANY_ID,
        USER_ID,
        exit_type="demission",
        last_working_day=lwd,
        source="dsn_reconciliation",
        supabase_client=MagicMock(),
    )

    assert result["id"] == "exit-1"
    mock_update_status.assert_called()
    assert mock_update_exit_status.call_count >= 2


@patch("app.modules.employee_exits.application.commands.create_default_checklist_sync")
@patch("app.modules.employee_exits.application.commands.update_exit_status")
@patch("app.modules.employee_exits.application.commands.update_employee_employment_status")
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
@patch("app.modules.employee_exits.application.commands.get_employee_by_id")
def test_create_reconciliation_exit_fast_archive_licenciement(
    mock_get_employee,
    mock_exit_repo_cls,
    mock_update_status,
    mock_update_exit_status,
    mock_checklist,
):
    mock_get_employee.return_value = {
        "id": EMPLOYEE_ID,
        "company_id": COMPANY_ID,
        "employment_status": "actif",
    }
    exit_repo = MagicMock()
    mock_exit_repo_cls.return_value = exit_repo
    lwd = date.today() - timedelta(days=10)
    exit_repo.create.return_value = {"id": "exit-1", "status": "licenciement_convocation"}
    exit_repo.get_by_id.return_value = {"id": "exit-1", "status": "licenciement_convocation"}
    exit_repo.get_by_id.side_effect = [
        {"id": "exit-1", "status": "licenciement_convocation"},
        {"id": "exit-1", "status": "archivee"},
    ]

    create_reconciliation_exit(
        EMPLOYEE_ID,
        COMPANY_ID,
        USER_ID,
        exit_type="licenciement",
        last_working_day=lwd,
        source="dsn_reconciliation",
        supabase_client=MagicMock(),
    )

    statuses = [call.args[2] for call in mock_update_exit_status.call_args_list]
    assert statuses == [
        "licenciement_notifie",
        "licenciement_effective",
        "archivee",
    ]


@patch("app.modules.employee_exits.application.commands.create_default_checklist_sync")
@patch("app.modules.employee_exits.application.commands.update_exit_status")
@patch("app.modules.employee_exits.application.commands.update_employee_employment_status")
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
@patch("app.modules.employee_exits.application.commands.get_employee_by_id")
def test_create_reconciliation_exit_fast_archive_rupture_conventionnelle(
    mock_get_employee,
    mock_exit_repo_cls,
    mock_update_status,
    mock_update_exit_status,
    mock_checklist,
):
    mock_get_employee.return_value = {
        "id": EMPLOYEE_ID,
        "company_id": COMPANY_ID,
        "employment_status": "actif",
    }
    exit_repo = MagicMock()
    mock_exit_repo_cls.return_value = exit_repo
    lwd = date.today() - timedelta(days=10)
    exit_repo.create.return_value = {"id": "exit-1", "status": "rupture_en_negociation"}
    exit_repo.get_by_id.return_value = {"id": "exit-1", "status": "rupture_en_negociation"}

    create_reconciliation_exit(
        EMPLOYEE_ID,
        COMPANY_ID,
        USER_ID,
        exit_type="rupture_conventionnelle",
        last_working_day=lwd,
        source="dsn_reconciliation",
        supabase_client=MagicMock(),
    )

    statuses = [call.args[2] for call in mock_update_exit_status.call_args_list]
    assert statuses == [
        "rupture_validee",
        "rupture_homologuee",
        "rupture_effective",
        "archivee",
    ]
