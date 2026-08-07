"""Repository paramètres congés / RTT et ajustements salarié."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import supabase
from app.modules.absences.domain.jtc import (
    JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT,
    JTC_ABSENCE_TYPES_DEFAULT,
    JTC_ANNUAL_DAYS_DEFAULT,
)
from app.modules.absences.domain.leave_policy import (
    DEFAULT_LEAVE_POLICY,
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
    RTT_FORFAIT_ANNUAL_DAYS_DEFAULT,
    RTT_FORFAIT_CP_OUVRES_DEDUCTION_DEFAULT,
)


def _row_to_policy(row: dict[str, Any] | None) -> LeavePolicySettings:
    if not row:
        return DEFAULT_LEAVE_POLICY
    max_days = row.get("cp_carryover_max_days")
    rtt_days = row.get("rtt_annual_days")
    return LeavePolicySettings(
        cp_acquisition_days_per_month=float(
            row.get("cp_acquisition_days_per_month") or 2.5
        ),
        cp_counting_unit=str(row.get("cp_counting_unit") or "ouvrable"),  # type: ignore[arg-type]
        cp_reference_period_start_month=int(
            row.get("cp_reference_period_start_month") or 6
        ),
        cp_carryover_enabled=bool(row.get("cp_carryover_enabled", False)),
        cp_carryover_max_days=float(max_days) if max_days is not None else None,
        rtt_annual_days=float(rtt_days) if rtt_days is not None else None,
        rtt_use_calendar_formula=bool(row.get("rtt_use_calendar_formula", False)),
        rtt_use_forfait_jours_formula=bool(
            row.get("rtt_use_forfait_jours_formula", False)
        ),
        rtt_forfait_annual_days=int(
            row.get("rtt_forfait_annual_days") or RTT_FORFAIT_ANNUAL_DAYS_DEFAULT
        ),
        rtt_forfait_cp_ouvres_deduction=float(
            row.get("rtt_forfait_cp_ouvres_deduction")
            or RTT_FORFAIT_CP_OUVRES_DEDUCTION_DEFAULT
        ),
        rtt_forfait_cadres_only=bool(row.get("rtt_forfait_cadres_only", True)),
        rtt_period_start_month=int(row.get("rtt_period_start_month") or 1),
        rtt_period_end_month=int(row.get("rtt_period_end_month") or 12),
        rtt_carryover_enabled=bool(row.get("rtt_carryover_enabled", False)),
        rtt_year_end_reminder_enabled=bool(
            row.get("rtt_year_end_reminder_enabled", False)
        ),
        rtt_year_end_reminder_days_before=int(
            row.get("rtt_year_end_reminder_days_before") or 15
        ),
        jtc_enabled=bool(row.get("jtc_enabled", False)),
        jtc_annual_days=int(row.get("jtc_annual_days") or JTC_ANNUAL_DAYS_DEFAULT),
        jtc_absence_threshold_days=int(
            row.get("jtc_absence_threshold_days")
            or JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT
        ),
        jtc_absence_types=tuple(
            row.get("jtc_absence_types") or JTC_ABSENCE_TYPES_DEFAULT
        ),
    )


def _row_to_adjustment(row: dict[str, Any] | None) -> EmployeeLeaveAdjustment:
    if not row:
        return EmployeeLeaveAdjustment.empty()
    forfeited_at = row.get("rtt_forfeited_at")
    return EmployeeLeaveAdjustment(
        cp_n1_opening_balance=float(row.get("cp_n1_opening_balance") or 0),
        cp_n_opening_balance=float(row.get("cp_n_opening_balance") or 0),
        rtt_opening_balance=float(row.get("rtt_opening_balance") or 0),
        rtt_forfeited_at=str(forfeited_at) if forfeited_at else None,
        rtt_forfeited_days=float(row.get("rtt_forfeited_days") or 0),
        jtc_opening_balance=float(row.get("jtc_opening_balance") or 0),
        note=row.get("note"),
    )


def get_leave_policy(company_id: str) -> LeavePolicySettings:
    resp = (
        supabase.table("company_leave_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return _row_to_policy(rows[0] if rows else None)


def get_leave_policy_row(company_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table("company_leave_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def upsert_leave_policy(company_id: str, data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    existing = get_leave_policy_row(company_id)
    payload = {**data, "company_id": company_id, "updated_at": now}
    if existing:
        resp = (
            supabase.table("company_leave_settings")
            .update(payload)
            .eq("company_id", company_id)
            .execute()
        )
    else:
        payload["created_at"] = now
        resp = supabase.table("company_leave_settings").insert(payload).execute()
    if not resp.data:
        raise RuntimeError("Upsert company_leave_settings sans données retournées")
    return resp.data[0] if isinstance(resp.data, list) else resp.data


def get_employee_adjustment(
    employee_id: str, year: int
) -> EmployeeLeaveAdjustment:
    resp = (
        supabase.table("employee_leave_adjustments")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return _row_to_adjustment(rows[0] if rows else None)


def get_adjustments_by_employees_year(
    employee_ids: list[str], year: int
) -> dict[str, EmployeeLeaveAdjustment]:
    if not employee_ids:
        return {}
    resp = (
        supabase.table("employee_leave_adjustments")
        .select("*")
        .in_("employee_id", employee_ids)
        .eq("year", year)
        .execute()
    )
    result: dict[str, EmployeeLeaveAdjustment] = {}
    for row in resp.data or []:
        eid = str(row["employee_id"])
        result[eid] = _row_to_adjustment(row)
    return result


def upsert_employee_adjustment(
    company_id: str,
    employee_id: str,
    year: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    resp = (
        supabase.table("employee_leave_adjustments")
        .select("id")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    payload = {
        **data,
        "company_id": company_id,
        "employee_id": employee_id,
        "year": year,
        "updated_at": now,
    }
    if rows:
        resp2 = (
            supabase.table("employee_leave_adjustments")
            .update(payload)
            .eq("employee_id", employee_id)
            .eq("year", year)
            .execute()
        )
    else:
        payload["created_at"] = now
        resp2 = supabase.table("employee_leave_adjustments").insert(payload).execute()
    if not resp2.data:
        raise RuntimeError("Upsert employee_leave_adjustments sans données")
    return resp2.data[0] if isinstance(resp2.data, list) else resp2.data


def list_company_adjustments(company_id: str, year: int) -> list[dict[str, Any]]:
    resp = (
        supabase.table("employee_leave_adjustments")
        .select("*")
        .eq("company_id", company_id)
        .eq("year", year)
        .execute()
    )
    return resp.data or []
