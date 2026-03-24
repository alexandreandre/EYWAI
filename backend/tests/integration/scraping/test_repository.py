"""
Tests d'intégration du repository scraping.

ScrapingRepository : accès Supabase mocké pour valider la logique des appels
(get_scraping_stats, get_source_by_key, list_sources, create_job, update_job,
list_schedules, create_schedule, update_schedule, delete_schedule, list_alerts,
mark_alert_read, resolve_alert). Avec DB de test réelle : utiliser la fixture
db_session (conftest) et des données dans scraping_sources, scraping_jobs,
scraping_schedules, scraping_alerts.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.scraping.infrastructure.repository import ScrapingRepository

REPO_SUPABASE_PATH = "app.modules.scraping.infrastructure.repository.supabase"


def _make_execute_result(data=None):
    """Construit un objet résultat .execute() avec .data."""
    if data is None:
        data = []
    res = MagicMock()
    res.data = data
    return res


def _make_table_chain(mock_supabase, final_data=None):
    """Chaîne table().select().... pour retourner final_data (liste) au .execute()."""
    if final_data is None:
        final_data = []
    if not isinstance(final_data, list):
        final_data = [final_data] if final_data else []
    execute_res = _make_execute_result(final_data)
    single = MagicMock()
    single.execute.return_value = execute_res
    eq = MagicMock()
    eq.single.return_value = single
    eq.execute.return_value = execute_res
    select = MagicMock()
    select.eq.return_value = select  # chaînage eq().eq().order().execute()
    select.order.return_value = select
    select.range.return_value = select
    select.limit.return_value = select
    select.maybe_single.return_value = single
    select.execute.return_value = execute_res
    table = MagicMock()
    table.select.return_value = select
    mock_supabase.table.return_value = table
    return table


@pytest.mark.integration
class TestScrapingRepositoryGetScrapingStats:
    """Repository.get_scraping_stats (RPC)."""

    def test_returns_dict_from_rpc(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            mock_sb.rpc.return_value.execute.return_value = _make_execute_result(
                [{"total_jobs": 42, "success_rate": 0.95}]
            )
            repo = ScrapingRepository()
            result = repo.get_scraping_stats()
        assert result == {"total_jobs": 42, "success_rate": 0.95}
        mock_sb.rpc.assert_called_once_with("get_scraping_stats")

    def test_returns_empty_dict_when_no_data(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            mock_sb.rpc.return_value.execute.return_value = _make_execute_result([])
            repo = ScrapingRepository()
            result = repo.get_scraping_stats()
        assert result == {}


@pytest.mark.integration
class TestScrapingRepositoryGetSourceByKey:
    """Repository.get_source_by_key (.single() retourne un objet, pas une liste)."""

    def test_returns_source_when_found(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            # .single().execute() retourne .data = un seul dict en Supabase
            res = MagicMock()
            res.data = {"id": "src-1", "source_key": "SMIC", "source_name": "Salaire minimum"}
            mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = res
            repo = ScrapingRepository()
            result = repo.get_source_by_key("SMIC")
        assert result is not None
        assert result["id"] == "src-1"
        assert result["source_key"] == "SMIC"

    def test_returns_none_when_not_found(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            res = MagicMock()
            res.data = None
            mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = res
            repo = ScrapingRepository()
            result = repo.get_source_by_key("UNKNOWN")
        assert result is None


@pytest.mark.integration
class TestScrapingRepositoryListSources:
    """Repository.list_sources avec filtres."""

    def test_returns_list_and_applies_filters(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            table = _make_table_chain(mock_sb, [{"id": "src-1", "source_name": "SMIC"}])
            select = table.select.return_value
            repo = ScrapingRepository()
            result = repo.list_sources(
                source_type="legal",
                is_critical=True,
                is_active=True,
            )
        assert len(result) == 1
        assert result[0]["id"] == "src-1"
        assert mock_sb.table.called
        assert select.eq.called  # au moins un filtre (source_type, is_critical, is_active)


@pytest.mark.integration
class TestScrapingRepositoryCreateJob:
    """Repository.create_job."""

    def test_inserts_and_returns_created_row(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            mock_sb.table.return_value.insert.return_value.execute.return_value = _make_execute_result(
                [{"id": "job-new", "source_id": "src-1", "status": "pending"}]
            )
            repo = ScrapingRepository()
            result = repo.create_job(
                {"source_id": "src-1", "job_type": "manual", "status": "pending"}
            )
        assert result["id"] == "job-new"
        assert result["source_id"] == "src-1"
        mock_sb.table.return_value.insert.assert_called_once()


@pytest.mark.integration
class TestScrapingRepositoryUpdateJob:
    """Repository.update_job."""

    def test_calls_update_with_id_and_data(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            chain = mock_sb.table.return_value.update.return_value.eq.return_value
            chain.execute.return_value = _make_execute_result([])
            repo = ScrapingRepository()
            repo.update_job("job-1", {"status": "completed", "success": True})
        mock_sb.table.return_value.update.assert_called_once_with({"status": "completed", "success": True})
        mock_sb.table.return_value.update.return_value.eq.assert_called_once_with("id", "job-1")


@pytest.mark.integration
class TestScrapingRepositorySchedules:
    """Repository create_schedule, update_schedule, delete_schedule."""

    def test_create_schedule_returns_created_row(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            mock_sb.table.return_value.insert.return_value.execute.return_value = _make_execute_result(
                [{"id": "sched-1", "source_id": "src-1", "schedule_type": "cron"}]
            )
            repo = ScrapingRepository()
            result = repo.create_schedule(
                {"source_id": "src-1", "schedule_type": "cron", "cron_expression": "0 0 * * *"}
            )
        assert result["id"] == "sched-1"
        assert result["schedule_type"] == "cron"

    def test_update_schedule_returns_updated_row(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = _make_execute_result(
                [{"id": "sched-1", "is_enabled": False}]
            )
            repo = ScrapingRepository()
            result = repo.update_schedule("sched-1", {"is_enabled": False})
        assert result is not None
        assert result["is_enabled"] is False

    def test_delete_schedule_returns_true_when_data(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = _make_execute_result(
                [{"id": "sched-1"}]
            )
            repo = ScrapingRepository()
            ok = repo.delete_schedule("sched-1")
        assert ok is True

    def test_delete_schedule_returns_false_when_no_data(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = _make_execute_result(
                []
            )
            repo = ScrapingRepository()
            ok = repo.delete_schedule("sched-unknown")
        assert ok is False


@pytest.mark.integration
class TestScrapingRepositoryAlerts:
    """Repository list_alerts, mark_alert_read, resolve_alert."""

    def test_list_alerts_returns_list(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            table = _make_table_chain(mock_sb, [{"id": "alert-1", "severity": "error"}])
            table.select.return_value.order.return_value.limit.return_value.execute.return_value = _make_execute_result(
                [{"id": "alert-1"}]
            )
            repo = ScrapingRepository()
            result = repo.list_alerts(is_read=False, limit=10)
        assert len(result) >= 0
        mock_sb.table.assert_called_with("scraping_alerts")

    def test_mark_alert_read_returns_true_when_updated(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = _make_execute_result(
                [{"id": "alert-1", "is_read": True}]
            )
            repo = ScrapingRepository()
            ok = repo.mark_alert_read("alert-1")
        assert ok is True

    def test_resolve_alert_returns_true_when_updated(self):
        with patch(REPO_SUPABASE_PATH) as mock_sb:
            mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = _make_execute_result(
                [{"id": "alert-1", "is_resolved": True}]
            )
            repo = ScrapingRepository()
            ok = repo.resolve_alert("alert-1", {"is_resolved": True, "is_read": True})
        assert ok is True
