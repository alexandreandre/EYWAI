# Domain layer for scraping (règles pures, interfaces ; pas de FastAPI).
from app.modules.scraping.domain.entities import (
    ScrapingAlert,
    ScrapingJob,
    ScrapingSchedule,
    ScrapingSource,
)
from app.modules.scraping.domain.enums import (
    AlertSeverity,
    AlertType,
    JobStatus,
    JobType,
    ScheduleType,
)
from app.modules.scraping.domain.rules import (
    can_execute_source,
    require_source_for_execution,
    validate_schedule_create,
    validate_schedule_update,
)
from app.modules.scraping.domain.value_objects import ScraperScriptType, SourceKey

__all__ = [
    "ScrapingSource",
    "ScrapingJob",
    "ScrapingSchedule",
    "ScrapingAlert",
    "JobStatus",
    "JobType",
    "ScheduleType",
    "AlertType",
    "AlertSeverity",
    "SourceKey",
    "ScraperScriptType",
    "can_execute_source",
    "require_source_for_execution",
    "validate_schedule_create",
    "validate_schedule_update",
]
