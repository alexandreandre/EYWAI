"""Tests unitaires réconciliation effectifs DSN."""

from unittest.mock import patch

import pytest

from app.modules.dsn_import.application.commit import _apply_workforce_resolutions
from app.modules.dsn_import.application.workforce_reconciliation import (
    compute_workforce_gaps,
    validate_workforce_resolutions_for_commit,
    workforce_blocks_commit,
)

pytestmark = pytest.mark.unit

COMPANY_ID = "co-1"


def _employee_item(nir: str, *, is_existing: bool = False, contract_end_date: str | None = None):
    return {
        "item_type": "employee",
        "source_ref": f"emp:siret:{nir}",
        "is_existing": is_existing,
        "mapped_payload": {
            "nir": nir,
            "first_name": "Jean",
            "last_name": "Dupont",
            "contract_end_date": contract_end_date,
        },
    }


@patch("app.modules.dsn_import.application.workforce_reconciliation.repo")
class TestComputeWorkforceGaps:
    def test_disabled_for_onboarding(self, mock_repo):
        summary, anomalies = compute_workforce_gaps(
            [_employee_item("111")],
            target_company_id=COMPANY_ID,
            import_mode="onboarding",
            summary={"cumul_periods": ["2026-03"]},
        )
        assert summary["enabled"] is False
        assert anomalies == []
        mock_repo.list_active_employees_with_nir.assert_not_called()

    def test_missing_from_dsn_departure_suspected(self, mock_repo):
        mock_repo.list_active_employees_with_nir.return_value = [
            {
                "id": "emp-a",
                "first_name": "Alex",
                "last_name": "Jolly",
                "nir": "1111111111111",
                "employment_status": "actif",
                "hire_date": "2026-01-15",
            },
            {
                "id": "emp-b",
                "first_name": "Marie",
                "last_name": "Martin",
                "nir": "2222222222222",
                "employment_status": "actif",
                "hire_date": "2025-06-01",
            },
        ]
        mock_repo.list_active_employees_without_nir.return_value = []
        mock_repo.find_company_by_id.return_value = {"company_name": "Test SA"}

        summary, anomalies = compute_workforce_gaps(
            [_employee_item("2222222222222")],
            target_company_id=COMPANY_ID,
            import_mode="monthly",
            summary={"cumul_periods": ["2026-03"]},
        )
        assert summary["enabled"] is True
        assert len(summary["gaps"]) == 1
        assert summary["gaps"][0]["gap_type"] == "missing_from_dsn"
        assert summary["gaps"][0]["likely_scenario"] == "departure"
        assert summary["gaps"][0]["employee_id"] == "emp-a"
        assert summary["gap_counts_by_type"]["missing_from_dsn"] == 1
        assert any(a["code"] == "workforce_reconciliation_required" for a in anomalies)

    def test_new_hire_not_in_dsn(self, mock_repo):
        mock_repo.list_active_employees_with_nir.return_value = [
            {
                "id": "emp-new",
                "first_name": "Mathys",
                "last_name": "Fillinger",
                "nir": "1111111111111",
                "employment_status": "actif",
                "hire_date": "2026-03-10",
            },
        ]
        mock_repo.list_active_employees_without_nir.return_value = []
        mock_repo.find_company_by_id.return_value = {"company_name": "Labo 404"}

        summary, anomalies = compute_workforce_gaps(
            [],
            target_company_id=COMPANY_ID,
            import_mode="monthly",
            summary={"cumul_periods": ["2026-03"]},
        )
        assert len(summary["gaps"]) == 1
        assert summary["gaps"][0]["gap_type"] == "new_hire_not_in_dsn"
        assert summary["gaps"][0]["likely_scenario"] == "new_hire"
        assert summary["gaps"][0]["suggested_last_working_day"] is None
        assert summary["gap_counts_by_type"]["new_hire_not_in_dsn"] == 1
        assert any(a["code"] == "employee_new_hire_not_in_dsn" for a in anomalies)

    def test_excluded_hire_after_period(self, mock_repo):
        mock_repo.list_active_employees_with_nir.return_value = [
            {
                "id": "emp-future",
                "first_name": "Future",
                "last_name": "Hire",
                "nir": "1111111111111",
                "employment_status": "actif",
                "hire_date": "2026-04-01",
            },
        ]
        mock_repo.list_active_employees_without_nir.return_value = []

        summary, anomalies = compute_workforce_gaps(
            [],
            target_company_id=COMPANY_ID,
            import_mode="monthly",
            summary={"cumul_periods": ["2026-03"]},
        )
        assert summary["gaps"] == []
        assert summary["excluded_out_of_scope_count"] == 1
        assert anomalies == []

    def test_excluded_departed_before_period(self, mock_repo):
        mock_repo.list_active_employees_with_nir.return_value = [
            {
                "id": "emp-gone",
                "first_name": "Parti",
                "last_name": "Avant",
                "nir": "1111111111111",
                "employment_status": "actif",
                "hire_date": "2025-01-01",
                "contract_end_date": "2026-02-28",
            },
        ]
        mock_repo.list_active_employees_without_nir.return_value = []

        summary, _ = compute_workforce_gaps(
            [],
            target_company_id=COMPANY_ID,
            import_mode="monthly",
            summary={"cumul_periods": ["2026-03"]},
        )
        assert summary["gaps"] == []
        assert summary["excluded_out_of_scope_count"] == 1

    def test_contract_end_in_dsn(self, mock_repo):
        mock_repo.list_active_employees_with_nir.return_value = [
            {
                "id": "emp-b",
                "first_name": "Marie",
                "last_name": "Martin",
                "nir": "2222222222222",
                "employment_status": "actif",
                "hire_date": "2024-01-01",
            },
        ]
        mock_repo.list_active_employees_without_nir.return_value = []
        mock_repo.find_company_by_id.return_value = {"company_name": "Test SA"}

        summary, _ = compute_workforce_gaps(
            [
                _employee_item(
                    "2222222222222",
                    is_existing=True,
                    contract_end_date="2026-03-15",
                )
            ],
            target_company_id=COMPANY_ID,
            import_mode="monthly",
            summary={"cumul_periods": ["2026-03"]},
        )
        assert len(summary["gaps"]) == 1
        assert summary["gaps"][0]["gap_type"] == "contract_end_in_dsn"

    def test_no_gap_when_present(self, mock_repo):
        mock_repo.list_active_employees_with_nir.return_value = [
            {
                "id": "emp-b",
                "first_name": "Marie",
                "last_name": "Martin",
                "nir": "2222222222222",
                "employment_status": "actif",
                "hire_date": "2024-01-01",
            },
        ]
        mock_repo.list_active_employees_without_nir.return_value = []

        summary, anomalies = compute_workforce_gaps(
            [_employee_item("2222222222222")],
            target_company_id=COMPANY_ID,
            import_mode="monthly",
            summary={"cumul_periods": ["2026-03"]},
        )
        assert summary["gaps"] == []
        assert anomalies == []

    def test_missing_from_dsn_matches_nir_without_spaces(self, mock_repo):
        mock_repo.list_active_employees_with_nir.return_value = [
            {
                "id": "emp-a",
                "first_name": "Alex",
                "last_name": "Jolly",
                "nir": "1 11 11 11 111 111",
                "employment_status": "actif",
                "hire_date": "2025-06-01",
            },
        ]
        mock_repo.list_active_employees_without_nir.return_value = []
        mock_repo.find_company_by_id.return_value = {"company_name": "Test SA"}

        summary, _ = compute_workforce_gaps(
            [_employee_item("1111111111111")],
            target_company_id=COMPANY_ID,
            import_mode="monthly",
            summary={"cumul_periods": ["2026-03"]},
        )
        assert summary["gaps"] == []


class TestWorkforceBlocksCommit:
    def test_workforce_blocks_commit_until_resolved(self):
        summary = {
            "workforce_reconciliation": {
                "enabled": True,
                "gaps": [{"gap_id": "missing:emp-a", "employee_name": "Alex"}],
                "resolutions": {},
            }
        }
        assert workforce_blocks_commit(summary) is True
        summary["workforce_reconciliation"]["resolutions"] = {
            "missing:emp-a": {"gap_id": "missing:emp-a", "action": "ignore"},
        }
        assert workforce_blocks_commit(summary) is False


class TestValidateWorkforceResolutions:
    def test_raises_when_unresolved(self):
        summary = {
            "workforce_reconciliation": {
                "enabled": True,
                "gaps": [
                    {
                        "gap_id": "missing:emp-a",
                        "employee_name": "Alex Jolly",
                    }
                ],
            }
        }
        with pytest.raises(ValueError, match="incomplète"):
            validate_workforce_resolutions_for_commit(summary, [])

    def test_accepts_ignore(self):
        summary = {
            "workforce_reconciliation": {
                "enabled": True,
                "gaps": [
                    {
                        "gap_id": "missing:emp-a",
                        "employee_name": "Alex Jolly",
                        "suggested_last_working_day": "2026-03-31",
                    }
                ],
            }
        }
        validate_workforce_resolutions_for_commit(
            summary,
            [
                {
                    "gap_id": "missing:emp-a",
                    "employee_id": "emp-a",
                    "action": "ignore",
                    "ignore_reason": "dsn_incomplete",
                }
            ],
        )

    def test_accepts_acknowledge_new_hire(self):
        summary = {
            "workforce_reconciliation": {
                "enabled": True,
                "gaps": [
                    {
                        "gap_id": "missing:emp-new",
                        "employee_name": "Mathys Fillinger",
                        "gap_type": "new_hire_not_in_dsn",
                    }
                ],
            }
        }
        validate_workforce_resolutions_for_commit(
            summary,
            [
                {
                    "gap_id": "missing:emp-new",
                    "employee_id": "emp-new",
                    "action": "acknowledge_new_hire",
                }
            ],
        )

    def test_requires_date_for_close(self):
        summary = {
            "workforce_reconciliation": {
                "enabled": True,
                "gaps": [
                    {
                        "gap_id": "missing:emp-a",
                        "employee_name": "Alex Jolly",
                    }
                ],
            }
        }
        with pytest.raises(ValueError, match="dernier jour ouvré"):
            validate_workforce_resolutions_for_commit(
                summary,
                [
                    {
                        "gap_id": "missing:emp-a",
                        "employee_id": "emp-a",
                        "action": "close_departure",
                    }
                ],
            )


class TestApplyWorkforceResolutions:
    def test_acknowledge_new_hire_does_not_create_exit(self):
        report = _apply_workforce_resolutions(
            [
                {
                    "gap_id": "missing:emp-new",
                    "employee_id": "emp-new",
                    "action": "acknowledge_new_hire",
                    "hire_date": "2026-03-10",
                }
            ],
            COMPANY_ID,
            "user-1",
        )
        assert len(report["acknowledged_new_hires"]) == 1
        assert report["acknowledged_new_hires"][0]["employee_id"] == "emp-new"
        assert report["closed"] == []
        assert report["open_exit_deferred"] == []

    def test_delete_permanently_calls_delete_employee(self):
        with patch(
            "app.modules.employees.application.commands.delete_employee"
        ) as mock_delete:
            report = _apply_workforce_resolutions(
                [
                    {
                        "gap_id": "missing:emp-a",
                        "employee_id": "emp-a",
                        "action": "delete_permanently",
                    }
                ],
                COMPANY_ID,
                "user-1",
            )
        mock_delete.assert_called_once_with("emp-a", COMPANY_ID)
        assert len(report["deleted"]) == 1
        assert report["deleted"][0]["employee_id"] == "emp-a"

    def test_delete_permanently_not_allowed_for_contract_end_gap(self):
        summary = {
            "workforce_reconciliation": {
                "enabled": True,
                "gaps": [
                    {
                        "gap_id": "end:emp-a",
                        "gap_type": "contract_end_in_dsn",
                        "employee_name": "Alex Jolly",
                    }
                ],
            }
        }
        with pytest.raises(ValueError, match="suppression définitive"):
            validate_workforce_resolutions_for_commit(
                summary,
                [
                    {
                        "gap_id": "end:emp-a",
                        "employee_id": "emp-a",
                        "action": "delete_permanently",
                    }
                ],
            )
