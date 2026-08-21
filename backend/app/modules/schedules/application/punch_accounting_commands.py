"""Commandes comptabilisation pointages."""

from __future__ import annotations

from typing import Any

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.infrastructure import punch_accounting_repository as repo
from app.modules.schedules.schemas.punch_accounting import (
    PunchAccountingSettingsResponse,
    PunchAccountingSettingsUpdate,
    PunchOvertimeReviewResponse,
    PunchOvertimeReviewUpdate,
    PunchShiftSlotCreate,
    PunchShiftSlotResponse,
    PunchShiftSlotUpdate,
)


def _int_ou_defaut(valeur, defaut: int) -> int:
    """0 est légal ; seul None retombe sur le défaut (`or` écrasait 0)."""
    return defaut if valeur is None else int(valeur)


def _settings_response(company_id: str) -> PunchAccountingSettingsResponse:
    row = repo.get_settings_row(company_id)
    if not row:
        return PunchAccountingSettingsResponse(configured=False)
    return PunchAccountingSettingsResponse(
        configured=True,
        enabled=bool(row.get("enabled")),
        tolerance_minutes=_int_ou_defaut(row.get("tolerance_minutes"), 30),
        default_break_deduct_minutes=_int_ou_defaut(
            row.get("default_break_deduct_minutes"), 45
        ),
        break_threshold_minutes=int(row.get("break_threshold_minutes") or 0),
        use_last_nonzero_exit=bool(row.get("use_last_nonzero_exit", True)),
        slot_detection=row.get("slot_detection") or "shift_code",
        within_tolerance_pay_theoretical=bool(
            row.get("within_tolerance_pay_theoretical", True)
        ),
        require_manager_validation_for_overtime=bool(
            row.get("require_manager_validation_for_overtime", True)
        ),
    )


def get_punch_accounting_settings(company_id: str) -> PunchAccountingSettingsResponse:
    return _settings_response(company_id)


def update_punch_accounting_settings(
    company_id: str, payload: PunchAccountingSettingsUpdate
) -> PunchAccountingSettingsResponse:
    data = payload.model_dump(exclude_unset=True)
    if data:
        repo.upsert_settings(company_id, data)
    return _settings_response(company_id)


def apply_punch_accounting_preset(company_id: str, preset: str) -> dict[str, Any]:
    try:
        slots = repo.apply_preset(company_id, preset)
    except ValueError as e:
        raise ScheduleAppError("validation", str(e), status_code=400) from e
    return {
        "settings": _settings_response(company_id).model_dump(),
        "slots": [_slot_response(s) for s in slots],
    }


def list_punch_shift_slots(company_id: str) -> list[PunchShiftSlotResponse]:
    from app.core.database import supabase

    resp = (
        supabase.table("company_punch_shift_slots")
        .select("*")
        .eq("company_id", company_id)
        .order("sort_order")
        .execute()
    )
    return [_slot_response(r) for r in resp.data or []]


def _slot_response(row: dict) -> PunchShiftSlotResponse:
    entry = row.get("entry_time") or "08:00"
    exit_t = row.get("exit_time") or "17:00"
    if hasattr(entry, "strftime"):
        entry = entry.strftime("%H:%M")[:5]
    else:
        entry = str(entry)[:5]
    if hasattr(exit_t, "strftime"):
        exit_t = exit_t.strftime("%H:%M")[:5]
    else:
        exit_t = str(exit_t)[:5]
    return PunchShiftSlotResponse(
        id=str(row["id"]),
        code=row.get("code"),
        label=str(row.get("label") or ""),
        entry_time=entry,
        exit_time=exit_t,
        theoretical_gross_minutes=_int_ou_defaut(row.get("theoretical_gross_minutes"), 465),
        break_deduct_minutes=_int_ou_defaut(row.get("break_deduct_minutes"), 45),
        paid_break_minutes=int(row.get("paid_break_minutes") or 0),
        paid_lunch_break=bool(row.get("paid_lunch_break")),
        sort_order=int(row.get("sort_order") or 0),
    )


def create_punch_shift_slot(
    company_id: str, payload: PunchShiftSlotCreate
) -> PunchShiftSlotResponse:
    row = repo.create_slot(company_id, payload.model_dump())
    return _slot_response(row)


def update_punch_shift_slot(
    company_id: str, slot_id: str, payload: PunchShiftSlotUpdate
) -> PunchShiftSlotResponse:
    row = repo.update_slot(company_id, slot_id, payload.model_dump(exclude_unset=True))
    if not row:
        raise ScheduleAppError("not_found", "Créneau introuvable.", status_code=404)
    return _slot_response(row)


def delete_punch_shift_slot(company_id: str, slot_id: str) -> None:
    if not repo.get_slot(company_id, slot_id):
        raise ScheduleAppError("not_found", "Créneau introuvable.", status_code=404)
    repo.delete_slot(company_id, slot_id)


def list_punch_overtime_reviews(
    company_id: str,
    *,
    year: int,
    month: int,
    status: str | None = None,
) -> list[PunchOvertimeReviewResponse]:
    rows = repo.list_overtime_reviews(
        company_id, year=year, month=month, status=status
    )
    out: list[PunchOvertimeReviewResponse] = []
    for row in rows:
        emp = row.get("employees") or {}
        name = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
        entry = row.get("raw_entry_time")
        exit_t = row.get("raw_exit_time")
        if hasattr(entry, "strftime"):
            entry = entry.strftime("%H:%M")
        if hasattr(exit_t, "strftime"):
            exit_t = exit_t.strftime("%H:%M")
        out.append(
            PunchOvertimeReviewResponse(
                id=str(row["id"]),
                employee_id=str(row["employee_id"]),
                employee_name=name or None,
                work_date=str(row["work_date"])[:10],
                overtime_hours=float(row.get("overtime_hours") or 0),
                reason=row.get("reason") or "daily_excess",
                raw_entry_time=str(entry)[:5] if entry else None,
                raw_exit_time=str(exit_t)[:5] if exit_t else None,
                applied_slot_id=(
                    str(row["applied_slot_id"])
                    if row.get("applied_slot_id")
                    else None
                ),
                status=row.get("status") or "pending",
                review_note=row.get("review_note"),
            )
        )
    return out


def update_punch_overtime_review(
    company_id: str,
    review_id: str,
    payload: PunchOvertimeReviewUpdate,
    *,
    reviewed_by: str | None,
) -> PunchOvertimeReviewResponse:
    row = repo.update_overtime_review(
        company_id,
        review_id,
        status=payload.status,
        reviewed_by=reviewed_by,
        review_note=payload.review_note,
    )
    if not row:
        raise ScheduleAppError("not_found", "Revue HS introuvable.", status_code=404)
    reviews = list_punch_overtime_reviews(
        company_id,
        year=int(str(row["work_date"])[:4]),
        month=int(str(row["work_date"])[5:7]),
    )
    for r in reviews:
        if r.id == review_id:
            return r
    raise ScheduleAppError("not_found", "Revue HS introuvable.", status_code=404)
