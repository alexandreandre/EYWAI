"""
Import des heures badgeuse (effectives) vers le calendrier réel employee_schedules.
"""
from __future__ import annotations

import calendar as cal_mod
from dataclasses import dataclass, field
from datetime import date

from app.shared.domain.temps_local import en_heure_locale
from typing import Any, Dict, List, Tuple

from app.modules.badgeuse.application import punch_service as badgeuse_punch_service
from app.modules.badgeuse.domain.time_tracking import TimeEntryType
from app.modules.badgeuse.infrastructure.repository import time_entry_repository
from app.modules.payroll.application.payslip_commands import is_forfait_jour
from app.modules.schedules.application.commands import (
    calculate_payroll_events,
    update_actual_hours,
)
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.application.service import get_employee_company_and_statut
from app.modules.schedules.infrastructure.mappers import (
    extract_calendrier_prevu_from_planned_calendar,
    extract_calendrier_reel_from_actual_hours,
)
from app.modules.schedules.infrastructure.repository import schedule_repository
from app.modules.schedules.schemas.requests import ActualHoursEntry, ActualHoursRequest


@dataclass
class ImportBadgeuseResult:
    employee_id: str
    year: int
    month: int
    days_updated: int = 0
    days_with_anomaly_warnings: List[int] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    payroll_recalculated: bool = False


def _planned_type_by_day(
    calendrier_prevu: List[Dict[str, Any]],
    year: int,
    month: int,
    days_in_month: int,
) -> Dict[int, str]:
    by_day: Dict[int, str] = {}
    for entry in calendrier_prevu:
        jour = entry.get("jour")
        if jour is None:
            continue
        by_day[int(jour)] = str(entry.get("type") or "travail")
    for j in range(1, days_in_month + 1):
        by_day.setdefault(j, _default_type_for_day(year, month, j))
    return by_day


def _default_type_for_day(year: int, month: int, jour: int) -> str:
    wd = date(year, month, jour).weekday()
    return "weekend" if wd >= 5 else "travail"


def _first_last_punch_minutes(
    employee_id: str, company_id: str, day: date
) -> Tuple[int | None, int | None]:
    entries = time_entry_repository.get_entries_for_employee_on_day(
        employee_id=employee_id,
        company_id=company_id,
        day=day,
    )
    if not entries:
        return None, None
    sorted_entries = sorted(entries, key=lambda e: e.timestamp)
    entry_min: int | None = None
    exit_min: int | None = None
    for entry in sorted_entries:
        # Heure MURALE Paris : le stockage est en UTC, un badge de 8 h
        # l'été vaudrait sinon 6 h → 2 h de fausses HS « entrée en avance ».
        locale = en_heure_locale(entry.timestamp)
        minutes = locale.hour * 60 + locale.minute
        if entry.event_type == TimeEntryType.ENTREE and entry_min is None:
            entry_min = minutes
        if entry.event_type == TimeEntryType.SORTIE:
            exit_min = minutes
    return entry_min, exit_min


def _planned_entry_by_day(
    calendrier_prevu: List[Dict[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for entry in calendrier_prevu:
        try:
            out[int(entry.get("jour"))] = entry
        except (TypeError, ValueError):
            continue
    return out


def _unpaid_break_from_planned(entry: Dict[str, Any] | None) -> int | None:
    if not entry:
        return None
    if entry.get("unpaid_break_minutes") is not None:
        return int(entry["unpaid_break_minutes"])
    pause_min = entry.get("pause_min")
    if pause_min and not entry.get("pause_payee"):
        return int(pause_min)
    return None


def _accounted_hours_for_day(
    *,
    company_id: str,
    employee_id: str,
    day: date,
    dto,
    planned_entry: Dict[str, Any] | None = None,
) -> float:
    from app.modules.schedules.application.punch_accounting_service import (
        compute_accounted_hours_for_badgeuse_day,
    )
    from app.modules.schedules.infrastructure import punch_accounting_repository

    if dto.has_override:
        return round(dto.effective_seconds / 3600.0, 2)

    settings = punch_accounting_repository.get_settings(company_id)
    if not settings.enabled:
        return round(dto.effective_seconds / 3600.0, 2)

    entry_min, exit_min = _first_last_punch_minutes(employee_id, company_id, day)
    # Pause réellement badgée = amplitude − temps travaillé en séquences.
    # Quand elle existe, elle prime sur le forfait : réintégrer la pause
    # puis déduire un forfait fabriquait des HS fantômes.
    mesure_pause: int | None = None
    if entry_min is not None and exit_min is not None and exit_min > entry_min:
        amplitude_min = exit_min - entry_min
        travail_min = int(round(float(dto.effective_seconds or 0) / 60.0))
        if 0 < travail_min < amplitude_min:
            mesure_pause = amplitude_min - travail_min
    shift_code = (
        str(planned_entry.get("shift_code")).strip().upper()
        if planned_entry and planned_entry.get("shift_code")
        else None
    )
    heures, needs_review, overtime_hours, reason = compute_accounted_hours_for_badgeuse_day(
        company_id,
        entry_minutes=entry_min,
        exit_minutes=exit_min,
        shift_code=shift_code,
        planned_unpaid_break_minutes=_unpaid_break_from_planned(planned_entry),
        measured_break_minutes=mesure_pause,
    )
    if needs_review and overtime_hours > 0:
        from app.modules.schedules.domain.punch_accounting_rules import (
            minutes_to_time_string,
        )

        punch_accounting_repository.upsert_overtime_review(
            company_id,
            employee_id=employee_id,
            work_date=day,
            overtime_hours=overtime_hours,
            reason=reason or "daily_excess",
            raw_entry_time=(
                minutes_to_time_string(entry_min) if entry_min is not None else None
            ),
            raw_exit_time=(
                minutes_to_time_string(exit_min) if exit_min is not None else None
            ),
            applied_slot_id=None,
            status="pending",
        )
    return heures


def import_actual_hours_from_badgeuse(
    employee_id: str,
    year: int,
    month: int,
    *,
    recalculate_payroll: bool = False,
) -> ImportBadgeuseResult:
    """
    Fusionne les heures effectives badgeuse dans calendrier_reel du mois.
    N'écrase que les jours avec pointage ou override RH explicite.
    """
    company_id, employee_statut = get_employee_company_and_statut(employee_id)
    if is_forfait_jour(employee_statut):
        raise ScheduleAppError(
            "forfait_jour",
            "Import badgeuse non applicable aux employés au forfait jour.",
            status_code=400,
        )

    days_in_month = cal_mod.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, days_in_month)

    planned_raw = schedule_repository.get_planned_calendar(employee_id, year, month)
    calendrier_prevu = extract_calendrier_prevu_from_planned_calendar(planned_raw)
    planned_types = _planned_type_by_day(
        calendrier_prevu, year, month, days_in_month
    )
    planned_by_day = _planned_entry_by_day(calendrier_prevu)

    actual_raw = schedule_repository.get_actual_hours(employee_id, year, month)
    existing_reel = extract_calendrier_reel_from_actual_hours(actual_raw)
    existing_by_day: Dict[int, Dict[str, Any]] = {
        int(e["jour"]): dict(e) for e in existing_reel if e.get("jour") is not None
    }

    day_summaries = badgeuse_punch_service.get_summary_for_employee_period(
        employee_id=employee_id,
        company_id=company_id,
        start=start,
        end=end,
    )

    result = ImportBadgeuseResult(employee_id=employee_id, year=year, month=month)
    updated_days: set[int] = set()

    for d, dto in day_summaries.items():
        if d.month != month or d.year != year:
            continue
        jour = d.day
        effective = dto.effective_seconds
        has_override = dto.has_override

        if effective <= 0 and not has_override:
            continue

        if dto.has_anomalies:
            result.days_with_anomaly_warnings.append(jour)
            result.warnings.append(
                f"Jour {jour:02d}/{month:02d} : pointage en anomalie importé quand même."
            )

        day_type = planned_types.get(jour) or _default_type_for_day(year, month, jour)
        heures = _accounted_hours_for_day(
            company_id=company_id,
            employee_id=employee_id,
            day=d,
            dto=dto,
            planned_entry=planned_by_day.get(jour),
        )
        existing_by_day[jour] = {
            "jour": jour,
            "type": day_type,
            "heures_faites": heures,
        }
        updated_days.add(jour)

    if not updated_days:
        result.warnings.append(
            "Aucun jour avec heures badgeuse à importer sur ce mois."
        )
        return result

    calendrier_reel: List[ActualHoursEntry] = []
    for j in range(1, days_in_month + 1):
        if j in existing_by_day:
            entry = existing_by_day[j]
            calendrier_reel.append(
                ActualHoursEntry(
                    jour=j,
                    type=entry.get("type"),
                    heures_faites=entry.get("heures_faites"),
                )
            )
        else:
            calendrier_reel.append(
                ActualHoursEntry(
                    jour=j,
                    type=planned_types.get(j) or _default_type_for_day(year, month, j),
                    heures_faites=None,
                )
            )

    payload = ActualHoursRequest(
        year=year, month=month, calendrier_reel=calendrier_reel
    )
    update_actual_hours(employee_id, payload)
    result.days_updated = len(updated_days)

    if recalculate_payroll:
        calculate_payroll_events(employee_id, year, month)
        result.payroll_recalculated = True

    return result


def import_actual_hours_from_badgeuse_bulk(
    *,
    company_id: str,
    employee_ids: List[str],
    year: int,
    month: int,
    recalculate_payroll: bool = False,
) -> Dict[str, Any]:
    """Import badgeuse pour plusieurs employés d'une entreprise (pool parallèle)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    total_days = 0

    def _one(emp_id: str) -> Dict[str, Any]:
        company_id_emp, _ = get_employee_company_and_statut(emp_id)
        if company_id_emp != company_id:
            raise ScheduleAppError(
                "validation",
                "Employé hors de l'entreprise active.",
                status_code=400,
            )
        return import_actual_hours_from_badgeuse(
            emp_id,
            year,
            month,
            recalculate_payroll=recalculate_payroll,
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_one, emp_id): emp_id for emp_id in employee_ids}
        for future in as_completed(futures):
            emp_id = futures[future]
            try:
                r = future.result()
                total_days += r.days_updated
                results.append(
                    {
                        "employee_id": emp_id,
                        "days_updated": r.days_updated,
                        "warnings": r.warnings,
                        "days_with_anomaly_warnings": r.days_with_anomaly_warnings,
                        "payroll_recalculated": r.payroll_recalculated,
                    }
                )
            except ScheduleAppError as e:
                errors.append({"employee_id": emp_id, "message": e.message})
            except Exception as e:
                errors.append({"employee_id": emp_id, "message": str(e)})

    return {
        "year": year,
        "month": month,
        "employees_processed": len(results),
        "total_days_updated": total_days,
        "results": results,
        "errors": errors,
    }
