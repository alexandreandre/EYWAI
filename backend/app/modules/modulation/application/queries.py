"""Queries modulation."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.modulation.domain.entities import ModulationSettings
from app.modules.modulation.infrastructure import repository as repo
from app.modules.modulation.schemas.requests import (
    ModulationOverviewRow,
    ModulationSettingsResponse,
    WeekTemplateSchema,
)


def _settings_to_response(
    company_id: str, settings: ModulationSettings
) -> ModulationSettingsResponse:
    row = repo.get_modulation_settings_row(company_id)
    return ModulationSettingsResponse(
        company_id=company_id,
        enabled=settings.enabled,
        configured=row is not None,
        reference_period_months=settings.reference_period_months,
        average_weekly_hours=settings.average_weekly_hours,
        weekly_high_hours=settings.weekly_high_hours,
        weekly_low_hours=settings.weekly_low_hours,
        high_weeks_per_cycle=settings.high_weeks_per_cycle,
        low_weeks_per_cycle=settings.low_weeks_per_cycle,
        cycle_start_week_iso=settings.cycle_start_week_iso,
        pay_smoothed=settings.pay_smoothed,
        weekly_cap_hours=settings.weekly_cap_hours,
        theoretical_annual_hours=settings.theoretical_annual_hours,
    )


def get_modulation_settings(company_id: str) -> ModulationSettingsResponse:
    settings = repo.get_modulation_settings(company_id)
    return _settings_to_response(company_id, settings)


def list_week_templates(company_id: str) -> list[WeekTemplateSchema]:
    templates = repo.list_week_templates(company_id)
    return [
        WeekTemplateSchema(
            id=t.id,
            name=t.name,
            weekly_hours=t.weekly_hours,
            day_configs=t.day_configs,
            modulation_tier=t.modulation_tier,
            is_active=t.is_active,
        )
        for t in templates
    ]


def get_modulation_overview(
    company_id: str, year: int | None = None
) -> list[ModulationOverviewRow]:
    ref_year = year or date.today().year
    counters = repo.list_employee_counters(company_id, ref_year)
    if counters:
        rows: list[ModulationOverviewRow] = []
        for c in counters:
            emp = c.get("employees") or {}
            rows.append(
                ModulationOverviewRow(
                    employee_id=str(c["employee_id"]),
                    first_name=emp.get("first_name") or "",
                    last_name=emp.get("last_name") or "",
                    theoretical_hours=float(c.get("theoretical_hours") or 0),
                    actual_hours=float(c.get("actual_hours") or 0),
                    balance_hours=float(c.get("balance_hours") or 0),
                )
            )
        return rows

    emp_resp = (
        supabase.table("employees")
        .select("id, first_name, last_name, duree_hebdomadaire")
        .eq("company_id", company_id)
        .in_("employment_status", ["actif", "active"])
        .execute()
    )
    settings = repo.get_modulation_settings(company_id)
    rows = []
    for emp in emp_resp.data or []:
        weekly = float(emp.get("duree_hebdomadaire") or settings.average_weekly_hours)
        theoretical = round(weekly * 52, 2)
        rows.append(
            ModulationOverviewRow(
                employee_id=str(emp["id"]),
                first_name=emp.get("first_name") or "",
                last_name=emp.get("last_name") or "",
                theoretical_hours=theoretical,
                actual_hours=theoretical,
                balance_hours=0.0,
            )
        )
    return rows
