"""Commandes écriture — module Planning."""

from __future__ import annotations

import logging
import traceback
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.planning.domain.conflict_engine import run_all_checks
from app.modules.planning.infrastructure import queries as infra_queries
from app.modules.planning.infrastructure.repository import planning_repository
from app.modules.planning.schemas.requests import (
    CompanyPlanningSettingsUpdate,
    DayLockRequest,
    ShiftCreate,
    ShiftUpdate,
    WeekDuplicateRequest,
    WeekLockRequest,
    WeekPublishRequest,
)

logger = logging.getLogger(__name__)


def _week_start_iso(week_start: str) -> str:
    return week_start[:10]


def _week_end_iso(week_start: str) -> str:
    d = date.fromisoformat(_week_start_iso(week_start))
    return (d + timedelta(days=6)).isoformat()


def _parse_time(value: Any) -> Optional[time]:
    if value is None:
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        parts = value.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
        return time(h, m, s)
    return None


def _times_overlap(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    """Chevauchement sur la même journée (même logique que start < other_end and end > other_start)."""
    d0 = date.min
    ta0 = datetime.combine(d0, a_start)
    ta1 = datetime.combine(d0, a_end)
    if ta1 <= ta0:
        ta1 += timedelta(days=1)
    tb0 = datetime.combine(d0, b_start)
    tb1 = datetime.combine(d0, b_end)
    if tb1 <= tb0:
        tb1 += timedelta(days=1)
    return ta0 < tb1 and ta1 > tb0


def _shift_hours_decimal(row: Dict[str, Any]) -> float:
    st = _parse_time(row.get("start_time"))
    et = _parse_time(row.get("end_time"))
    if st is None or et is None:
        return 0.0
    d0 = date.min
    t0 = datetime.combine(d0, st)
    t1 = datetime.combine(d0, et)
    if t1 <= t0:
        t1 += timedelta(days=1)
    return round((t1 - t0).total_seconds() / 3600.0, 2)


def _ensure_week_status_row(company_id: str, week_start: str) -> None:
    if not planning_repository.get_week_status(company_id, _week_start_iso(week_start)):
        planning_repository.upsert_week_status(
            company_id,
            _week_start_iso(week_start),
            {"status": "draft"},
        )


def _parse_shift_date_value(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return None


def create_shift(data: ShiftCreate, company_id: str, created_by: str) -> dict:
    """
    1. Vérifie conflits (absence, chevauchement, repos hebdo, dépassement contrat).
    2. Construit le dict d'insertion avec company_id, created_by, source='manual'.
    3. Appelle planning_repository.create_shift(insert_data).
    """
    shift_date_iso = data.shift_date.isoformat()
    absence_row = infra_queries.check_absence_on_date(
        data.employee_id, shift_date_iso
    )
    existing_absences = [absence_row] if absence_row else []
    existing_day_shifts = infra_queries.get_employee_shifts_for_conflict_check(
        data.employee_id, shift_date_iso
    )
    monday = data.shift_date - timedelta(days=data.shift_date.weekday())
    week_start_s = monday.isoformat()
    week_end_s = (monday + timedelta(days=6)).isoformat()
    week_shifts = planning_repository.get_shifts_by_employee_week(
        data.employee_id, week_start_s, week_end_s
    )
    emp_r = (
        supabase.table("employees")
        .select("duree_hebdomadaire")
        .eq("id", data.employee_id)
        .maybe_single()
        .execute()
    )
    ch_raw = (
        (emp_r.data or {}).get("duree_hebdomadaire")
        if emp_r and emp_r.data
        else None
    )
    contract_hours = float(ch_raw) if ch_raw is not None else 35.0

    provisional: Dict[str, Any] = {
        "shift_date": shift_date_iso,
        "start_time": data.start_time.isoformat(timespec="seconds"),
        "end_time": data.end_time.isoformat(timespec="seconds"),
        "transverse_category": data.transverse_category,
    }
    week_shifts_for_checks = list(week_shifts) + [provisional]

    results = run_all_checks(
        shift_date=shift_date_iso,
        new_start=data.start_time.isoformat(timespec="seconds"),
        new_end=data.end_time.isoformat(timespec="seconds"),
        existing_absences=existing_absences,
        existing_day_shifts=existing_day_shifts,
        week_shifts=week_shifts_for_checks,
        contract_hours_per_week=contract_hours,
        exclude_shift_id=None,
        min_rest_hours=35,
    )
    for r in results:
        if r.has_blocking_conflict:
            raise ValueError(r.message)

    insert_data: Dict[str, Any] = {
        "company_id": company_id,
        "employee_id": data.employee_id,
        "shift_type_id": data.shift_type_id,
        "transverse_category": data.transverse_category,
        "shift_date": shift_date_iso,
        "start_time": data.start_time.isoformat(timespec="seconds"),
        "end_time": data.end_time.isoformat(timespec="seconds"),
        "post": data.post,
        "location": data.location,
        "comment_internal": data.comment_internal,
        "comment_employee": data.comment_employee,
        "source": "manual",
        "created_by": created_by,
    }
    created = planning_repository.create_shift(insert_data)
    warnings = [
        {"type": r.conflict_type, "message": r.message, "details": r.details}
        for r in results
        if r.is_warning_only
    ]
    if warnings:
        created = {**created, "conflict_warnings": warnings}
    return created


def update_shift(shift_id: str, data: ShiftUpdate, company_id: str) -> dict:
    """
    1. Récupère le shift → LookupError si inexistant.
    2. Vérifie company_id → PermissionError si mismatch.
    3. Vérifie is_locked → ValueError si True.
    4. Si start_time ou end_time modifié : re-vérifie chevauchement (exclude_shift_id).
    5. Appelle planning_repository.update_shift().
    """
    row = planning_repository.get_shift_by_id(shift_id)
    if not row:
        raise LookupError("Shift introuvable.")
    if str(row.get("company_id") or "") != str(company_id):
        raise PermissionError("Shift hors entreprise active.")
    if bool(row.get("is_locked")):
        raise ValueError(
            "Cette semaine est verrouillée. Déverrouillez pour modifier."
        )
    payload = data.model_dump(exclude_unset=True)
    if "start_time" in payload and isinstance(payload["start_time"], time):
        payload["start_time"] = payload["start_time"].isoformat(timespec="seconds")
    if "end_time" in payload and isinstance(payload["end_time"], time):
        payload["end_time"] = payload["end_time"].isoformat(timespec="seconds")

    merged: Dict[str, Any] = dict(row)
    merged.update(payload)
    new_start = merged.get("start_time")
    new_end = merged.get("end_time")
    st_new = _parse_time(new_start)
    et_new = _parse_time(new_end)
    shift_date_str = str(merged.get("shift_date") or row.get("shift_date"))[:10]
    employee_id = str(row.get("employee_id") or "")
    absence_row = infra_queries.check_absence_on_date(employee_id, shift_date_str)
    existing_absences = [absence_row] if absence_row else []
    existing_day_shifts = infra_queries.get_employee_shifts_for_conflict_check(
        employee_id,
        shift_date_str,
        exclude_shift_id=shift_id,
    )
    sd = _parse_shift_date_value(merged.get("shift_date") or row.get("shift_date"))
    if sd:
        monday = sd - timedelta(days=sd.weekday())
        week_start_s = monday.isoformat()
        week_end_s = (monday + timedelta(days=6)).isoformat()
    else:
        week_start_s = shift_date_str
        week_end_s = shift_date_str
    week_shifts = planning_repository.get_shifts_by_employee_week(
        employee_id, week_start_s, week_end_s
    )
    week_for_checks = [s for s in week_shifts if str(s.get("id")) != str(shift_id)]
    week_for_checks.append(merged)
    emp_r = (
        supabase.table("employees")
        .select("duree_hebdomadaire")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    ch_raw = (
        (emp_r.data or {}).get("duree_hebdomadaire")
        if emp_r and emp_r.data
        else None
    )
    contract_hours = float(ch_raw) if ch_raw is not None else 35.0

    ns = st_new.isoformat(timespec="seconds") if st_new else str(new_start)
    ne = et_new.isoformat(timespec="seconds") if et_new else str(new_end)
    results = run_all_checks(
        shift_date=shift_date_str,
        new_start=ns,
        new_end=ne,
        existing_absences=existing_absences,
        existing_day_shifts=existing_day_shifts,
        week_shifts=week_for_checks,
        contract_hours_per_week=contract_hours,
        exclude_shift_id=shift_id,
        min_rest_hours=35,
    )
    for r in results:
        if r.has_blocking_conflict:
            raise ValueError(r.message)

    if not payload:
        return row
    updated = planning_repository.update_shift(shift_id, payload)
    warnings = [
        {"type": r.conflict_type, "message": r.message, "details": r.details}
        for r in results
        if r.is_warning_only
    ]
    if warnings:
        updated = {**updated, "conflict_warnings": warnings}
    return updated


def delete_shift(shift_id: str, company_id: str) -> bool:
    """Supprime un shift après contrôles entreprise et verrouillage."""
    row = planning_repository.get_shift_by_id(shift_id)
    if not row:
        raise LookupError("Shift introuvable.")
    if str(row.get("company_id") or "") != str(company_id):
        raise PermissionError("Shift hors entreprise active.")
    if bool(row.get("is_locked")):
        raise ValueError(
            "Cette semaine est verrouillée. Déverrouillez pour modifier."
        )
    return planning_repository.delete_shift(shift_id)


def lock_day(
    data: DayLockRequest, company_id: str, locked_by: str
) -> dict:
    """Verrouille un jour (shifts + day_status + historique)."""
    day_iso = data.day_date.isoformat()
    if infra_queries.get_payroll_period_locked(
        company_id, data.day_date.month, data.day_date.year
    ):
        raise RuntimeError(
            "La paie de ce mois est clôturée. Demandez au Super Admin de rouvrir la période."
        )
    shifts = planning_repository.get_shifts_by_day(company_id, day_iso)
    for s in shifts:
        planning_repository.lock_shift(str(s["id"]))
    now_iso = datetime.now(timezone.utc).isoformat()
    day_status = planning_repository.upsert_day_status(
        company_id,
        day_iso,
        {
            "is_locked": True,
            "locked_at": now_iso,
            "locked_by": locked_by,
            "lock_reason": data.reason,
        },
    )
    total_hours = sum(_shift_hours_decimal(s) for s in shifts)
    planning_repository.create_lock_history(
        {
            "company_id": company_id,
            "action": "lock_day",
            "target_date": day_iso,
            "performed_by": locked_by,
            "reason": data.reason,
            "shifts_count": len(shifts),
            "total_hours": total_hours,
        }
    )
    return day_status


def unlock_day(
    day_date: str,
    company_id: str,
    unlocked_by: str,
    reason: Optional[str] = None,
) -> dict:
    """Déverrouille un jour."""
    d = date.fromisoformat(day_date[:10])
    if infra_queries.get_payroll_period_locked(company_id, d.month, d.year):
        raise RuntimeError(
            "La paie de ce mois est clôturée. Demandez au Super Admin de rouvrir la période."
        )
    shifts = planning_repository.get_shifts_by_day(company_id, day_date[:10])
    for s in shifts:
        planning_repository.update_shift(str(s["id"]), {"is_locked": False})
    day_status = planning_repository.upsert_day_status(
        company_id,
        day_date[:10],
        {"is_locked": False, "locked_at": None, "locked_by": None},
    )
    planning_repository.create_lock_history(
        {
            "company_id": company_id,
            "action": "unlock_day",
            "target_date": day_date[:10],
            "performed_by": unlocked_by,
            "reason": reason,
            "shifts_count": len(shifts),
            "total_hours": sum(_shift_hours_decimal(s) for s in shifts),
        }
    )
    return day_status


def lock_week(
    data: WeekLockRequest, company_id: str, locked_by: str
) -> dict:
    """Verrouille une semaine, historique et transmission paie (best effort)."""
    ws = data.week_start
    ws_iso = ws.isoformat()
    if infra_queries.get_payroll_period_locked(company_id, ws.month, ws.year):
        raise RuntimeError(
            "La paie de ce mois est clôturée. Demandez au Super Admin de rouvrir la période."
        )
    we_iso = _week_end_iso(ws_iso)
    _ensure_week_status_row(company_id, ws_iso)
    shifts = planning_repository.get_shifts_by_week(company_id, ws_iso, we_iso)
    for s in shifts:
        planning_repository.lock_shift(str(s["id"]))
    week_status = planning_repository.lock_week(company_id, ws_iso, locked_by)
    total_hours = sum(_shift_hours_decimal(s) for s in shifts)
    planning_repository.create_lock_history(
        {
            "company_id": company_id,
            "action": "lock_week",
            "target_week_start": ws_iso,
            "performed_by": locked_by,
            "reason": data.reason,
            "shifts_count": len(shifts),
            "total_hours": total_hours,
        }
    )
    _transmit_to_payroll(company_id, ws_iso, shifts)
    return week_status


def unlock_week(
    week_start: str,
    company_id: str,
    unlocked_by: str,
    reason: Optional[str] = None,
) -> dict:
    """Repasse une semaine en publiée et déverrouille les shifts."""
    ws_iso = _week_start_iso(week_start)
    d = date.fromisoformat(ws_iso)
    if infra_queries.get_payroll_period_locked(company_id, d.month, d.year):
        raise RuntimeError(
            "La paie de ce mois est clôturée. Demandez au Super Admin de rouvrir la période."
        )
    we_iso = _week_end_iso(week_start)
    _ensure_week_status_row(company_id, ws_iso)
    shifts = planning_repository.get_shifts_by_week(company_id, ws_iso, we_iso)
    for s in shifts:
        planning_repository.update_shift(str(s["id"]), {"is_locked": False})
    week_status = planning_repository.upsert_week_status(
        company_id,
        ws_iso,
        {"status": "published", "locked_at": None, "locked_by": None},
    )
    planning_repository.create_lock_history(
        {
            "company_id": company_id,
            "action": "unlock_week",
            "target_week_start": ws_iso,
            "performed_by": unlocked_by,
            "reason": reason,
            "shifts_count": len(shifts),
            "total_hours": sum(_shift_hours_decimal(s) for s in shifts),
        }
    )
    return week_status


def publish_week(data: WeekPublishRequest, company_id: str) -> dict:
    """Publie une semaine (totale ou partielle selon publish_days)."""
    ws_iso = data.week_start.isoformat()
    _ensure_week_status_row(company_id, ws_iso)
    if data.publish_days is None:
        new_status = "published"
    else:
        new_status = "partially_published"
    return planning_repository.upsert_week_status(
        company_id, ws_iso, {"status": new_status}
    )


def duplicate_week(
    data: WeekDuplicateRequest, company_id: str, created_by: str
) -> dict:
    """Duplique une semaine source vers des semaines cibles."""
    source_iso = data.source_week_start.isoformat()
    we_source = _week_end_iso(source_iso)
    source_shifts = planning_repository.get_shifts_by_week(
        company_id, source_iso, we_source
    )
    shifts_created = 0
    shifts_skipped = 0
    conflicts: List[Dict[str, Any]] = []

    for target_monday in data.target_weeks:
        delta = (target_monday - data.source_week_start).days

        for src in source_shifts:
            emp_id = str(src.get("employee_id") or "")
            src_day = _parse_shift_date_value(src.get("shift_date"))
            if not src_day:
                shifts_skipped += 1
                continue
            target_day = src_day + timedelta(days=delta)
            target_day_iso = target_day.isoformat()

            ds = planning_repository.get_day_status(company_id, target_day_iso)
            if ds and bool(ds.get("is_locked")) and data.skip_locked_days:
                shifts_skipped += 1
                conflicts.append(
                    {
                        "employee_id": emp_id,
                        "date": target_day_iso,
                        "reason": "day_locked",
                    }
                )
                continue

            has_absence = bool(
                infra_queries.check_absence_on_date(emp_id, target_day_iso)
            )
            if has_absence and data.skip_absent_employees:
                shifts_skipped += 1
                conflicts.append(
                    {
                        "employee_id": emp_id,
                        "date": target_day_iso,
                        "reason": "absence",
                    }
                )
                continue

            others = infra_queries.get_employee_shifts_for_conflict_check(
                emp_id, target_day_iso
            )
            st_src = _parse_time(src.get("start_time"))
            et_src = _parse_time(src.get("end_time"))
            overlap = False
            if st_src and et_src:
                for ex in others:
                    st0 = _parse_time(ex.get("start_time"))
                    et0 = _parse_time(ex.get("end_time"))
                    if st0 and et0 and _times_overlap(st_src, et_src, st0, et0):
                        overlap = True
                        break
            if overlap:
                shifts_skipped += 1
                conflicts.append(
                    {
                        "employee_id": emp_id,
                        "date": target_day_iso,
                        "reason": "shift_overlap",
                    }
                )
                continue

            st_ins = _parse_time(src.get("start_time"))
            et_ins = _parse_time(src.get("end_time"))
            insert_data: Dict[str, Any] = {
                "company_id": company_id,
                "employee_id": emp_id,
                "shift_type_id": src.get("shift_type_id"),
                "transverse_category": src.get("transverse_category"),
                "shift_date": target_day_iso,
                "start_time": st_ins.isoformat(timespec="seconds") if st_ins else str(
                    src.get("start_time")
                ),
                "end_time": et_ins.isoformat(timespec="seconds") if et_ins else str(
                    src.get("end_time")
                ),
                "post": src.get("post"),
                "location": src.get("location"),
                "source": "manual",
                "created_by": created_by,
            }
            if data.include_comments:
                insert_data["comment_internal"] = src.get("comment_internal")
                insert_data["comment_employee"] = src.get("comment_employee")
            else:
                insert_data["comment_internal"] = None
                insert_data["comment_employee"] = None

            try:
                planning_repository.create_shift(insert_data)
                shifts_created += 1
            except Exception:
                shifts_skipped += 1
                conflicts.append(
                    {
                        "employee_id": emp_id,
                        "date": target_day_iso,
                        "reason": "insert_failed",
                    }
                )

    return {
        "shifts_created": shifts_created,
        "shifts_skipped": shifts_skipped,
        "conflicts": conflicts,
    }


def _transmit_to_payroll(
    company_id: str, week_start: str, shifts: list
) -> None:
    """
    Transmet les heures des shifts verrouillés vers employee_schedules (payroll_events).
    Best effort : ne jamais faire échouer le verrouillage.
    """
    try:
        week_start_clean = week_start[:10]
        by_employee_month: Dict[tuple, List[Dict[str, Any]]] = {}
        for shift in shifts:
            employee_id = shift.get("employee_id")
            if not employee_id:
                continue
            shift_date = _parse_shift_date_value(shift.get("shift_date"))
            if not shift_date:
                continue
            year = shift_date.year
            month = shift_date.month
            key = (str(employee_id), year, month)
            by_employee_month.setdefault(key, []).append(shift)

        transmitted_at = datetime.now(timezone.utc).isoformat()

        for (employee_id, year, month), employee_shifts in by_employee_month.items():
            planning_hours: List[Dict[str, Any]] = []
            for s in employee_shifts:
                hours = float(_shift_hours_decimal(s))
                shift_type = (
                    s.get("shift_types")
                    if isinstance(s.get("shift_types"), dict)
                    else {}
                )
                sd_raw = s.get("shift_date")
                sd_str = str(sd_raw)[:10] if sd_raw is not None else ""
                planning_hours.append(
                    {
                        "shift_id": s.get("id"),
                        "shift_date": sd_str,
                        "shift_type_code": shift_type.get("code", "UNKNOWN"),
                        "shift_type_label": shift_type.get("label", ""),
                        "hours_worked": round(hours, 2),
                        "source": "planning_lock",
                    }
                )

            payload_planning = {
                "planning_hours": planning_hours,
                "planning_week_start": week_start_clean,
                "planning_transmitted_at": transmitted_at,
            }

            r = (
                supabase.table("employee_schedules")
                .select("id, payroll_events")
                .eq("employee_id", employee_id)
                .eq("year", year)
                .eq("month", month)
                .maybe_single()
                .execute()
            )
            existing = r.data if r else None

            if existing:
                existing_events = existing.get("payroll_events") or {}
                if not isinstance(existing_events, dict):
                    existing_events = {}
                merged = {**existing_events, **payload_planning}
                supabase.table("employee_schedules").update(
                    {
                        "payroll_events": merged,
                        "updated_at": transmitted_at,
                    }
                ).eq("id", existing["id"]).execute()
            else:
                logger.warning(
                    "[Planning] Pas de ligne employee_schedules pour employee=%s "
                    "%s-%s (transmission planning ignorée).",
                    employee_id,
                    year,
                    month,
                )

        planning_repository.set_payroll_transmitted(company_id, week_start_clean)
    except Exception as e:
        logger.error(
            "[Planning] Échec transmission paie company=%s week=%s : %s",
            company_id,
            week_start,
            e,
        )
        traceback.print_exc()


def update_company_settings(
    data: CompanyPlanningSettingsUpdate, company_id: str
) -> dict:
    """Met à jour les paramètres planning entreprise."""
    payload = data.model_dump(exclude_unset=True)
    return planning_repository.update_company_planning_settings(company_id, payload)
