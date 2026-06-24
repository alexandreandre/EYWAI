"""Tests commit import export paie (enrichissement uniquement)."""

from unittest.mock import patch

import pytest

from app.modules.admin_import.application.payroll_export_import import (
    commit_payroll_export,
)
from app.modules.admin_import.schemas.requests import (
    PayrollExportCommitBody,
    PayrollExportCommitRow,
)


@pytest.fixture
def company_id():
    return "co-test-123"


def test_commit_skips_unmatched(company_id):
    body = PayrollExportCommitBody(
        company_id=company_id,
        rows=[
            PayrollExportCommitRow(
                row_index=1,
                employee_id="emp-1",
                employee_patch={"phone_number": "0612345678"},
                confirmed=True,
            )
        ],
    )
    with patch(
        "app.modules.admin_import.application.payroll_export_import.repo.find_company",
        return_value={"id": company_id, "company_name": "Test"},
    ), patch(
        "app.modules.admin_import.application.payroll_export_import.repo.list_company_employees",
        return_value=[{"id": "emp-1", "first_name": "A", "last_name": "B", "email": "a@b.fr"}],
    ), patch(
        "app.modules.admin_import.application.payroll_export_import.employee_commands.update_employee",
        return_value={"id": "emp-1", "warnings": []},
    ) as mock_update:
        result = commit_payroll_export(body)
        assert result["applied"] == 1
        mock_update.assert_called_once()
        call_patch = mock_update.call_args[0][1]
        assert call_patch["phone_number"] == "0612345678"


def test_commit_replaces_dsn_placeholder_email(company_id):
    body = PayrollExportCommitBody(
        company_id=company_id,
        rows=[
            PayrollExportCommitRow(
                row_index=2,
                employee_id="emp-1",
                employee_patch={"email": "real.user@example.com"},
                confirmed=True,
            )
        ],
    )
    with patch(
        "app.modules.admin_import.application.payroll_export_import.repo.find_company",
        return_value={"id": company_id},
    ), patch(
        "app.modules.admin_import.application.payroll_export_import.repo.list_company_employees",
        return_value=[
            {
                "id": "emp-1",
                "first_name": "Samir",
                "last_name": "TEST",
                "email": "import.samir.test@498610351.dsn-import.local",
            }
        ],
    ), patch(
        "app.modules.admin_import.application.payroll_export_import.employee_commands.update_employee",
        return_value={"id": "emp-1"},
    ) as mock_update:
        commit_payroll_export(body)
        call_patch = mock_update.call_args[0][1]
        assert call_patch["email"] == "real.user@example.com"


def test_commit_assigns_team_and_boeth(company_id):
    body = PayrollExportCommitBody(
        company_id=company_id,
        rows=[
            PayrollExportCommitRow(
                row_index=3,
                employee_id="emp-1",
                employee_patch={},
                team_name="MOI",
                boeth={"boeth_code": "01"},
                confirmed=True,
            )
        ],
    )
    with patch(
        "app.modules.admin_import.application.payroll_export_import.repo.find_company",
        return_value={"id": company_id},
    ), patch(
        "app.modules.admin_import.application.payroll_export_import.repo.list_company_employees",
        return_value=[{"id": "emp-1", "first_name": "T", "last_name": "L"}],
    ), patch(
        "app.modules.admin_import.application.payroll_export_import._get_or_create_team",
        return_value="team-moi",
    ), patch(
        "app.modules.admin_import.application.payroll_export_import.assign_employee_to_team",
        return_value={"id": "emp-1"},
    ) as mock_assign, patch(
        "app.modules.admin_import.application.payroll_export_import.save_employee_boeth",
        return_value={},
    ) as mock_boeth:
        result = commit_payroll_export(body)
        assert result["applied"] == 1
        mock_assign.assert_called_once()
        mock_boeth.assert_called_once()
