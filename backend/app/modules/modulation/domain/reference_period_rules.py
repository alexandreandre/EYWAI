"""Règles périodes de référence horaire — domaine pur."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


@dataclass(frozen=True)
class WorkTimePeriod:
    id: str
    company_id: str
    label: str
    start_date: date
    end_date: date | None
    daily_reference_hours: float | None
    weekly_reference_hours: float | None
    affects_payroll: bool
    affects_planning: bool
    default_week_template_id: str | None
    is_active: bool


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def period_from_row(row: dict[str, Any]) -> WorkTimePeriod:
    return WorkTimePeriod(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        label=str(row.get("label") or ""),
        start_date=_parse_date(row["start_date"]) or date.today(),
        end_date=_parse_date(row.get("end_date")),
        daily_reference_hours=(
            float(row["daily_reference_hours"])
            if row.get("daily_reference_hours") is not None
            else None
        ),
        weekly_reference_hours=(
            float(row["weekly_reference_hours"])
            if row.get("weekly_reference_hours") is not None
            else None
        ),
        affects_payroll=bool(row.get("affects_payroll", True)),
        affects_planning=bool(row.get("affects_planning", False)),
        default_week_template_id=(
            str(row["default_week_template_id"])
            if row.get("default_week_template_id")
            else None
        ),
        is_active=bool(row.get("is_active", True)),
    )


def period_covers_date(period: WorkTimePeriod, d: date) -> bool:
    if not period.is_active:
        return False
    if d < period.start_date:
        return False
    if period.end_date is not None and d > period.end_date:
        return False
    return True


def period_weekly_hours(period: WorkTimePeriod) -> float | None:
    if period.weekly_reference_hours is not None:
        return float(period.weekly_reference_hours)
    if period.daily_reference_hours is not None:
        return round(float(period.daily_reference_hours) * 5, 2)
    return None


def active_period_for_date(
    periods: list[WorkTimePeriod], d: date, *, affects_payroll: bool = True
) -> WorkTimePeriod | None:
    candidates = [
        p
        for p in periods
        if period_covers_date(p, d)
        and (not affects_payroll or p.affects_payroll)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.start_date)


def resolve_effective_weekly_hours_for_week(
    base_weekly_hours: float,
    week_monday: date,
    modulation_map: dict[tuple[int, int], float] | None,
    reference_periods: list[WorkTimePeriod],
) -> float:
    """Priorité : période réduite active > modulation > contrat."""
    period = active_period_for_date(reference_periods, week_monday)
    if period:
        ref = period_weekly_hours(period)
        if ref is not None:
            return ref
    iso_key = week_monday.isocalendar()[:2]
    if modulation_map and iso_key in modulation_map:
        return float(modulation_map[iso_key])
    return float(base_weekly_hours)


def build_effective_weekly_hours_map(
    year: int,
    base_weekly_hours: float,
    modulation_map: dict[tuple[int, int], float] | None,
    reference_periods: list[WorkTimePeriod],
) -> dict[tuple[int, int], float]:
    out: dict[tuple[int, int], float] = {}
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        monday = d - timedelta(days=d.weekday())
        key = monday.isocalendar()[:2]
        if key not in out:
            out[key] = resolve_effective_weekly_hours_for_week(
                base_weekly_hours, monday, modulation_map, reference_periods
            )
        d += timedelta(days=7)
    return out


def validate_no_overlap(
    periods: list[WorkTimePeriod],
    candidate: WorkTimePeriod,
    *,
    exclude_id: str | None = None,
) -> None:
    for p in periods:
        if exclude_id and p.id == exclude_id:
            continue
        if not p.is_active or not candidate.is_active:
            continue
        c_end = candidate.end_date or date(9999, 12, 31)
        p_end = p.end_date or date(9999, 12, 31)
        if candidate.start_date <= p_end and c_end >= p.start_date:
            raise ValueError(
                f"Chevauchement avec la période « {p.label} » ({p.start_date} – {p.end_date or '…'})."
            )
