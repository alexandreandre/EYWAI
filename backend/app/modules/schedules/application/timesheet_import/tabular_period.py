"""Détection de période et finalisation pour imports tabulaires (Excel/CSV)."""

from __future__ import annotations

import calendar as cal_mod
from dataclasses import dataclass
from datetime import date
from typing import List, Literal, Sequence

from app.modules.schedules.application.timesheet_import.structured_parser import (
    TabularDayRow,
    filter_tabular_rows_to_period,
)
from app.modules.schedules.application.timesheet_period import TimesheetPeriodDetection
from app.modules.schedules.schemas.ai import AiCalendarProposalResponse, RosterEmployee

PeriodImportMode = Literal["auto", "month", "year", "range"]


@dataclass
class ImportPeriodConfig:
    mode: PeriodImportMode = "month"
    year: int = 2026
    month: int = 6
    start_year: int | None = None
    start_month: int | None = None
    end_year: int | None = None
    end_month: int | None = None

    def explicit_bounds(self) -> tuple[date | None, date | None]:
        if self.mode == "month":
            last = cal_mod.monthrange(self.year, self.month)[1]
            return date(self.year, self.month, 1), date(self.year, self.month, last)
        if self.mode == "year":
            return date(self.year, 1, 1), date(self.year, 12, 31)
        if self.mode == "range":
            sy = self.start_year or self.year
            sm = self.start_month or 1
            ey = self.end_year or self.year
            em = self.end_month or 12
            last = cal_mod.monthrange(ey, em)[1]
            return date(sy, sm, 1), date(ey, em, last)
        return None, None


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
    from app.modules.schedules.application.timesheet_import.multi_month import row_date

    dates: List[date] = []
    for row in rows:
        d = row_date(row)
        if d:
            dates.append(d)
    return sorted(set(dates))


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


def apply_import_period_to_rows(
    rows: List[TabularDayRow],
    *,
    config: ImportPeriodConfig,
) -> TabularPeriodResolution:
    """Filtre les lignes selon le mode de période demandé (mois, année, plage, auto)."""
    from app.modules.schedules.application.timesheet_import.multi_month import (
        pick_anchor_month,
        row_date,
    )
    from app.modules.schedules.application.timesheet_period import (
        detect_timesheet_period_from_dates,
        resolve_effective_target_month,
    )

    if config.mode == "month":
        return apply_tabular_period_to_rows(
            rows,
            requested_year=config.year,
            requested_month=config.month,
        )

    row_dates = collect_dates_from_rows(rows)
    period_detection = detect_timesheet_period_from_dates(
        row_dates,
        target_year=config.year,
        target_month=config.month,
    )
    requested_year, requested_month = config.year, config.month
    month_auto_corrected = False
    correction_msg: str | None = None

    if config.mode == "auto":
        start = period_detection.start_date
        end = period_detection.end_date
        eff_year, eff_month, month_auto_corrected, correction_msg = (
            resolve_effective_target_month(
                period_detection, config.year, config.month
            )
        )
        if month_auto_corrected:
            requested_year, requested_month = eff_year, eff_month
    else:
        start, end = config.explicit_bounds()
        period_detection.start_date = start
        period_detection.end_date = end
        period_detection.warnings = [
            w
            for w in period_detection.warnings
            if "hors du mois affiché" not in w
        ]

    filtered: List[TabularDayRow] = []
    for row in rows:
        d = row_date(row)
        if not d:
            continue
        if start and end and (d < start or d > end):
            continue
        filtered.append(row)

    if not filtered:
        return TabularPeriodResolution(
            rows=[],
            year=config.year,
            month=config.month,
            period_detection=period_detection,
            month_auto_corrected=False,
            correction_msg=None,
            requested_year=config.year,
            requested_month=config.month,
        )

    anchor_y, anchor_m = pick_anchor_month(filtered)
    return TabularPeriodResolution(
        rows=filtered,
        year=anchor_y,
        month=anchor_m,
        period_detection=period_detection,
        month_auto_corrected=month_auto_corrected,
        correction_msg=correction_msg,
        requested_year=requested_year,
        requested_month=requested_month,
    )


def period_filter_empty_message(
    *,
    rows_before: Sequence[TabularDayRow],
    config: ImportPeriodConfig,
) -> str:
    from app.modules.schedules.application.timesheet_import.multi_month import (
        row_date,
        unique_months_in_rows,
    )

    if not rows_before:
        return (
            "Impossible de lire des lignes dans ce fichier. "
            "Vérifiez le format (Excel/CSV : une ligne par jour ou par pointage, "
            "colonnes date, matricule/nom, heures)."
        )

    months = unique_months_in_rows(rows_before)
    if months:
        first_y, first_m = months[0]
        last_y, last_m = months[-1]
        detected = (
            f"{first_m:02d}/{first_y}"
            if len(months) == 1
            else f"{first_m:02d}/{first_y} → {last_m:02d}/{last_y}"
        )
    else:
        detected = "dates illisibles"

    if config.mode == "year":
        target = str(config.year)
    elif config.mode == "range":
        sy = config.start_year or config.year
        sm = config.start_month or 1
        ey = config.end_year or config.year
        em = config.end_month or 12
        target = f"{sm:02d}/{sy} → {em:02d}/{ey}"
    elif config.mode == "month":
        target = f"{config.month:02d}/{config.year}"
    else:
        target = f"{config.month:02d}/{config.year} (indicatif)"

    return (
        f"Aucune ligne pour la période cible ({target}). "
        f"Période détectée dans le fichier : {detected}. "
        "Ajustez la période ou vérifiez les dates du fichier."
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
    "ImportPeriodConfig",
    "PeriodImportMode",
    "TabularPeriodResolution",
    "apply_import_period_to_rows",
    "apply_tabular_period_to_rows",
    "collect_dates_from_proposal",
    "collect_dates_from_rows",
    "period_filter_empty_message",
    "finalize_tabular_proposal",
]
