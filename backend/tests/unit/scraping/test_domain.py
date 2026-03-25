"""
Tests du domain scraping : entités, value objects, règles, enums.

Sans DB, sans HTTP. Comportement pur du domaine.
"""

from datetime import datetime

import pytest

from app.modules.scraping.domain.entities import (
    ScrapingSource,
    ScrapingJob,
    ScrapingSchedule,
    ScrapingAlert,
)
from app.modules.scraping.domain.value_objects import SourceKey, ScraperScriptType
from app.modules.scraping.domain.rules import (
    can_execute_source,
    require_source_for_execution,
    validate_schedule_create,
    validate_schedule_update,
)
from app.modules.scraping.domain.enums import (
    JobStatus,
    JobType,
    ScheduleType,
    AlertType,
    AlertSeverity,
)


# --- Entités ---


class TestScrapingSource:
    """Entité ScrapingSource."""

    def test_instanciation_required_fields(self):
        s = ScrapingSource(
            id="src-1",
            source_key="SMIC",
            source_name="Salaire minimum",
            source_type="legal",
            is_active=True,
            is_critical=True,
        )
        assert s.id == "src-1"
        assert s.source_key == "SMIC"
        assert s.source_name == "Salaire minimum"
        assert s.source_type == "legal"
        assert s.is_active is True
        assert s.is_critical is True
        assert s.orchestrator_path is None
        assert s.available_scrapers is None
        assert s.raw is None

    def test_instanciation_with_optionals(self):
        s = ScrapingSource(
            id="src-2",
            source_key="PSS",
            source_name="Plafond Sécurité Sociale",
            source_type="legal",
            is_active=False,
            is_critical=False,
            orchestrator_path="scraping/pss/main.py",
            available_scrapers=["scraper_a.py", "scraper_b.py"],
            raw={"extra": "data"},
        )
        assert s.orchestrator_path == "scraping/pss/main.py"
        assert s.available_scrapers == ["scraper_a.py", "scraper_b.py"]
        assert s.raw == {"extra": "data"}


class TestScrapingJob:
    """Entité ScrapingJob."""

    def test_instanciation_required_fields(self):
        j = ScrapingJob(
            id="job-1",
            source_id="src-1",
            job_type="manual",
            status="running",
        )
        assert j.id == "job-1"
        assert j.source_id == "src-1"
        assert j.job_type == "manual"
        assert j.status == "running"
        assert j.success is None
        assert j.started_at is None
        assert j.completed_at is None
        assert j.duration_ms is None
        assert j.raw is None

    def test_instanciation_with_optionals(self):
        started = datetime.now()
        completed = datetime.now()
        j = ScrapingJob(
            id="job-2",
            source_id="src-1",
            job_type="scheduled",
            status="completed",
            success=True,
            started_at=started,
            completed_at=completed,
            duration_ms=1500,
            raw={"logs_count": 10},
        )
        assert j.success is True
        assert j.started_at == started
        assert j.completed_at == completed
        assert j.duration_ms == 1500
        assert j.raw == {"logs_count": 10}


class TestScrapingSchedule:
    """Entité ScrapingSchedule."""

    def test_instanciation(self):
        s = ScrapingSchedule(
            id="sched-1",
            source_id="src-1",
            schedule_type="cron",
            is_enabled=True,
        )
        assert s.id == "sched-1"
        assert s.source_id == "src-1"
        assert s.schedule_type == "cron"
        assert s.is_enabled is True
        assert s.raw is None

    def test_instanciation_with_raw(self):
        s = ScrapingSchedule(
            id="sched-2",
            source_id="src-2",
            schedule_type="interval",
            is_enabled=False,
            raw={"interval_days": 7},
        )
        assert s.raw == {"interval_days": 7}


class TestScrapingAlert:
    """Entité ScrapingAlert."""

    def test_instanciation_required_fields(self):
        a = ScrapingAlert(
            id="alert-1",
            alert_type="failure",
            severity="error",
        )
        assert a.id == "alert-1"
        assert a.alert_type == "failure"
        assert a.severity == "error"
        assert a.job_id is None
        assert a.source_id is None
        assert a.is_read is False
        assert a.is_resolved is False
        assert a.raw is None

    def test_instanciation_with_optionals(self):
        a = ScrapingAlert(
            id="alert-2",
            alert_type="discrepancy",
            severity="warning",
            job_id="job-1",
            source_id="src-1",
            is_read=True,
            is_resolved=True,
            raw={"details": "x"},
        )
        assert a.job_id == "job-1"
        assert a.source_id == "src-1"
        assert a.is_read is True
        assert a.is_resolved is True
        assert a.raw == {"details": "x"}


# --- Value objects ---


class TestSourceKey:
    """Value object SourceKey."""

    def test_instanciation_frozen(self):
        sk = SourceKey(value="AGIRC-ARRCO")
        assert sk.value == "AGIRC-ARRCO"
        with pytest.raises(Exception):  # frozen dataclass
            sk.value = "OTHER"

    def test_equality_by_value(self):
        assert SourceKey(value="SMIC") == SourceKey(value="SMIC")
        assert SourceKey(value="SMIC") != SourceKey(value="PSS")


class TestScraperScriptType:
    """Value object ScraperScriptType."""

    def test_instanciation(self):
        st = ScraperScriptType(value="orchestrator")
        assert st.value == "orchestrator"
        st2 = ScraperScriptType(value="single_scraper")
        assert st2.value == "single_scraper"


# --- Règles ---


class TestCanExecuteSource:
    """Règle can_execute_source."""

    def test_returns_true_when_is_active_true(self):
        assert can_execute_source({"is_active": True}) is True

    def test_returns_false_when_is_active_false(self):
        assert can_execute_source({"is_active": False}) is False

    def test_returns_false_when_is_active_absent(self):
        assert can_execute_source({}) is False

    def test_returns_false_when_is_active_none(self):
        assert can_execute_source({"is_active": None}) is False


class TestRequireSourceForExecution:
    """Règle require_source_for_execution."""

    def test_does_not_raise_when_source_active(self):
        require_source_for_execution({"is_active": True})

    def test_raises_when_source_none(self):
        with pytest.raises(ValueError, match="Source non trouvée"):
            require_source_for_execution(None)

    def test_raises_when_source_disabled(self):
        with pytest.raises(ValueError, match="Cette source est désactivée"):
            require_source_for_execution({"is_active": False})

    def test_raises_when_source_no_is_active_key(self):
        with pytest.raises(ValueError, match="Cette source est désactivée"):
            require_source_for_execution({"source_key": "X"})


class TestValidateScheduleCreate:
    """Règle validate_schedule_create."""

    def test_does_not_raise_when_cron_with_expression(self):
        validate_schedule_create("cron", "0 0 * * *", None)

    def test_raises_when_cron_without_expression(self):
        with pytest.raises(ValueError, match="Expression cron requise"):
            validate_schedule_create("cron", None, None)
        with pytest.raises(ValueError, match="Expression cron requise"):
            validate_schedule_create("cron", "", None)

    def test_does_not_raise_when_interval_with_days(self):
        validate_schedule_create("interval", None, 7)

    def test_raises_when_interval_without_days(self):
        with pytest.raises(ValueError, match="Intervalle en jours requis"):
            validate_schedule_create("interval", None, None)
        with pytest.raises(ValueError, match="Intervalle en jours requis"):
            validate_schedule_create("interval", None, 0)


class TestValidateScheduleUpdate:
    """Règle validate_schedule_update."""

    def test_does_not_raise_when_data_non_empty(self):
        validate_schedule_update({"is_enabled": False})
        validate_schedule_update({"cron_expression": "0 0 * * *"})

    def test_raises_when_data_empty(self):
        with pytest.raises(ValueError, match="Aucune donnée à mettre à jour"):
            validate_schedule_update({})


# --- Enums ---


class TestJobStatus:
    """Enum JobStatus."""

    def test_values(self):
        assert JobStatus.PENDING == "pending"
        assert JobStatus.RUNNING == "running"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.CANCELLED == "cancelled"


class TestJobType:
    """Enum JobType."""

    def test_values(self):
        assert JobType.MANUAL == "manual"
        assert JobType.SCHEDULED == "scheduled"
        assert JobType.TEST == "test"


class TestScheduleType:
    """Enum ScheduleType."""

    def test_values(self):
        assert ScheduleType.CRON == "cron"
        assert ScheduleType.INTERVAL == "interval"


class TestAlertType:
    """Enum AlertType."""

    def test_values(self):
        assert AlertType.FAILURE == "failure"
        assert AlertType.DISCREPANCY == "discrepancy"
        assert AlertType.CRITICAL_CHANGE == "critical_change"
        assert AlertType.SUCCESS == "success"


class TestAlertSeverity:
    """Enum AlertSeverity."""

    def test_values(self):
        assert AlertSeverity.INFO == "info"
        assert AlertSeverity.WARNING == "warning"
        assert AlertSeverity.ERROR == "error"
        assert AlertSeverity.CRITICAL == "critical"
