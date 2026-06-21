"""Repository modulation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import supabase
from app.modules.modulation.domain.entities import (
    ModulationSettings,
    WeekScheduleTemplate,
)


def _row_to_settings(row: dict[str, Any]) -> ModulationSettings:
    cycle_start = row.get("cycle_start_week_iso")
    if isinstance(cycle_start, str):
        from datetime import date

        cycle_start = date.fromisoformat(cycle_start[:10])
    theoretical = row.get("theoretical_annual_hours")
    franchise = row.get("hs_franchise_hours_per_period")
    max_bal = row.get("max_account_balance_hours")
    franchise_period = row.get("hs_franchise_period") or "month"
    credit_source = row.get("account_credit_source") or "overtime_only"
    debit_timing = row.get("recovery_debit_timing") or "on_validation"
    if franchise_period not in ("month", "pay_period"):
        franchise_period = "month"
    if credit_source not in ("overtime_only", "surplus_over_modulated"):
        credit_source = "overtime_only"
    if debit_timing not in ("on_validation", "on_payroll"):
        debit_timing = "on_validation"
    hs_policy = row.get("hs_routing_policy") or "franchise"
    if hs_policy not in ("pay_all", "account_all", "franchise", "manual"):
        hs_policy = "franchise"
    return ModulationSettings(
        enabled=bool(row.get("enabled")),
        reference_period_months=int(row.get("reference_period_months") or 12),
        average_weekly_hours=float(row.get("average_weekly_hours") or 35),
        weekly_high_hours=float(row.get("weekly_high_hours") or 37),
        weekly_low_hours=float(row.get("weekly_low_hours") or 32),
        high_weeks_per_cycle=int(row.get("high_weeks_per_cycle") or 1),
        low_weeks_per_cycle=int(row.get("low_weeks_per_cycle") or 1),
        cycle_start_week_iso=cycle_start,
        pay_smoothed=bool(row.get("pay_smoothed", True)),
        weekly_cap_hours=float(row.get("weekly_cap_hours") or 44),
        theoretical_annual_hours=(
            float(theoretical) if theoretical is not None else None
        ),
        hour_account_enabled=bool(row.get("hour_account_enabled", False)),
        hs_franchise_hours_per_period=(
            float(franchise) if franchise is not None else None
        ),
        hs_franchise_period=franchise_period,
        max_account_balance_hours=float(max_bal) if max_bal is not None else None,
        account_credit_source=credit_source,
        recovery_absence_enabled=bool(row.get("recovery_absence_enabled", True)),
        recovery_debit_timing=debit_timing,
        hs_routing_policy=hs_policy,
    )


def get_modulation_settings_row(company_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table("company_modulation_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def get_modulation_settings(company_id: str) -> ModulationSettings:
    row = get_modulation_settings_row(company_id)
    if not row:
        return ModulationSettings()
    return _row_to_settings(row)


def upsert_modulation_settings(
    company_id: str, data: dict[str, Any]
) -> ModulationSettings:
    now = datetime.now(timezone.utc).isoformat()
    row = {"company_id": company_id, **data, "updated_at": now}
    existing = get_modulation_settings_row(company_id)
    if existing:
        supabase.table("company_modulation_settings").update(row).eq(
            "company_id", company_id
        ).execute()
    else:
        row["created_at"] = now
        supabase.table("company_modulation_settings").insert(row).execute()
    return get_modulation_settings(company_id)


def list_week_templates(company_id: str) -> list[WeekScheduleTemplate]:
    resp = (
        supabase.table("company_week_schedule_templates")
        .select("*")
        .eq("company_id", company_id)
        .eq("is_active", True)
        .order("name")
        .execute()
    )
    out: list[WeekScheduleTemplate] = []
    for row in resp.data or []:
        tier = row.get("modulation_tier") or "neutral"
        if tier not in ("high", "low", "neutral"):
            tier = "neutral"
        out.append(
            WeekScheduleTemplate(
                id=str(row["id"]),
                company_id=str(row["company_id"]),
                name=row.get("name") or "",
                weekly_hours=float(row.get("weekly_hours") or 35),
                day_configs=row.get("day_configs") or [],
                modulation_tier=tier,
                is_active=bool(row.get("is_active", True)),
                team_id=str(row["team_id"]) if row.get("team_id") else None,
                description=row.get("description"),
            )
        )
    return out


def upsert_week_template(
    company_id: str, payload: dict[str, Any], template_id: str | None = None
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    row = {**payload, "company_id": company_id, "updated_at": now}
    if template_id:
        supabase.table("company_week_schedule_templates").update(row).eq(
            "id", template_id
        ).execute()
        resp = (
            supabase.table("company_week_schedule_templates")
            .select("*")
            .eq("id", template_id)
            .limit(1)
            .execute()
        )
        return (resp.data or [{}])[0]
    row["created_at"] = now
    resp = (
        supabase.table("company_week_schedule_templates").insert(row).execute()
    )
    return (resp.data or [{}])[0]


def delete_week_template(company_id: str, template_id: str) -> None:
    supabase.table("company_week_schedule_templates").update(
        {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("company_id", company_id).eq("id", template_id).execute()


def upsert_employee_counter(
    company_id: str,
    employee_id: str,
    year: int,
    theoretical: float,
    actual: float,
    balance: float,
    *,
    account_balance_hours: float | None = None,
    period_credited_hours: float | None = None,
    period_paid_hours: float | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    row: dict[str, Any] = {
        "company_id": company_id,
        "employee_id": employee_id,
        "year": year,
        "theoretical_hours": theoretical,
        "actual_hours": actual,
        "balance_hours": balance,
        "updated_at": now,
    }
    if account_balance_hours is not None:
        row["account_balance_hours"] = account_balance_hours
    if period_credited_hours is not None:
        row["period_credited_hours"] = period_credited_hours
    if period_paid_hours is not None:
        row["period_paid_hours"] = period_paid_hours
    resp = (
        supabase.table("employee_modulation_counters")
        .select("id")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .limit(1)
        .execute()
    )
    if resp.data:
        supabase.table("employee_modulation_counters").update(row).eq(
            "employee_id", employee_id
        ).eq("year", year).execute()
    else:
        supabase.table("employee_modulation_counters").insert(row).execute()


def list_employee_counters(company_id: str, year: int) -> list[dict[str, Any]]:
    resp = (
        supabase.table("employee_modulation_counters")
        .select("*, employees(first_name, last_name)")
        .eq("company_id", company_id)
        .eq("year", year)
        .execute()
    )
    return resp.data or []


def insert_movement(row: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    payload = {**row, "created_at": now, "updated_at": now}
    resp = supabase.table("employee_modulation_movements").insert(payload).execute()
    return (resp.data or [{}])[0]


def list_movements(
    employee_id: str,
    year: int | None = None,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    query = (
        supabase.table("employee_modulation_movements")
        .select("*")
        .eq("employee_id", employee_id)
        .order("created_at", desc=True)
        .range(offset, offset + max(0, limit - 1))
    )
    if year is not None:
        query = query.eq("year", year)
    resp = query.execute()
    return resp.data or []


def list_movements_for_employee_year(employee_id: str, year: int) -> list[dict[str, Any]]:
    resp = (
        supabase.table("employee_modulation_movements")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .execute()
    )
    return resp.data or []


def get_franchise_consumed_in_period(
    employee_id: str,
    year: int,
    month: int,
) -> float:
    resp = (
        supabase.table("employee_modulation_movements")
        .select("hours")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .eq("movement_type", "credit_hs")
        .in_("status", ["validated", "applied_payroll"])
        .execute()
    )
    return round(
        sum(float(r.get("hours") or 0) for r in (resp.data or [])),
        2,
    )


def mark_movements_applied_payroll(movement_ids: list[str]) -> None:
    if not movement_ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("employee_modulation_movements").update(
        {"status": "applied_payroll", "updated_at": now}
    ).in_("id", movement_ids).execute()


def count_pending_movements(company_id: str) -> int:
    resp = (
        supabase.table("employee_modulation_movements")
        .select("id", count="exact")
        .eq("company_id", company_id)
        .eq("status", "pending")
        .execute()
    )
    return int(resp.count or 0)


def count_employees_over_balance_cap(company_id: str, year: int) -> int:
    """Salariés dont le solde compte dépasse le plafond entreprise (si configuré)."""
    settings = get_modulation_settings(company_id)
    if not settings.hour_account_enabled or settings.max_account_balance_hours is None:
        return 0
    cap = float(settings.max_account_balance_hours)
    counters = list_employee_counters(company_id, year)
    return sum(
        1
        for row in counters
        if float(row.get("account_balance_hours") or 0) > cap
    )
