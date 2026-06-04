# Schemas for schedules — ré-exports pour préparation migration.
from .ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
    ParseInstructionRequest,
    RosterEmployee,
)
from .requests import (
    ActualHoursEntry,
    ActualHoursRequest,
    ApplyModelRequest,
    DayConfigModel,
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
    "ParseInstructionRequest",
    "PlannedCalendarEntry",
    "PlannedCalendarRequest",
    "RosterEmployee",
    "WeekConfigModel",
]
