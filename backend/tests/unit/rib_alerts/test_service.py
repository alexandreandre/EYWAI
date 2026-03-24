"""
Tests unitaires du service applicatif rib_alerts (application/service.py).

Dépendances mockées : commandes et queries (get_rib_alerts, mark_rib_alert_read, resolve_rib_alert).
Couvre list_rib_alerts, mark_read, resolve.
"""
from unittest.mock import MagicMock, patch

from app.modules.rib_alerts.application.dto import RibAlertListFilters, RibAlertListResult
from app.modules.rib_alerts.application.service import list_rib_alerts, mark_read, resolve


class TestListRibAlertsService:
    """Service list_rib_alerts : délègue à get_rib_alerts."""

    def test_returns_result_from_get_rib_alerts(self):
        """list_rib_alerts retourne le RibAlertListResult de get_rib_alerts."""
        expected = RibAlertListResult(alerts=[{"id": "a1", "title": "IBAN modifié"}], total=1)
        with patch("app.modules.rib_alerts.application.service.get_rib_alerts", return_value=expected) as mock_get:
            result = list_rib_alerts(company_id="company-1", filters=RibAlertListFilters())
        assert result is expected
        mock_get.assert_called_once_with("company-1", RibAlertListFilters())

    def test_passes_filters_through(self):
        """Les filtres sont passés tels quels à get_rib_alerts."""
        filters = RibAlertListFilters(
            is_read=True,
            is_resolved=False,
            alert_type="rib_duplicate",
            employee_id="emp-1",
            limit=20,
            offset=10,
        )
        with patch("app.modules.rib_alerts.application.service.get_rib_alerts", return_value=RibAlertListResult(alerts=[], total=0)) as mock_get:
            list_rib_alerts(company_id="c1", filters=filters)
        mock_get.assert_called_once_with("c1", filters)


class TestMarkReadService:
    """Service mark_read : délègue à mark_rib_alert_read."""

    def test_returns_true_when_command_succeeds(self):
        """mark_read retourne True si la commande réussit."""
        with patch("app.modules.rib_alerts.application.service.mark_rib_alert_read", return_value=True) as mock_cmd:
            result = mark_read(alert_id="alert-1", company_id="company-1")
        assert result is True
        mock_cmd.assert_called_once_with("alert-1", "company-1")

    def test_returns_false_when_alert_not_found(self):
        """mark_read retourne False si l'alerte n'existe pas."""
        with patch("app.modules.rib_alerts.application.service.mark_rib_alert_read", return_value=False) as mock_cmd:
            result = mark_read(alert_id="unknown", company_id="company-1")
        assert result is False
        mock_cmd.assert_called_once_with("unknown", "company-1")


class TestResolveService:
    """Service resolve : délègue à resolve_rib_alert."""

    def test_returns_true_when_command_succeeds(self):
        """resolve retourne True si la commande réussit."""
        with patch("app.modules.rib_alerts.application.service.resolve_rib_alert", return_value=True) as mock_cmd:
            result = resolve(
                alert_id="alert-1",
                company_id="company-1",
                resolved_by="user-1",
                resolution_note="Résolu",
            )
        assert result is True
        mock_cmd.assert_called_once_with("alert-1", "company-1", "user-1", "Résolu")

    def test_returns_false_when_alert_not_found(self):
        """resolve retourne False si l'alerte n'existe pas."""
        with patch("app.modules.rib_alerts.application.service.resolve_rib_alert", return_value=False) as mock_cmd:
            result = resolve(alert_id="unknown", company_id="company-1", resolved_by="user-1", resolution_note=None)
        assert result is False
        mock_cmd.assert_called_once_with("unknown", "company-1", "user-1", None)

    def test_passes_none_resolution_note(self):
        """resolution_note peut être None."""
        with patch("app.modules.rib_alerts.application.service.resolve_rib_alert", return_value=True) as mock_cmd:
            resolve(alert_id="a1", company_id="c1", resolved_by="u1", resolution_note=None)
        mock_cmd.assert_called_once_with("a1", "c1", "u1", None)
