"""Service application — comptabilisation pointages sur propositions et badgeuse."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any, List

from app.modules.schedules.domain.punch_accounting_entities import (
    PlannedShiftBreak,
    PunchDayInput,
)
from app.modules.schedules.domain.punch_accounting_rules import (
    compute_from_raw_times,
    compute_punch_day,
    minutes_to_time_string,
    parse_hhmm_value,
)
from app.modules.schedules.infrastructure import punch_accounting_repository as repo
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
    TimesheetQualityCheck,
)


# Version des règles de calcul des heures pointées. À incrémenter dès qu'un
# même relevé peut donner des heures différentes — les aperçus mis en cache
# sous une version antérieure sont alors ignorés.
#   2 : pause des feuilles importées alignée sur le paramétrage société.
PUNCH_CALC_RULES_VERSION = 3  # lot 4 : pauses brutes sur imports (prompt + repli supprimé)


def punch_calc_fingerprint(company_id: str | None) -> str:
    """Empreinte des règles qui ont produit des heures, cache d'aperçu compris."""
    parts: List[str] = [f"v{PUNCH_CALC_RULES_VERSION}"]
    if not company_id:
        return ":".join(parts + ["no-company"])

    settings = repo.get_settings(company_id)
    parts.append(
        "|".join(
            str(v)
            for v in (
                settings.enabled,
                settings.tolerance_minutes,
                settings.default_break_deduct_minutes,
                settings.break_threshold_minutes,
                settings.slot_detection,
                settings.within_tolerance_pay_theoretical,
                settings.require_manager_validation_for_overtime,
            )
        )
    )
    if settings.enabled:
        slots = "|".join(
            f"{s.code}-{s.entry_minutes}-{s.exit_minutes}-{s.break_deduct_minutes}"
            f"-{s.paid_break_minutes}-{s.paid_lunch_break}"
            for s in sorted(repo.list_slots(company_id), key=lambda s: s.sort_order)
        )
        parts.append(hashlib.sha1(slots.encode()).hexdigest()[:12])
    return ":".join(parts)


def _resolve_exit_raw(row: dict[str, Any], use_last: bool) -> object:
    exit_last = row.get("exit_last") or row.get("sortie_3") or row.get("exit_3")
    if parse_hhmm_value(exit_last):
        return exit_last
    if not use_last:
        return exit_last
    for key in ("sortie_2", "exit_2", "sortie_1", "exit_1"):
        val = row.get(key)
        if parse_hhmm_value(val):
            return val
    return exit_last


def apply_punch_accounting_to_proposal(
    proposal: AiCalendarProposalResponse,
    company_id: str,
) -> AiCalendarProposalResponse:
    settings = repo.get_settings(company_id)
    if not settings.enabled:
        return proposal

    # Absence de créneau volontaire chez les sociétés à horaires variables :
    # la pause s'y résout par le seuil de présence, pas par une grille, et le
    # théorique de la journée vaut le pointé.
    slots = repo.list_slots(company_id)

    quality_checks: List[TimesheetQualityCheck] = list(proposal.quality_checks)
    employees_out: List[AiEmployeeProposal] = []

    for emp in proposal.employees:
        new_days: List[AiDayEntry] = []
        warnings = list(emp.warnings)
        for day in emp.days:
            entry_raw = day.punch_entry_raw
            exit_raw = day.punch_exit_raw
            shift_code = day.shift_code

            if entry_raw is None and exit_raw is None and (
                day.heures is not None or not slots
            ):
                # Rien à recomptabiliser : soit les heures sont déjà là, soit,
                # sans grille horaire, la journée ne porte aucun élément à
                # confronter — l'inventer en absence effacerait une saisie.
                new_days.append(day)
                continue

            result = compute_from_raw_times(
                entry_raw=entry_raw,
                exit_raw=exit_raw,
                shift_code=shift_code,
                settings=settings,
                slots=slots,
                planned_shift=(
                    PlannedShiftBreak(paid_break_minutes=day.planned_paid_break_minutes)
                    if day.planned_paid_break_minutes
                    else None
                ),
            )

            if result.is_absent:
                new_days.append(
                    day.model_copy(update={"heures": 0.0, "type": "absence"})
                )
                continue

            warnings = list(emp.warnings)
            for alert in result.alerts:
                warnings.append(f"Jour {day.jour} : {alert}")
                quality_checks.append(
                    TimesheetQualityCheck(
                        level="warning",
                        code="punch_overtime_review",
                        message=f"Jour {day.jour} : {alert}",
                        employee_raw_name=emp.raw_name,
                        matricule=emp.time_tracking_id,
                    )
                )

            new_days.append(
                day.model_copy(update={"heures": result.accounted_hours})
            )

            if result.needs_review and emp.employee_id:
                work_date = date(
                    day.year or proposal.year, day.month or proposal.month, day.jour
                )
                entry_min = parse_hhmm_value(entry_raw)
                exit_min = parse_hhmm_value(exit_raw)
                repo.upsert_overtime_review(
                    company_id,
                    employee_id=emp.employee_id,
                    work_date=work_date,
                    overtime_hours=result.overtime_hours,
                    reason=result.overtime_reason or "daily_excess",
                    raw_entry_time=(
                        minutes_to_time_string(entry_min) if entry_min else None
                    ),
                    raw_exit_time=(
                        minutes_to_time_string(exit_min) if exit_min else None
                    ),
                    applied_slot_id=result.applied_slot_id,
                    status="pending",
                )

        employees_out.append(emp.model_copy(update={"days": new_days, "warnings": warnings}))

    return proposal.model_copy(
        update={"employees": employees_out, "quality_checks": quality_checks}
    )


def compute_accounted_hours_for_badgeuse_day(
    company_id: str,
    *,
    entry_minutes: int | None,
    exit_minutes: int | None,
    shift_code: str | None = None,
    planned_paid_break_minutes: int = 0,
    planned_unpaid_break_minutes: int | None = None,
) -> tuple[float, bool, float, str | None]:
    """Retourne (heures_comptabilisées, needs_review, overtime_hours, reason)."""
    settings = repo.get_settings(company_id)
    if not settings.enabled:
        if entry_minutes and exit_minutes and exit_minutes > entry_minutes:
            gross = exit_minutes - entry_minutes
            return round(gross / 60.0, 2), False, 0.0, None
        return 0.0, False, 0.0, None

    slots = repo.list_slots(company_id)
    planned_shift: PlannedShiftBreak | None = None
    if planned_unpaid_break_minutes is not None or shift_code:
        planned_shift = PlannedShiftBreak(
            unpaid_break_minutes=planned_unpaid_break_minutes,
            slot_code=shift_code,
        )
    elif planned_paid_break_minutes > 0:
        planned_shift = PlannedShiftBreak(paid_break_minutes=planned_paid_break_minutes)

    result = compute_punch_day(
        PunchDayInput(
            entry_minutes=entry_minutes,
            exit_minutes=exit_minutes,
            shift_code=shift_code,
            planned_shift=planned_shift,
        ),
        settings,
        slots,
    )
    return (
        result.accounted_hours,
        result.needs_review,
        result.overtime_hours,
        result.overtime_reason,
    )


def inject_approved_punch_overtime_into_calendar(
    calendrier_analyse: list[dict[str, Any]],
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    """Ajoute les HS pointage validées au calendrier analyse paie."""
    settings = repo.get_settings(company_id)
    if not settings.enabled:
        return calendrier_analyse

    approved = [
        r
        for r in repo.list_approved_overtime_for_month(company_id, year, month)
        if str(r.get("employee_id")) == employee_id
    ]
    if not approved:
        return calendrier_analyse

    total_hs = round(sum(float(r.get("overtime_hours") or 0) for r in approved), 2)
    if total_hs <= 0:
        return calendrier_analyse

    updated = list(calendrier_analyse)
    found = False
    for entry in updated:
        if entry.get("type") == "travail_hs25":
            entry["heures"] = round(float(entry.get("heures") or 0) + total_hs, 2)
            found = True
            break
    if not found:
        updated.append({"type": "travail_hs25", "heures": total_hs})
    return updated
