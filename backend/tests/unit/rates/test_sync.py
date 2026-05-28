"""Tests unitaires de la synchronisation des taux (registre + agrégation statut)."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.rates.application.sync import (
    cancel_rates_sync,
    get_rates_sync_status,
    reset_sync_registry_for_tests,
    start_rates_sync,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_sync_registry_for_tests()
    yield
    reset_sync_registry_for_tests()


class TestStartRatesSync:
    @patch("app.modules.rates.application.sync.execute_scraper")
    @patch("app.modules.rates.application.sync.ScrapingRepository")
    def test_start_creates_batch(self, mock_repo_cls, mock_execute):
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_critical_sources.return_value = [
            {"source_key": "smic", "source_name": "SMIC", "orchestrator_path": "/x"},
            {"source_key": "pss", "source_name": "PSS", "orchestrator_path": None},
        ]
        mock_execute.side_effect = [
            {"source": "SMIC", "source_key": "smic", "job_id": "job-1"},
            {"source": "PSS", "source_key": "pss", "job_id": "job-2"},
        ]

        bg = MagicMock()
        result = start_rates_sync(triggered_by="user-1", background_task_fn=bg)

        assert result["total"] == 2
        assert len(result["jobs"]) == 2
        assert result["sync_id"]
        assert mock_execute.call_count == 2

    @patch("app.modules.rates.application.sync.execute_scraper")
    @patch("app.modules.rates.application.sync.ScrapingRepository")
    def test_start_single_rate_key(self, mock_repo_cls, mock_execute):
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.list_sources.return_value = [
            {"source_key": "SMIC", "source_name": "SMIC", "orchestrator_path": "/x"},
        ]
        mock_execute.return_value = {
            "source": "SMIC",
            "source_key": "SMIC",
            "job_id": "job-1",
        }

        result = start_rates_sync(
            triggered_by="u",
            background_task_fn=MagicMock(),
            rate_keys=["smic"],
        )
        assert result["total"] == 1
        mock_execute.assert_called_once()

    @patch("app.modules.rates.application.sync.ScrapingRepository")
    def test_start_raises_when_no_sources(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_critical_sources.return_value = []

        with pytest.raises(ValueError, match="Aucune source"):
            start_rates_sync(triggered_by="u", background_task_fn=MagicMock())


class TestGetRatesSyncStatus:
    @patch("app.modules.rates.application.sync.execute_scraper")
    @patch("app.modules.rates.application.sync.ScrapingRepository")
    def test_status_running_then_completed(self, mock_repo_cls, mock_execute):
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_critical_sources.return_value = [
            {"source_key": "smic", "source_name": "SMIC", "orchestrator_path": "/x"},
        ]
        mock_execute.return_value = {
            "source": "SMIC",
            "source_key": "smic",
            "job_id": "job-1",
        }
        mock_repo.get_job.return_value = {
            "id": "job-1",
            "status": "running",
            "success": None,
        }

        started = start_rates_sync(triggered_by="u", background_task_fn=MagicMock())
        sync_id = started["sync_id"]

        status_running = get_rates_sync_status(sync_id)
        assert status_running["status"] == "running"
        assert status_running["progress"]["running"] == 1

        mock_repo.get_job.return_value = {
            "id": "job-1",
            "status": "completed",
            "success": True,
            "error_message": None,
            "completed_at": "2025-01-01T00:00:00Z",
        }
        status_done = get_rates_sync_status(sync_id)
        assert status_done["status"] == "completed"
        assert status_done["progress"]["completed"] == 1

    def test_status_unknown_sync_raises(self):
        with pytest.raises(ValueError, match="non trouvée"):
            get_rates_sync_status("missing-id")


class TestCancelRatesSync:
    @patch("app.modules.rates.application.sync.cancel_scraper_job")
    @patch("app.modules.rates.application.sync.execute_scraper")
    @patch("app.modules.rates.application.sync.ScrapingRepository")
    def test_cancel_marks_batch_cancelled(self, mock_repo_cls, mock_execute, mock_cancel_job):
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_critical_sources.return_value = [
            {"source_key": "smic", "source_name": "SMIC", "orchestrator_path": "/x"},
        ]
        mock_execute.return_value = {
            "source": "SMIC",
            "source_key": "smic",
            "job_id": "job-1",
        }
        mock_cancel_job.return_value = True

        started = start_rates_sync(triggered_by="u", background_task_fn=MagicMock())
        sync_id = started["sync_id"]

        status = cancel_rates_sync(sync_id)
        assert status["status"] == "cancelled"
        mock_cancel_job.assert_called_once_with("job-1")

    def test_cancel_unknown_sync_raises(self):
        with pytest.raises(ValueError, match="non trouvée"):
            cancel_rates_sync("missing-id")
