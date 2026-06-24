"""Tests reset onboarding après purge employés."""

from unittest.mock import MagicMock, patch

from app.modules.employees.application.company_onboarding_reset import (
    reset_company_onboarding_after_employee_purge,
)


@patch("app.modules.employees.application.company_onboarding_reset.get_supabase_admin_client")
@patch("app.modules.employees.application.company_onboarding_reset.compute_coverage")
@patch("app.modules.employees.application.company_onboarding_reset.dsn_repo")
def test_reset_company_onboarding_after_employee_purge(mock_dsn_repo, mock_coverage, mock_client_fn):
    mock_dsn_repo.find_company_by_id.return_value = {
        "id": "co-1",
        "company_name": "Comitech",
        "siret": "49861035100013",
    }
    mock_dsn_repo.list_committed_batches.return_value = []
    mock_dsn_repo.list_revoked_periods.return_value = []
    mock_coverage.return_value = {"months_covered": ["2026-01", "2026-02", "2026-03"]}

    client = MagicMock()
    mock_client_fn.return_value = client
    client.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "x"}]
    )

    result = reset_company_onboarding_after_employee_purge("co-1")

    assert result["revoked_periods"] == ["2026-01", "2026-02", "2026-03"]
    assert mock_dsn_repo.upsert_period_revocation.call_count == 3
    assert client.table.call_count == 2
