# Schémas du module absences (source : requests.py, responses.py).
# schemas/absence.py en réexporte pour compatibilité legacy (api/routers/absences.py, expenses.py).

from app.modules.absences.schemas.requests import (
    AbsenceRequestCreate,
    AbsenceRequestStatusUpdate,
    AbsenceStatus,
    AbsenceType,
)
from app.modules.absences.schemas.responses import (
    AbsenceBalance,
    AbsenceBalancesResponse,
    AbsencePageData,
    AbsenceRequest,
    AbsenceRequestWithEmployee,
    CalendarDay,
    EvenementFamilialEvent,
    EvenementFamilialQuotaResponse,
    MonthlyCalendarResponse,
    SimpleEmployee,
    SimpleEmployeeWithBalances,
    SignedUploadURL,
)

__all__ = [
    "AbsenceRequestCreate",
    "AbsenceRequestStatusUpdate",
    "AbsenceStatus",
    "AbsenceType",
    "AbsenceBalance",
    "AbsenceBalancesResponse",
    "AbsencePageData",
    "AbsenceRequest",
    "AbsenceRequestWithEmployee",
    "CalendarDay",
    "EvenementFamilialEvent",
    "EvenementFamilialQuotaResponse",
    "MonthlyCalendarResponse",
    "SimpleEmployee",
    "SimpleEmployeeWithBalances",
    "SignedUploadURL",
]
