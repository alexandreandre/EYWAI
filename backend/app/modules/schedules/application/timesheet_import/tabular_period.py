"""Détection de période et finalisation pour imports tabulaires (Excel/CSV)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Sequence

from app.modules.schedules.application.timesheet_import.structured_parser import (
    TabularDayRow,
    filter_tabular_rows_to_period,
)
from app.modules.schedules.application.timesheet_period import TimesheetPeriodDetection
from app.modules.schedules.schemas.ai import AiCalendarProposalResponse, RosterEmployee


@dataclass
class TabularPeriodResolution:
    rows: List[TabularDayRow]
    year: int
    month: int
    period_detection: TimesheetPeriodDetection
    month_auto_corrected: bool
    correction_msg: str | None
    requested_year: int
    requested_month: int


def collect_dates_from_rows(rows: Sequence[TabularDayRow]) -> List[date]:
    return sorted({date(r.year, r.month, r.jour) for r in rows if r.jour})


def collect_dates_from_proposal(proposal: AiCalendarProposalResponse) -> List[date]:
    dates: set[date] = set()
    for emp in proposal.employees:
        for day in emp.days:
            if day.jour:
                dates.add(date(proposal.year, proposal.month, day.jour))
    return sorted(dates)


def apply_tabular_period_to_rows(
    rows: List[TabularDayRow],
    *,
    requested_year: int,
    requested_month: int,
) -> TabularPeriodResolution:
    """Filtre les lignes selon la période détectée."""
    from app.modules.schedules.application.timesheet_period import (
        align_period_warnings,
        detect_timesheet_period_from_dates,
        resolve_effective_target_month,
    )

    row_dates = collect_dates_from_rows(rows)
    period_detection = detect_timesheet_period_from_dates(
        row_dates,
        target_year=requested_year,
        target_month=requested_month,
    )
    eff_year, eff_month, month_auto_corrected, correction_msg = (
        resolve_effective_target_month(
            period_detection, requested_year, requested_month
        )
    )
    year, month = requested_year, requested_month
    if month_auto_corrected:
        year, month = eff_year, eff_month
        align_period_warnings(period_detection, year, month)

    filtered = filter_tabular_rows_to_period(
        rows,
        start=period_detection.start_date,
        end=period_detection.end_date,
        eff_year=year,
        eff_month=month,
    )
    return TabularPeriodResolution(
        rows=filtered,
        year=year,
        month=month,
        period_detection=period_detection,
        month_auto_corrected=month_auto_corrected,
        correction_msg=correction_msg,
        requested_year=requested_year,
        requested_month=requested_month,
    )


def finalize_tabular_proposal(
    proposal: AiCalendarProposalResponse,
    *,
    dates: List[date],
    requested_year: int,
    requested_month: int,
    roster: List[RosterEmployee],
    company_id: str | None,
    parser_key: str,
    parse_confidence: float | None,
    extraction_warnings: List[str] | None,
) -> AiCalendarProposalResponse:
    from app.modules.schedules.application.ai_fill import _finalize_timesheet_proposal
    from app.modules.schedules.application.timesheet_period import (
        align_period_warnings,
        detect_timesheet_period_from_dates,
        resolve_effective_target_month,
    )

    period_detection = detect_timesheet_period_from_dates(
        dates,
        target_year=requested_year,
        target_month=requested_month,
    )
    eff_year, eff_month, month_auto_corrected, correction_msg = (
        resolve_effective_target_month(
            period_detection, requested_year, requested_month
        )
    )
    year, month = requested_year, requested_month
    if month_auto_corrected:
        year, month = eff_year, eff_month
        align_period_warnings(period_detection, year, month)
        proposal = proposal.model_copy(update={"year": year, "month": month})

    return _finalize_timesheet_proposal(
        proposal,
        roster=roster,
        company_id=company_id,
        period_detection=period_detection,
        month_auto_corrected=month_auto_corrected,
        requested_year=requested_year if month_auto_corrected else None,
        requested_month=requested_month if month_auto_corrected else None,
        month_correction_message=correction_msg,
        detected_format=parser_key,
        parse_confidence=parse_confidence,
        extraction_method="structured",
        extraction_warnings=extraction_warnings or [],
    )


__all__ = [
    "TabularPeriodResolution",
    "apply_tabular_period_to_rows",
    "collect_dates_from_proposal",
    "collect_dates_from_rows",
    "finalize_tabular_proposal",
]
