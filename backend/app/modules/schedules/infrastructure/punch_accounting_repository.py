"""Repository comptabilisation pointages."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.core.database import supabase
from app.modules.schedules.domain.punch_accounting_entities import (
    EQUIPE_PAID_LUNCH_SLOTS_PRESET,
    INDUSTRIAL_3X8_BREAKS_PRESET,
    PunchAccountingSettings,
    PunchShiftSlot,
    THREE_DAILY_SLOTS_PRESET,
)
from app.modules.schedules.domain.punch_accounting_rules import slot_from_row


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_settings(row: dict[str, Any] | None) -> PunchAccountingSettings:
    if not row:
        return PunchAccountingSettings()
    detection = row.get("slot_detection") or "shift_code"
    if detection not in ("shift_code", "nearest_entry", "planning_first"):
        detection = "shift_code"
    return PunchAccountingSettings(
        enabled=bool(row.get("enabled")),
        tolerance_minutes=int(row.get("tolerance_minutes") or 30),
        default_break_deduct_minutes=int(row.get("default_break_deduct_minutes") or 45),
        use_last_nonzero_exit=bool(row.get("use_last_nonzero_exit", True)),
        slot_detection=detection,
        within_tolerance_pay_theoretical=bool(
            row.get("within_tolerance_pay_theoretical", True)
        ),
        require_manager_validation_for_overtime=bool(
            row.get("require_manager_validation_for_overtime", True)
        ),
    )


def get_settings_row(company_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table("company_punch_accounting_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def get_settings(company_id: str) -> PunchAccountingSettings:
    return _row_to_settings(get_settings_row(company_id))


def upsert_settings(company_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "enabled",
        "tolerance_minutes",
        "default_break_deduct_minutes",
        "use_last_nonzero_exit",
        "slot_detection",
        "within_tolerance_pay_theoretical",
        "require_manager_validation_for_overtime",
    }
    data = {k: v for k, v in payload.items() if k in allowed}
    data["company_id"] = company_id
    data["updated_at"] = _now_iso()
    existing = get_settings_row(company_id)
    if existing:
        resp = (
            supabase.table("company_punch_accounting_settings")
            .update(data)
            .eq("company_id", company_id)
            .execute()
        )
    else:
        data["created_at"] = _now_iso()
        resp = supabase.table("company_punch_accounting_settings").insert(data).execute()
    rows = resp.data or []
    return rows[0] if rows else data


def list_slots(company_id: str) -> list[PunchShiftSlot]:
    resp = (
        supabase.table("company_punch_shift_slots")
        .select("*")
        .eq("company_id", company_id)
        .order("sort_order")
        .execute()
    )
    return [slot_from_row(r) for r in resp.data or []]


def create_slot(company_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = {
        "company_id": company_id,
        "code": payload.get("code"),
        "label": payload.get("label") or "",
        "entry_time": payload.get("entry_time"),
        "exit_time": payload.get("exit_time"),
        "theoretical_gross_minutes": int(
            payload.get("theoretical_gross_minutes") or 465
        ),
        "break_deduct_minutes": int(payload.get("break_deduct_minutes") or 45),
        "paid_break_minutes": int(payload.get("paid_break_minutes") or 0),
        "paid_lunch_break": bool(payload.get("paid_lunch_break")),
        "sort_order": int(payload.get("sort_order") or 0),
        "updated_at": _now_iso(),
        "created_at": _now_iso(),
    }
    resp = supabase.table("company_punch_shift_slots").insert(data).execute()
    rows = resp.data or []
    return rows[0]


def update_slot(
    company_id: str, slot_id: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    allowed = {
        "code",
        "label",
        "entry_time",
        "exit_time",
        "theoretical_gross_minutes",
        "break_deduct_minutes",
        "paid_break_minutes",
        "paid_lunch_break",
        "sort_order",
    }
    data = {k: v for k, v in payload.items() if k in allowed}
    if not data:
        return get_slot(company_id, slot_id)
    data["updated_at"] = _now_iso()
    resp = (
        supabase.table("company_punch_shift_slots")
        .update(data)
        .eq("id", slot_id)
        .eq("company_id", company_id)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def delete_slot(company_id: str, slot_id: str) -> None:
    supabase.table("company_punch_shift_slots").delete().eq("id", slot_id).eq(
        "company_id", company_id
    ).execute()


def get_slot(company_id: str, slot_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table("company_punch_shift_slots")
        .select("*")
        .eq("id", slot_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def apply_preset(company_id: str, preset: str) -> list[dict[str, Any]]:
    if preset == "three_daily_slots":
        preset_rows = THREE_DAILY_SLOTS_PRESET
    elif preset == "equipe_paid_lunch":
        preset_rows = EQUIPE_PAID_LUNCH_SLOTS_PRESET
    elif preset in ("industrial_3x8_breaks", "industrial_3x8_mbc"):
        preset_rows = INDUSTRIAL_3X8_BREAKS_PRESET
    else:
        raise ValueError(f"Preset inconnu : {preset}")
    supabase.table("company_punch_shift_slots").delete().eq(
        "company_id", company_id
    ).execute()
    created: list[dict[str, Any]] = []
    for row in preset_rows:
        created.append(create_slot(company_id, row))
    upsert_settings(
        company_id,
        {"enabled": True},
    )
    return created


def list_overtime_reviews(
    company_id: str,
    *,
    year: int,
    month: int,
    status: str | None = None,
) -> list[dict[str, Any]]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    q = (
        supabase.table("employee_punch_overtime_reviews")
        .select("*, employees(first_name, last_name)")
        .eq("company_id", company_id)
        .gte("work_date", start.isoformat())
        .lt("work_date", end.isoformat())
    )
    if status:
        q = q.eq("status", status)
    resp = q.order("work_date").execute()
    return resp.data or []


def count_pending_reviews(company_id: str, year: int, month: int) -> int:
    rows = list_overtime_reviews(
        company_id, year=year, month=month, status="pending"
    )
    return len(rows)


def upsert_overtime_review(
    company_id: str,
    *,
    employee_id: str,
    work_date: date,
    overtime_hours: float,
    reason: str,
    raw_entry_time: str | None,
    raw_exit_time: str | None,
    applied_slot_id: str | None,
    status: str = "pending",
) -> dict[str, Any]:
    payload = {
        "company_id": company_id,
        "employee_id": employee_id,
        "work_date": work_date.isoformat(),
        "overtime_hours": round(overtime_hours, 2),
        "reason": reason,
        "raw_entry_time": raw_entry_time,
        "raw_exit_time": raw_exit_time,
        "applied_slot_id": applied_slot_id,
        "status": status,
        "updated_at": _now_iso(),
    }
    existing = (
        supabase.table("employee_punch_overtime_reviews")
        .select("id")
        .eq("employee_id", employee_id)
        .eq("work_date", work_date.isoformat())
        .limit(1)
        .execute()
    )
    rows = existing.data or []
    if rows:
        resp = (
            supabase.table("employee_punch_overtime_reviews")
            .update(payload)
            .eq("id", rows[0]["id"])
            .execute()
        )
    else:
        payload["created_at"] = _now_iso()
        resp = supabase.table("employee_punch_overtime_reviews").insert(payload).execute()
    out = resp.data or []
    return out[0] if out else payload


def update_overtime_review(
    company_id: str,
    review_id: str,
    *,
    status: str,
    reviewed_by: str | None,
    review_note: str | None,
) -> dict[str, Any] | None:
    data: dict[str, Any] = {
        "status": status,
        "updated_at": _now_iso(),
    }
    if reviewed_by:
        data["reviewed_by"] = reviewed_by
    if review_note is not None:
        data["review_note"] = review_note
    resp = (
        supabase.table("employee_punch_overtime_reviews")
        .update(data)
        .eq("id", review_id)
        .eq("company_id", company_id)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def list_approved_overtime_for_month(
    company_id: str, year: int, month: int
) -> list[dict[str, Any]]:
    return list_overtime_reviews(
        company_id, year=year, month=month, status="approved"
    )
