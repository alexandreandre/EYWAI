"""Tests rapprochement manuel import calendrier."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.admin_import.application.planning_import_mappings import (
    apply_planning_manual_mappings,
)
from app.modules.schedules.application.exceptions import ScheduleAppError


def test_apply_manual_mapping_updates_summary() -> None:
    batch = {
        "id": "batch-1",
        "status": "previewed",
        "company_id": "co-1",
        "parser_key": "quadra_planning_calendar",
        "filename": "cal.xlsx",
        "period_year": 2026,
        "period_month": 1,
        "preview_json": {
            "year": 2026,
            "month": 1,
            "warnings": [],
            "affected_months": [{"year": 2026, "month": 1}],
        },
        "summary_json": {
            "period_mode": "year",
            "month_groups": [
                {
                    "year": 2026,
                    "month": 1,
                    "employees": [
                        {
                            "raw_name": "EL IDRISSI",
                            "employee_id": None,
                            "review_status": "error",
                            "days": [{"jour": 1, "nature": "prevu", "type": "travail"}],
                        }
                    ],
                }
            ],
            "sheets_parsed": 1,
        },
    }
    employee = {
        "id": "emp-hafida",
        "first_name": "Hafida",
        "last_name": "MARCHICH",
    }

    with patch(
        "app.modules.admin_import.application.planning_import_mappings.timesheet_import_repository"
    ) as repo_mock, patch(
        "app.modules.admin_import.application.planning_import_mappings.repo.list_company_employees",
        return_value=[employee],
    ):
        repo_mock.get_batch.return_value = batch
        result = apply_planning_manual_mappings(
            "batch-1",
            "co-1",
            [{"raw_name": "EL IDRISSI", "employee_id": "emp-hafida"}],
        )

    assert result["summary"]["employees_ok"] == 1
    assert result["summary"]["employees_error"] == 0
    assert result["summary"]["review_items"] == []
    repo_mock.update_batch.assert_called_once()


def test_apply_manual_mapping_rejects_duplicate_target_in_request() -> None:
    batch = {
        "id": "batch-1",
        "status": "previewed",
        "company_id": "co-1",
        "parser_key": "quadra_planning_calendar",
        "period_year": 2026,
        "period_month": 1,
        "preview_json": {"year": 2026, "month": 1, "warnings": []},
        "summary_json": {
            "period_mode": "year",
            "month_groups": [
                {
                    "year": 2026,
                    "month": 1,
                    "employees": [
                        {"raw_name": "COUTANT", "employee_id": None, "review_status": "error"},
                        {"raw_name": "DIAS", "employee_id": None, "review_status": "error"},
                    ],
                }
            ],
        },
    }
    employee = {"id": "emp-1", "first_name": "Denis", "last_name": "COUTANT"}

    with patch(
        "app.modules.admin_import.application.planning_import_mappings.timesheet_import_repository"
    ) as repo_mock, patch(
        "app.modules.admin_import.application.planning_import_mappings.repo.list_company_employees",
        return_value=[employee],
    ):
        repo_mock.get_batch.return_value = batch
        with pytest.raises(ScheduleAppError, match="déjà sélectionné"):
            apply_planning_manual_mappings(
                "batch-1",
                "co-1",
                [
                    {"raw_name": "COUTANT", "employee_id": "emp-1"},
                    {"raw_name": "DIAS", "employee_id": "emp-1"},
                ],
            )


def test_apply_manual_mapping_rejects_already_assigned_employee() -> None:
    batch = {
        "id": "batch-1",
        "status": "previewed",
        "company_id": "co-1",
        "parser_key": "quadra_planning_calendar",
        "period_year": 2026,
        "period_month": 1,
        "preview_json": {"year": 2026, "month": 1, "warnings": []},
        "summary_json": {
            "period_mode": "year",
            "month_groups": [
                {
                    "year": 2026,
                    "month": 1,
                    "employees": [
                        {"raw_name": "ALVES", "employee_id": "emp-1", "review_status": "ok"},
                        {"raw_name": "DIAS", "employee_id": None, "review_status": "error"},
                    ],
                }
            ],
        },
    }
    employee = {"id": "emp-1", "first_name": "Lucas", "last_name": "ALVES"}

    with patch(
        "app.modules.admin_import.application.planning_import_mappings.timesheet_import_repository"
    ) as repo_mock, patch(
        "app.modules.admin_import.application.planning_import_mappings.repo.list_company_employees",
        return_value=[employee],
    ):
        repo_mock.get_batch.return_value = batch
        with pytest.raises(ScheduleAppError, match="déjà associé"):
            apply_planning_manual_mappings(
                "batch-1",
                "co-1",
                [{"raw_name": "DIAS", "employee_id": "emp-1"}],
            )
