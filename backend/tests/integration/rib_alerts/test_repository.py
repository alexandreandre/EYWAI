"""
Tests d'intégration du repository rib_alerts.

SupabaseRibAlertRepository : list, get_by_id, mark_read, resolve, create.
Les requêtes DB (infrastructure/queries) sont mockées pour valider la logique et les appels.
Avec DB de test réelle : utiliser la fixture db_session (conftest) et des données dans rib_alerts.
"""
from unittest.mock import patch

import pytest

from app.modules.rib_alerts.domain.entities import RibAlert
from app.modules.rib_alerts.infrastructure.repository import SupabaseRibAlertRepository


# Patch au niveau du module repository (où les queries sont importées)
QUERIES_PATH = "app.modules.rib_alerts.infrastructure.repository"


@pytest.mark.integration
class TestSupabaseRibAlertRepositoryList:
    """Repository.list : liste avec filtres et pagination."""

    def test_list_returns_alerts_and_total_from_queries(self):
        """list délègue à list_rib_alerts_rows et mappe les lignes en RibAlert."""
        row1 = {
            "id": "alert-1",
            "company_id": "company-1",
            "employee_id": "emp-1",
            "alert_type": "rib_modified",
            "severity": "warning",
            "title": "IBAN modifié",
            "message": "Message",
            "details": {"old_iban_masked": "FR76***1"},
            "is_read": False,
            "is_resolved": False,
            "resolved_at": None,
            "resolution_note": None,
            "created_at": "2024-01-15T10:00:00Z",
        }
        with patch(f"{QUERIES_PATH}.list_rib_alerts_rows", return_value=([row1], 1)):
            repo = SupabaseRibAlertRepository()
            alerts, total = repo.list("company-1", limit=50, offset=0)
        assert total == 1
        assert len(alerts) == 1
        assert isinstance(alerts[0], RibAlert)
        assert alerts[0].id == "alert-1"
        assert alerts[0].company_id == "company-1"
        assert alerts[0].alert_type == "rib_modified"
        assert alerts[0].is_read is False

    def test_list_passes_filters_to_query(self):
        """list transmet is_read, is_resolved, alert_type, employee_id, limit, offset."""
        with patch(f"{QUERIES_PATH}.list_rib_alerts_rows", return_value=([], 0)) as mock_list:
            repo = SupabaseRibAlertRepository()
            repo.list(
                "company-1",
                is_read=True,
                is_resolved=False,
                alert_type="rib_duplicate",
                employee_id="emp-1",
                limit=20,
                offset=10,
            )
        mock_list.assert_called_once_with(
            "company-1",
            is_read=True,
            is_resolved=False,
            alert_type="rib_duplicate",
            employee_id="emp-1",
            limit=20,
            offset=10,
        )

    def test_list_empty_returns_empty_list_and_zero_total(self):
        """Aucune ligne : ([], 0)."""
        with patch(f"{QUERIES_PATH}.list_rib_alerts_rows", return_value=([], 0)):
            repo = SupabaseRibAlertRepository()
            alerts, total = repo.list("company-1")
        assert alerts == []
        assert total == 0


@pytest.mark.integration
class TestSupabaseRibAlertRepositoryGetById:
    """Repository.get_by_id."""

    def test_get_by_id_returns_alert_when_found(self):
        """get_by_id retourne RibAlert si la ligne existe."""
        row = {
            "id": "alert-1",
            "company_id": "company-1",
            "employee_id": None,
            "alert_type": "rib_duplicate",
            "severity": "error",
            "title": "Doublon",
            "message": "Msg",
            "details": {},
            "is_read": True,
            "is_resolved": True,
            "resolved_at": "2024-01-16T12:00:00Z",
            "resolution_note": "OK",
            "created_at": "2024-01-15T10:00:00Z",
        }
        with patch(f"{QUERIES_PATH}.get_rib_alert_row_by_id", return_value=row):
            repo = SupabaseRibAlertRepository()
            alert = repo.get_by_id("alert-1", "company-1")
        assert alert is not None
        assert alert.id == "alert-1"
        assert alert.company_id == "company-1"
        assert alert.is_resolved is True
        assert alert.resolution_note == "OK"

    def test_get_by_id_returns_none_when_not_found(self):
        """get_by_id retourne None si la ligne n'existe pas."""
        with patch(f"{QUERIES_PATH}.get_rib_alert_row_by_id", return_value=None):
            repo = SupabaseRibAlertRepository()
            alert = repo.get_by_id("unknown", "company-1")
        assert alert is None


@pytest.mark.integration
class TestSupabaseRibAlertRepositoryMarkRead:
    """Repository.mark_read."""

    def test_mark_read_calls_update_and_returns_true(self):
        """mark_read appelle update_rib_alert_read et retourne True."""
        with patch(f"{QUERIES_PATH}.update_rib_alert_read", return_value=True) as mock_update:
            repo = SupabaseRibAlertRepository()
            result = repo.mark_read("alert-1", "company-1")
        assert result is True
        mock_update.assert_called_once_with("alert-1", "company-1")

    def test_mark_read_returns_false_when_no_row_updated(self):
        """mark_read retourne False si aucune ligne mise à jour."""
        with patch(f"{QUERIES_PATH}.update_rib_alert_read", return_value=False):
            repo = SupabaseRibAlertRepository()
            result = repo.mark_read("alert-unknown", "company-1")
        assert result is False


@pytest.mark.integration
class TestSupabaseRibAlertRepositoryResolve:
    """Repository.resolve."""

    def test_resolve_calls_update_with_resolved_by_and_note(self):
        """resolve appelle update_rib_alert_resolve avec resolved_by et resolution_note."""
        with patch(f"{QUERIES_PATH}.update_rib_alert_resolve", return_value=True) as mock_update:
            repo = SupabaseRibAlertRepository()
            result = repo.resolve("alert-1", "company-1", "user-1", "Résolu manuellement")
        assert result is True
        mock_update.assert_called_once_with("alert-1", "company-1", "user-1", "Résolu manuellement")

    def test_resolve_with_none_note(self):
        """resolution_note peut être None."""
        with patch(f"{QUERIES_PATH}.update_rib_alert_resolve", return_value=True) as mock_update:
            repo = SupabaseRibAlertRepository()
            repo.resolve("alert-1", "company-1", "user-1", None)
        mock_update.assert_called_once_with("alert-1", "company-1", "user-1", None)

    def test_resolve_returns_false_when_no_row_updated(self):
        """resolve retourne False si aucune ligne mise à jour."""
        with patch(f"{QUERIES_PATH}.update_rib_alert_resolve", return_value=False):
            repo = SupabaseRibAlertRepository()
            result = repo.resolve("alert-unknown", "company-1", "user-1", None)
        assert result is False


@pytest.mark.integration
class TestSupabaseRibAlertRepositoryCreate:
    """Repository.create (usage interne)."""

    def test_create_returns_alert_when_insert_succeeds(self):
        """create insère via insert_rib_alert et retourne RibAlert mappé."""
        row = {
            "id": "alert-new",
            "company_id": "company-1",
            "employee_id": "emp-1",
            "alert_type": "rib_modified",
            "severity": "warning",
            "title": "Nouvelle alerte",
            "message": "Msg",
            "details": {},
            "is_read": False,
            "is_resolved": False,
            "resolved_at": None,
            "resolution_note": None,
            "created_at": "2024-01-17T00:00:00Z",
        }
        with patch(f"{QUERIES_PATH}.insert_rib_alert", return_value=row):
            repo = SupabaseRibAlertRepository()
            alert = repo.create({"company_id": "company-1", "alert_type": "rib_modified", "title": "Nouvelle alerte", "message": "Msg", "severity": "warning", "details": {}})
        assert alert is not None
        assert alert.id == "alert-new"
        assert alert.company_id == "company-1"
        assert alert.alert_type == "rib_modified"

    def test_create_returns_none_when_insert_fails(self):
        """create retourne None si insert_rib_alert échoue."""
        with patch(f"{QUERIES_PATH}.insert_rib_alert", return_value=None):
            repo = SupabaseRibAlertRepository()
            alert = repo.create({"company_id": "c1"})
        assert alert is None
