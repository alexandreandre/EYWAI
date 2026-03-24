"""
Tests unitaires des commandes rib_alerts (application/commands.py).

Repository mocké : get_rib_alert_repository. Couvre mark_rib_alert_read et resolve_rib_alert.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.rib_alerts.application.commands import mark_rib_alert_read, resolve_rib_alert
from app.modules.rib_alerts.domain.exceptions import MissingCompanyContextError


class TestMarkRibAlertRead:
    """Commande mark_rib_alert_read."""

    def test_returns_true_when_repository_marks_read(self):
        """Si le repository marque comme lu, retourne True."""
        mock_repo = MagicMock()
        mock_repo.mark_read.return_value = True
        with patch("app.modules.rib_alerts.application.commands.get_rib_alert_repository", return_value=mock_repo):
            result = mark_rib_alert_read(alert_id="alert-1", company_id="company-1")
        assert result is True
        mock_repo.mark_read.assert_called_once_with("alert-1", "company-1")

    def test_returns_false_when_alert_not_found(self):
        """Si l'alerte n'existe pas, le repository retourne False."""
        mock_repo = MagicMock()
        mock_repo.mark_read.return_value = False
        with patch("app.modules.rib_alerts.application.commands.get_rib_alert_repository", return_value=mock_repo):
            result = mark_rib_alert_read(alert_id="alert-unknown", company_id="company-1")
        assert result is False
        mock_repo.mark_read.assert_called_once_with("alert-unknown", "company-1")

    def test_raises_missing_company_context_when_company_id_none(self):
        """company_id None lève MissingCompanyContextError (avant appel au repository)."""
        with patch("app.modules.rib_alerts.application.commands.get_rib_alert_repository", return_value=MagicMock()):
            with pytest.raises(MissingCompanyContextError):
                mark_rib_alert_read(alert_id="alert-1", company_id=None)
        # Le repository ne doit pas être appelé
        # (require_company_id lève avant)

    def test_raises_missing_company_context_when_company_id_empty(self):
        """company_id vide lève MissingCompanyContextError."""
        with patch("app.modules.rib_alerts.application.commands.get_rib_alert_repository", return_value=MagicMock()):
            with pytest.raises(MissingCompanyContextError):
                mark_rib_alert_read(alert_id="alert-1", company_id="")

    def test_strips_company_id_before_call(self):
        """company_id est strippé par require_company_id avant passage au repository."""
        mock_repo = MagicMock()
        mock_repo.mark_read.return_value = True
        with patch("app.modules.rib_alerts.application.commands.get_rib_alert_repository", return_value=mock_repo):
            mark_rib_alert_read(alert_id="a1", company_id="  company-1  ")
        mock_repo.mark_read.assert_called_once_with("a1", "company-1")


class TestResolveRibAlert:
    """Commande resolve_rib_alert."""

    def test_returns_true_when_repository_resolves(self):
        """Si le repository marque comme résolu, retourne True."""
        mock_repo = MagicMock()
        mock_repo.resolve.return_value = True
        with patch("app.modules.rib_alerts.application.commands.get_rib_alert_repository", return_value=mock_repo):
            result = resolve_rib_alert(
                alert_id="alert-1",
                company_id="company-1",
                resolved_by="user-1",
                resolution_note="Résolu manuellement",
            )
        assert result is True
        mock_repo.resolve.assert_called_once_with(
            "alert-1",
            "company-1",
            "user-1",
            "Résolu manuellement",
        )

    def test_returns_false_when_alert_not_found(self):
        """Si l'alerte n'existe pas, retourne False."""
        mock_repo = MagicMock()
        mock_repo.resolve.return_value = False
        with patch("app.modules.rib_alerts.application.commands.get_rib_alert_repository", return_value=mock_repo):
            result = resolve_rib_alert(
                alert_id="alert-unknown",
                company_id="company-1",
                resolved_by="user-1",
                resolution_note=None,
            )
        assert result is False
        mock_repo.resolve.assert_called_once_with("alert-unknown", "company-1", "user-1", None)

    def test_raises_missing_company_context_when_company_id_none(self):
        """company_id None lève MissingCompanyContextError."""
        with patch("app.modules.rib_alerts.application.commands.get_rib_alert_repository", return_value=MagicMock()):
            with pytest.raises(MissingCompanyContextError):
                resolve_rib_alert(
                    alert_id="alert-1",
                    company_id=None,
                    resolved_by="user-1",
                    resolution_note=None,
                )

    def test_calls_repository_with_none_note(self):
        """resolution_note peut être None."""
        mock_repo = MagicMock()
        mock_repo.resolve.return_value = True
        with patch("app.modules.rib_alerts.application.commands.get_rib_alert_repository", return_value=mock_repo):
            resolve_rib_alert(alert_id="a1", company_id="c1", resolved_by="u1", resolution_note=None)
        mock_repo.resolve.assert_called_once_with("a1", "c1", "u1", None)
