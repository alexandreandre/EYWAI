"""
Tests unitaires des queries scraping (application/queries.py).

Repository mocké. Couvre get_scraping_dashboard, list_sources, get_source_details,
list_jobs, get_job_details, get_job_logs, list_schedules, list_alerts.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.scraping.application import queries

QUERIES_MODULE = "app.modules.scraping.application.queries"


class TestGetScrapingDashboard:
    """Query get_scraping_dashboard."""

    def test_returns_stats_recent_jobs_unread_alerts_critical_sources(self):
        mock_repo = MagicMock()
        mock_repo.get_scraping_stats.return_value = {"total_jobs": 100, "success_rate": 0.95}
        mock_repo.get_recent_jobs.return_value = [{"id": "job-1", "status": "completed"}]
        mock_repo.get_unread_alerts.return_value = [{"id": "alert-1", "is_read": False}]
        mock_repo.get_critical_sources.return_value = [
            {"id": "src-1", "source_name": "SMIC"},
        ]
        mock_repo.get_last_job_for_source.return_value = {"id": "job-last", "success": True}

        with patch(f"{QUERIES_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = queries.get_scraping_dashboard()

        assert result["stats"] == {"total_jobs": 100, "success_rate": 0.95}
        assert len(result["recent_jobs"]) == 1
        assert result["recent_jobs"][0]["id"] == "job-1"
        assert len(result["unread_alerts"]) == 1
        assert result["unread_alerts"][0]["id"] == "alert-1"
        assert len(result["critical_sources"]) == 1
        assert result["critical_sources"][0]["last_job"] == {"id": "job-last", "success": True}
        mock_repo.get_recent_jobs.assert_called_once_with(limit=10)
        mock_repo.get_unread_alerts.assert_called_once_with(limit=5)


class TestListSources:
    """Query list_sources."""

    def test_returns_sources_with_total_and_enrichment(self):
        mock_repo = MagicMock()
        mock_repo.list_sources.return_value = [
            {"id": "src-1", "source_key": "SMIC", "source_name": "Salaire minimum"},
        ]
        mock_repo.get_last_job_for_source.return_value = {"id": "job-1"}
        mock_repo.get_jobs_for_source_30d.return_value = ([{"success": True}, {"success": False}], 2)
        mock_repo.get_unresolved_alerts_count.return_value = 0

        with patch(f"{QUERIES_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = queries.list_sources(
                source_type="legal",
                is_critical=True,
                is_active=True,
            )

        assert result["total"] == 1
        assert len(result["sources"]) == 1
        assert result["sources"][0]["source_key"] == "SMIC"
        assert result["sources"][0]["last_job"] == {"id": "job-1"}
        assert result["sources"][0]["success_rate_30d"] == 50.0
        assert result["sources"][0]["unresolved_alerts_count"] == 0
        mock_repo.list_sources.assert_called_once_with(
            source_type="legal",
            is_critical=True,
            is_active=True,
        )


class TestGetSourceDetails:
    """Query get_source_details."""

    def test_returns_source_with_jobs_history_schedules_recent_alerts(self):
        mock_repo = MagicMock()
        mock_repo.get_source_by_id.return_value = {
            "id": "src-1",
            "source_key": "SMIC",
            "source_name": "Salaire minimum",
        }
        mock_repo.get_jobs_history_for_source.return_value = [{"id": "job-1"}]
        mock_repo.get_schedules_for_source.return_value = [{"id": "sched-1"}]
        mock_repo.get_recent_alerts_for_source.return_value = [{"id": "alert-1"}]

        with patch(f"{QUERIES_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = queries.get_source_details("src-1")

        assert result["id"] == "src-1"
        assert result["source_name"] == "Salaire minimum"
        assert result["jobs_history"] == [{"id": "job-1"}]
        assert result["schedules"] == [{"id": "sched-1"}]
        assert result["recent_alerts"] == [{"id": "alert-1"}]
        mock_repo.get_source_by_id.assert_called_once_with("src-1")
        mock_repo.get_jobs_history_for_source.assert_called_once_with("src-1", limit=20)
        mock_repo.get_schedules_for_source.assert_called_once_with("src-1")
        mock_repo.get_recent_alerts_for_source.assert_called_once_with("src-1", limit=10)

    def test_raises_when_source_not_found(self):
        mock_repo = MagicMock()
        mock_repo.get_source_by_id.return_value = None
        mock_repo.get_jobs_history_for_source.return_value = []
        mock_repo.get_schedules_for_source.return_value = []
        mock_repo.get_recent_alerts_for_source.return_value = []

        with patch(f"{QUERIES_MODULE}.ScrapingRepository", return_value=mock_repo):
            # infra_get_source_details_enriched retourne None quand get_source_by_id retourne None
            with pytest.raises(ValueError, match="Source non trouvée"):
                queries.get_source_details("src-unknown")


class TestListJobs:
    """Query list_jobs."""

    def test_returns_jobs_and_total(self):
        mock_repo = MagicMock()
        mock_repo.list_jobs.return_value = [
            {"id": "job-1", "status": "completed"},
            {"id": "job-2", "status": "running"},
        ]

        with patch(f"{QUERIES_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = queries.list_jobs(
                source_id="src-1",
                status="completed",
                success=True,
                limit=20,
                offset=0,
            )

        assert result["total"] == 2
        assert len(result["jobs"]) == 2
        assert result["jobs"][0]["id"] == "job-1"
        mock_repo.list_jobs.assert_called_once_with(
            source_id="src-1",
            status="completed",
            success=True,
            limit=20,
            offset=0,
        )


class TestGetJobDetails:
    """Query get_job_details."""

    def test_returns_job_when_found(self):
        mock_repo = MagicMock()
        job = {"id": "job-1", "source_id": "src-1", "status": "completed", "success": True}
        mock_repo.get_job.return_value = job

        with patch(f"{QUERIES_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = queries.get_job_details("job-1")

        assert result == job
        mock_repo.get_job.assert_called_once_with("job-1")

    def test_raises_when_job_not_found(self):
        mock_repo = MagicMock()
        mock_repo.get_job.return_value = None

        with patch(f"{QUERIES_MODULE}.ScrapingRepository", return_value=mock_repo):
            with pytest.raises(ValueError, match="Job non trouvé"):
                queries.get_job_details("job-unknown")


class TestGetJobLogs:
    """Query get_job_logs."""

    def test_returns_job_id_status_logs_success_error_completed_at(self):
        mock_repo = MagicMock()
        mock_repo.get_job_logs_fields.return_value = {
            "id": "job-1",
            "status": "completed",
            "execution_logs": ["log1", "log2"],
            "success": True,
            "error_message": None,
            "completed_at": "2025-01-15T12:00:00",
        }

        with patch(f"{QUERIES_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = queries.get_job_logs("job-1")

        assert result["job_id"] == "job-1"
        assert result["status"] == "completed"
        assert result["logs"] == ["log1", "log2"]
        assert result["success"] is True
        assert result["error_message"] is None
        assert result["completed_at"] == "2025-01-15T12:00:00"
        mock_repo.get_job_logs_fields.assert_called_once_with("job-1")

    def test_raises_when_job_not_found(self):
        mock_repo = MagicMock()
        mock_repo.get_job_logs_fields.return_value = None

        with patch(f"{QUERIES_MODULE}.ScrapingRepository", return_value=mock_repo):
            with pytest.raises(ValueError, match="Job non trouvé"):
                queries.get_job_logs("job-unknown")


class TestListSchedules:
    """Query list_schedules."""

    def test_returns_schedules_and_total(self):
        mock_repo = MagicMock()
        mock_repo.list_schedules.return_value = [
            {"id": "sched-1", "source_id": "src-1", "is_enabled": True},
        ]

        with patch(f"{QUERIES_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = queries.list_schedules(is_enabled=True)

        assert result["total"] == 1
        assert len(result["schedules"]) == 1
        assert result["schedules"][0]["id"] == "sched-1"
        mock_repo.list_schedules.assert_called_once_with(is_enabled=True)


class TestListAlerts:
    """Query list_alerts."""

    def test_returns_alerts_and_total(self):
        mock_repo = MagicMock()
        mock_repo.list_alerts.return_value = [
            {"id": "alert-1", "severity": "error", "is_read": False},
        ]

        with patch(f"{QUERIES_MODULE}.ScrapingRepository", return_value=mock_repo):
            result = queries.list_alerts(
                is_read=False,
                is_resolved=False,
                severity="error",
                limit=20,
            )

        assert result["total"] == 1
        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["id"] == "alert-1"
        mock_repo.list_alerts.assert_called_once_with(
            is_read=False,
            is_resolved=False,
            severity="error",
            limit=20,
        )
