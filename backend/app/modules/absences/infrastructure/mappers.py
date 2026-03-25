"""
Mappers : ligne DB ↔ entités / DTOs (optionnel).

- absence_requests row → AbsenceRequestEntity / AbsenceRequestDto
- soldes bruts → AbsenceBalanceDto
- planned_calendar entries → CalendarDayDto
"""
from typing import Any, Dict

from app.modules.absences.application.dto import (
    AbsenceBalanceDto,
    AbsenceRequestDto,
    CalendarDayDto,
)
from app.modules.absences.domain.entities import AbsenceRequestEntity


def row_to_absence_entity(row: Dict[str, Any]) -> AbsenceRequestEntity:
    """Ligne absence_requests → AbsenceRequestEntity."""
    raise NotImplementedError("À implémenter avec conversion selected_days, dates")


def row_to_absence_dto(row: Dict[str, Any]) -> AbsenceRequestDto:
    """Ligne absence_requests → AbsenceRequestDto."""
    raise NotImplementedError("À implémenter")


def to_balance_dto(type_label: str, acquired: float, taken: float, remaining: Any) -> AbsenceBalanceDto:
    """Construit AbsenceBalanceDto (libellés identiques : Congés Payés, RTT, etc.)."""
    return AbsenceBalanceDto(type=type_label, acquired=acquired, taken=taken, remaining=remaining)


def calendar_entry_to_dto(entry: Dict[str, Any]) -> CalendarDayDto:
    """Entrée calendrier_prevu → CalendarDayDto."""
    return CalendarDayDto(
        jour=entry.get("jour", 0),
        type=entry.get("type", "travail"),
        heures_prevues=float(entry.get("heures_prevues") or 0),
    )
