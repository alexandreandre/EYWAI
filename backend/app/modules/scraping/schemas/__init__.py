# Schémas scraping : requêtes et réponses (définitions canoniques).
# Compatibilité : le routeur legacy peut importer ainsi lors du basculement :
#   from app.modules.scraping.schemas import (
#       ScraperExecutionRequest, ScheduleCreate, ScheduleUpdate, AlertResolve,
#   )
from app.modules.scraping.schemas.requests import (
    AlertResolve,
    ScheduleCreate,
    ScheduleUpdate,
    ScraperExecutionRequest,
)
from app.modules.scraping.schemas.responses import (
    AlertsListResponse,
    DeleteScheduleResponse,
    ExecuteScraperResponse,
    JobExecutionResultResponse,
    JobLogsResponse,
    JobsListResponse,
    ScheduleMutationResponse,
    SchedulesListResponse,
    ScrapingDashboardResponse,
    SourcesListResponse,
    SuccessResponse,
)

__all__ = [
    # Requêtes
    "ScraperExecutionRequest",
    "ScheduleCreate",
    "ScheduleUpdate",
    "AlertResolve",
    # Réponses
    "ScrapingDashboardResponse",
    "SourcesListResponse",
    "ExecuteScraperResponse",
    "JobExecutionResultResponse",
    "JobsListResponse",
    "JobLogsResponse",
    "SchedulesListResponse",
    "ScheduleMutationResponse",
    "DeleteScheduleResponse",
    "AlertsListResponse",
    "SuccessResponse",
]
