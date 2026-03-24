"""
Enums du domaine scraping.

Alignés sur les tables scraping_sources, scraping_jobs, scraping_schedules, scraping_alerts.
"""
from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """Statut d'un job de scraping."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(StrEnum):
    """Type de déclenchement du job."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    TEST = "test"


class ScheduleType(StrEnum):
    """Type de planification."""

    CRON = "cron"
    INTERVAL = "interval"


class AlertType(StrEnum):
    """Type d'alerte."""

    FAILURE = "failure"
    DISCREPANCY = "discrepancy"
    CRITICAL_CHANGE = "critical_change"
    SUCCESS = "success"


class AlertSeverity(StrEnum):
    """Sévérité d'une alerte."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
