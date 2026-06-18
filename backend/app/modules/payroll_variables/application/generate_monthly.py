"""Génération mensuelle variables paie."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from app.core.database import supabase
from app.modules.payroll_variables.domain.rules import (
    compute_rule_amount,
    employee_matches_conditions,
)
from app.modules.payroll_variables.infrastructure import repository as repo


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    _, last = calendar.monthrange(year, month)
    return date(year, month, 1), date(year, month, last)


def _count_astreinte_weeks(employee_id: str, start: date, end: date) -> int:
    resp = (
        supabase.table("shifts")
        .select("shift_date")
        .eq("employee_id", employee_id)
        .in_("transverse_category", ["astreinte", "on_call"])
        .gte("shift_date", start.isoformat())
        .lte("shift_date", end.isoformat())
        .execute()
    )
    weeks: set[str] = set()
    for row in resp.data or []:
        d_raw = row.get("shift_date")
        if not d_raw:
            continue
        d = date.fromisoformat(str(d_raw)[:10])
        monday = d - timedelta(days=d.weekday())
        weeks.add(monday.isoformat())
    return len(weeks)


def _sum_actual_hours(employee_id: str, year: int, month: int) -> float:
    resp = (
        supabase.table("employee_schedules")
        .select("actual_hours")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return 0.0
    actual = rows[0].get("actual_hours") or {}
    if not isinstance(actual, dict):
        return 0.0
    total = 0.0
    for day_data in actual.values():
        if isinstance(day_data, dict):
            total += float(day_data.get("heures_faites") or 0)
        elif isinstance(day_data, (int, float)):
            total += float(day_data)
    return round(total, 2)


def _modulation_balance_hours(
    employee_id: str, company_id: str, year: int
) -> float:
    resp = (
        supabase.table("employee_modulation_counters")
        .select("balance_hours")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .eq("year", year)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if rows:
        return float(rows[0].get("balance_hours") or 0)
    return 0.0


def _sum_planning_hours(employee_id: str, year: int, month: int) -> float:
    """Heures issues du planning verrouillé (payroll_events.planning_hours)."""
    resp = (
        supabase.table("employee_schedules")
        .select("payroll_events")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return 0.0
    events = rows[0].get("payroll_events") or {}
    if not isinstance(events, dict):
        return 0.0
    planning_hours = events.get("planning_hours") or []
    if not isinstance(planning_hours, list):
        return 0.0
    total = 0.0
    for entry in planning_hours:
        if isinstance(entry, dict):
            total += float(entry.get("hours_worked") or 0)
    return round(total, 2)


def _count_shift_type_occurrences(
    employee_id: str,
    year: int,
    month: int,
    shift_type_codes: list[str] | None,
) -> float:
    start, end = _month_bounds(year, month)
    query = (
        supabase.table("shifts")
        .select("shift_date, shift_types(code)")
        .eq("employee_id", employee_id)
        .gte("shift_date", start.isoformat())
        .lte("shift_date", end.isoformat())
    )
    resp = query.execute()
    count = 0.0
    codes = {c.lower() for c in (shift_type_codes or [])}
    for row in resp.data or []:
        st = row.get("shift_types") if isinstance(row.get("shift_types"), dict) else {}
        code = str(st.get("code") or "").lower()
        if not codes or code in codes:
            count += 1.0
    if count > 0:
        return count
    return _sum_planning_hours(employee_id, year, month) or 1.0


def _resolve_quantity(
    rule: dict[str, Any],
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
) -> float:
    rule_type = rule.get("rule_type") or ""
    start, end = _month_bounds(year, month)
    if rule_type == "per_astreinte_week":
        return float(_count_astreinte_weeks(employee_id, start, end))
    if rule_type == "per_modulation_payout":
        return max(0.0, _modulation_balance_hours(employee_id, company_id, year))
    if rule_type == "per_night_hour":
        return _sum_actual_hours(employee_id, year, month)
    if rule_type == "per_shift_type":
        shift_codes = (rule.get("conditions") or {}).get("shift_type_codes")
        codes = [str(c) for c in shift_codes] if isinstance(shift_codes, list) else None
        return _count_shift_type_occurrences(employee_id, year, month, codes)
    return 1.0


def _bonus_label(rule: dict[str, Any]) -> str:
    if rule.get("bonus_type_id"):
        resp = (
            supabase.table("company_bonus_types")
            .select("libelle")
            .eq("id", rule["bonus_type_id"])
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if rows and rows[0].get("libelle"):
            return str(rows[0]["libelle"])
    return str(rule.get("label") or rule.get("code") or "Variable paie")


def generate_monthly_variables(
    company_id: str,
    year: int,
    month: int,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    rules = [r for r in repo.list_rules(company_id) if r.get("enabled")]
    emp_resp = (
        supabase.table("employees")
        .select("id, first_name, last_name, statut")
        .eq("company_id", company_id)
        .in_("employment_status", ["actif", "active"])
        .execute()
    )
    employees = emp_resp.data or []
    preview: list[dict[str, Any]] = []
    written = 0

    for rule in rules:
        conditions = rule.get("conditions") or {}
        for emp in employees:
            if not employee_matches_conditions(emp, conditions):
                continue
            eid = str(emp["id"])
            qty = _resolve_quantity(rule, eid, company_id, year, month)
            amount = compute_rule_amount(
                rule.get("rule_type") or "",
                float(rule["amount"]) if rule.get("amount") is not None else None,
                float(rule["rate"]) if rule.get("rate") is not None else None,
                qty,
                conditions=conditions,
            )
            if amount <= 0:
                continue
            label = _bonus_label(rule)
            entry = {
                "employee_id": eid,
                "first_name": emp.get("first_name"),
                "last_name": emp.get("last_name"),
                "rule_code": rule.get("code"),
                "rule_label": rule.get("label"),
                "amount": amount,
                "quantity": qty,
            }
            preview.append(entry)
            if not dry_run and rule.get("generation_mode") == "auto":
                repo.upsert_monthly_input(
                    {
                        "employee_id": eid,
                        "year": year,
                        "month": month,
                        "name": label,
                        "description": f"Auto: {rule.get('code')}",
                        "amount": amount,
                        "is_socially_taxed": True,
                        "is_taxable": True,
                    }
                )
                written += 1

    return {
        "company_id": company_id,
        "year": year,
        "month": month,
        "dry_run": dry_run,
        "preview": preview,
        "written_count": written,
    }
