"""
Règles métier suivi contingent annuel d'heures supplémentaires.

Logique pure : HS structurelles, HS payées (conjoncturelles), pauses, RCR, plafonds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.modules.repos_compensateur.domain.rules import (
    extraire_heures_hs_conjoncturelles_du_bulletin,
)

LEGAL_COR_CONTINGENT_DEFAULT = 220.0
MANAGEMENT_CONTINGENT_DEFAULT = 360.0
HOURS_PER_REST_DAY_DEFAULT = 7.0
PAUSE_HS_DEDUCTION_PER_WORKDAY_DEFAULT = 0.058765
WORKDAYS_PER_YEAR_FOR_PAUSE_DEFAULT = 260


@dataclass(frozen=True)
class ContingentSettings:
    legal_cor_contingent_hours: float = LEGAL_COR_CONTINGENT_DEFAULT
    management_contingent_hours: float | None = MANAGEMENT_CONTINGENT_DEFAULT
    hours_per_rest_day: float = HOURS_PER_REST_DAY_DEFAULT
    include_structural_hours: bool = True
    pause_deduction_enabled: bool = False
    pause_hs_deduction_per_workday: float = PAUSE_HS_DEDUCTION_PER_WORKDAY_DEFAULT
    workdays_per_year_for_pause: int = WORKDAYS_PER_YEAR_FOR_PAUSE_DEFAULT

    @property
    def effective_management_contingent(self) -> float:
        if self.management_contingent_hours is not None:
            return float(self.management_contingent_hours)
        return float(self.legal_cor_contingent_hours)


@dataclass(frozen=True)
class ContingentEmployeeInput:
    employee_id: str
    first_name: str
    last_name: str
    hire_date: date | None
    duree_hebdomadaire: float | None
    opening_balance_hours: float = 0.0
    validated_repos_requests: list[dict] | None = None
    bulletins_par_mois: dict[int, dict[str, Any]] | None = None


@dataclass(frozen=True)
class ContingentBreakdown:
    structural_hours: float
    paid_hours: float
    pause_deduction: float
    manual_adjustment: float
    rcr_hours: float
    consumed_hours: float
    total_for_ceiling: float
    margin_hours: float
    legal_cor_excess: float
    management_contingent: float
    legal_cor_contingent: float
    usage_percent: float
    status: str


@dataclass(frozen=True)
class ContingentMonthlyRow:
    month: int
    paid_hours: float
    cumulative_consumed: float
    cumulative_total: float


def _year_bounds(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def _period_start(hire_date: date | None, year: int) -> date:
    year_start, _ = _year_bounds(year)
    if hire_date is None:
        return year_start
    return max(year_start, hire_date)


def compute_weeks_worked(
    hire_date: date | None,
    year: int,
    reference_date: date,
) -> float:
    """Semaines travaillées entre début de période (entrée ou 1er jan) et date de référence."""
    period_start = _period_start(hire_date, year)
    if reference_date < period_start:
        return 0.0
    days = (reference_date - period_start).days + 1
    return round(max(0.0, days / 7.0), 2)


def compute_workdays_in_period(
    hire_date: date | None,
    year: int,
    reference_date: date,
    workdays_per_year: int,
) -> float:
    """Jours ouvrés proratisés sur la période (base annuelle paramétrable)."""
    period_start = _period_start(hire_date, year)
    year_start, year_end = _year_bounds(year)
    if reference_date < period_start:
        return 0.0
    effective_end = min(reference_date, year_end)
    days_in_period = (effective_end - period_start).days + 1
    total_year_days = (year_end - year_start).days + 1
    return round(workdays_per_year * (days_in_period / total_year_days), 2)


def compute_structural_hours(
    duree_hebdomadaire: float | None,
    weeks_worked: float,
    *,
    include: bool,
) -> float:
    if not include or duree_hebdomadaire is None:
        return 0.0
    delta = max(0.0, float(duree_hebdomadaire) - 35.0)
    return round(delta * weeks_worked, 2)


def sum_paid_hours_until_month(
    bulletins_par_mois: dict[int, dict[str, Any]] | None,
    until_month: int,
) -> float:
    if not bulletins_par_mois:
        return 0.0
    total = 0.0
    for month in range(1, min(until_month, 12) + 1):
        payslip_data = bulletins_par_mois.get(month)
        total += extraire_heures_hs_conjoncturelles_du_bulletin(payslip_data)
    return round(total, 2)


def compute_pause_deduction(
    settings: ContingentSettings,
    hire_date: date | None,
    year: int,
    reference_date: date,
) -> float:
    if not settings.pause_deduction_enabled:
        return 0.0
    workdays = compute_workdays_in_period(
        hire_date,
        year,
        reference_date,
        settings.workdays_per_year_for_pause,
    )
    return round(workdays * settings.pause_hs_deduction_per_workday, 2)


def compute_rcr_hours(
    validated_requests: list[dict] | None,
    reference_date: date,
    year: int,
    hours_per_rest_day: float,
) -> float:
    if not validated_requests:
        return 0.0
    year_start, _ = _year_bounds(year)
    days = 0.0
    for req in validated_requests:
        if req.get("type") != "repos_compensateur":
            continue
        if req.get("status") != "validated":
            continue
        for day in req.get("selected_days") or []:
            parsed = _parse_day(day)
            if parsed is None:
                continue
            if parsed > reference_date or parsed < year_start:
                continue
            days += 1.0
    return round(days * hours_per_rest_day, 2)


def _parse_day(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _contingent_status(usage_percent: float, legal_cor_excess: float) -> str:
    if legal_cor_excess > 0:
        return "cor_exceeded"
    if usage_percent >= 100:
        return "management_exceeded"
    if usage_percent >= 80:
        return "near_limit"
    return "ok"


def compute_contingent_breakdown(
    employee: ContingentEmployeeInput,
    settings: ContingentSettings,
    year: int,
    reference_date: date,
) -> ContingentBreakdown:
    """Calcule le détail contingent pour un salarié à une date de référence."""
    ref_month = reference_date.month if reference_date.year == year else 12
    if reference_date.year < year:
        ref_month = 0
    elif reference_date.year > year:
        ref_month = 12

    weeks = compute_weeks_worked(employee.hire_date, year, reference_date)
    structural = compute_structural_hours(
        employee.duree_hebdomadaire,
        weeks,
        include=settings.include_structural_hours,
    )
    paid = sum_paid_hours_until_month(employee.bulletins_par_mois, ref_month)
    pause = compute_pause_deduction(
        settings, employee.hire_date, year, reference_date
    )
    manual = round(float(employee.opening_balance_hours or 0), 2)
    rcr = compute_rcr_hours(
        employee.validated_repos_requests,
        reference_date,
        year,
        settings.hours_per_rest_day,
    )

    consumed = round(structural + paid - pause + manual, 2)
    total = round(consumed + rcr, 2)
    management = settings.effective_management_contingent
    margin = round(management - total, 2)
    legal_excess = round(max(0.0, consumed - settings.legal_cor_contingent_hours), 2)
    usage = round((total / management * 100) if management > 0 else 0.0, 1)

    return ContingentBreakdown(
        structural_hours=structural,
        paid_hours=paid,
        pause_deduction=pause,
        manual_adjustment=manual,
        rcr_hours=rcr,
        consumed_hours=consumed,
        total_for_ceiling=total,
        margin_hours=margin,
        legal_cor_excess=legal_excess,
        management_contingent=management,
        legal_cor_contingent=settings.legal_cor_contingent_hours,
        usage_percent=usage,
        status=_contingent_status(usage, legal_excess),
    )


def compute_monthly_breakdown(
    employee: ContingentEmployeeInput,
    settings: ContingentSettings,
    year: int,
    reference_date: date,
) -> list[ContingentMonthlyRow]:
    """Détail mensuel cumulé jusqu'à la date de référence."""
    rows: list[ContingentMonthlyRow] = []
    max_month = reference_date.month if reference_date.year == year else (
        12 if reference_date.year > year else 0
    )
    for month in range(1, max_month + 1):
        month_ref = date(year, month, 28)
        if month == reference_date.month and reference_date.year == year:
            month_ref = reference_date
        elif month < max_month:
            import calendar

            last_day = calendar.monthrange(year, month)[1]
            month_ref = date(year, month, last_day)

        breakdown = compute_contingent_breakdown(
            employee, settings, year, month_ref
        )
        paid_mois = extraire_heures_hs_conjoncturelles_du_bulletin(
            (employee.bulletins_par_mois or {}).get(month)
        )
        rows.append(
            ContingentMonthlyRow(
                month=month,
                paid_hours=round(paid_mois, 2),
                cumulative_consumed=breakdown.consumed_hours,
                cumulative_total=breakdown.total_for_ceiling,
            )
        )
    return rows


def aggregate_contingent_kpis(rows: list[ContingentBreakdown]) -> dict[str, int]:
    return {
        "total_employees": len(rows),
        "near_limit_count": sum(1 for r in rows if r.status == "near_limit"),
        "management_exceeded_count": sum(
            1 for r in rows if r.status == "management_exceeded"
        ),
        "cor_exceeded_count": sum(1 for r in rows if r.status == "cor_exceeded"),
    }


__all__ = [
    "ContingentBreakdown",
    "ContingentEmployeeInput",
    "ContingentMonthlyRow",
    "ContingentSettings",
    "aggregate_contingent_kpis",
    "compute_contingent_breakdown",
    "compute_monthly_breakdown",
    "compute_pause_deduction",
    "compute_rcr_hours",
    "compute_structural_hours",
    "compute_weeks_worked",
    "sum_paid_hours_until_month",
]
