# Schemas for schedules — ré-exports pour préparation migration.
from .ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
    ParseInstructionRequest,
    RosterEmployee,
    TimesheetExtractJobResponse,
    TimesheetExtractProgress,
    TimesheetExtractStartResponse,
)
from .requests import (
    ActualHoursEntry,
    ActualHoursRequest,
    ApplyModelRequest,
    DayConfigModel,
    ImportBadgeuseBulkRequest,
    ImportBadgeuseEmployeeRequest,
    PlannedCalendarEntry,
    PlannedCalendarRequest,
    WeekConfigModel,
)
from .responses import (
    CalendarData,
    CalendarResponse,
    CumulsPeriode,
    CumulsResponse,
    CumulsValues,
)

__all__ = [
    "ActualHoursEntry",
    "ActualHoursRequest",
    "AiCalendarProposalResponse",
    "AiDayEntry",
    "AiEmployeeProposal",
    "ApplyModelRequest",
    "CalendarData",
    "CalendarResponse",
    "CumulsPeriode",
    "CumulsResponse",
    "CumulsValues",
    "DayConfigModel",
    "ImportBadgeuseBulkRequest",
    "ImportBadgeuseEmployeeRequest",
    "ParseInstructionRequest",
    "PlannedCalendarEntry",
    "PlannedCalendarRequest",
    "RosterEmployee",
    "TimesheetExtractJobResponse",
    "TimesheetExtractProgress",
    "TimesheetExtractStartResponse",
    "WeekConfigModel",
]
