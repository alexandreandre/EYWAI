"""Tests unitaires réconciliation effectifs DSN."""

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.dsn_import.application.workforce_reconciliation import (
    compute_workforce_gaps,
    validate_workforce_resolutions_for_commit,
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

    def test_missing_from_dsn(self, mock_repo):
        mock_repo.list_active_employees_with_nir.return_value = [
            {
                "id": "emp-a",
                "first_name": "Alex",
                "last_name": "Jolly",
                "nir": "1111111111111",
                "employment_status": "actif",
            },
            {
                "id": "emp-b",
                "first_name": "Marie",
                "last_name": "Martin",
                "nir": "2222222222222",
                "employment_status": "actif",
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
        assert summary["gaps"][0]["employee_id"] == "emp-a"
        assert any(a["code"] == "workforce_reconciliation_required" for a in anomalies)

    def test_contract_end_in_dsn(self, mock_repo):
        mock_repo.list_active_employees_with_nir.return_value = [
            {
                "id": "emp-b",
                "first_name": "Marie",
                "last_name": "Martin",
                "nir": "2222222222222",
                "employment_status": "actif",
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
