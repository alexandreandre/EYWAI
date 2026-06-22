"""Tests révocation import DSN mensuel."""

from unittest.mock import patch

import pytest

from app.modules.dsn_import.application.revoke_period import revoke_period_import


def test_revoke_period_import_success():
    company = {"id": "co-1", "dsn_sync_mode": "external", "siret": "80248516900022"}
    with patch("app.modules.dsn_import.application.revoke_period.repo") as repo, patch(
        "app.modules.dsn_import.application.revoke_period.compute_coverage"
    ) as cov, patch(
        "app.modules.dsn_import.application.revoke_period.delete_cumuls_file"
    ) as delete_file:
        repo.find_company_by_id.return_value = company
        repo.list_committed_batches.return_value = []
        repo.list_revoked_periods.return_value = []
        cov.return_value = {"months_covered": ["2026-03"]}
        repo.list_employees_with_folder.return_value = [
            {"id": "e1", "employee_folder_name": "JOLLY_Alex"},
            {"id": "e2", "employee_folder_name": "DUPONT_Marie"},
        ]
        delete_file.side_effect = [True, False]

        result = revoke_period_import("co-1", "2026-03", revoked_by="admin-1")

    repo.upsert_period_revocation.assert_called_once_with(
        "co-1", "2026-03", revoked_by="admin-1"
    )
    assert delete_file.call_count == 2
    assert result["cumuls_deleted"] == 1
    assert result["period"] == "2026-03"


def test_revoke_period_import_not_covered():
    with patch("app.modules.dsn_import.application.revoke_period.repo") as repo, patch(
        "app.modules.dsn_import.application.revoke_period.compute_coverage"
    ) as cov:
        repo.find_company_by_id.return_value = {"id": "co-1"}
        repo.list_committed_batches.return_value = []
        repo.list_revoked_periods.return_value = []
        cov.return_value = {"months_covered": ["2026-02"]}

        with pytest.raises(ValueError, match="n'est pas couverte"):
            revoke_period_import("co-1", "2026-03")


def test_revoke_period_import_invalid_period():
    with patch("app.modules.dsn_import.application.revoke_period.repo") as repo:
        repo.find_company_by_id.return_value = {"id": "co-1"}
        with pytest.raises(ValueError, match="Période invalide"):
            revoke_period_import("co-1", "bad-period")
