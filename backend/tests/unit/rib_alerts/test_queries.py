"""
Tests unitaires des queries rib_alerts (application/queries.py).

Repository et mappers mockés : get_rib_alert_repository, rib_alert_to_response_dict.
Couvre get_rib_alerts.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.modules.rib_alerts.application.dto import (
    RibAlertListFilters,
    RibAlertListResult,
)
from app.modules.rib_alerts.application.queries import get_rib_alerts
from app.modules.rib_alerts.domain.entities import RibAlert
from app.modules.rib_alerts.domain.exceptions import MissingCompanyContextError


def _make_alert(
    alert_id: str = "alert-1",
    company_id: str = "company-1",
    employee_id: str | None = None,
    alert_type: str = "rib_modified",
    severity: str = "warning",
    is_read: bool = False,
    is_resolved: bool = False,
    created_at: datetime | None = None,
) -> RibAlert:
    return RibAlert(
        id=alert_id,
        company_id=company_id,
        employee_id=employee_id,
        alert_type=alert_type,
        severity=severity,
        title="IBAN modifié",
        message="L'IBAN a été modifié.",
        details={"old_iban_masked": "FR76***1", "new_iban_masked": "FR76***2"},
        is_read=is_read,
        is_resolved=is_resolved,
        resolved_at=None,
        resolution_note=None,
        resolved_by=None,
        created_at=created_at or datetime.now(timezone.utc),
    )


class TestGetRibAlerts:
    """Query get_rib_alerts."""

    def test_returns_list_result_with_alerts_and_total(self):
        """Retourne RibAlertListResult avec alerts (dicts) et total."""
        alert1 = _make_alert("a1", is_read=False)
        alert2 = _make_alert("a2", is_read=True)
        mock_repo = MagicMock()
        mock_repo.list.return_value = ([alert1, alert2], 2)

        def fake_mapper(a: RibAlert) -> dict:
            return {
                "id": a.id,
                "company_id": a.company_id,
                "alert_type": a.alert_type,
                "total": 2,
            }

        with (
            patch(
                "app.modules.rib_alerts.application.queries.get_rib_alert_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.rib_alerts.application.queries.rib_alert_to_response_dict",
                side_effect=fake_mapper,
            ),
        ):
            result = get_rib_alerts(
                company_id="company-1",
                filters=RibAlertListFilters(
                    is_read=None, is_resolved=None, limit=50, offset=0
                ),
            )

        assert isinstance(result, RibAlertListResult)
        assert result.total == 2
        assert len(result.alerts) == 2
        assert result.alerts[0]["id"] == "a1"
        assert result.alerts[1]["id"] == "a2"
        mock_repo.list.assert_called_once_with(
            "company-1",
            is_read=None,
            is_resolved=None,
            alert_type=None,
            employee_id=None,
            limit=50,
            offset=0,
        )

    def test_passes_filters_to_repository(self):
        """Les filtres (is_read, is_resolved, alert_type, employee_id, limit, offset) sont passés au repository."""
        mock_repo = MagicMock()
        mock_repo.list.return_value = ([], 0)
        with (
            patch(
                "app.modules.rib_alerts.application.queries.get_rib_alert_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.rib_alerts.application.queries.rib_alert_to_response_dict",
                return_value={},
            ),
        ):
            get_rib_alerts(
                company_id="company-1",
                filters=RibAlertListFilters(
                    is_read=True,
                    is_resolved=False,
                    alert_type="rib_duplicate",
                    employee_id="emp-1",
                    limit=20,
                    offset=10,
                ),
            )
        mock_repo.list.assert_called_once_with(
            "company-1",
            is_read=True,
            is_resolved=False,
            alert_type="rib_duplicate",
            employee_id="emp-1",
            limit=20,
            offset=10,
        )

    def test_raises_missing_company_context_when_company_id_none(self):
        """company_id None lève MissingCompanyContextError (pas d'appel au repository)."""
        with patch(
            "app.modules.rib_alerts.application.queries.get_rib_alert_repository",
            return_value=MagicMock(),
        ):
            with pytest.raises(MissingCompanyContextError):
                get_rib_alerts(company_id=None, filters=RibAlertListFilters())

    def test_raises_missing_company_context_when_company_id_empty(self):
        """company_id vide lève MissingCompanyContextError."""
        with patch(
            "app.modules.rib_alerts.application.queries.get_rib_alert_repository",
            return_value=MagicMock(),
        ):
            with pytest.raises(MissingCompanyContextError):
                get_rib_alerts(company_id="", filters=RibAlertListFilters())

    def test_empty_list_returns_zero_total(self):
        """Aucune alerte : liste vide et total 0."""
        mock_repo = MagicMock()
        mock_repo.list.return_value = ([], 0)
        with (
            patch(
                "app.modules.rib_alerts.application.queries.get_rib_alert_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.rib_alerts.application.queries.rib_alert_to_response_dict",
                return_value={},
            ),
        ):
            result = get_rib_alerts(
                company_id="company-1", filters=RibAlertListFilters()
            )
        assert result.total == 0
        assert result.alerts == []
