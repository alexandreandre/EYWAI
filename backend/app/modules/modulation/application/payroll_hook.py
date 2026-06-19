"""Intégration modulation — calcul paie et compteurs salariés."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.core.database import supabase
from app.modules.modulation.application.hour_account_queries import (
    sync_account_balance_cache,
)
from app.modules.modulation.domain.entities import ModulationSettings
from app.modules.modulation.domain.hour_account_rules import (
    reduce_hs_in_calendar,
    split_hs_for_period,
    sum_hs_from_payroll_events,
)
from app.modules.modulation.domain.rules import (
    compute_balance_hours,
    resolve_modulation_tier,
    theoretical_weekly_hours,
)
from app.modules.modulation.infrastructure import repository as repo


@dataclass(frozen=True)
class ModulationPayrollResult:
    hs_realisees: float = 0.0
    hs_credited: float = 0.0
    hs_paid: float = 0.0
    movement_ids: tuple[str, ...] = ()


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build_modulation_weekly_hours_map(
    settings: ModulationSettings,
    year: int,
) -> dict[tuple[int, int], float]:
    """Carte (année ISO, semaine ISO) → heures théoriques modulation."""
    if not settings.enabled:
        return {}
    out: dict[tuple[int, int], float] = {}
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        monday = _monday_of_week(d)
        iso = monday.isocalendar()
        key = (iso[0], iso[1])
        if key not in out:
            tier = resolve_modulation_tier(monday, settings)
            out[key] = theoretical_weekly_hours(tier, settings)
        d += timedelta(days=7)
    return out


def _sum_hours_from_actual(actual: dict[str, Any] | None) -> float:
    if not actual or not isinstance(actual, dict):
        return 0.0
    total = 0.0
    for day_data in actual.values():
        if isinstance(day_data, dict):
            total += float(day_data.get("heures_faites") or 0)
        elif isinstance(day_data, (int, float)):
            total += float(day_data)
    return round(total, 2)


def _theoretical_hours_for_year(settings: ModulationSettings, year: int) -> float:
    weekly_map = build_modulation_weekly_hours_map(settings, year)
    return round(sum(weekly_map.values()), 2)


def sync_employee_modulation_counter(
    company_id: str,
    employee_id: str,
    year: int,
    *,
    settings: ModulationSettings | None = None,
    period_credited_hours: float | None = None,
    period_paid_hours: float | None = None,
) -> None:
    """Met à jour le compteur annuel théorique / réalisé / solde + cache compte."""
    settings = settings or repo.get_modulation_settings(company_id)
    if not settings.enabled and not settings.hour_account_enabled:
        return

    actual_total = 0.0
    theoretical = 0.0
    balance = 0.0
    if settings.enabled:
        resp = (
            supabase.table("employee_schedules")
            .select("month, actual_hours")
            .eq("employee_id", employee_id)
            .eq("year", year)
            .execute()
        )
        for row in resp.data or []:
            actual_total += _sum_hours_from_actual(row.get("actual_hours"))
        theoretical = _theoretical_hours_for_year(settings, year)
        balance = compute_balance_hours(theoretical, actual_total)

    account_balance = 0.0
    if settings.hour_account_enabled:
        account_balance = sync_account_balance_cache(company_id, employee_id, year)

    repo.upsert_employee_counter(
        company_id,
        employee_id,
        year,
        theoretical,
        actual_total,
        balance,
        account_balance_hours=account_balance,
        period_credited_hours=period_credited_hours,
        period_paid_hours=period_paid_hours,
    )


def _sum_hs_from_extended_calendar(calendrier: list[dict[str, Any]]) -> float:
    total = 0.0
    for jour in calendrier:
        ev_type = str(jour.get("type") or "")
        if ev_type in ("travail_hs25", "travail_hs50"):
            total += float(jour.get("heures") or 0)
    return round(total, 2)


def apply_modulation_hour_account_to_calendar(
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    calendrier_etendu: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], ModulationPayrollResult]:
    """
    Applique la franchise compte modulation : crédit HS différées, réduction calendrier paie.
    """
    settings = repo.get_modulation_settings(company_id)
    if not settings.hour_account_enabled:
        return calendrier_etendu, [], ModulationPayrollResult()

    total_hs = _sum_hs_from_extended_calendar(calendrier_etendu)
    if total_hs <= 0:
        return calendrier_etendu, [], ModulationPayrollResult(hs_realisees=0.0)

    from app.modules.modulation.domain.hour_account_rules import (
        compute_balance_from_movements,
    )

    movements = repo.list_movements_for_employee_year(employee_id, year)
    current_balance = compute_balance_from_movements(movements)
    franchise = float(settings.hs_franchise_hours_per_period or 0)
    consumed = repo.get_franchise_consumed_in_period(employee_id, year, month)
    split = split_hs_for_period(
        total_hs,
        franchise,
        consumed,
        current_balance,
        settings.max_account_balance_hours,
    )

    updated_calendar = calendrier_etendu
    movement_ids: list[str] = []
    if split.to_account > 0:
        updated_calendar, _ = reduce_hs_in_calendar(calendrier_etendu, split.to_account)
        row = repo.insert_movement(
            {
                "company_id": company_id,
                "employee_id": employee_id,
                "year": year,
                "month": month,
                "movement_type": "credit_hs",
                "hours": split.to_account,
                "status": "validated",
                "source": "payroll_auto",
                "metadata": {
                    "hs_realisees": total_hs,
                    "hs_paid": split.to_pay,
                },
            }
        )
        movement_ids.append(str(row["id"]))
        sync_account_balance_cache(company_id, employee_id, year)

    sync_employee_modulation_counter(
        company_id,
        employee_id,
        year,
        settings=settings,
        period_credited_hours=split.to_account,
        period_paid_hours=split.to_pay,
    )

    return (
        updated_calendar,
        movement_ids,
        ModulationPayrollResult(
            hs_realisees=total_hs,
            hs_credited=split.to_account,
            hs_paid=split.to_pay,
            movement_ids=tuple(movement_ids),
        ),
    )


def apply_modulation_to_payroll_events(
    payroll_events: list[dict[str, Any]],
    hours_to_defer: float,
) -> tuple[list[dict[str, Any]], float]:
    """Réduit les HS dans les événements de paie (analyse calendrier)."""
    from app.modules.modulation.domain.hour_account_rules import reduce_payroll_hs_events

    return reduce_payroll_hs_events(payroll_events, hours_to_defer)


def enrich_payroll_events_metadata(
    payroll_events_json: dict[str, Any],
    events_list: list[dict[str, Any]],
    modulation_result: ModulationPayrollResult | None = None,
) -> dict[str, Any]:
    """Ajoute hs_realisees_mois et champs compte modulation aux payroll_events."""
    out = dict(payroll_events_json)
    out["hs_realisees_mois"] = sum_hs_from_payroll_events(events_list)
    if modulation_result:
        out["modulation_account_credited_hours"] = modulation_result.hs_credited
        out["modulation_account_paid_hs_hours"] = modulation_result.hs_paid
    return out


def finalize_modulation_payroll_application(movement_ids: list[str]) -> None:
    repo.mark_movements_applied_payroll(movement_ids)


def compute_pay_smoothing_gain(
    company_id: str,
    year: int,
    month: int,
    hourly_rate: float,
) -> float:
    from app.modules.modulation.domain.pay_smoothing_rules import (
        compute_smoothing_gain_for_month,
    )

    settings = repo.get_modulation_settings(company_id)
    return compute_smoothing_gain_for_month(settings, year, month, hourly_rate)


def week_config_from_template(day_configs: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Convertit day_configs DB en WeekConfig apply-model."""
    day_keys = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    default_work = {"type": "travail", "hours": 8.0}
    default_weekend = {"type": "weekend", "hours": 0.0}
    week: dict[str, Any] = {k: dict(default_weekend) for k in day_keys}
    for i, k in enumerate(day_keys[:5]):
        week[k] = dict(default_work)
    for cfg in day_configs or []:
        day_num = int(cfg.get("day") or 0)
        if 1 <= day_num <= 7:
            key = day_keys[day_num - 1]
            hours = float(cfg.get("hours") or 0)
            day_type = str(cfg.get("type") or "travail")
            if day_type == "repos" or hours <= 0:
                week[key] = {"type": "weekend", "hours": 0.0}
            else:
                week[key] = {"type": "travail", "hours": hours}
    return week
